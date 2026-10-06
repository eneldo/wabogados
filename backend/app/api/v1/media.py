"""The multimedia library API (MASTER_PROMPT V4).

Every route is authorised by an explicit `media:*` permission, and there is no
route here that the client role can reach: the library is firm material and
nothing in it is published to the portal.

`DELETE` deactivates and never deletes (ADR-051), and the file survives the
deactivation so the row can be brought back with its bytes still in place.
"""

import re
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    _trusted_proxies,
    get_client_ip,
    get_session,
    get_user_scope,
    require_permission,
)
from app.core.config import get_settings
from app.core.http_status import (
    HTTP_416_RANGE_NOT_SATISFIABLE,
    HTTP_422_UNPROCESSABLE,
)
from app.models import Case, ChangeLog, MediaItem, User
from app.schemas.media import (
    MediaCreate,
    MediaResponse,
    MediaUpdate,
    PaginatedMedia,
    media_response,
)
from app.services.cases import CaseScope, case_scoped, scope_filter
from app.services.media import (
    MEDIA_ENTITY,
    MediaError,
    MediaService,
    media_type_label,
)

router = APIRouter(prefix="/media", tags=["media"])

_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _attachment_disposition(file_name: str | None, *, inline: bool) -> str:
    """Build a Content-Disposition with a sanitised name.

    `inline` is what a `<video>` needs and what a browser will only honour when the
    MIME type is one it can play. Everything the library serves inline is a
    detected media type, never the name the uploader chose, and `nosniff` is set
    on every response so the browser cannot be talked into a different type.
    """
    safe = _SAFE_FILE_NAME.sub("_", file_name or "archivo").strip("._") or "archivo"
    quoted = quote(safe, safe="")
    return f"{'inline' if inline else 'attachment'}; filename=\"{safe}\"; filename*=UTF-8''{quoted}"


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado"
    )


def _fail(error: MediaError) -> HTTPException:
    """Turn a refusal into a response.

    A file the library will not accept is the caller's mistake and says so in its
    own words, which the body carries through unchanged: the alternative, an
    invented sentence, is what made a form "claim to send" in this project.
    """
    return HTTPException(
        status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
    )


async def _clause(
    session: AsyncSession, actor: User, scope: CaseScope
) -> ColumnElement[bool] | None:
    """What the caller may see of the library.

    `None` means everything, which is what `CaseScope.ALL` resolves to.

    Same rule as billing, and for the same reason: a resource tied to an expediente
    is filtered on it, while one with no `case_id` is firm material — templates,
    firm-wide recordings — and remains reachable for whoever holds `media:read`.
    `case_scoped` drops the NULL rows, so they are ORed back here.
    `test_firm_material_stays_visible_to_everybody_with_the_permission` pins that.
    """
    clause = case_scoped(MediaItem.case_id, await scope_filter(session, actor, scope))
    if clause is None:
        return None
    return or_(MediaItem.case_id.is_(None), clause)


async def _require_case(
    session: AsyncSession, actor: User, scope: CaseScope, case_id: UUID | None
) -> None:
    """Refuse to file the library's material into an expediente out of reach."""
    if case_id is None or scope is CaseScope.ALL:
        return
    clause = await scope_filter(session, actor, scope)
    if clause is None:
        return
    allowed = await session.execute(
        select(Case.id).where(Case.id == case_id, clause)
    )
    if not allowed.all():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a ese expediente",
        )


async def _require_item(
    session: AsyncSession,
    actor: User,
    scope: CaseScope,
    media_id: UUID,
) -> tuple[MediaService, MediaItem]:
    service = MediaService(session)
    item = await service.get(media_id, scope_clause=await _clause(session, actor, scope))
    if item is None:
        raise _not_found()
    return service, item


@router.get("", response_model=PaginatedMedia)
async def list_media(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
    kind: Annotated[str | None, Query(max_length=20)] = None,
    item_status: Annotated[
        str | None, Query(alias="status", max_length=20)
    ] = None,
    confidentiality: Annotated[str | None, Query(max_length=20)] = None,
    case_id: Annotated[UUID | None, Query()] = None,
    include_inactive: Annotated[bool, Query()] = False,
) -> PaginatedMedia:
    """List the library, most recent first.

    `include_inactive` is the only way to see a deactivated resource, exactly as
    with clients and lawyers: it leaves the default listing because a deactivated
    row has no business in the everyday view.
    """
    service = MediaService(session)
    items, total = await service.list_media(
        skip,
        limit,
        scope_clause=await _clause(session, actor, scope),
        search=search,
        kind=kind,
        status=item_status,
        confidentiality=confidentiality,
        case_id=case_id,
        include_inactive=include_inactive,
    )
    return PaginatedMedia(
        items=[media_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{media_id}", response_model=MediaResponse)
async def read_media(
    media_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MediaResponse:
    service, item = await _require_item(session, actor, scope, media_id)
    return media_response(item, case_number=await service.case_number_for(item))


@router.post("", response_model=MediaResponse, status_code=status.HTTP_201_CREATED)
async def create_media(
    payload: MediaCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MediaResponse:
    """Register the row. The bytes are uploaded to `/media/{id}/content`."""
    await _require_case(session, actor, scope, payload.case_id)
    service = MediaService(session)
    item = await service.create(payload, actor)
    await session.commit()
    return media_response(item)


@router.patch("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_id: UUID,
    payload: MediaUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MediaResponse:
    service, item = await _require_item(session, actor, scope, media_id)
    updated = await service.update(item, payload, actor)
    await session.commit()
    return media_response(updated)


@router.put("/{media_id}/content", response_model=MediaResponse)
async def upload_media_content(
    media_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:upload"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    file: Annotated[UploadFile, File()],
) -> MediaResponse:
    """Attach or replace the file of a registered resource.

    The whole upload is read into memory and then stored. That is acceptable up to
    `max_media_bytes` and no further: past it the file belongs in the worker queue
    (ADR-049), which does not exist yet, so the cap is what keeps a video from
    exhausting the request thread instead.
    """
    cap = get_settings().max_media_bytes
    content = await file.read(cap + 1)
    if len(content) > cap:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"El archivo supera el máximo de {cap // (1024 * 1024)} MB de la "
                "biblioteca. Un archivo mayor debe subirse por la cola, que todavía "
                "no está disponible."
            ),
        )

    service, item = await _require_item(session, actor, scope, media_id)
    try:
        updated = await service.attach_file(item, content, file.filename)
    except MediaError as error:
        raise _fail(error) from error
    await session.commit()
    return media_response(updated)


@router.get("/{media_id}/content")
async def download_media(
    media_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
actor: Annotated[User, Depends(require_permission("media:download"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Response:
    """Serve the bytes, with `Range` support so a video can be scrubbed.

    A player that asks for bytes 1000000- does not want the whole file, and
    answering 200 with everything makes seeking impossible on anything larger than
    a few megabytes. `Accept-Ranges` is therefore always advertised and a `Range`
    header is answered with `206 Partial Content`.

    Video, image and audio are served **inline**, because a library whose files can
    only be downloaded cannot be watched. Everything carries `nosniff` and the
    declared type is the one detected at upload, never the name's extension.
    """
    service, item = await _require_item(session, actor, scope, media_id)
    if not item.has_file:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El recurso todavía no tiene archivo",
        )

    try:
        content = await service.read_file(item)
    except MediaError as error:
        raise _fail(error) from error

    total = len(content)
    mime = item.mime_type or "application/octet-stream"
    inline = item.kind in ("video", "image", "audio")
    headers: dict[str, Any] = {
        "Content-Disposition": _attachment_disposition(
            item.original_filename, inline=inline
        ),
        "X-Content-SHA256": item.sha256 or "",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
    }

    range_header = request.headers.get("Range")
    if range_header is None:
        chunk = content
        served_status = status.HTTP_200_OK
        headers["Content-Length"] = str(total)
    else:
        start, end = _parse_range(range_header, total)
        if start is None:
            # An unsatisfiable range is a 416, not a silent full body: a player that
            # asked for the end of the file must be told the file is shorter. Nothing
            # was served, so nothing is recorded.
            headers["Content-Range"] = f"bytes */{total}"
            raise HTTPException(
                status_code=HTTP_416_RANGE_NOT_SATISFIABLE,
                detail="El rango solicitado no existe en el archivo",
                headers=headers,
            )
        chunk = content[start : end + 1]
        served_status = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        headers["Content-Length"] = str(len(chunk))

    await service.record_access(
        item,
        user=actor,
        access_type="download",
        ip_address=get_client_ip(request, _trusted_proxies()),
        user_agent=request.headers.get("User-Agent"),
        bytes_served=len(chunk),
    )
    await session.commit()

    return Response(
        content=chunk,
        status_code=served_status,
        media_type=mime,
        headers=headers,
    )


def _parse_range(header: str, total: int) -> tuple[int | None, int]:
    """Return the inclusive byte range, or `(None, 0)` when it cannot be served.

    Only the two forms a player actually sends are accepted — `bytes=start-` and
    `bytes=start-end`. A suffix range (`bytes=-500`) is honoured as the last 500
    bytes because a scrub bar that jumped past the end produces one.
    """
    if not header.startswith("bytes="):
        return None, 0
    spec = header.removeprefix("bytes=").strip()
    if "," in spec:
        # Multipart ranges are for resumable downloads of many chunks; a media
        # player never asks for one and serving them wrong is worse than not.
        return None, 0
    raw_start, _, raw_end = spec.partition("-")
    if not raw_start:
        if not raw_end.isdigit():
            return None, 0
        length = int(raw_end)
        if length <= 0:
            return None, 0
        start = max(0, total - length)
        return start, total - 1
    if not raw_start.isdigit():
        return None, 0
    start = int(raw_start)
    if start >= total:
        return None, 0
    if raw_end.isdigit():
        end = min(int(raw_end), total - 1)
    else:
        end = total - 1
    if end < start:
        return None, 0
    return start, end


@router.delete("/{media_id}", response_model=MediaResponse)
async def deactivate_media(
    media_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:delete"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MediaResponse:
    """Take a resource out of the library. Nothing is deleted.

    The row, its history and its file all survive, so this is reversible:
    `POST /media/{id}/reactivate` brings it back with the bytes in place.
    """
    service, item = await _require_item(session, actor, scope, media_id)
    updated = await service.deactivate(item, actor)
    await session.commit()
    return media_response(updated)


@router.post("/{media_id}/reactivate", response_model=MediaResponse)
async def reactivate_media(
    media_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:delete"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MediaResponse:
    """Bring a deactivated resource back, file included."""
    service, item = await _require_item(session, actor, scope, media_id)
    updated = await service.reactivate(item, actor)
    await session.commit()
    return media_response(updated)


@router.get("/{media_id}/history")
async def media_history(
    media_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("media:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """Field level history of a resource, newest first.

    Reads `change_logs` directly rather than through a service: the recorder
    already wrote it, and a second indirection would only add a place to forget
    the `media_items` entity name.
    """
    _service, item = await _require_item(session, actor, scope, media_id)
    result = await session.execute(
        select(ChangeLog)
        .where(ChangeLog.entity == MEDIA_ENTITY, ChangeLog.entity_id == item.id)
        .order_by(ChangeLog.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "field_name": entry.field_name,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "change_reason": entry.change_reason,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in result.scalars()
    ]


__all__ = [
    "create_media",
    "deactivate_media",
    "download_media",
    "list_media",
    "media_history",
    "media_type_label",
    "reactivate_media",
    "read_media",
    "router",
    "update_media",
    "upload_media_content",
]

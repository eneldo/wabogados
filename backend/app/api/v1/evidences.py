"""Evidence endpoints.

Access rules that are not negotiable (MASTER_PROMPT section 40):

- The original download is a separate permission from viewing, and every one is
  audited.
- A client may see published evidence and its consultation derivative. Never the
  original.
- Evidence outside the caller's scope answers 404, not 403, so the API cannot be
  used to confirm that another case holds evidence.
"""

import re
from typing import Annotated
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    _trusted_proxies,
    get_client_ip,
    get_current_user,
    get_session,
    get_user_scope,
    require_permission,
)
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import Case, Evidence, User
from app.schemas.clients import ChangeLogResponse
from app.schemas.evidence import (
    EvidenceAccessLogResponse,
    EvidenceCreate,
    EvidenceCustodyResponse,
    EvidenceDetailResponse,
    EvidenceEventResponse,
    EvidenceResponse,
    EvidenceUpdate,
    EvidenceUploadResponse,
)
from app.services.cases import CaseScope, case_scoped, scope_filter
from app.services.evidence import (
    EVIDENCE_ENTITY,
    MUTABLE_FIELDS,
    EvidenceError,
    EvidenceService,
)
from app.services.history import record_changes
from app.services.uploads import MAX_UPLOAD_BYTES

router = APIRouter(tags=["evidences"])

_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada"
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail=message
    )


def _attachment_disposition(file_name: str) -> str:
    safe = _SAFE_FILE_NAME.sub("_", file_name).strip("._") or "evidencia"
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(safe, safe='')}"


async def _require_case(
    session: AsyncSession, actor: User, scope: CaseScope, case_id: UUID
) -> None:
    """Refuse to write into an expediente the caller may not see.

    `create_evidence` used to call `scope_filter(session, actor, CaseScope.ALL)`,
    which resolves to `None` by definition, so the branch below it never ran and the
    route had no scope check at all. Taking `scope` as a parameter, rather than
    hardcoding it here, is what makes that mistake impossible to write again: the
    caller cannot pass anything but the resolved scope.
    """
    clause = await scope_filter(session, actor, scope)
    if clause is None:
        return
    allowed = await session.execute(select(Case.id).where(Case.id == case_id, clause))
    if not allowed.all():
        raise _forbidden("No tiene acceso a ese expediente")


@router.get(
    "/evidences/{evidence_id}",
    response_model=EvidenceDetailResponse,
    responses={404: {"description": "No existe o no está en el alcance del llamador"}},
)
async def get_evidence(
    evidence_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> EvidenceDetailResponse:
    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        current_user,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, current_user, scope)
        ),
    )
    if evidence is None:
        raise _not_found()
    return EvidenceDetailResponse.from_evidence(evidence)


@router.get("/cases/{case_id}/evidences", response_model=list[EvidenceResponse])
async def list_case_evidences(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    evidence_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[EvidenceResponse]:
    """Evidence of one case, filtered by what the caller may see."""
    # The scope clause is built over `cases`, so it is translated onto the
    # evidence case id. Applying it directly would cross join and leak other
    # cases, exactly the bug fixed in Fase 5.
    clause = case_scoped(
        Evidence.case_id, await scope_filter(session, current_user, scope)
    )
    evidences = await EvidenceService(session).list_evidences(
        current_user,
        scope_clause=clause,
        status=status_filter,
        evidence_type=evidence_type,
        limit=limit,
    )
    return [
        EvidenceResponse.from_evidence(item)
        for item in evidences
        if str(item.case_id) == str(case_id)
    ]


@router.post(
    "/cases/{case_id}/evidences",
    response_model=EvidenceDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence(
    case_id: UUID,
    payload: EvidenceCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> EvidenceDetailResponse:
    """Register an evidence. The file arrives in a separate upload call."""
    await _require_case(session, actor, scope, case_id)

    if payload.case_id != case_id:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="El case_id del cuerpo no coincide con la ruta",
        )

    service = EvidenceService(session)
    try:
        evidence = await service.create_evidence(
            case_id=case_id,
            title=payload.title,
            evidence_type=payload.evidence_type,
            actor=actor,
            description=payload.description,
            action_id=payload.action_id,
            visibility=payload.visibility,
            confidentiality=payload.confidentiality,
            captured_at=payload.captured_at,
            captured_location=payload.captured_location,
            ip_address=get_client_ip(request, _trusted_proxies()),
        )
    except EvidenceError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
        ) from error

    await session.commit()
    # Re-read through the service: after a commit the ORM may have expired the
    # collections, and touching them here would raise MissingGreenlet.
    reloaded = await service.get_evidence(evidence.id)
    assert reloaded is not None
    return EvidenceDetailResponse.from_evidence(reloaded)


@router.post(
    "/evidences/{evidence_id}/original",
    response_model=EvidenceUploadResponse,
    responses={
        409: {"description": "El archivo no es una evidencia válida"},
    },
)
async def upload_evidence_original(
    evidence_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:upload"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    file: Annotated[UploadFile, File()],
) -> EvidenceUploadResponse:
    """Validate, store and process the received original.

    The original is never modified. Derived files are produced from the bytes
    received and stored under their own keys.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el máximo de {MAX_UPLOAD_BYTES} bytes",
        )

    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        actor,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, actor, scope)
        ),
    )
    if evidence is None:
        raise _not_found()
    if evidence.files:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La evidencia ya tiene un original; no se puede sustituir",
        )

    try:
        evidence_file, outcome = await service.attach_original(
            evidence,
            content,
            file.filename or "evidencia",
            declared_mime=file.content_type,
            actor=actor,
            ip_address=get_client_ip(request, _trusted_proxies()),
        )
    except EvidenceError as error:
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    await session.commit()
    assert evidence_file is not None
    reloaded = await service.get_evidence(evidence.id)
    assert reloaded is not None
    return EvidenceUploadResponse(
        evidence=EvidenceDetailResponse.from_evidence(reloaded),
        derivatives_created=outcome.derivatives,
        queued=outcome.queued,
        page_count=outcome.pages,
        is_signed_pdf=outcome.is_signed_pdf,
        signature_broken=outcome.signature_broken,
        detail=outcome.detail,
    )


@router.patch("/evidences/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    evidence_id: UUID,
    payload: EvidenceUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> EvidenceResponse:
    """Change the mutable metadata. The original and its hash are untouchable."""
    changes = payload.changes()
    if not changes:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="No se envió ningún campo a modificar",
        )

    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        actor,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, actor, scope)
        ),
    )
    if evidence is None:
        raise _not_found()

    before = {field: getattr(evidence, field, None) for field in MUTABLE_FIELDS}
    try:
        await service.update_evidence(
            evidence, changes, actor=actor, ip_address=get_client_ip(request, _trusted_proxies())
        )
    except EvidenceError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
        ) from error

    record_changes(
        session,
        entity=EVIDENCE_ENTITY,
        entity_id=evidence.id,
        before=before,
        after=changes,
        changed_by=actor.id,
        fields=MUTABLE_FIELDS,
    )
    await session.commit()
    reloaded = await service.get_evidence(evidence.id)
    assert reloaded is not None
    return EvidenceResponse.from_evidence(reloaded)


@router.get(
    "/evidences/{evidence_id}/original",
    response_class=Response,
    responses={
        200: {"content": {"application/octet-stream": {}}},
        403: {"description": "Sin permiso para descargar el original"},
    },
)
async def download_original(
    evidence_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:download_original"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Response:
    """Download the immutable original. Every download is audited."""
    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        actor,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, actor, scope)
        ),
    )
    if evidence is None:
        raise _not_found()

    try:
        content = await service.read_original(
            evidence,
            user=actor,
            ip_address=get_client_ip(request, _trusted_proxies()),
            user_agent=request.headers.get("User-Agent"),
        )
    except EvidenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    original = await service.original_of(evidence)
    assert original is not None
    await session.commit()
    return Response(
        content=content,
        media_type=original.mime_type,
        headers={
            "Content-Disposition": _attachment_disposition(original.original_filename),
            "X-Content-SHA256": original.sha256,
            "X-Evidence-Signed": str(original.is_signed_pdf).lower(),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/evidences/{evidence_id}/derivatives/{derivative_id}",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_derivative(
    evidence_id: UUID,
    derivative_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:download_optimized"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Response:
    """Download a consultation derivative. Never the original."""
    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        actor,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, actor, scope)
        ),
    )
    if evidence is None:
        raise _not_found()

    try:
        derivative, content = await service.read_derivative(
            evidence,
            derivative_id,
            user=actor,
            ip_address=get_client_ip(request, _trusted_proxies()),
            user_agent=request.headers.get("User-Agent"),
        )
    except EvidenceError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    await session.commit()
    stem = f"{derivative.derivative_type}_{evidence.id}"
    return Response(
        content=content,
        media_type=derivative.mime_type,
        headers={
            "Content-Disposition": _attachment_disposition(stem),
            "X-Content-SHA256": derivative.sha256,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/evidences/{evidence_id}/custody", response_model=EvidenceCustodyResponse)
async def get_custody(
    evidence_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("evidences:audit"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> EvidenceCustodyResponse:
    """Full chain of custody: every event and every access.

    The case scope applies here too. Without it, anyone holding
    `evidences:audit` could read the custody trail of any evidence in the firm.
    """
    service = EvidenceService(session)
    clause = case_scoped(
        Evidence.case_id, await scope_filter(session, actor, scope)
    )
    evidence = await service.get_evidence(evidence_id)
    if evidence is None or not evidence.is_active:
        raise _not_found()

    if clause is not None:
        allowed = await session.execute(
            select(Evidence.id).where(Evidence.id == evidence_id, clause)
        )
        if not allowed.all():
            raise _not_found()

    await service.record_view(
        evidence, user=actor, ip_address=get_client_ip(request, _trusted_proxies())
    )
    await session.commit()

    return EvidenceCustodyResponse(
        evidence_id=evidence.id,
        original_sha256=evidence.original_sha256,
        events=[
            EvidenceEventResponse.model_validate(event)
            for event in await service.custody_events(evidence_id, limit)
        ],
        accesses=[
            EvidenceAccessLogResponse.model_validate(entry)
            for entry in await service.access_logs(evidence_id, limit)
        ],
    )


@router.get("/evidences/{evidence_id}/history", response_model=list[ChangeLogResponse])
async def get_evidence_history(
    evidence_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ChangeLogResponse]:
    """Field level history, shared with the rest of the platform."""
    from sqlalchemy import select

    from app.models import ChangeLog

    service = EvidenceService(session)
    evidence = await service.get_visible_evidence(
        evidence_id,
        current_user,
        scope_clause=case_scoped(
            Evidence.case_id, await scope_filter(session, current_user, scope)
        ),
    )
    if evidence is None:
        raise _not_found()
    result = await session.execute(
        select(ChangeLog)
        .where(ChangeLog.entity == EVIDENCE_ENTITY, ChangeLog.entity_id == evidence_id)
        .order_by(ChangeLog.created_at.desc())
        .limit(limit)
    )
    return [ChangeLogResponse.model_validate(entry) for entry in result.scalars().all()]

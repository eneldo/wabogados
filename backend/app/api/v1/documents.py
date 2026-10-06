import re
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
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
from app.core.config import get_settings as settings_for_retention
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import Document, User
from app.schemas.clients import ChangeLogResponse
from app.schemas.documents import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
    IntegrityReportResponse,
    IntegrityScanResponse,
    LegalHoldUpdate,
    PaginatedDocuments,
    RetentionCandidateResponse,
    RetentionReportResponse,
    RetentionRunResponse,
)
from app.services.cases import CaseScope, case_scoped, scope_filter
from app.services.documents import (
    DOCUMENT_ENTITY,
    DocumentError,
    DocumentService,
    visible_visibilities,
)
from app.services.history import record_changes
from app.services.integrity import IntegrityService
from app.services.retention import RetentionService
from app.services.uploads import MAX_UPLOAD_BYTES

router = APIRouter(tags=["documents"])


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado"
    )


async def _require_visible_case(
    session: AsyncSession, case_id: UUID, user: User, scope: CaseScope
) -> None:
    from app.services.cases import CaseService

    if scope is CaseScope.NONE:
        raise _forbidden("No tiene permisos para consultar expedientes")
    service = CaseService(session)
    if await service.get_case(case_id) is None or not await service.can_view(
        user, case_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expediente no encontrado"
        )


async def _visible_document(
    session: AsyncSession,
    document_id: UUID,
    user: User,
    scope: CaseScope,
    *,
    require_read: bool = True,
) -> Document:
    """Fetch a document the caller may reach, or 404.

    Every route that takes a document id goes through here. One place to get it
    wrong was the original defect: the listing filtered by case scope and the
    detail did not, so the identifier path bypassed the very rule the listing
    enforced. Centralising the lookup means a new document route inherits the
    check instead of having to remember it.

    `require_read` distinguishes "may the caller see documents at all" from "the
    document is missing": a staff member with no `documents:read` gets 403, and
    anyone who may read gets 404 for a record they may not reach — a 403 there
    would confirm the record exists.
    """
    if require_read and not visible_visibilities(user):
        raise _forbidden("No tiene permisos para consultar documentos")

    clause = case_scoped(Document.case_id, await scope_filter(session, user, scope))
    document = await DocumentService(session).get_visible_document(
        document_id, user, scope_clause=clause
    )
    if document is None:
        raise _not_found()
    return document


@router.get("/cases/{case_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    document_type: Annotated[str | None, Query()] = None,
    document_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[DocumentResponse]:
    if not visible_visibilities(current_user):
        raise _forbidden("No tiene permisos para consultar documentos")
    await _require_visible_case(session, case_id, current_user, scope)

    documents = await DocumentService(session).list_documents(
        current_user,
        scope_clause=None,
        case_id=case_id,
        document_type=document_type,
        status=document_status,
        limit=limit,
    )
    return [DocumentResponse.from_document(document) for document in documents]


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    case_id: UUID,
    payload: DocumentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> DocumentResponse:
    if payload.case_id != case_id:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="El cuerpo no coincide con el expediente de la ruta",
        )
    await _require_visible_case(session, case_id, actor, scope)
    service = DocumentService(session)
    try:
        document = await service.create_document(payload, actor_id=actor.id)
        await session.commit()
    except DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    await session.refresh(document)
    return DocumentResponse.from_document(document)


@router.get("/documents", response_model=PaginatedDocuments)
async def browse_documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    search: Annotated[str | None, Query(max_length=120)] = None,
    case_id: Annotated[UUID | None, Query()] = None,
    document_type: Annotated[str | None, Query()] = None,
    document_status: Annotated[str | None, Query(alias="status")] = None,
    confidentiality: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    legal_hold: Annotated[bool | None, Query()] = None,
) -> PaginatedDocuments:
    """Every document the caller is allowed to see, across every case.

    The contract is the one the per-case listing already has: the document
    visibility decides what may be read, the case scope decides over which
    cases, and neither can be widened by a query parameter. Nothing here
    grants a permission — it browses what is already authorised.
    """
    if not visible_visibilities(current_user):
        raise _forbidden("No tiene permisos para consultar documentos")
    clause = case_scoped(
        Document.case_id,
        await scope_filter(session, current_user, scope),
    )
    documents, total = await DocumentService(session).browse_documents(
        current_user,
        scope_clause=clause,
        skip=skip,
        limit=limit,
        search=search,
        case_id=case_id,
        document_type=document_type,
        status=document_status,
        confidentiality=confidentiality,
        visibility=visibility,
        legal_hold=legal_hold,
    )
    return PaginatedDocuments(
        items=[DocumentResponse.from_document(document) for document in documents],
        total=total,
        skip=skip,
        limit=limit,
    )


# Retention routes are declared before `/documents/{document_id}` so that the
# literal segment always wins over the parameterised one.


@router.get("/documents/retention/report", response_model=RetentionReportResponse)
async def get_retention_report(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:retention"))],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> RetentionReportResponse:
    """Preview what the retention policy would archive. Changes nothing."""
    service = RetentionService(session)
    candidates = await service.plan(limit=limit)
    totals = await service.count_by_tier()
    holds = await service.count_legal_holds()
    return RetentionReportResponse(
        hot_days=settings_for_retention().retention_hot_days,
        tiering_enabled=settings_for_retention().retention_tiering_enabled,
        backend=type(service.storage).__name__,
        native_tiers=service.storage.supports_native_tiers(),
        total_by_tier=totals,
        legal_holds=holds,
        eligible=len(candidates),
        candidates=[
            RetentionCandidateResponse(
                version_id=candidate.version_id,
                document_id=candidate.document_id,
                age_days=candidate.age_days,
                reason=candidate.reason,
            )
            for candidate in candidates
        ],
    )


@router.post("/documents/retention/apply", response_model=RetentionRunResponse)
async def apply_retention_policy(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:retention"))],
    dry_run: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> RetentionRunResponse:
    """Archive eligible versions.

    This never deletes content: superseded versions move to the archive tier and
    stay fully retrievable (PROJECT_RULES, rule 5).
    """
    service = RetentionService(session)
    if not service.settings.retention_tiering_enabled and not dry_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La política de retención está desactivada (RETENTION_TIERING_ENABLED)",
        )
    report = await service.apply(dry_run=dry_run, limit=limit, actor_id=actor.id)
    await session.commit()
    return RetentionRunResponse(**report.as_dict())


@router.get("/documents/integrity/latest", response_model=IntegrityReportResponse)
async def get_latest_integrity_scan(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:retention"))],
) -> IntegrityReportResponse:
    """Last integrity verification run, for an auditor.

    Reports what was verified and what was found. It never repairs anything, and
    it does not trigger a scan: a full scan downloads the whole bucket and must
    be an explicit operation.
    """
    service = IntegrityService(session)
    scan = await service.latest_scan()
    if scan is None:
        return IntegrityReportResponse(
            total_versions=await service.total_versions(),
            last_scan=None,
        )
    return IntegrityReportResponse(
        total_versions=await service.total_versions(),
        last_scan=IntegrityScanResponse.model_validate(scan),
    )


@router.patch("/documents/{document_id}/legal-hold", response_model=DocumentResponse)
async def set_legal_hold(
    document_id: UUID,
    payload: LegalHoldUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:legal_hold"))],
) -> DocumentResponse:
    """Freeze or release the retention policy for a document.

    While the hold is active no version of the document is moved between tiers.
    """
    document = await session.get(Document, document_id)
    if document is None or not document.is_active:
        raise _not_found()

    now = datetime.now(UTC)
    before = {
        "legal_hold": document.legal_hold,
        "legal_hold_reason": document.legal_hold_reason,
    }
    if payload.active:
        if not payload.reason:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="Activar una retención legal exige indicar el motivo",
            )
        document.legal_hold = True
        document.legal_hold_reason = payload.reason
        document.legal_hold_at = now
    else:
        document.legal_hold = False
        document.legal_hold_reason = None
        document.legal_hold_at = None

    record_changes(
        session,
        entity=DOCUMENT_ENTITY,
        entity_id=document.id,
        before=before,
        after={
            "legal_hold": document.legal_hold,
            "legal_hold_reason": document.legal_hold_reason,
        },
        changed_by=actor.id,
        fields=("legal_hold", "legal_hold_reason"),
    )
    await session.commit()
    await session.refresh(document)
    return DocumentResponse.from_document(document)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> DocumentDetailResponse:
    document = await _visible_document(session, document_id, current_user, scope)
    base = DocumentResponse.from_document(document)
    return DocumentDetailResponse(
        **base.model_dump(),
        versions=[
            DocumentVersionResponse.from_version(version) for version in document.versions
        ],
    )


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> DocumentResponse:
    service = DocumentService(session)
    document = await _visible_document(
        session, document_id, actor, scope, require_read=False
    )
    try:
        updated = await service.update_document(document, payload, actor_id=actor.id)
        await session.commit()
    except DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return DocumentResponse.from_document(updated)


@router.post(
    "/documents/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_document_version(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    file: Annotated[UploadFile, File()],
    notes: Annotated[str | None, Form(max_length=1000)] = None,
) -> DocumentVersionResponse:
    """Append a new immutable version. The previous content is never replaced."""
    service = DocumentService(session)
    document = await _visible_document(
        session, document_id, actor, scope, require_read=False
    )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el máximo de {MAX_UPLOAD_BYTES} bytes",
        )
    try:
        version = await service.add_version(
            document,
            content,
            file.filename or "documento",
            declared_mime=file.content_type,
            notes=notes,
            actor_id=actor.id,
        )
        await session.commit()
    except DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return DocumentVersionResponse.from_version(version)


@router.get(
    "/documents/{document_id}/versions/{version_id}/download",
    response_class=Response,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Bytes of the requested immutable version.",
        }
    },
)
async def download_version(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("documents:download"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Response:
    """Return the stored bytes. Every download is recorded in the audit trail.

    The file is always served as an attachment with a sanitised name and the
    detected MIME type, never as an inline document that a browser could
    render in the origin of the application.
    """
    service = DocumentService(session)
    document = await _visible_document(
        session, document_id, actor, scope, require_read=False
    )

    version = next((item for item in document.versions if item.id == version_id), None)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada"
        )

    content = await service.read_version(
        version,
        user=actor,
        ip_address=get_client_ip(request, _trusted_proxies()),
        user_agent=request.headers.get("User-Agent"),
    )
    await session.commit()

    return Response(
        content=content,
        media_type=version.mime_type,
        headers={
            "Content-Disposition": _attachment_disposition(version.original_name),
            "X-Content-SHA256": version.sha256,
            "X-Document-Version": str(version.version_number),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _attachment_disposition(file_name: str) -> str:
    """Build a header safe Content-Disposition for an untrusted file name."""
    safe = _SAFE_FILE_NAME.sub("_", file_name).strip("._") or "documento"
    quoted = quote(safe, safe="")
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quoted}"


@router.get("/documents/{document_id}/history", response_model=list[ChangeLogResponse])
async def get_document_history(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ChangeLogResponse]:
    from app.models import ChangeLog

    # Awaited for its side effect: the lookup *is* the authorisation check, and
    # reaching the next line is the proof that the caller may see the document.
    await _visible_document(session, document_id, current_user, scope)
    result = await session.execute(
        select(ChangeLog)
        .where(ChangeLog.entity == "documents", ChangeLog.entity_id == document_id)
        .order_by(ChangeLog.created_at.desc())
        .limit(limit)
    )
    return [ChangeLogResponse.model_validate(entry) for entry in result.scalars().all()]

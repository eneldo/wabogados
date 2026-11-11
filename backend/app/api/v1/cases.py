from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_session,
    get_user_permission_names,
    get_user_scope,
    require_permission,
)
from app.models import Case, User
from app.schemas.actions import ActionResponse
from app.schemas.calendar import CalendarEventResponse, HearingResponse
from app.schemas.cases import (
    Case360Response,
    CaseAssignmentRequest,
    CaseCloseRequest,
    CaseCollaboratorResponse,
    CaseCreate,
    CasePartyCreate,
    CasePartyResponse,
    CaseResponse,
    CaseSection,
    CaseUpdate,
    PaginatedCases,
)
from app.schemas.clients import ChangeLogResponse
from app.schemas.documents import DocumentResponse
from app.schemas.evidence import EvidenceResponse
from app.services.actions import ActionService
from app.services.calendar import CalendarService, HearingService
from app.services.cases import CaseError, CaseScope, CaseService, scope_filter
from app.services.documents import DocumentService
from app.services.evidence import EvidenceService

router = APIRouter(prefix="/cases", tags=["cases"])

PENDING_SECTIONS = (
    "actuaciones",
    "documentos",
    "agenda",
    "audiencias",
    "tareas",
    "mensajes",
)


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tiene permisos para consultar expedientes",
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Expediente no encontrado"
    )


async def _resolve_visible(
    service: CaseService, case_id: UUID, scope: CaseScope, user: User
) -> Case:
    """Return the case only when the caller may see it.

    Inaccessible cases answer 404 instead of 403 so an identifier cannot be
    confirmed by probing.
    """
    if scope is CaseScope.NONE:
        raise _forbidden()
    case = await service.get_case(case_id)
    if case is None:
        raise _not_found()
    if not await service.can_view(user, case_id):
        raise _not_found()
    return case


@router.get("", response_model=PaginatedCases)
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=120),
    case_status: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    legal_area_id: Annotated[UUID | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
    open_only: bool = Query(default=False),
) -> PaginatedCases:
    service = CaseService(session)
    clause = await scope_filter(session, current_user, scope)
    cases, total = await service.list_cases(
        skip,
        limit,
        scope_filter_clause=clause,
        include_closed=not open_only,
        search=search,
        status=case_status,
        priority=priority,
        legal_area_id=legal_area_id,
        client_id=client_id,
    )
    return PaginatedCases(
        items=[CaseResponse.from_case(case) for case in cases],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:create"))],
) -> CaseResponse:
    service = CaseService(session)
    try:
        case = await service.create_case(payload, actor_id=actor.id)
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    await session.refresh(case)
    return CaseResponse.from_case(case)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CaseResponse:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, current_user)
    return CaseResponse.from_case(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    payload: CaseUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CaseResponse:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, actor)
    try:
        updated = await service.update_case(case, payload, actor_id=actor.id)
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return CaseResponse.from_case(updated)


@router.post("/{case_id}/close", response_model=CaseResponse)
async def close_case(
    case_id: UUID,
    payload: CaseCloseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:close"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CaseResponse:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, actor)
    try:
        closed = await service.close_case(
            case,
            closed_at=payload.closed_at or date.today(),
            notes=payload.notes,
            actor_id=actor.id,
        )
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return CaseResponse.from_case(closed)


@router.get("/{case_id}/360", response_model=Case360Response)
async def get_case_360(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Case360Response:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, current_user)
    collaborators = await service.list_case_lawyers(case_id)
    parties = await service.list_parties(case_id)
    history = await service.list_history(case_id, 200)

    clause = await scope_filter(session, current_user, scope)
    actions, action_total = await ActionService(session).list_actions(
        0, 50, user=current_user, case_id=case_id
    )

    now = datetime.now(UTC)
    horizon = now + timedelta(days=90)
    events = await CalendarService(session).list_events(
        current_user, scope_clause=clause, start=now, end=horizon, limit=200
    )
    case_events = [event for event in events if event.case_id == case_id]
    permission_names = get_user_permission_names(current_user)
    hearings = (
        await HearingService(session).list_hearings(
            current_user, scope_clause=clause, start=now, end=horizon
        )
        if current_user.is_superuser or "hearings:read" in permission_names
        else []
    )
    case_hearings = [item for item in hearings if item.case_id == case_id]

    documents = await DocumentService(session).list_documents(
        current_user, scope_clause=clause, case_id=case_id, limit=50
    )
    evidences = await EvidenceService(session).list_evidences(
        current_user, scope_clause=clause, case_id=case_id, limit=50
    )

    pending = {
        name: CaseSection(available=False)
        for name in PENDING_SECTIONS
        if name not in ("actuaciones", "agenda", "audiencias", "documentos")
    }
    return Case360Response(
        case=CaseResponse.from_case(case),
        collaborators=[
            CaseCollaboratorResponse(
                lawyer_id=item.lawyer_id,
                lawyer_name=item.lawyer.full_name,
                role=item.role,
                assigned_at=item.assigned_at,
            )
            for item in collaborators
        ],
        parties=[CasePartyResponse.model_validate(party) for party in parties],
        history_entries=len(history),
        actuaciones=CaseSection(
            available=True,
            items=[
                ActionResponse.from_action(action).model_dump(mode="json")
                for action in actions
            ],
        ),
        actuaciones_total=action_total,
        agenda=CaseSection(
            available=True,
            items=[
                CalendarEventResponse.from_event(event).model_dump(mode="json")
                for event in case_events
            ],
        ),
        agenda_total=len(case_events),
        audiencias=CaseSection(
            available=True,
            items=[
                HearingResponse.from_hearing(hearing).model_dump(mode="json")
                for hearing in case_hearings
            ],
        ),
        audiencias_total=len(case_hearings),
        documentos=CaseSection(
            available=True,
            items=[
                DocumentResponse.from_document(document).model_dump(mode="json")
                for document in documents
            ],
        ),
        documentos_total=len(documents),
        evidencias=CaseSection(
            available=True,
            items=[
                EvidenceResponse.from_evidence(evidence).model_dump(mode="json")
                for evidence in evidences
            ],
        ),
        evidencias_total=len(evidences),
        **pending,
    )


@router.post("/{case_id}/lawyers", response_model=CaseCollaboratorResponse)
async def assign_lawyer(
    case_id: UUID,
    payload: CaseAssignmentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:assign"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CaseCollaboratorResponse:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, actor)
    try:
        assignment = await service.assign_lawyer(case, payload.lawyer_id, actor_id=actor.id)
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return CaseCollaboratorResponse(
        lawyer_id=assignment.lawyer_id,
        lawyer_name=assignment.lawyer.full_name,
        role=assignment.role,
        assigned_at=assignment.assigned_at,
    )


@router.delete("/{case_id}/lawyers/{lawyer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_lawyer(
    case_id: UUID,
    lawyer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:assign"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> None:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, actor)
    try:
        await service.revoke_lawyer(case, lawyer_id)
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error


@router.get("/{case_id}/parties", response_model=list[CasePartyResponse])
async def list_parties(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> list[CasePartyResponse]:
    service = CaseService(session)
    await _resolve_visible(service, case_id, scope, current_user)
    return [
        CasePartyResponse.model_validate(party)
        for party in await service.list_parties(case_id)
    ]


@router.post(
    "/{case_id}/parties",
    response_model=CasePartyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_party(
    case_id: UUID,
    payload: CasePartyCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:assign"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CasePartyResponse:
    service = CaseService(session)
    case = await _resolve_visible(service, case_id, scope, actor)
    try:
        party = await service.add_party(
            case, payload.model_dump(), actor_id=actor.id
        )
        await session.commit()
    except CaseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return CasePartyResponse.model_validate(party)


@router.get("/{case_id}/history", response_model=list[ChangeLogResponse])
async def get_case_history(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChangeLogResponse]:
    service = CaseService(session)
    await _resolve_visible(service, case_id, scope, current_user)
    entries = await service.list_history(case_id, limit)
    return [ChangeLogResponse.model_validate(entry) for entry in entries]

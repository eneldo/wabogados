from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, get_user_scope, require_permission
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import Case, User
from app.schemas.actions import (
    ActionCreate,
    ActionResponse,
    ActionTimelineEntry,
    ActionUpdate,
    PendingActionResponse,
    TimelineResponse,
)
from app.schemas.clients import ChangeLogResponse
from app.services.actions import ActionError, ActionService, visible_visibilities
from app.services.cases import (
    CaseError,
    CaseScope,
    CaseService,
    assigned_case_ids,
    scope_filter,
)

router = APIRouter(tags=["actions"])


async def _require_visible_case(
    session: AsyncSession, case_id: UUID, user: User, scope: CaseScope
) -> None:
    """Return 404 when the case is missing or outside the caller's scope."""
    if scope is CaseScope.NONE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar expedientes",
        )
    service = CaseService(session)
    if await service.get_case(case_id) is None or not await service.can_view(
        user, case_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expediente no encontrado"
        )


@router.post(
    "/cases/{case_id}/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action(
    case_id: UUID,
    payload: ActionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("actions:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> ActionResponse:
    if payload.case_id != case_id:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="El cuerpo no coincide con el expediente de la ruta",
        )
    await _require_visible_case(session, case_id, actor, scope)
    service = ActionService(session)
    try:
        action = await service.create_action(payload, actor_id=actor.id)
        await session.commit()
    except (ActionError, CaseError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    await session.refresh(action)
    return ActionResponse.from_action(action)


@router.get("/cases/{case_id}/timeline", response_model=TimelineResponse)
async def get_case_timeline(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: int = Query(default=100, ge=1, le=500),
) -> TimelineResponse:
    await _require_visible_case(session, case_id, current_user, scope)
    case_service = CaseService(session)
    case = await case_service.get_case(case_id)
    actions, total = await ActionService(session).list_actions(
        0, limit, user=current_user, case_id=case_id
    )
    now = datetime.now(UTC)

    return TimelineResponse(
        case_id=case_id,
        case_number=case.case_number if case else "",
        total=total,
        entries=[
            ActionTimelineEntry(
                action=ActionResponse.from_action(action),
                case_status=case.status if case else "desconocido",
                is_pending=bool(
                    action.next_action_at and action.next_action_at <= now
                ),
            )
            for action in actions
        ],
    )


@router.get("/actions", response_model=list[ActionResponse])
async def list_actions(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action_type: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
) -> list[ActionResponse]:
    if not visible_visibilities(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar actuaciones",
        )
    clause = await scope_filter(session, current_user, scope)
    case_ids = None
    if clause is not None:
        case_ids = list(
            (await session.execute(select(Case.id).where(clause))).scalars().all()
        )

    actions, _total = await ActionService(session).list_actions(
        skip,
        limit,
        user=current_user,
        case_ids=case_ids,
        action_type=action_type,
        visibility=visibility,
        pending_only=pending_only,
    )
    return [ActionResponse.from_action(action) for action in actions]


@router.get("/actions/pending", response_model=list[PendingActionResponse])
async def list_pending_actions(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PendingActionResponse]:
    """Next actions that are already due across the caller's case scope."""
    if not visible_visibilities(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar actuaciones",
        )

    if scope is CaseScope.ALL:
        case_ids = None
    else:
        case_ids = await assigned_case_ids(session, current_user)
        if not case_ids:
            return []

    filters = [Case.is_active.is_(True)]
    if case_ids is not None:
        filters.append(Case.id.in_(case_ids))

    result = await session.execute(select(Case).where(*filters))
    cases = {case.id: case for case in result.scalars().all()}
    if not cases:
        return []

    actions, _total = await ActionService(session).list_actions(
        0,
        limit,
        user=current_user,
        case_ids=list(cases),
        pending_only=True,
    )
    now = datetime.now(UTC)
    return [
        PendingActionResponse(
            action_id=action.id,
            case_id=action.case_id,
            case_number=cases[action.case_id].case_number,
            case_title=cases[action.case_id].title,
            next_action=action.next_action or "",
            next_action_at=action.next_action_at,
            overdue=bool(action.next_action_at and action.next_action_at < now),
        )
        for action in actions
        if action.case_id in cases and action.next_action_at is not None
    ]


@router.get("/actions/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ActionResponse:
    service = ActionService(session)
    action = await service.get_visible_action(action_id, current_user)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actuación no encontrada"
        )
    if not await CaseService(session).can_view(current_user, action.case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actuación no encontrada"
        )
    return ActionResponse.from_action(action)


@router.patch("/actions/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: UUID,
    payload: ActionUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("actions:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> ActionResponse:
    service = ActionService(session)
    action = await service.get_visible_action(action_id, actor)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actuación no encontrada"
        )
    await _require_visible_case(session, action.case_id, actor, scope)

    try:
        updated = await service.update_action(action, payload, actor_id=actor.id)
        await session.commit()
    except ActionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return ActionResponse.from_action(updated)


@router.get("/actions/{action_id}/history", response_model=list[ChangeLogResponse])
async def get_action_history(
    action_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChangeLogResponse]:
    service = ActionService(session)
    action = await service.get_visible_action(action_id, current_user)
    if action is None or not await CaseService(session).can_view(
        current_user, action.case_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Actuación no encontrada"
        )
    entries = await service.history_for_action(action_id, limit)
    return [ChangeLogResponse.model_validate(entry) for entry in entries]

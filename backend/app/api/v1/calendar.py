from datetime import UTC, date, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, get_user_scope, require_permission
from app.models import Case, User
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarEventUpdate,
    CalendarView,
    CalendarViewResponse,
    DeadlineItem,
    HearingCreate,
    HearingReschedule,
    HearingResponse,
    HearingUpdate,
)
from app.services.actions import ActionService
from app.services.calendar import (
    CalendarError,
    CalendarService,
    HearingService,
    view_range,
    visible_visibilities,
)
from app.services.cases import CaseScope, scope_filter

router = APIRouter(tags=["calendar"])


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


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


def today() -> date:
    """Default reference for calendar views, resolved per request."""
    return date.today()


@router.get("/calendar", response_model=CalendarViewResponse)
async def get_calendar(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    view: Annotated[str, Query(pattern="^(day|week|month|lawyer|case)$")] = "week",
    reference: date = Query(default_factory=today),  # noqa: B008
    lawyer_id: Annotated[UUID | None, Query()] = None,
    case_id: Annotated[UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> CalendarViewResponse:
    if not visible_visibilities(current_user):
        raise _forbidden("No tiene permisos para consultar la agenda")

    start, end = view_range(view, reference)
    service = CalendarService(session)
    clause: ColumnElement[bool] | None
    if case_id is not None:
        await _require_visible_case(session, case_id, current_user, scope)
        clause = Case.id == case_id
    else:
        clause = await scope_filter(session, current_user, scope)

    events = await service.list_events(
        current_user,
        scope_clause=clause,
        start=start,
        end=end,
        lawyer_id=lawyer_id,
        event_type=event_type,
        limit=limit,
    )

    return CalendarViewResponse(
        view=cast(CalendarView, view),
        start=start,
        end=end,
        total=len(events),
        events=[CalendarEventResponse.from_event(event) for event in events],
    )


@router.post("/calendar", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: CalendarEventCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("calendar:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CalendarEventResponse:
    await _require_visible_case(session, payload.case_id, actor, scope)
    service = CalendarService(session)
    try:
        event = await service.create_event(payload, actor_id=actor.id)
        await session.commit()
    except CalendarError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    await session.refresh(event)
    return CalendarEventResponse.from_event(event)


@router.patch("/calendar/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: UUID,
    payload: CalendarEventUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("calendar:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> CalendarEventResponse:
    service = CalendarService(session)
    event = await service.get_visible_event(event_id, actor)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )
    await _require_visible_case(session, event.case_id, actor, scope)
    try:
        updated = await service.update_event(event, payload, actor_id=actor.id)
        await session.commit()
    except CalendarError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return CalendarEventResponse.from_event(updated)


@router.get("/hearings", response_model=list[HearingResponse])
async def list_hearings(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_permission("hearings:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    hearing_status: Annotated[str | None, Query(alias="status")] = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[HearingResponse]:
    if not visible_visibilities(current_user):
        raise _forbidden("No tiene permisos para consultar audiencias")
    service = HearingService(session)
    hearings = await service.list_hearings(
        current_user,
        scope_clause=await scope_filter(session, current_user, scope),
        start=start,
        end=end,
        status=hearing_status,
        limit=limit,
    )
    return [
        HearingResponse.from_hearing(hearing, await service.reschedule_count(hearing))
        for hearing in hearings
    ]


@router.post(
    "/hearings", response_model=HearingResponse, status_code=status.HTTP_201_CREATED
)
async def create_hearing(
    payload: HearingCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("hearings:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> HearingResponse:
    await _require_visible_case(session, payload.case_id, actor, scope)
    service = HearingService(session)
    try:
        hearing = await service.create_hearing(payload, actor_id=actor.id)
        await session.commit()
    except CalendarError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return HearingResponse.from_hearing(hearing, await service.reschedule_count(hearing))


@router.patch("/hearings/{hearing_id}", response_model=HearingResponse)
async def update_hearing(
    hearing_id: UUID,
    payload: HearingUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("hearings:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> HearingResponse:
    service = HearingService(session)
    hearing = await service.get_hearing(hearing_id)
    if hearing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Audiencia no encontrada"
        )
    await _require_visible_case(session, hearing.case_id, actor, scope)
    try:
        updated = await service.update_hearing(hearing, payload, actor_id=actor.id)
        await session.commit()
    except CalendarError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return HearingResponse.from_hearing(updated, await service.reschedule_count(updated))


@router.post("/hearings/{hearing_id}/reschedule", response_model=HearingResponse)
async def reschedule_hearing(
    hearing_id: UUID,
    payload: HearingReschedule,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("hearings:reschedule"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> HearingResponse:
    service = HearingService(session)
    hearing = await service.get_hearing(hearing_id)
    if hearing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Audiencia no encontrada"
        )
    await _require_visible_case(session, hearing.case_id, actor, scope)
    try:
        moved = await service.reschedule_hearing(hearing, payload, actor_id=actor.id)
        await session.commit()
    except CalendarError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return HearingResponse.from_hearing(moved, await service.reschedule_count(moved))


@router.get("/calendar/deadlines", response_model=list[DeadlineItem])
async def list_deadlines(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DeadlineItem]:
    """Merge explicit `vencimiento` events with pending action due dates."""
    if not visible_visibilities(current_user):
        raise _forbidden("No tiene permisos para consultar la agenda")

    now = datetime.now(UTC)
    horizon = now + timedelta(days=days)
    clause = await scope_filter(session, current_user, scope)

    events = await CalendarService(session).list_events(
        current_user,
        scope_clause=clause,
        # No lower bound: overdue deadlines are exactly what the firm needs.
        start=None,
        end=horizon,
        event_type="vencimiento",
        limit=limit,
    )
    actions, _total = await ActionService(session).list_actions(
        0,
        limit,
        user=current_user,
        # No lower bound for the same reason: overdue items are the priority.
        due_after=None,
        due_before=horizon,
    )

    case_numbers: dict[UUID, str] = {}
    if clause is not None:
        rows = await session.execute(select(Case.id, Case.case_number).where(clause))
        case_numbers = {row[0]: row[1] for row in rows.all()}

    def _case_number(action: object) -> str:
        case = getattr(action, "case", None)
        if case is not None:
            return str(case.case_number)
        case_id = getattr(action, "case_id", None)
        if isinstance(case_id, UUID):
            return case_numbers.get(case_id, "")
        return ""

    items: list[DeadlineItem] = [
        DeadlineItem(
            source="evento",
            reference_id=event.id,
            case_id=event.case_id,
            case_number=event.case.case_number if event.case else "",
            title=event.title,
            due_at=event.starts_at,
            overdue=event.starts_at < now,
            source_label="Vencimiento",
        )
        for event in events
    ]
    for action in actions:
        if action.next_action_at is None or action.next_action_at > horizon:
            continue
        items.append(
            DeadlineItem(
                source="actuacion",
                reference_id=action.id,
                case_id=action.case_id,
                case_number=_case_number(action),
                title=action.next_action or "Próxima acción",
                due_at=action.next_action_at,
                overdue=action.next_action_at < now,
                source_label="Próxima actuación",
            )
        )
    items.sort(key=lambda item: item.due_at)
    return items[:limit]

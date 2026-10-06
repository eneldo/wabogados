"""Calendar and hearing services.

Events inherit the access scope of their case, exactly like actions do. Hearings
add procedural data on top of the `audiencia` event type.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_permission_names
from app.models import CalendarEvent, Case, Hearing, Lawyer, User
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
    HearingCreate,
    HearingReschedule,
    HearingUpdate,
)
from app.services.cases import case_scoped
from app.services.history import record_changes

EVENT_ENTITY = "calendar_events"
HEARING_ENTITY = "hearings"

INTERNAL_VISIBILITY = ("interna", "equipo")
PUBLISHED_VISIBILITY = "publicada"

HEARING_EVENT_TYPE = "audiencia"

TRACKED_EVENT_FIELDS = (
    "title",
    "starts_at",
    "ends_at",
    "location",
    "lawyer_id",
    "visibility",
    "status",
    "reminder_minutes",
)

TRACKED_HEARING_FIELDS = (
    "court",
    "courtroom",
    "judge",
    "procedural_stage",
    "file_number",
    "notified_at",
    "attendance",
    "result",
    "status",
)


class CalendarError(Exception):
    """Raised when a calendar or hearing operation violates a business rule."""


def visible_visibilities(user: User) -> tuple[str, ...]:
    """Visibility levels the caller may read, mirroring the action rules."""
    permissions = get_user_permission_names(user)
    if user.is_superuser or "calendar:read" in permissions:
        return (*INTERNAL_VISIBILITY, PUBLISHED_VISIBILITY)
    if "calendar:read_published" in permissions:
        return (PUBLISHED_VISIBILITY,)
    return ()


def view_range(view: str, reference: date) -> tuple[datetime, datetime]:
    """Return the [start, end) window for a calendar view."""
    day_start = datetime.combine(reference, datetime.min.time(), tzinfo=UTC)
    if view == "day":
        return day_start, day_start + timedelta(days=1)
    if view == "week":
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
    if view == "month":
        start = day_start.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month
    # "lawyer" and "case" views fall back to a 30 day window around the reference.
    return day_start, day_start + timedelta(days=30)


class CalendarService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _visibility_filter(self, allowed: tuple[str, ...]) -> ColumnElement[bool]:
        if not allowed:
            return func.false()
        return CalendarEvent.visibility.in_(allowed)

    async def list_events(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
        start: datetime | None,
        end: datetime,
        case_ids: list[UUID] | None = None,
        lawyer_id: UUID | None = None,
        event_type: str | None = None,
        status: str | None = None,
        visibility: str | None = None,
        limit: int = 200,
    ) -> list[CalendarEvent]:
        allowed = visible_visibilities(user)
        filters: list[ColumnElement[bool]] = [
            CalendarEvent.is_active.is_(True),
            self._visibility_filter(allowed),
            CalendarEvent.starts_at < end,
        ]
        if start is not None:
            # Overlapping the window, so multi day events are not cut in half.
            filters.append(CalendarEvent.ends_at >= start)
        scoped = case_scoped(CalendarEvent.case_id, scope_clause)
        if scoped is not None:
            filters.append(scoped)
        elif case_ids is not None:
            filters.append(CalendarEvent.case_id.in_(case_ids) if case_ids else func.false())
        if lawyer_id is not None:
            filters.append(CalendarEvent.lawyer_id == lawyer_id)
        if event_type:
            filters.append(CalendarEvent.event_type == event_type)
        if status:
            filters.append(CalendarEvent.status == status)
        if visibility:
            if visibility not in allowed:
                return []
            filters.append(CalendarEvent.visibility == visibility)

        result = await self.session.execute(
            select(CalendarEvent)
            .where(*filters)
            .order_by(CalendarEvent.starts_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_event(self, event_id: UUID) -> CalendarEvent | None:
        return await self.session.get(CalendarEvent, event_id)

    async def get_visible_event(
        self, event_id: UUID, user: User
    ) -> CalendarEvent | None:
        event = await self.get_event(event_id)
        if event is None or not event.is_active:
            return None
        if event.visibility not in visible_visibilities(user):
            return None
        return event

    async def _require_case(self, case_id: UUID) -> Case:
        result = await self.session.execute(
            select(Case).where(Case.id == case_id, Case.is_active.is_(True))
        )
        case = result.scalar_one_or_none()
        if case is None:
            raise CalendarError("El expediente no existe o está inactivo")
        return case

    async def _require_lawyer(self, lawyer_id: UUID) -> Lawyer:
        result = await self.session.execute(
            select(Lawyer).where(Lawyer.id == lawyer_id, Lawyer.is_active.is_(True))
        )
        lawyer = result.scalar_one_or_none()
        if lawyer is None:
            raise CalendarError("El abogado no existe o está inactivo")
        return lawyer

    async def create_event(
        self, payload: CalendarEventCreate, *, actor_id: UUID | None = None
    ) -> CalendarEvent:
        await self._require_case(payload.case_id)
        if payload.lawyer_id is not None:
            await self._require_lawyer(payload.lawyer_id)
        ends_at = payload.ends_at or payload.starts_at
        if ends_at <= payload.starts_at:
            raise CalendarError("ends_at debe ser posterior a starts_at")

        event = CalendarEvent(
            case_id=payload.case_id,
            event_type=payload.event_type,
            title=payload.title,
            description=payload.description,
            starts_at=payload.starts_at,
            ends_at=ends_at,
            all_day=payload.all_day,
            location=payload.location,
            lawyer_id=payload.lawyer_id,
            visibility=payload.visibility,
            status=payload.status,
            reminder_minutes=payload.reminder_minutes,
            created_by=actor_id,
            is_active=True,
        )
        self.session.add(event)
        await self.session.flush()
        record_changes(
            self.session,
            entity=EVENT_ENTITY,
            entity_id=event.id,
            before={},
            after=payload.model_dump(mode="json"),
            changed_by=actor_id,
            fields=TRACKED_EVENT_FIELDS,
        )
        await self.session.flush()
        return event

    async def update_event(
        self,
        event: CalendarEvent,
        payload: CalendarEventUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> CalendarEvent:
        if event.event_type == HEARING_EVENT_TYPE:
            raise CalendarError(
                "Una audiencia se actualiza o reprograma mediante /hearings"
            )
        data = payload.model_dump(exclude_unset=True)
        if data.get("lawyer_id") is not None:
            await self._require_lawyer(data["lawyer_id"])

        starts_at = data.get("starts_at", event.starts_at)
        ends_at = data.get("ends_at", event.ends_at)
        if ends_at <= starts_at:
            raise CalendarError("ends_at debe ser posterior a starts_at")

        before = {field: getattr(event, field, None) for field in TRACKED_EVENT_FIELDS}
        for field, value in data.items():
            setattr(event, field, value)
        record_changes(
            self.session,
            entity=EVENT_ENTITY,
            entity_id=event.id,
            before=before,
            after=data,
            changed_by=actor_id,
            fields=TRACKED_EVENT_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(event)
        return event


class HearingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.calendar = CalendarService(session)

    async def find_conflicts(
        self,
        starts_at: datetime,
        ends_at: datetime,
        lawyer_id: UUID | None,
        *,
        exclude_event_id: UUID | None = None,
    ) -> list[CalendarEvent]:
        """Return events overlapping the slot for the same lawyer."""
        if lawyer_id is None:
            return []
        filters = [
            CalendarEvent.is_active.is_(True),
            CalendarEvent.lawyer_id == lawyer_id,
            CalendarEvent.status.notin_(("cancelada",)),
            CalendarEvent.starts_at < ends_at,
            CalendarEvent.ends_at > starts_at,
        ]
        if exclude_event_id is not None:
            filters.append(CalendarEvent.id != exclude_event_id)
        result = await self.session.execute(
            select(CalendarEvent).where(*filters).order_by(CalendarEvent.starts_at).limit(5)
        )
        return list(result.scalars().all())

    async def create_hearing(
        self, payload: HearingCreate, *, actor_id: UUID | None = None
    ) -> Hearing:
        await self.calendar._require_case(payload.case_id)
        if payload.lawyer_id is not None:
            await self.calendar._require_lawyer(payload.lawyer_id)
        ends_at = payload.ends_at or payload.starts_at + timedelta(hours=1)
        if ends_at <= payload.starts_at:
            raise CalendarError("ends_at debe ser posterior a starts_at")

        conflicts = await self.find_conflicts(
            payload.starts_at, ends_at, payload.lawyer_id
        )
        if conflicts:
            raise CalendarError("El abogado ya tiene un evento en esa franja")

        event = CalendarEvent(
            case_id=payload.case_id,
            event_type=HEARING_EVENT_TYPE,
            title=payload.title,
            description=payload.description,
            starts_at=payload.starts_at,
            ends_at=ends_at,
            all_day=False,
            location=payload.location,
            lawyer_id=payload.lawyer_id,
            visibility=payload.visibility,
            status="programada",
            created_by=actor_id,
            is_active=True,
        )
        self.session.add(event)
        await self.session.flush()

        hearing = Hearing(
            event_id=event.id,
            case_id=payload.case_id,
            court=payload.court,
            courtroom=payload.courtroom,
            judge=payload.judge,
            procedural_stage=payload.procedural_stage,
            file_number=payload.file_number,
            notified_at=payload.notified_at,
            attendance="pendiente",
            status="programada",
        )
        self.session.add(hearing)
        await self.session.flush()
        record_changes(
            self.session,
            entity=HEARING_ENTITY,
            entity_id=hearing.id,
            before={},
            after=payload.model_dump(mode="json"),
            changed_by=actor_id,
            fields=TRACKED_HEARING_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(hearing)
        return hearing

    async def get_hearing(self, hearing_id: UUID) -> Hearing | None:
        return await self.session.get(Hearing, hearing_id)

    async def list_hearings(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
        case_ids: list[UUID] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Hearing]:
        filters: list[ColumnElement[bool]] = [
            Hearing.event_id.is_not(None),
            CalendarEvent.is_active.is_(True),
            self.calendar._visibility_filter(visible_visibilities(user)),
        ]
        scoped = case_scoped(Hearing.case_id, scope_clause)
        if scoped is not None:
            filters.append(scoped)
        elif case_ids is not None:
            filters.append(Hearing.case_id.in_(case_ids) if case_ids else func.false())
        if status:
            filters.append(Hearing.status == status)
        if start is not None and end is not None:
            filters.append(CalendarEvent.starts_at < end)
            filters.append(CalendarEvent.ends_at >= start)

        result = await self.session.execute(
            select(Hearing)
            .join(CalendarEvent, Hearing.event_id == CalendarEvent.id)
            .where(*filters)
            .order_by(CalendarEvent.starts_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_hearing(
        self,
        hearing: Hearing,
        payload: HearingUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> Hearing:
        data = payload.model_dump(exclude_unset=True)
        if data.get("status") == "realizada" and not (
            data.get("result") or hearing.result
        ):
            raise CalendarError("Una audiencia realizada exige registrar el resultado")

        before = {field: getattr(hearing, field, None) for field in TRACKED_HEARING_FIELDS}
        for field, value in data.items():
            setattr(hearing, field, value)

        if data.get("status") == "realizada" and hearing.event_id:
            event = await self.session.get(CalendarEvent, hearing.event_id)
            if event is not None:
                event.status = "realizada"

        record_changes(
            self.session,
            entity=HEARING_ENTITY,
            entity_id=hearing.id,
            before=before,
            after=data,
            changed_by=actor_id,
            fields=TRACKED_HEARING_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(hearing)
        return hearing

    async def reschedule_hearing(
        self,
        hearing: Hearing,
        payload: HearingReschedule,
        *,
        actor_id: UUID | None = None,
    ) -> Hearing:
        """Move a hearing, keeping a trace of the previous scheduling."""
        if hearing.status in ("realizada", "cancelada"):
            raise CalendarError("Una audiencia realizada o cancelada no se reprograma")

        event = await self.session.get(CalendarEvent, hearing.event_id)
        if event is None:
            raise CalendarError("El evento de la audiencia no existe")

        ends_at = payload.ends_at or payload.starts_at + timedelta(hours=1)
        if ends_at <= payload.starts_at:
            raise CalendarError("ends_at debe ser posterior a starts_at")

        conflicts = await self.find_conflicts(
            payload.starts_at, ends_at, event.lawyer_id, exclude_event_id=event.id
        )
        if conflicts:
            raise CalendarError("El abogado ya tiene un evento en esa franja")

        before = {
            "starts_at": event.starts_at,
            "ends_at": event.ends_at,
            "status": hearing.status,
        }
        event.starts_at = payload.starts_at
        event.ends_at = ends_at
        event.status = "programada"
        hearing.status = "aplazada"
        hearing.rescheduled_from_id = hearing.id

        record_changes(
            self.session,
            entity=HEARING_ENTITY,
            entity_id=hearing.id,
            before=before,
            after={
                "starts_at": payload.starts_at,
                "ends_at": ends_at,
                "status": "aplazada",
                "motivo": payload.reason,
            },
            changed_by=actor_id,
            fields=("status",),
        )
        await self.session.flush()
        await self.session.refresh(hearing)
        return hearing

    async def reschedule_count(self, hearing: Hearing) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Hearing)
            .where(Hearing.rescheduled_from_id == hearing.id)
        )
        return int(result.scalar_one())


ViewName = Literal["day", "week", "month", "lawyer", "case"]


__all__ = [
    "EVENT_ENTITY",
    "HEARING_ENTITY",
    "HEARING_EVENT_TYPE",
    "CalendarError",
    "CalendarService",
    "HearingService",
    "view_range",
    "visible_visibilities",
]

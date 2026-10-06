"""Role dashboards.

Every figure returned here is a ``COUNT`` over a query that already carries the
caller's case scope and visibility. A dashboard is an aggregate over the same
rows the caller could page through: if a number can exceed the detail it
summarises, the aggregate is leaking. Nothing is counted in Python and nothing
is filtered after counting.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.api.deps import get_user_permission_names
from app.models import (
    Action,
    CalendarEvent,
    Case,
    CaseLawyer,
    Client,
    Document,
    Evidence,
    Hearing,
    Lawyer,
    User,
)
from app.services.actions import visible_visibilities as action_visibilities
from app.services.cases import (
    CaseScope,
    case_scoped,
    resolve_scope,
    scope_filter,
)
from app.services.messaging import MessagingService

#: A case stays active until it is closed or archived.
CLOSED_STATUSES = ("cerrado", "archivado")

#: Hearings in these states are no longer on the horizon.
FINISHED_HEARING_STATUSES = ("cancelada", "celebrada", "realizada")

#: Visibility level the portal is allowed to read.
PUBLISHED = "publicada"

#: How far ahead the dashboard looks without being asked.
DEFAULT_HORIZON_DAYS = 30

#: How many rows each list carries.
DEFAULT_LIST_LIMIT = 8


@dataclass(frozen=True)
class DeadlineEntry:
    """A due date, from either an explicit event or an actuación's next step."""

    source: str
    reference_id: UUID
    case_id: UUID
    title: str
    due_at: datetime
    is_overdue: bool


def month_start(reference: datetime) -> datetime:
    """First instant of the month `reference` falls in, in UTC."""
    return datetime(reference.year, reference.month, 1, tzinfo=UTC)


def _is_client_scope(scope: CaseScope) -> bool:
    return scope is CaseScope.OWN_PUBLISHED


class DashboardService:
    """Builds the dashboard of whoever is asking.

    The dashboard is shaped by the caller's *scope*, not by a role name. Scope is
    what the rest of the application already enforces, so deriving the aggregate
    from the same place keeps the two from disagreeing.
    """

    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user
        self.scope: CaseScope = CaseScope.NONE
        self._case_clause: ColumnElement[bool] | None = None

    # -- scope plumbing ---------------------------------------------------

    async def prepare(self) -> None:
        self.scope = await resolve_scope(self.session, self.user)
        self._case_clause = await scope_filter(self.session, self.user, self.scope)

    def _cases(self, *extra: ColumnElement[bool]) -> Select[Any]:
        """A `cases` query already restricted to what the caller may see."""
        filters = [*extra]
        if self._case_clause is not None:
            filters.append(self._case_clause)
        statement = select(Case)
        return statement.where(and_(*filters)) if filters else statement

    def _child_scope(
        self, case_id_column: InstrumentedAttribute[UUID]
    ) -> ColumnElement[bool] | None:
        """Translate the case scope for an entity that only carries `case_id`."""
        return case_scoped(case_id_column, self._case_clause)

    def _visibility(
        self, column: InstrumentedAttribute[str]
    ) -> ColumnElement[bool] | None:
        """Restrict a visibility column to what this caller may read."""
        return column == PUBLISHED if _is_client_scope(self.scope) else None

    async def _count(self, statement: Select[Any], *filters: ColumnElement[bool]) -> int:
        """Count the rows of a select.

    The filters go **inside** the statement, never in the outer count. Filtering
    after wrapping it in a subquery makes SQLAlchemy re-join the source table
    into the outer query, and the result becomes the cartesian product of the
    two: counting two cases returns four as soon as any other row exists. This
    is the same shape of bug as the one `case_scoped` documents.
    """
        for condition in filters:
            statement = statement.where(condition)
        counted = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(counted)
        return int(result.scalar() or 0)

    async def _rows(self, statement: Select[Any]) -> list[Any]:
        return list((await self.session.execute(statement)).all())

    # -- entity scoped statements ----------------------------------------

    def _clients_scoped(self) -> Select[Any]:
        """Active clients behind the cases the caller may see."""
        statement = select(Client).where(Client.is_active.is_(True))
        if self._case_clause is None:
            return statement
        return statement.where(Client.id.in_(select(Case.client_id).where(self._case_clause)))

    def _lawyers_scoped(self) -> Select[Any]:
        """Active lawyers working on the cases the caller may see."""
        statement = select(Lawyer).where(Lawyer.is_active.is_(True))
        if self._case_clause is None:
            return statement
        return statement.where(
            Lawyer.id.in_(
                select(Case.responsible_lawyer_id).where(
                    self._case_clause, Case.responsible_lawyer_id.is_not(None)
                )
            )
            | Lawyer.id.in_(
                select(CaseLawyer.lawyer_id).where(
                    CaseLawyer.case_id.in_(select(Case.id).where(self._case_clause))
                )
            )
        )

    def _actions_scoped(self) -> Select[Any]:
        statement = select(Action)
        scope = self._child_scope(Action.case_id)
        if scope is not None:
            statement = statement.where(scope)
        allowed = action_visibilities(self.user)
        if allowed:
            statement = statement.where(Action.visibility.in_(allowed))
        else:
            statement = statement.where(literal(False))
        return statement

    def _events_scoped(self) -> Select[Any]:
        statement = select(CalendarEvent)
        scope = self._child_scope(CalendarEvent.case_id)
        if scope is not None:
            statement = statement.where(scope)
        if _is_client_scope(self.scope):
            statement = statement.where(CalendarEvent.visibility == PUBLISHED)
        return statement

    def _hearings_scoped(self) -> Select[Any, Any]:
        statement: Select[Any, Any] = select(Hearing, CalendarEvent).join(
            CalendarEvent, CalendarEvent.id == Hearing.event_id
        )
        scope = self._child_scope(Hearing.case_id)
        if scope is not None:
            statement = statement.where(scope)
        if _is_client_scope(self.scope):
            statement = statement.where(CalendarEvent.visibility == PUBLISHED)
        return statement

    def _documents_scoped(self) -> Select[Any]:
        statement = select(Document)
        scope = self._child_scope(Document.case_id)
        if scope is not None:
            statement = statement.where(scope)
        visibility = self._visibility(Document.visibility)
        if visibility is not None:
            statement = statement.where(visibility)
        return statement

    def _evidences_scoped(self) -> Select[Any]:
        statement = select(Evidence)
        scope = self._child_scope(Evidence.case_id)
        if scope is not None:
            statement = statement.where(scope)
        visibility = self._visibility(Evidence.visibility)
        if visibility is not None:
            statement = statement.where(visibility)
        return statement

    # -- figures ----------------------------------------------------------

    async def active_clients(self) -> int:
        return await self._count(self._clients_scoped())

    async def active_lawyers(self) -> int:
        return await self._count(self._lawyers_scoped())

    async def active_cases(self) -> int:
        return await self._count(self._cases(), Case.status.notin_(CLOSED_STATUSES))

    async def closed_cases(self) -> int:
        return await self._count(self._cases(), Case.status == "cerrado")

    async def evidences(self) -> int:
        return await self._count(self._evidences_scoped())

    async def recent_documents(self, *, days: int = 7) -> int:
        since = datetime.now(UTC) - timedelta(days=days)
        return await self._count(self._documents_scoped(), Document.created_at >= since)

    async def actions_this_month(self) -> int:
        since = month_start(datetime.now(UTC))
        return await self._count(self._actions_scoped(), Action.occurred_at >= since)

    async def upcoming_hearings(self, *, days: int = DEFAULT_HORIZON_DAYS) -> int:
        now = datetime.now(UTC)
        statement = self._hearings_scoped().where(
            CalendarEvent.starts_at >= now,
            CalendarEvent.starts_at <= now + timedelta(days=days),
            Hearing.status.notin_(FINISHED_HEARING_STATUSES),
        )
        return await self._count(statement)

    async def pending_actions(self, *, days: int = DEFAULT_HORIZON_DAYS) -> int:
        """Actuaciones whose next step falls due. Overdue ones are included."""
        limit = datetime.now(UTC) + timedelta(days=days)
        return await self._count(
            self._actions_scoped(),
            Action.next_action_at.is_not(None),
            Action.next_action_at <= limit,
        )

    async def open_deadlines(self, *, days: int = DEFAULT_HORIZON_DAYS) -> int:
        """Vencimientos still ahead. Overdue ones are counted apart."""
        now = datetime.now(UTC)
        statement = self._events_scoped().where(
            CalendarEvent.event_type == "vencimiento",
            CalendarEvent.starts_at >= now,
            CalendarEvent.starts_at <= now + timedelta(days=days),
        )
        return await self._count(statement)

    async def overdue_deadlines(self) -> int:
        statement = self._events_scoped().where(
            CalendarEvent.event_type == "vencimiento",
            CalendarEvent.starts_at < datetime.now(UTC),
        )
        return await self._count(statement)

    async def pending_messages(self) -> int:
        return await MessagingService(self.session).total_unread(self.user)

    async def unread_notifications(self) -> int:
        return await MessagingService(self.session).unread_notifications(self.user)

    # -- lists ------------------------------------------------------------

    async def my_cases(self, *, limit: int = DEFAULT_LIST_LIMIT) -> list[Case]:
        statement = (
            self._cases()
            .where(Case.status.notin_(CLOSED_STATUSES))
            .order_by(Case.opened_at.desc(), Case.case_number.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def next_hearing(self) -> tuple[Hearing, CalendarEvent] | None:
        statement = (
            self._hearings_scoped()
            .where(
                CalendarEvent.starts_at >= datetime.now(UTC),
                Hearing.status.notin_(FINISHED_HEARING_STATUSES),
            )
            .order_by(CalendarEvent.starts_at)
            .limit(1)
        )
        rows = await self._rows(statement)
        if not rows:
            return None
        return (rows[0][0], rows[0][1])

    async def upcoming_hearings_list(
        self,
        *,
        days: int = DEFAULT_HORIZON_DAYS,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[tuple[Hearing, CalendarEvent]]:
        now = datetime.now(UTC)
        statement = (
            self._hearings_scoped()
            .where(
                CalendarEvent.starts_at >= now,
                CalendarEvent.starts_at <= now + timedelta(days=days),
                Hearing.status.notin_(FINISHED_HEARING_STATUSES),
            )
            .order_by(CalendarEvent.starts_at)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in await self._rows(statement)]

    async def deadlines_list(
        self, *, days: int = DEFAULT_HORIZON_DAYS, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[DeadlineEntry]:
        """Due dates coming up or overdue, soonest first."""
        now = datetime.now(UTC)
        horizon = now + timedelta(days=days)

        events = await self.session.execute(
            self._events_scoped()
            .where(
                CalendarEvent.event_type == "vencimiento",
                CalendarEvent.starts_at <= horizon,
            )
            .order_by(CalendarEvent.starts_at)
            .limit(limit)
        )
        actions = await self.session.execute(
            self._actions_scoped()
            .where(
                Action.next_action_at.is_not(None),
                Action.next_action_at <= horizon,
            )
            .order_by(Action.next_action_at)
            .limit(limit)
        )

        items: list[DeadlineEntry] = [
            DeadlineEntry(
                source="evento",
                reference_id=event.id,
                case_id=event.case_id,
                title=event.title,
                due_at=event.starts_at,
                is_overdue=event.starts_at < now,
            )
            for event in events.scalars().all()
        ]
        items.extend(
            DeadlineEntry(
                source="actuacion",
                reference_id=action.id,
                case_id=action.case_id,
                title=action.next_action or action.description,
                due_at=action.next_action_at,
                is_overdue=bool(action.next_action_at and action.next_action_at < now),
            )
            for action in actions.scalars().all()
            if action.next_action_at is not None
        )
        items.sort(key=lambda item: item.due_at)
        return items

    async def recent_actions(self, *, limit: int = DEFAULT_LIST_LIMIT) -> list[Action]:
        statement = self._actions_scoped().order_by(Action.occurred_at.desc()).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def published_documents(
        self, *, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[Document]:
        statement = (
            self._documents_scoped().order_by(Document.created_at.desc()).limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def visible_evidences(self, *, limit: int = DEFAULT_LIST_LIMIT) -> list[Evidence]:
        statement = (
            self._evidences_scoped().order_by(Evidence.created_at.desc()).limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # -- composed payloads ------------------------------------------------

    async def kpis(self) -> dict[str, int]:
        """The figures. Counts only, no rows: safe to poll."""
        return {
            "active_clients": await self.active_clients(),
            "active_cases": await self.active_cases(),
            "closed_cases": await self.closed_cases(),
            "active_lawyers": await self.active_lawyers(),
            "actions_this_month": await self.actions_this_month(),
            "upcoming_hearings": await self.upcoming_hearings(),
            "pending_actions": await self.pending_actions(),
            "open_deadlines": await self.open_deadlines(),
            "overdue_deadlines": await self.overdue_deadlines(),
            "evidences": await self.evidences(),
            "pending_messages": await self.pending_messages(),
            "unread_notifications": await self.unread_notifications(),
        }

    async def summary(self) -> dict[str, int]:
        """The two counters the header badge polls."""
        return {
            "pending_messages": await self.pending_messages(),
            "unread_notifications": await self.unread_notifications(),
        }


def dashboard_view_for(user: User, scope: CaseScope) -> str:
    """Which dashboard the caller gets. Shapes the payload, never the data."""
    if _is_client_scope(scope):
        return "cliente"
    if user.is_superuser or "cases:read_all" in get_user_permission_names(user):
        return "administrador"
    return "abogado"


__all__ = [
    "CLOSED_STATUSES",
    "DEFAULT_HORIZON_DAYS",
    "DEFAULT_LIST_LIMIT",
    "DashboardService",
    "dashboard_view_for",
    "month_start",
]
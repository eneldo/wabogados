"""Isolation of the calendar and hearing scope filter.

`scope_filter` builds predicates on the ``cases`` table. When those predicates
are applied to a query over ``calendar_events`` or ``hearings`` without joining
``cases``, SQLAlchemy adds ``cases`` as a cross product: the predicate then
matches whenever *any* case in the table satisfies it, which silently disables
the scope restriction and leaks rows of other cases.

These tests assert that a lawyer only ever sees events of their own cases.
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CalendarEvent, Case, CaseLawyer, Client, Hearing, Lawyer, User
from app.services.calendar import CalendarService
from app.services.cases import CaseScope, scope_filter

CALENDAR = "/api/v1/calendar"
DEADLINES = "/api/v1/calendar/deadlines"
HEARINGS = "/api/v1/hearings"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _assign(session: AsyncSession, case: Case, lawyer: Lawyer) -> None:
    session.add(CaseLawyer(case_id=case.id, lawyer_id=lawyer.id, role="responsable"))
    await session.flush()


#:
#: Anchored to a Wednesday of the current week, not to "today".
#:
#: The week view spans Monday 00:00 UTC to the following Monday, and the events are
#: placed at `TODAY + days`. With `TODAY` set to the real current date the suite
#: passed by luck and failed by calendar: on a Sunday the reference is the last day
#: of its own week, so "tomorrow" falls outside the window and the scope assertions
#: see no events at all. A Wednesday leaves room for the offsets the tests use and
#: is inside the window on every day of the week.
_today = datetime.now(UTC).date()
TODAY: date = _today - timedelta(days=_today.weekday()) + timedelta(days=2)
CALENDAR_PARAMS = {"view": "week", "reference": TODAY.isoformat()}


async def _add_event(
    session: AsyncSession,
    case: Case,
    *,
    title: str,
    days: int = 1,
    event_type: str = "reunion",
    visibility: str = "interna",
) -> CalendarEvent:
    start = datetime.combine(TODAY, time(hour=9), tzinfo=UTC) + timedelta(days=days)
    event = CalendarEvent(
        case_id=case.id,
        title=title,
        event_type=event_type,
        status="programada",
        visibility=visibility,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        is_active=True,
    )
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_lawyer_only_sees_events_of_assigned_cases(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    other_case: Case,
    sample_lawyer: Lawyer,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """Assigned to `sample_case` only: the other case must stay invisible."""
    other_lawyer, token = second_lawyer_token
    await _assign(database_session, sample_case, other_lawyer)
    await _add_event(database_session, sample_case, title="Reunion propia")
    await _add_event(database_session, other_case, title="Reunion ajena")

    response = await client.get(CALENDAR, params=CALENDAR_PARAMS, headers=_auth(token))

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["events"]}
    assert "Reunion propia" in titles
    assert "Reunion ajena" not in titles
    assert sample_lawyer.id != other_lawyer.id


@pytest.mark.asyncio
async def test_unassigned_lawyer_sees_no_events(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    _lawyer, token = second_lawyer_token
    await _add_event(database_session, sample_case, title="Reunion de otro")

    response = await client.get(CALENDAR, params=CALENDAR_PARAMS, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.asyncio
async def test_deadlines_do_not_leak_other_cases(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    other_lawyer, token = second_lawyer_token
    await _assign(database_session, sample_case, other_lawyer)
    await _add_event(
        database_session,
        sample_case,
        title="Vencimiento propio",
        event_type="vencimiento",
    )
    await _add_event(
        database_session,
        other_case,
        title="Vencimiento ajeno",
        event_type="vencimiento",
    )

    response = await client.get(DEADLINES, headers=_auth(token))

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()}
    assert "Vencimiento propio" in titles
    assert "Vencimiento ajeno" not in titles


@pytest.mark.asyncio
async def test_hearings_do_not_leak_other_cases(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    other_lawyer, token = second_lawyer_token
    await _assign(database_session, sample_case, other_lawyer)
    own_event = await _add_event(
        database_session, sample_case, title="Audiencia propia", event_type="audiencia"
    )
    foreign_event = await _add_event(
        database_session, other_case, title="Audiencia ajena", event_type="audiencia"
    )
    database_session.add_all(
        [
            Hearing(
                event_id=own_event.id,
                case_id=sample_case.id,
                court="Juzgado propio",
                status="programada",
            ),
            Hearing(
                event_id=foreign_event.id,
                case_id=other_case.id,
                court="Juzgado ajeno",
                status="programada",
            ),
        ]
    )
    await database_session.flush()

    response = await client.get(HEARINGS, headers=_auth(token))

    assert response.status_code == 200
    courts = {item["court"] for item in response.json()}
    assert courts == {"Juzgado propio"}


@pytest.mark.asyncio
async def test_client_deadlines_only_include_own_cases(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_client: Client,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """A client linked to one case must not see deadlines of another client."""
    _lawyer, token = second_lawyer_token
    other_client = Client(
        client_type="natural",
        document_type="cedula",
        document_number="99999999",
        full_name="Cliente ajeno",
        is_active=True,
    )
    database_session.add(other_client)
    await database_session.flush()

    mine = Case(
        case_number="WA-2026-000401",
        title="Expediente del cliente",
        client_id=sample_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 4, 1),
        is_active=True,
    )
    theirs = Case(
        case_number="WA-2026-000402",
        title="Expediente de otro cliente",
        client_id=other_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 4, 2),
        is_active=True,
    )
    database_session.add_all([mine, theirs])
    await database_session.flush()

    await _add_event(
        database_session,
        theirs,
        title="Vencimiento de otro cliente",
        event_type="vencimiento",
        visibility="publicada",
    )

    response = await client.get(DEADLINES, headers=_auth(token))

    assert response.status_code == 200
    assert all(item["title"] != "Vencimiento de otro cliente" for item in response.json())


@pytest.mark.asyncio
async def test_scope_filter_is_not_a_cross_product(
    database_session: AsyncSession,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
    second_lawyer_user: tuple[User, str],
) -> None:
    """Directly assert the SQL shape: no cartesian product with `cases`."""
    other_lawyer, _token = second_lawyer_token
    user, _unused = second_lawyer_user
    await _assign(database_session, sample_case, other_lawyer)

    clause = await scope_filter(database_session, user, CaseScope.ASSIGNED)
    assert clause is not None

    statement = select(CalendarEvent.id).where(CalendarEvent.is_active.is_(True), clause)
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert "JOIN cases" not in compiled, "the scope predicate must not cross join `cases`"
    assert "cases.id IN" in compiled
    assert "FROM cases, calendar_events" not in compiled
    assert sample_case.id is not None


@pytest.mark.asyncio
async def test_service_filters_by_scope_clause(
    database_session: AsyncSession,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
    second_lawyer_user: tuple[User, str],
) -> None:
    other_lawyer, _token = second_lawyer_token
    user, _unused = second_lawyer_user
    await _assign(database_session, sample_case, other_lawyer)
    await _add_event(database_session, sample_case, title="Propia")
    await _add_event(database_session, other_case, title="Ajena")

    clause = await scope_filter(database_session, user, CaseScope.ASSIGNED)
    events = await CalendarService(database_session).list_events(
        user,
        scope_clause=clause,
        start=None,
        end=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert [event.title for event in events] == ["Propia"]


@pytest.mark.asyncio
async def test_case_scoped_ignores_a_none_clause() -> None:
    from app.services.cases import case_scoped

    assert case_scoped(CalendarEvent.case_id, None) is None


@pytest.mark.asyncio
async def test_empty_scope_matches_nothing(
    database_session: AsyncSession,
    sample_case: Case,
    second_lawyer_user: tuple[User, str],
) -> None:
    """A lawyer with no assignments must not match any event."""
    user, _token = second_lawyer_user
    await _add_event(database_session, sample_case, title="Ajena")

    clause = await scope_filter(database_session, user, CaseScope.ASSIGNED)
    assert clause is not None

    statement = select(CalendarEvent.id).where(clause)
    result = await database_session.execute(statement)

    assert list(result.scalars().all()) == []

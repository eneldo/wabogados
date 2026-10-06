"""Dashboard tests.

The property under test throughout: **a dashboard figure never exceeds the
detail the same caller could page through.** Every test compares the number
against the rows that back it, and the tests written from an outsider's point of
view are the ones that matter.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.cases import resolve_scope
from app.services.dashboard import DashboardService, dashboard_view_for, month_start

DASHBOARD = "/api/v1/dashboard"
SUMMARY = "/api/v1/dashboard/summary"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _soon(days: float) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


async def _make_action(
    session: AsyncSession,
    case: Case,
    *,
    visibility: str = "interna",
    next_action_at: datetime | None = None,
    occurred_at: datetime | None = None,
) -> Action:
    action = Action(
        case_id=case.id,
        action_type="reunion",
        occurred_at=occurred_at or datetime.now(UTC),
        description="Actuación de prueba",
        visibility=visibility,
        next_action="Preparar escrito" if next_action_at else None,
        next_action_at=next_action_at,
    )
    session.add(action)
    await session.flush()
    return action


async def _make_hearing(
    session: AsyncSession,
    case: Case,
    *,
    starts_in_days: float = 3,
    visibility: str = "interna",
    status: str = "programada",
) -> Hearing:
    starts_at = _soon(starts_in_days)
    event = CalendarEvent(
        case_id=case.id,
        event_type="audiencia",
        title="Audiencia de prueba",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
        visibility=visibility,
        status="programado",
    )
    session.add(event)
    await session.flush()
    hearing = Hearing(
        event_id=event.id,
        case_id=case.id,
        procedural_stage="prueba",
        attendance="pendiente",
        status=status,
        updated_at=datetime.now(UTC),
    )
    session.add(hearing)
    await session.flush()
    return hearing


async def _make_document(
    session: AsyncSession, case: Case, *, visibility: str = "interna"
) -> Document:
    document = Document(
        case_id=case.id,
        document_type="escrito",
        title="Documento de prueba",
        status="vigente",
        confidentiality="interno",
        visibility=visibility,
    )
    session.add(document)
    await session.flush()
    return document


async def _make_evidence(
    session: AsyncSession, case: Case, *, visibility: str = "interna"
) -> Evidence:
    evidence = Evidence(
        case_id=case.id,
        title="Evidencia de prueba",
        evidence_type="documental",
        status="recibida",
        visibility=visibility,
        confidentiality="interno",
    )
    session.add(evidence)
    await session.flush()
    return evidence


# -- view selection -------------------------------------------------------


@pytest.mark.asyncio
async def test_view_follows_the_scope_not_the_name(
    database_session: AsyncSession,
    admin_user: User,
    staff_user: User,
    portal_user: tuple[User, Client],
) -> None:
    portal_identity, _client = portal_user

    admin_scope = await resolve_scope(database_session, admin_user)
    staff_scope = await resolve_scope(database_session, staff_user)
    client_scope = await resolve_scope(database_session, portal_identity)

    assert dashboard_view_for(admin_user, admin_scope) == "administrador"
    assert dashboard_view_for(staff_user, staff_scope) == "abogado"
    assert dashboard_view_for(portal_identity, client_scope) == "cliente"


# -- administrator --------------------------------------------------------


@pytest.mark.asyncio
async def test_administrator_sees_every_case(
    database_session: AsyncSession,
    admin_user: User,
    sample_case: Case,
    other_case: Case,
) -> None:
    service = DashboardService(database_session, admin_user)
    await service.prepare()

    listed = await service.my_cases(limit=50)

    assert {case.id for case in listed} == {sample_case.id, other_case.id}
    assert await service.active_cases() == 2


@pytest.mark.asyncio
async def test_administrator_counts_hearings_deadlines_and_documents(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    service = DashboardService(database_session, admin_user)
    await service.prepare()

    await _make_hearing(database_session, sample_case, starts_in_days=2)
    await _make_action(
        database_session,
        sample_case,
        next_action_at=_soon(5),
        occurred_at=datetime.now(UTC),
    )
    await _make_document(database_session, sample_case)

    assert await service.upcoming_hearings() == 1
    assert await service.pending_actions() == 1
    assert await service.recent_documents() == 1


@pytest.mark.asyncio
async def test_closed_cases_are_counted_apart(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    sample_case.status = "cerrado"
    sample_case.closed_at = datetime.now(UTC).date()
    await database_session.flush()

    service = DashboardService(database_session, admin_user)
    await service.prepare()

    assert await service.active_cases() == 0
    assert await service.closed_cases() == 1


@pytest.mark.asyncio
async def test_actions_of_last_month_are_not_counted(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    last_month = month_start(datetime.now(UTC)) - timedelta(days=1)
    await _make_action(database_session, sample_case, occurred_at=last_month)

    service = DashboardService(database_session, admin_user)
    await service.prepare()

    assert await service.actions_this_month() == 0


@pytest.mark.asyncio
async def test_overdue_deadlines_are_separate_from_upcoming(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    for days, title in ((-5, "Vencido"), (10, "Por llegar")):
        starts_at = _soon(days)
        database_session.add(
            CalendarEvent(
                case_id=sample_case.id,
                event_type="vencimiento",
                title=title,
                starts_at=starts_at,
                ends_at=starts_at,
                visibility="interna",
                status="programado",
            )
        )
    await database_session.flush()

    service = DashboardService(database_session, admin_user)
    await service.prepare()

    assert await service.overdue_deadlines() == 1
    assert await service.open_deadlines() == 1
    deadlines = await service.deadlines_list()
    assert [item.title for item in deadlines] == ["Vencido", "Por llegar"]
    assert [item.is_overdue for item in deadlines] == [True, False]


@pytest.mark.asyncio
async def test_cancelled_hearings_are_not_upcoming(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    await _make_hearing(database_session, sample_case, status="cancelada")

    service = DashboardService(database_session, admin_user)
    await service.prepare()

    assert await service.upcoming_hearings() == 0


# -- lawyer: the isolation that matters ----------------------------------


@pytest.mark.asyncio
async def test_lawyer_dashboard_excludes_unassigned_cases(
    database_session: AsyncSession,
    staff_user: User,
    sample_lawyer: Lawyer,
    sample_case: Case,
    other_case: Case,
) -> None:
    """`other_case` has no lawyer. Its figures must not appear anywhere."""
    sample_lawyer.user_id = staff_user.id
    await database_session.flush()

    await _make_action(database_session, sample_case, next_action_at=_soon(2))
    await _make_action(database_session, other_case, next_action_at=_soon(2))
    await _make_hearing(database_session, sample_case)
    await _make_hearing(database_session, other_case)

    service = DashboardService(database_session, staff_user)
    await service.prepare()

    assert {case.id for case in await service.my_cases()} == {sample_case.id}
    assert await service.active_cases() == 1
    assert await service.pending_actions() == 1
    assert await service.upcoming_hearings() == 1


@pytest.mark.asyncio
async def test_lawyer_dashboard_excludes_collaborators_only_cases(
    database_session: AsyncSession,
    staff_user: User,
    sample_lawyer: Lawyer,
    other_case: Case,
) -> None:
    """Being a collaborator is enough; being the responsible lawyer is not required."""
    sample_lawyer.user_id = staff_user.id
    await database_session.flush()
    database_session.add(
        CaseLawyer(
            case_id=other_case.id, lawyer_id=sample_lawyer.id, role="colaborador"
        )
    )
    await database_session.flush()

    service = DashboardService(database_session, staff_user)
    await service.prepare()

    assert await service.active_cases() == 1


@pytest.mark.asyncio
async def test_lawyer_without_assignments_sees_nothing(
    database_session: AsyncSession,
    second_lawyer_token: tuple[Lawyer, str],
    sample_case: Case,
) -> None:
    lawyer, _token = second_lawyer_token
    user = await database_session.get(User, lawyer.user_id)
    assert user is not None

    await _make_action(database_session, sample_case, next_action_at=_soon(1))
    await _make_hearing(database_session, sample_case)

    service = DashboardService(database_session, user)
    await service.prepare()

    assert await service.active_cases() == 0
    assert await service.my_cases() == []
    assert await service.pending_actions() == 0
    assert await service.upcoming_hearings() == 0


@pytest.mark.asyncio
async def test_active_clients_follow_the_case_scope(
    database_session: AsyncSession, staff_user: User, sample_client: Client
) -> None:
    """`sample_client` owns a case the lawyer does not, so it is not counted."""
    service = DashboardService(database_session, staff_user)
    await service.prepare()

    assert await service.active_clients() == 0


# -- client portal --------------------------------------------------------


@pytest.mark.asyncio
async def test_client_dashboard_only_counts_published_content(
    database_session: AsyncSession,
    portal_user: tuple[User, Client],
    portal_case: Case,
) -> None:
    portal_identity, _client = portal_user
    await _make_document(database_session, portal_case, visibility="interna")
    await _make_document(database_session, portal_case, visibility="publicada")
    await _make_evidence(database_session, portal_case, visibility="interna")
    await _make_evidence(database_session, portal_case, visibility="publicada")
    await _make_action(database_session, portal_case, visibility="interna")
    await _make_action(database_session, portal_case, visibility="publicada")

    service = DashboardService(database_session, portal_identity)
    await service.prepare()

    assert await service.recent_documents() == 1
    assert await service.evidences() == 1
    assert await service.actions_this_month() == 1
    assert len(await service.published_documents()) == 1
    assert len(await service.visible_evidences()) == 1


@pytest.mark.asyncio
async def test_client_dashboard_sees_only_its_own_cases(
    database_session: AsyncSession,
    portal_user: tuple[User, Client],
    portal_case: Case,
    other_case: Case,
) -> None:
    portal_identity, _client = portal_user
    await _make_action(database_session, other_case, visibility="publicada")
    await _make_action(database_session, portal_case, visibility="publicada")

    service = DashboardService(database_session, portal_identity)
    await service.prepare()

    assert {case.id for case in await service.my_cases()} == {portal_case.id}
    assert await service.actions_this_month() == 1


@pytest.mark.asyncio
async def test_client_sees_no_internal_hearings(
    database_session: AsyncSession,
    portal_user: tuple[User, Client],
    portal_case: Case,
) -> None:
    portal_identity, _client = portal_user
    await _make_hearing(database_session, portal_case, visibility="interna")
    await _make_hearing(database_session, portal_case, visibility="publicada")

    service = DashboardService(database_session, portal_identity)
    await service.prepare()

    assert await service.upcoming_hearings() == 1
    assert len(await service.upcoming_hearings_list()) == 1


@pytest.mark.asyncio
async def test_client_without_cases_gets_empty_figures(
    database_session: AsyncSession,
    portal_user: tuple[User, Client],
    sample_case: Case,
) -> None:
    portal_identity, _client = portal_user
    await _make_action(database_session, sample_case)

    service = DashboardService(database_session, portal_identity)
    await service.prepare()

    kpis = await service.kpis()
    assert kpis["active_cases"] == 0
    assert kpis["active_clients"] == 0
    assert kpis["actions_this_month"] == 0


# -- numbers never exceed the detail -------------------------------------


@pytest.mark.asyncio
async def test_kpi_count_never_exceeds_the_visible_rows(
    database_session: AsyncSession,
    staff_user: User,
    sample_lawyer: Lawyer,
    sample_case: Case,
    other_case: Case,
) -> None:
    sample_lawyer.user_id = staff_user.id
    await database_session.flush()

    for case, internal in ((sample_case, 2), (other_case, 3)):
        for _index in range(internal):
            await _make_action(database_session, case, visibility="interna")
    for _index in range(4):
        await _make_action(database_session, other_case, visibility="publicada")

    service = DashboardService(database_session, staff_user)
    await service.prepare()

    visible_rows = (
        await database_session.execute(
            select(func.count())
            .select_from(Action)
            .where(Action.case_id == sample_case.id, Action.visibility == "interna")
        )
    ).scalar_one()
    listed = await service.recent_actions(limit=100)

    assert await service.actions_this_month() == visible_rows
    assert len(listed) == visible_rows


# -- unread counters ------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_reports_pending_messages(
    database_session: AsyncSession, admin_user: User, staff_user: User, sample_case: Case
) -> None:
    from app.services.messaging import MessagingService

    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Pendiente",
        case_id=sample_case.id,
        participant_ids=[staff_user.id],
    )
    await service.send_message(conversation, admin_user, "Revísalo")

    dashboard = DashboardService(database_session, staff_user)
    await dashboard.prepare()

    assert await dashboard.pending_messages() == 1
    assert (await dashboard.summary())["pending_messages"] == 1


@pytest.mark.asyncio
async def test_a_count_is_not_a_cartesian_product(
    database_session: AsyncSession, admin_user: User, sample_case: Case, other_case: Case
) -> None:
    """Regression: filtering outside the subquery multiplies the count.

    Counting two cases used to return four as soon as a second row existed
    anywhere in the table, because the outer filter made SQLAlchemy join the
    source table back into the query.
    """
    await _make_action(database_session, sample_case)

    service = DashboardService(database_session, admin_user)
    await service.prepare()

    assert await service.active_cases() == 2
    assert await service.actions_this_month() == 1
    assert (await service.kpis())["active_cases"] == 2


# -- API ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_dashboard_for_administrator(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.get(DASHBOARD, headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["view"] == "administrador"
    assert payload["kpis"]["active_cases"] >= 1
    assert payload["cases"][0]["case_number"] == sample_case.case_number
    assert payload["cases"][0]["client_name"]


@pytest.mark.asyncio
async def test_api_dashboard_for_client(
    client: AsyncClient, portal_token: str, portal_case: Case, other_case: Case
) -> None:
    response = await client.get(DASHBOARD, headers=_auth(portal_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["view"] == "cliente"
    assert [item["case_number"] for item in payload["cases"]] == [portal_case.case_number]
    assert other_case.case_number not in {
        item["case_number"] for item in payload["cases"]
    }


@pytest.mark.asyncio
async def test_api_summary_only_carries_the_badge_counters(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(SUMMARY, headers=_auth(admin_token))

    assert response.status_code == 200
    assert set(response.json()) == {"pending_messages", "unread_notifications"}


@pytest.mark.asyncio
async def test_api_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(DASHBOARD)).status_code == 401
    assert (await client.get(SUMMARY)).status_code == 401


@pytest.mark.asyncio
async def test_api_limit_is_bounded(client: AsyncClient, admin_token: str) -> None:
    over_limit = await client.get(
        DASHBOARD, params={"limit": 0}, headers=_auth(admin_token)
    )
    bad_days = await client.get(
        DASHBOARD, params={"days": 0}, headers=_auth(admin_token)
    )

    assert over_limit.status_code == 422
    assert bad_days.status_code == 422


@pytest.mark.asyncio
async def test_api_lawyer_without_assignments_sees_nothing(
    client: AsyncClient,
    database_session: AsyncSession,
    staff_token: str,
    sample_case: Case,
) -> None:
    """The API must not widen what the service already refuses."""
    await _make_action(database_session, sample_case, next_action_at=_soon(1))

    response = await client.get(DASHBOARD, headers=_auth(staff_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["view"] == "abogado"
    assert payload["cases"] == []
    assert payload["kpis"]["active_cases"] == 0


def test_month_start_is_the_first_instant_of_the_month() -> None:
    reference = datetime(2026, 3, 17, 14, 30, tzinfo=UTC)

    assert month_start(reference) == datetime(2026, 3, 1, tzinfo=UTC)
    assert month_start(reference).tzinfo is UTC
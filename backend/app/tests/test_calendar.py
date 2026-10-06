from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

from app.models import Case, Lawyer, User
from app.services.calendar import view_range

CALENDAR = "/api/v1/calendar"
HEARINGS = "/api/v1/hearings"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _inside_this_week(offset_days: int = 2) -> datetime:
    """A datetime that is inside the current week whatever day the suite runs on.

    `now + 1 day` is not good enough, and the suite proved it: the week view spans
    Monday 00:00 UTC to the following Monday, so on a Saturday or a Sunday
    "tomorrow" lands in the *next* week and the event stops being listed. Four
    calendar tests failed that way on a Saturday evening without a line of
    application code having changed.

    Counting from the Monday keeps every run inside the window, and the offset is
    counted in days so a caller asking for a hearing three days out still gets a
    distinct instant from the default.
    """
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    inside = monday + timedelta(days=offset_days)
    return datetime.combine(inside, datetime.min.time(), tzinfo=UTC) + timedelta(hours=12)


def _ahead_of_now(days: int) -> datetime:
    """A datetime in the future, for endpoints whose window starts at *now*.

    The case 360 record asks for the agenda from the current instant forward, so an
    event inside the current week is behind us on a Saturday and would not be
    counted. This is the companion to `_inside_this_week`: same reasoning, opposite
    requirement.
    """
    return datetime.now(UTC) + timedelta(days=days)


def _event(case_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "event_type": "reunion",
        "title": "Reunion de equipo",
        "starts_at": _inside_this_week().isoformat(),
    }
    payload.update(overrides)
    return payload


def _hearing(case_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "title": "Audiencia de prueba",
        "starts_at": _inside_this_week(offset_days=3).isoformat(),
        "procedural_stage": "primera_instancia",
    }
    payload.update(overrides)
    return payload


def test_view_range_covers_expected_windows() -> None:
    reference = date(2026, 5, 20)  # a Wednesday

    day_start, day_end = view_range("day", reference)
    week_start, week_end = view_range("week", reference)
    month_start, month_end = view_range("month", reference)
    lawyer_start, lawyer_end = view_range("lawyer", reference)

    assert day_start.day == 20 and (day_end - day_start).days == 1
    assert week_start.weekday() == 0 and (week_end - week_start).days == 7
    assert week_start.day == 18
    assert month_start.day == 1 and (month_end - month_start).days == 31
    assert (lawyer_end - lawyer_start).days == 30


async def test_create_event_defaults_to_one_hour(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        CALENDAR, json=_event(str(sample_case.id)), headers=_auth(admin_token)
    )

    assert response.status_code == 201
    payload = response.json()
    starts = datetime.fromisoformat(payload["starts_at"])
    ends = datetime.fromisoformat(payload["ends_at"])
    assert (ends - starts).seconds == 3600
    assert payload["case_number"] == sample_case.case_number


async def test_all_day_event_defaults_to_one_day(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        CALENDAR, json=_event(str(sample_case.id), all_day=True), headers=_auth(admin_token)
    )

    assert response.status_code == 201
    payload = response.json()
    starts = datetime.fromisoformat(payload["starts_at"])
    ends = datetime.fromisoformat(payload["ends_at"])
    assert (ends - starts).days == 1


async def test_create_event_rejects_inverted_dates(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    starts = datetime.now(UTC) + timedelta(days=2)
    response = await client.post(
        CALENDAR,
        json=_event(
            str(sample_case.id),
            starts_at=starts.isoformat(),
            ends_at=(starts - timedelta(hours=1)).isoformat(),
        ),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_generic_calendar_endpoint_rejects_hearing_type(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        CALENDAR,
        json=_event(str(sample_case.id), event_type="audiencia"),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_create_event_outside_case_scope_is_hidden(
    client: AsyncClient, other_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token
    response = await client.post(
        CALENDAR, json=_event(str(other_case.id)), headers=_auth(token)
    )

    assert response.status_code == 404


async def test_calendar_week_view_lists_events(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        CALENDAR, json=_event(str(sample_case.id)), headers=_auth(admin_token)
    )

    response = await client.get(CALENDAR, headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["view"] == "week"
    assert payload["total"] == 1
    assert payload["events"][0]["case_id"] == str(sample_case.id)


async def test_calendar_filters_by_lawyer_and_case(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    await client.post(
        CALENDAR,
        json=_event(str(sample_case.id), lawyer_id=str(sample_lawyer.id)),
        headers=_auth(admin_token),
    )
    await client.post(
        CALENDAR, json=_event(str(sample_case.id)), headers=_auth(admin_token)
    )

    by_lawyer = await client.get(
        CALENDAR, params={"lawyer_id": str(sample_lawyer.id)}, headers=_auth(admin_token)
    )
    by_case = await client.get(
        CALENDAR, params={"case_id": str(sample_case.id)}, headers=_auth(admin_token)
    )
    by_type = await client.get(
        CALENDAR, params={"event_type": "audiencia"}, headers=_auth(admin_token)
    )

    assert by_lawyer.json()["total"] == 1
    assert by_lawyer.json()["events"][0]["lawyer_name"] == sample_lawyer.full_name
    assert by_case.json()["total"] == 2
    assert by_type.json()["total"] == 0


async def test_client_sees_only_published_events(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, object],
    portal_token: str,
    database_session: object,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import Client as ClientModel

    session: AsyncSession = database_session  # type: ignore[assignment]
    _user, portal_client = portal_user
    case = Case(
        case_number="WA-2026-000200",
        title="Expediente con agenda",
        client_id=portal_client.id,  # type: ignore[attr-defined]
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 4, 1),
        is_active=True,
    )
    session.add(case)
    await session.flush()

    for visibility in ("publicada", "interna"):
        await client.post(
            CALENDAR,
            json=_event(str(case.id), visibility=visibility, title=f"Evento {visibility}"),
            headers=_auth(admin_token),
        )

    staff_view = await client.get(CALENDAR, headers=_auth(admin_token))
    client_view = await client.get(CALENDAR, headers=_auth(portal_token))

    assert staff_view.json()["total"] == 2
    assert client_view.json()["total"] == 1
    assert client_view.json()["events"][0]["title"] == "Evento publicada"
    assert isinstance(portal_client, ClientModel)


async def test_update_event_status(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        CALENDAR, json=_event(str(sample_case.id)), headers=_auth(admin_token)
    )

    response = await client.patch(
        f"{CALENDAR}/{created.json()['id']}",
        json={"status": "cancelada", "title": "Reunion cancelada"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelada"
    assert response.json()["title"] == "Reunion cancelada"


async def test_hearing_event_cannot_be_updated_through_calendar(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )

    response = await client.patch(
        f"{CALENDAR}/{created.json()['event_id']}",
        json={"status": "cancelada"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "audiencia" in response.json()["error"]["message"].lower()


async def test_create_hearing(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        HEARINGS,
        json=_hearing(
            str(sample_case.id),
            lawyer_id=str(sample_lawyer.id),
            court="Juzgado Civil",
            courtroom="Sala 3",
            judge="Dr. Perez",
        ),
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["procedural_stage"] == "primera_instancia"
    assert payload["attendance"] == "pendiente"
    assert payload["status"] == "programada"
    assert payload["case_number"] == sample_case.case_number
    assert payload["court"] == "Juzgado Civil"


async def test_create_hearing_rejects_inactive_lawyer(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    sample_lawyer: Lawyer,
    database_session: object,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = database_session  # type: ignore[assignment]
    sample_lawyer.is_active = False
    await session.flush()

    response = await client.post(
        HEARINGS,
        json=_hearing(str(sample_case.id), lawyer_id=str(sample_lawyer.id)),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "inactivo" in response.json()["error"]["message"]


async def test_hearing_conflict_is_rejected(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    starts = datetime.now(UTC) + timedelta(days=4)
    await client.post(
        HEARINGS,
        json=_hearing(
            str(sample_case.id), lawyer_id=str(sample_lawyer.id), starts_at=starts.isoformat()
        ),
        headers=_auth(admin_token),
    )

    response = await client.post(
        HEARINGS,
        json=_hearing(
            str(sample_case.id),
            lawyer_id=str(sample_lawyer.id),
            starts_at=(starts + timedelta(minutes=30)).isoformat(),
        ),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "franja" in response.json()["error"]["message"]


async def test_realize_hearing_requires_result(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )

    rejected = await client.patch(
        f"{HEARINGS}/{created.json()['id']}",
        json={"status": "realizada"},
        headers=_auth(admin_token),
    )
    accepted = await client.patch(
        f"{HEARINGS}/{created.json()['id']}",
        json={"status": "realizada", "result": "Se admitio la demanda"},
        headers=_auth(admin_token),
    )

    assert rejected.status_code == 409
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "realizada"
    assert accepted.json()["result"] == "Se admitio la demanda"


async def test_reschedule_hearing_requires_permission(
    client: AsyncClient, admin_token: str, staff_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )
    new_date = (datetime.now(UTC) + timedelta(days=9)).isoformat()

    response = await client.post(
        f"{HEARINGS}/{created.json()['id']}/reschedule",
        json={"starts_at": new_date, "reason": "El juez notifico el aplazamiento"},
        headers=_auth(staff_token),
    )

    assert response.status_code == 403


async def test_reschedule_hearing_records_trace(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )
    new_date = (datetime.now(UTC) + timedelta(days=12)).isoformat()

    response = await client.post(
        f"{HEARINGS}/{created.json()['id']}/reschedule",
        json={"starts_at": new_date, "reason": "Aplazamiento dispuesto por el juez"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "aplazada"
    assert payload["rescheduled_from_id"] == created.json()["id"]
    assert datetime.fromisoformat(payload["starts_at"]).date() == datetime.fromisoformat(
        new_date
    ).date()


async def test_realized_hearing_cannot_be_rescheduled(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )
    await client.patch(
        f"{HEARINGS}/{created.json()['id']}",
        json={"status": "realizada", "result": "Concluida"},
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{HEARINGS}/{created.json()['id']}/reschedule",
        json={
            "starts_at": (datetime.now(UTC) + timedelta(days=20)).isoformat(),
            "reason": "Intento de reprogramacion",
        },
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_list_hearings_filtered_by_status(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        HEARINGS, json=_hearing(str(sample_case.id)), headers=_auth(admin_token)
    )
    await client.patch(
        f"{HEARINGS}/{created.json()['id']}",
        json={"status": "realizada", "result": "OK"},
        headers=_auth(admin_token),
    )

    scheduled = await client.get(HEARINGS, headers=_auth(admin_token))
    realized = await client.get(
        HEARINGS, params={"status": "realizada"}, headers=_auth(admin_token)
    )

    assert scheduled.json()[0]["status"] == "realizada"
    assert realized.json() != []


async def test_deadlines_merge_events_and_actions(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    soon = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    await client.post(
        CALENDAR,
        json=_event(
            str(sample_case.id),
            event_type="vencimiento",
            title="Vencimiento de contestacion",
            starts_at=past,
        ),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json={
            "case_id": str(sample_case.id),
            "action_type": "seguimiento",
            "occurred_at": datetime.now(UTC).isoformat(),
            "description": "Revision pendiente",
            "next_action": "Presentar descargo",
            "next_action_at": soon,
        },
        headers=_auth(admin_token),
    )

    response = await client.get(f"{CALENDAR}/deadlines", headers=_auth(admin_token))

    assert response.status_code == 200
    items = response.json()
    sources = {item["source"] for item in items}
    assert sources == {"evento", "actuacion"}
    assert items[0]["overdue"] is True
    assert items[0]["source_label"] == "Vencimiento"


async def test_deadlines_include_overdue_actions(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    overdue = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json={
            "case_id": str(sample_case.id),
            "action_type": "seguimiento",
            "occurred_at": datetime.now(UTC).isoformat(),
            "description": "Actuacion vencida",
            "next_action": "Presentar el descargo",
            "next_action_at": overdue,
        },
        headers=_auth(admin_token),
    )

    response = await client.get(f"{CALENDAR}/deadlines", headers=_auth(admin_token))

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["source"] == "actuacion"
    assert items[0]["overdue"] is True
    assert items[0]["case_number"] == sample_case.case_number


async def test_deadlines_exclude_far_future(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        CALENDAR,
        json=_event(
            str(sample_case.id),
            event_type="vencimiento",
            title="Vencimiento lejano",
            starts_at=(datetime.now(UTC) + timedelta(days=120)).isoformat(),
        ),
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{CALENDAR}/deadlines", params={"days": 30}, headers=_auth(admin_token)
    )

    assert response.json() == []


async def test_hearing_hidden_from_unassigned_lawyer(
    client: AsyncClient, sample_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token
    response = await client.get(HEARINGS, headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == []


async def test_client_without_hearing_permission_cannot_list_hearings(
    client: AsyncClient, portal_token: str
) -> None:
    response = await client.get(HEARINGS, headers=_auth(portal_token))

    assert response.status_code == 403


async def test_case_360_includes_agenda_and_hearings(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        CALENDAR,
        json=_event(
            str(sample_case.id),
            starts_at=_ahead_of_now(3).isoformat(),
        ),
        headers=_auth(admin_token),
    )
    await client.post(
        HEARINGS,
        json=_hearing(
            str(sample_case.id),
            starts_at=_ahead_of_now(2).isoformat(),
        ),
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/360", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    # The meeting plus the hearing, which is also a calendar event.
    assert payload["agenda"]["available"] is True
    assert payload["agenda_total"] == 2
    assert payload["audiencias"]["available"] is True
    assert payload["audiencias_total"] == 1
    assert payload["documentos"]["available"] is True
    assert payload["evidencias"]["available"] is True
    assert payload["evidencias_total"] == 0


async def test_anonymous_cannot_read_calendar(client: AsyncClient) -> None:
    assert (await client.get(CALENDAR)).status_code == 401
    assert (await client.get(HEARINGS)).status_code == 401


async def test_unknown_hearing_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.patch(
        f"{HEARINGS}/{uuid4()}", json={"court": "X"}, headers=_auth(admin_token)
    )

    assert response.status_code == 404

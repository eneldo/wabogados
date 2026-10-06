from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Action, Case, Client, Lawyer, User
from app.services.actions import visible_visibilities

ACTIONS = "/api/v1/actions"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(case_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "action_type": "reunion",
        "occurred_at": datetime.now(UTC).isoformat(),
        "description": "Reunion de seguimiento con el cliente",
        "visibility": "interna",
    }
    payload.update(overrides)
    return payload


async def test_create_action(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(
            str(sample_case.id), responsible_lawyer_id=str(sample_lawyer.id)
        ),
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["case_number"] == sample_case.case_number
    assert payload["responsible_lawyer_name"] == sample_lawyer.full_name
    assert payload["visibility"] == "interna"
    assert payload["case_id"] == str(sample_case.id)


async def test_create_action_rejects_unknown_case(
    client: AsyncClient, admin_token: str
) -> None:
    orphan = uuid4()
    response = await client.post(
        f"/api/v1/cases/{orphan}/actions",
        json=_payload(str(orphan)),
        headers=_auth(admin_token),
    )

    assert response.status_code == 404


async def test_create_action_requires_matching_body(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(uuid4())),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_next_action_requires_description(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id), next_action_at=datetime.now(UTC).isoformat()),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_lawyer_cannot_create_action_outside_scope(
    client: AsyncClient, other_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.post(
        f"/api/v1/cases/{other_case.id}/actions",
        json=_payload(str(other_case.id)),
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_client_role_cannot_create_action(
    client: AsyncClient, plain_user_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(plain_user_token),
    )

    assert response.status_code == 403


async def test_timeline_is_chronological(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    now = datetime.now(UTC)
    entries = ((3, "Primera actuación"), (1, "Segunda actuación"), (2, "Tercera actuación"))
    for offset, description in entries:
        await client.post(
            f"/api/v1/cases/{sample_case.id}/actions",
            json=_payload(
                str(sample_case.id),
                occurred_at=(now - timedelta(days=offset)).isoformat(),
                description=description,
            ),
            headers=_auth(admin_token),
        )

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/timeline", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["case_number"] == sample_case.case_number
    descriptions = [entry["action"]["description"] for entry in payload["entries"]]
    assert descriptions == ["Segunda actuación", "Tercera actuación", "Primera actuación"]
    assert payload["entries"][0]["case_status"] == sample_case.status
    assert payload["entries"][0]["is_pending"] is False


async def test_timeline_hidden_from_unassigned_lawyer(
    client: AsyncClient, sample_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/timeline", headers=_auth(token)
    )

    assert response.status_code == 404


async def test_client_only_sees_published_actions(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    portal_token: str,
    database_session: AsyncSession,
) -> None:
    _portal, portal_client = portal_user
    case = Case(
        case_number="WA-2026-000100",
        title="Expediente del cliente",
        client_id=portal_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 3, 1),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()

    await client.post(
        f"/api/v1/cases/{case.id}/actions",
        json=_payload(
            str(case.id), visibility="publicada", description="Actuacion publicada"
        ),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{case.id}/actions",
        json=_payload(
            str(case.id), visibility="interna", description="Actuacion interna"
        ),
        headers=_auth(admin_token),
    )

    staff_view = await client.get(ACTIONS, headers=_auth(admin_token))
    client_view = await client.get(ACTIONS, headers=_auth(portal_token))

    assert staff_view.status_code == 200
    assert len(staff_view.json()) == 2
    assert client_view.status_code == 200
    descriptions = {item["description"] for item in client_view.json()}
    assert descriptions == {"Actuacion publicada"}


async def test_client_does_not_see_other_clients_cases(
    client: AsyncClient, sample_case: Case, portal_token: str
) -> None:
    response = await client.get(ACTIONS, headers=_auth(portal_token))
    other = await client.get(f"/api/v1/cases/{sample_case.id}", headers=_auth(portal_token))

    assert response.json() == []
    assert other.status_code == 404


async def test_client_cannot_force_internal_visibility(
    client: AsyncClient, portal_token: str
) -> None:
    """A published-only reader cannot widen the filter to internal actions."""
    response = await client.get(
        ACTIONS, params={"visibility": "interna"}, headers=_auth(portal_token)
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_update_action_records_history(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(admin_token),
    )
    action_id = created.json()["id"]

    updated = await client.patch(
        f"{ACTIONS}/{action_id}",
        json={"result": "Acuerdo alcanzado", "visibility": "publicada"},
        headers=_auth(admin_token),
    )
    history = await client.get(f"{ACTIONS}/{action_id}/history", headers=_auth(admin_token))

    assert updated.status_code == 200
    assert updated.json()["result"] == "Acuerdo alcanzado"
    assert updated.json()["visibility"] == "publicada"
    fields = {entry["field_name"] for entry in history.json()}
    assert {"result", "visibility"} <= fields


async def test_update_action_rejects_orphan_next_date(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(admin_token),
    )

    response = await client.patch(
        f"{ACTIONS}/{created.json()['id']}",
        json={"next_action_at": datetime.now(UTC).isoformat()},
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_pending_actions_are_listed(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    due = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(
            str(sample_case.id),
            next_action="Presentar contestacion",
            next_action_at=due,
        ),
        headers=_auth(admin_token),
    )

    pending = await client.get(f"{ACTIONS}/pending", headers=_auth(admin_token))
    filtered = await client.get(
        ACTIONS, params={"pending_only": "true"}, headers=_auth(admin_token)
    )

    assert pending.status_code == 200
    assert len(pending.json()) == 1
    assert pending.json()[0]["case_number"] == sample_case.case_number
    assert pending.json()[0]["overdue"] is True
    assert len(filtered.json()) == 1


async def test_future_next_action_is_not_pending(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(
            str(sample_case.id),
            next_action="Revision de prueba",
            next_action_at=future,
        ),
        headers=_auth(admin_token),
    )

    pending = await client.get(f"{ACTIONS}/pending", headers=_auth(admin_token))

    assert pending.json() == []


async def test_actions_filtered_by_case_and_type(
    client: AsyncClient, admin_token: str, sample_case: Case, other_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{other_case.id}/actions",
        json=_payload(str(other_case.id), action_type="llamada"),
        headers=_auth(admin_token),
    )

    timeline = await client.get(
        f"/api/v1/cases/{other_case.id}/timeline", headers=_auth(admin_token)
    )
    by_type = await client.get(
        ACTIONS, params={"action_type": "llamada"}, headers=_auth(admin_token)
    )

    assert timeline.json()["total"] == 1
    assert by_type.json()[0]["action_type"] == "llamada"


async def test_get_action_hides_internal_from_client(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    portal_token: str,
    database_session: AsyncSession,
) -> None:
    _portal, portal_client = portal_user
    case = Case(
        case_number="WA-2026-000101",
        title="Expediente con actuación interna",
        client_id=portal_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 3, 2),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()
    created = await client.post(
        f"/api/v1/cases/{case.id}/actions",
        json=_payload(str(case.id), visibility="interna"),
        headers=_auth(admin_token),
    )
    action_id = created.json()["id"]

    staff_view = await client.get(f"{ACTIONS}/{action_id}", headers=_auth(admin_token))
    client_view = await client.get(f"{ACTIONS}/{action_id}", headers=_auth(portal_token))

    assert staff_view.status_code == 200
    assert client_view.status_code == 404


async def test_unknown_action_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{ACTIONS}/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_anonymous_cannot_list_actions(client: AsyncClient) -> None:
    response = await client.get(ACTIONS)

    assert response.status_code == 401


async def test_case_360_includes_actions(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(admin_token),
    )

    response = await client.get(f"/api/v1/cases/{sample_case.id}/360", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["actuaciones"]["available"] is True
    assert payload["actuaciones_total"] == 1
    assert payload["evidencias"]["available"] is True
    assert payload["evidencias_total"] == 0


async def test_visibility_matrix_by_role(
    admin_user: object, staff_user: object, plain_user: object
) -> None:
    assert set(visible_visibilities(admin_user)) == {  # type: ignore[arg-type]
        "interna",
        "equipo",
        "publicada",
    }
    assert set(visible_visibilities(staff_user)) == {  # type: ignore[arg-type]
        "interna",
        "equipo",
        "publicada",
    }
    assert visible_visibilities(plain_user) == ("publicada",)  # type: ignore[arg-type]


async def test_soft_deleted_actions_are_hidden(
    client: AsyncClient, database_session: AsyncSession, admin_token: str, sample_case: Case
) -> None:
    from sqlalchemy import select

    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/actions",
        json=_payload(str(sample_case.id)),
        headers=_auth(admin_token),
    )
    action = (
        await database_session.execute(
            select(Action).where(Action.id == created.json()["id"])
        )
    ).scalar_one()
    action.is_active = False
    await database_session.flush()

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/timeline", headers=_auth(admin_token)
    )

    assert response.json()["total"] == 0

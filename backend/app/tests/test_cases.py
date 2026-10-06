from datetime import date
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseLawyer, Client, Lawyer

CASES = "/api/v1/cases"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(client_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Cobranza de deuda civil",
        "client_id": client_id,
        "process_type": "civil",
        "description": "Resumen del caso",
        "amount": "15000.50",
    }
    payload.update(overrides)
    return payload


async def test_create_case_assigns_sequential_number(
    client: AsyncClient, admin_token: str, sample_client: Client, sample_lawyer: Lawyer
) -> None:
    first = await client.post(
        CASES, json=_payload(str(sample_client.id)), headers=_auth(admin_token)
    )
    second = await client.post(
        CASES,
        json=_payload(str(sample_client.id), title="Segundo asunto"),
        headers=_auth(admin_token),
    )

    assert first.status_code == 201
    assert first.json()["case_number"] == "WA-2026-000001"
    assert first.json()["client_name"] == sample_client.display_name
    assert first.json()["status"] == "abierto"
    assert second.json()["case_number"] == "WA-2026-000002"


async def test_create_case_with_responsible_lawyer(
    client: AsyncClient, admin_token: str, sample_client: Client, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        CASES,
        json=_payload(
            str(sample_client.id), responsible_lawyer_id=str(sample_lawyer.id)
        ),
        headers=_auth(admin_token),
    )
    collaborators = await client.get(
        f"{CASES}/{response.json()['id']}/parties", headers=_auth(admin_token)
    )

    assert response.status_code == 201
    assert response.json()["responsible_lawyer_name"] == sample_lawyer.full_name
    assert collaborators.status_code == 200


async def test_create_case_rejects_inactive_client(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    sample_client.is_active = False

    response = await client.post(
        CASES, json=_payload(str(sample_client.id)), headers=_auth(admin_token)
    )

    assert response.status_code == 409
    assert "cliente" in response.json()["error"]["message"]


async def test_create_case_requires_permission(
    client: AsyncClient, plain_user_token: str, sample_client: Client
) -> None:
    response = await client.post(
        CASES, json=_payload(str(sample_client.id)), headers=_auth(plain_user_token)
    )

    assert response.status_code == 403


async def test_list_cases_as_admin_sees_all(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    other_case: Case,
) -> None:
    response = await client.get(CASES, headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_list_cases_isolated_for_lawyer(
    client: AsyncClient, sample_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.get(CASES, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_list_cases_sees_own_assignment(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    lawyer, token = second_lawyer_token
    assigned = await client.post(
        f"{CASES}/{sample_case.id}/lawyers",
        json={"lawyer_id": str(lawyer.id)},
        headers=_auth(admin_token),
    )
    assert assigned.status_code == 200

    response = await client.get(CASES, headers=_auth(token))

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(sample_case.id)


async def test_lawyer_cannot_open_case_he_is_not_assigned(
    client: AsyncClient, other_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.get(f"{CASES}/{other_case.id}", headers=_auth(token))

    assert response.status_code == 404


async def test_list_cases_filters(
    client: AsyncClient, admin_token: str, sample_case: Case, other_case: Case
) -> None:
    by_status = await client.get(
        CASES, params={"status": "abierto"}, headers=_auth(admin_token)
    )
    by_priority = await client.get(
        CASES, params={"priority": "alta"}, headers=_auth(admin_token)
    )
    by_search = await client.get(
        CASES, params={"search": "ajeno"}, headers=_auth(admin_token)
    )
    by_number = await client.get(
        CASES, params={"search": "WA-2026-000001"}, headers=_auth(admin_token)
    )
    by_client = await client.get(
        CASES,
        params={"client_id": str(sample_case.client_id)},
        headers=_auth(admin_token),
    )

    assert by_status.json()["total"] == 2
    assert by_priority.json()["total"] == 1
    assert by_search.json()["items"][0]["id"] == str(other_case.id)
    assert by_number.json()["items"][0]["id"] == str(sample_case.id)
    assert by_client.json()["total"] == 2


async def test_open_only_filter_hides_closed(
    client: AsyncClient, admin_token: str, sample_case: Case, other_case: Case
) -> None:
    closed = await client.post(
        f"{CASES}/{other_case.id}/close",
        json={"closed_at": "2026-03-01"},
        headers=_auth(admin_token),
    )
    response = await client.get(CASES, params={"open_only": "true"}, headers=_auth(admin_token))

    assert closed.status_code == 200
    assert closed.json()["status"] == "cerrado"
    assert response.json()["total"] == 1


async def test_update_case_records_history(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.patch(
        f"{CASES}/{sample_case.id}",
        json={"title": "Titulo actualizado", "priority": "urgente"},
        headers=_auth(admin_token),
    )
    history = await client.get(f"{CASES}/{sample_case.id}/history", headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["title"] == "Titulo actualizado"
    fields = {entry["field_name"] for entry in history.json()}
    assert "title" in fields
    assert "priority" in fields


async def test_close_case_twice_is_rejected(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    first = await client.post(
        f"{CASES}/{sample_case.id}/close", json={}, headers=_auth(admin_token)
    )
    second = await client.post(
        f"{CASES}/{sample_case.id}/close", json={}, headers=_auth(admin_token)
    )

    assert first.status_code == 200
    assert first.json()["closed_at"] == str(date.today())
    assert second.status_code == 409


async def test_close_requires_permission(
    client: AsyncClient, staff_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"{CASES}/{sample_case.id}/close", json={}, headers=_auth(staff_token)
    )

    assert response.status_code == 403


async def test_assign_and_revoke_collaborator(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    lawyer, _token = second_lawyer_token

    assigned = await client.post(
        f"{CASES}/{sample_case.id}/lawyers",
        json={"lawyer_id": str(lawyer.id)},
        headers=_auth(admin_token),
    )
    revoked = await client.delete(
        f"{CASES}/{sample_case.id}/lawyers/{lawyer.id}", headers=_auth(admin_token)
    )

    assert assigned.status_code == 200
    assert assigned.json()["role"] == "colaborador"
    assert assigned.json()["lawyer_name"] == lawyer.full_name
    assert revoked.status_code == 204


async def test_cannot_revoke_responsible_lawyer(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    response = await client.delete(
        f"{CASES}/{sample_case.id}/lawyers/{sample_lawyer.id}", headers=_auth(admin_token)
    )

    assert response.status_code == 409
    assert "responsable" in response.json()["error"]["message"]


async def test_assign_same_lawyer_twice_is_idempotent(
    client: AsyncClient, admin_token: str, sample_case: Case, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        f"{CASES}/{sample_case.id}/lawyers",
        json={"lawyer_id": str(sample_lawyer.id)},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "responsable"


async def test_change_responsible_demotes_previous(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    sample_lawyer: Lawyer,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    new_lawyer, _token = second_lawyer_token

    response = await client.patch(
        f"{CASES}/{sample_case.id}",
        json={"responsible_lawyer_id": str(new_lawyer.id)},
        headers=_auth(admin_token),
    )
    view = await client.get(f"{CASES}/{sample_case.id}/360", headers=_auth(admin_token))
    roles = {item["lawyer_id"]: item["role"] for item in view.json()["collaborators"]}

    assert response.status_code == 200
    assert roles[str(new_lawyer.id)] == "responsable"
    assert roles[str(sample_lawyer.id)] == "colaborador"


async def test_parties_lifecycle(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"{CASES}/{sample_case.id}/parties",
        json={"name": "Demandado Corp", "party_role": "demandado"},
        headers=_auth(admin_token),
    )
    listed = await client.get(f"{CASES}/{sample_case.id}/parties", headers=_auth(admin_token))

    assert created.status_code == 201
    assert created.json()["party_role"] == "demandado"
    assert created.json()["is_external"] is True
    assert len(listed.json()) == 1


async def test_party_rejects_unknown_client(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"{CASES}/{sample_case.id}/parties",
        json={"name": "Algo", "party_role": "tercero", "client_id": str(uuid4())},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_case_360_exposes_structure(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.get(f"{CASES}/{sample_case.id}/360", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["case"]["id"] == str(sample_case.id)
    assert payload["collaborators"][0]["lawyer_name"]
    assert payload["actuaciones"]["available"] is True
    assert payload["agenda"]["available"] is True
    assert payload["audiencias"]["available"] is True
    assert payload["documentos"]["available"] is True
    assert payload["evidencias"]["available"] is True
    assert payload["evidencias_total"] == 0
    for section in ("tareas", "mensajes"):
        assert payload[section]["available"] is False
        assert payload[section]["items"] == []
    assert payload["history_entries"] >= 0


async def test_case_360_hidden_from_unassigned_lawyer(
    client: AsyncClient, sample_case: Case, second_lawyer_token: tuple[Lawyer, str]
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.get(f"{CASES}/{sample_case.id}/360", headers=_auth(token))

    assert response.status_code == 404


async def test_unknown_case_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{CASES}/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_anonymous_cannot_list_cases(client: AsyncClient) -> None:
    response = await client.get(CASES)

    assert response.status_code == 401


async def test_collaborators_are_recorded_on_creation(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_token: str,
    sample_client: Client,
    sample_lawyer: Lawyer,
) -> None:
    from uuid import UUID

    from sqlalchemy import select

    response = await client.post(
        CASES,
        json=_payload(str(sample_client.id), responsible_lawyer_id=str(sample_lawyer.id)),
        headers=_auth(admin_token),
    )
    assignments = list(
        (
            await database_session.execute(
                select(CaseLawyer).where(
                    CaseLawyer.case_id == UUID(response.json()["id"])
                )
            )
        )
        .scalars()
        .all()
    )

    assert response.status_code == 201
    assert len(assignments) == 1
    assert assignments[0].role == "responsable"

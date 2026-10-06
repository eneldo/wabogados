from uuid import uuid4

from httpx import AsyncClient

from app.models import Client, LegalArea

CLIENTS = "/api/v1/clients"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _natural_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_type": "natural",
        "document_type": "DNI",
        "document_number": "11122233",
        "full_name": "Ana Pérez",
        "email": "ana.perez@wabogados.com",
        "phone": "+51 999000111",
    }
    payload.update(overrides)
    return payload


async def test_create_natural_client(client: AsyncClient, admin_token: str) -> None:
    response = await client.post(CLIENTS, json=_natural_payload(), headers=_auth(admin_token))

    assert response.status_code == 201
    payload = response.json()
    assert payload["client_type"] == "natural"
    assert payload["display_name"] == "Ana Pérez"
    assert payload["is_active"] is True
    assert payload["deleted_at"] is None


async def test_create_juridical_client(client: AsyncClient, admin_token: str) -> None:
    response = await client.post(
        CLIENTS,
        json=_natural_payload(
            client_type="juridica",
            document_type="RUC",
            document_number="20501234567",
            full_name=None,
            legal_name="Constructora Andina S.A.C.",
        ),
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    assert response.json()["display_name"] == "Constructora Andina S.A.C."


async def test_natural_client_requires_full_name(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        CLIENTS, json=_natural_payload(full_name=None), headers=_auth(admin_token)
    )

    assert response.status_code == 422


async def test_juridical_client_requires_legal_name(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        CLIENTS,
        json=_natural_payload(client_type="juridica", document_type="RUC", full_name=None),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_duplicate_document_is_rejected(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    response = await client.post(
        CLIENTS,
        json=_natural_payload(document_number=sample_client.document_number),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "Ya existe un cliente" in response.json()["error"]["message"]


async def test_list_clients_is_paginated(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    response = await client.get(CLIENTS, headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(sample_client.id)


async def test_list_clients_search_and_filter(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    by_name = await client.get(CLIENTS, params={"search": "Prueba"}, headers=_auth(admin_token))
    by_type = await client.get(
        CLIENTS, params={"client_type": "juridica"}, headers=_auth(admin_token)
    )
    by_document = await client.get(
        CLIENTS, params={"search": sample_client.document_number}, headers=_auth(admin_token)
    )

    assert by_name.json()["total"] == 1
    assert by_type.json()["total"] == 0
    assert by_document.json()["total"] == 1


async def test_get_client(client: AsyncClient, admin_token: str, sample_client: Client) -> None:
    response = await client.get(f"{CLIENTS}/{sample_client.id}", headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["full_name"] == "Cliente de Prueba"


async def test_get_unknown_client_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{CLIENTS}/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_update_client_records_history(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    response = await client.patch(
        f"{CLIENTS}/{sample_client.id}",
        json={"phone": "+51 900000000", "notes": "Nota inicial"},
        headers=_auth(admin_token),
    )
    history = await client.get(
        f"{CLIENTS}/{sample_client.id}/history", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "+51 900000000"
    fields = {entry["field_name"] for entry in history.json()}
    assert fields == {"phone", "notes"}
    for entry in history.json():
        assert entry["entity"] == "clients"
        assert entry["entity_id"] == str(sample_client.id)


async def test_update_without_changes_records_nothing(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    await client.patch(
        f"{CLIENTS}/{sample_client.id}",
        json={"phone": sample_client.phone},
        headers=_auth(admin_token),
    )
    history = await client.get(
        f"{CLIENTS}/{sample_client.id}/history", headers=_auth(admin_token)
    )

    assert history.json() == []


async def test_deactivate_client_keeps_record(
    client: AsyncClient, admin_token: str, admin_user: object, sample_client: Client
) -> None:
    response = await client.delete(f"{CLIENTS}/{sample_client.id}", headers=_auth(admin_token))
    listed = await client.get(CLIENTS, headers=_auth(admin_token))
    with_inactive = await client.get(
        CLIENTS, params={"include_inactive": "true"}, headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["deleted_at"] is not None
    assert listed.json()["total"] == 0
    assert with_inactive.json()["total"] == 1


async def test_staff_cannot_delete_client(
    client: AsyncClient, staff_token: str, sample_client: Client
) -> None:
    response = await client.delete(f"{CLIENTS}/{sample_client.id}", headers=_auth(staff_token))

    assert response.status_code == 403
    assert "clients:delete" in response.json()["error"]["message"]


async def test_staff_can_create_and_update_client(
    client: AsyncClient, staff_token: str, sample_client: Client
) -> None:
    created = await client.post(
        CLIENTS, json=_natural_payload(), headers=_auth(staff_token)
    )
    updated = await client.patch(
        f"{CLIENTS}/{sample_client.id}",
        json={"full_name": "Cliente Actualizado"},
        headers=_auth(staff_token),
    )

    assert created.status_code == 201
    assert updated.status_code == 200


async def test_client_role_has_no_access(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get(CLIENTS, headers=_auth(plain_user_token))

    assert response.status_code == 403


async def test_anonymous_cannot_list_clients(client: AsyncClient) -> None:
    response = await client.get(CLIENTS)

    assert response.status_code == 401


async def test_history_of_unknown_client_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{CLIENTS}/{uuid4()}/history", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_legal_areas_are_seeded(legal_area: LegalArea) -> None:
    assert legal_area.name == "Civil"
    assert legal_area.is_active is True

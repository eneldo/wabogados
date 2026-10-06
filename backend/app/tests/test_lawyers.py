from uuid import uuid4

from httpx import AsyncClient

from app.models import Lawyer, LegalArea

LAWYERS = "/api/v1/lawyers"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(legal_area_id: str | None = None, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "document_type": "DNI",
        "document_number": "44555666",
        "full_name": "Luis Ramírez",
        "professional_card": "CAL-99999",
        "email": "luis.ramirez@wabogados.com",
        "specialties": ["Penal", "Procesal"],
        "status": "activo",
    }
    if legal_area_id:
        payload["legal_area_ids"] = [legal_area_id]
    payload.update(overrides)
    return payload


async def test_create_lawyer_with_legal_areas(
    client: AsyncClient, admin_token: str, legal_area: LegalArea
) -> None:
    response = await client.post(
        LAWYERS, json=_payload(str(legal_area.id)), headers=_auth(admin_token)
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["legal_areas"] == ["Civil"]
    assert payload["specialties"] == ["Penal", "Procesal"]
    assert payload["status"] == "activo"


async def test_create_lawyer_with_unknown_legal_area(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        LAWYERS, json=_payload(str(uuid4())), headers=_auth(admin_token)
    )

    assert response.status_code == 409
    assert "área jurídica" in response.json()["error"]["message"]


async def test_duplicate_professional_card_is_rejected(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        LAWYERS,
        json=_payload(professional_card=sample_lawyer.professional_card),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "tarjeta profesional" in response.json()["error"]["message"]


async def test_duplicate_document_is_rejected(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    response = await client.post(
        LAWYERS,
        json=_payload(document_number=sample_lawyer.document_number),
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_repeated_specialties_are_rejected(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        LAWYERS,
        json=_payload(specialties=["Civil", "Civil"]),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_list_lawyers_search_and_status(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    all_lawyers = await client.get(LAWYERS, headers=_auth(admin_token))
    by_name = await client.get(LAWYERS, params={"search": "Prueba"}, headers=_auth(admin_token))
    by_status = await client.get(
        LAWYERS, params={"status": "suspendido"}, headers=_auth(admin_token)
    )
    by_card = await client.get(
        LAWYERS, params={"search": "CAL-12345"}, headers=_auth(admin_token)
    )

    assert all_lawyers.json()["total"] == 1
    assert by_name.json()["total"] == 1
    assert by_status.json()["total"] == 0
    assert by_card.json()["total"] == 1


async def test_get_lawyer(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    response = await client.get(f"{LAWYERS}/{sample_lawyer.id}", headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["professional_card"] == "CAL-12345"


async def test_get_unknown_lawyer_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{LAWYERS}/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_update_lawyer_records_history(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer, legal_area: LegalArea
) -> None:
    response = await client.patch(
        f"{LAWYERS}/{sample_lawyer.id}",
        json={"status": "suspendido", "legal_area_ids": [str(legal_area.id)]},
        headers=_auth(admin_token),
    )
    history = await client.get(
        f"{LAWYERS}/{sample_lawyer.id}/history", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspendido"
    fields = {entry["field_name"] for entry in history.json()}
    assert "status" in fields


async def test_update_lawyer_rejects_duplicate_card(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    other = await client.post(LAWYERS, json=_payload(), headers=_auth(admin_token))

    response = await client.patch(
        f"{LAWYERS}/{sample_lawyer.id}",
        json={"professional_card": other.json()["professional_card"]},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_deactivate_lawyer_marks_inactive(
    client: AsyncClient, admin_token: str, sample_lawyer: Lawyer
) -> None:
    response = await client.delete(
        f"{LAWYERS}/{sample_lawyer.id}", headers=_auth(admin_token)
    )
    listed = await client.get(LAWYERS, headers=_auth(admin_token))
    with_inactive = await client.get(
        LAWYERS, params={"include_inactive": "true"}, headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["status"] == "inactivo"
    assert listed.json()["total"] == 0
    assert with_inactive.json()["total"] == 1


async def test_staff_can_read_but_not_create_or_delete(
    client: AsyncClient, staff_token: str, sample_lawyer: Lawyer
) -> None:
    read = await client.get(LAWYERS, headers=_auth(staff_token))
    create = await client.post(LAWYERS, json=_payload(), headers=_auth(staff_token))
    delete = await client.delete(
        f"{LAWYERS}/{sample_lawyer.id}", headers=_auth(staff_token)
    )

    assert read.status_code == 200
    assert create.status_code == 403
    assert delete.status_code == 403


async def test_anonymous_cannot_list_lawyers(client: AsyncClient) -> None:
    response = await client.get(LAWYERS)

    assert response.status_code == 401


async def test_legal_areas_endpoint(
    client: AsyncClient, admin_token: str, legal_area: LegalArea
) -> None:
    response = await client.get(f"{LAWYERS}/legal-areas", headers=_auth(admin_token))

    assert response.status_code == 200
    names = [area["name"] for area in response.json()]
    assert "Civil" in names
    assert "Penal" in names
    assert names == sorted(names)


async def test_legal_areas_requires_permission(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get(f"{LAWYERS}/legal-areas", headers=_auth(plain_user_token))

    assert response.status_code == 403


async def test_history_of_unknown_lawyer_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{LAWYERS}/{uuid4()}/history", headers=_auth(admin_token))

    assert response.status_code == 404

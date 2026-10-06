"""The public consultation form and the intake queue behind it.

These tests exist because the endpoint is the only unauthenticated write in the
application. Three properties are worth more than the happy path:

1. **A success message means a row exists.** The public site promises that only
   when the backend confirms, so the test asserts the row and not just the 201.
2. **The response echoes nothing personal.** Returning the stored row would
   repeat the person's legal problem back to them.
3. **The queue is not public.** Reading it requires a permission, and the client
   role does not hold it.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ConsultationRequest

CONSULTATIONS = "/api/v1/consultations"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "  María   Fernanda  ",
        "phone": "+57 300 123 4567",
        "email": "maria.fernanda@example.com",
        "area": "Derecho laboral",
        "message": "Requiero asesoría sobre un despido que occurred este mes.",
        "consent": True,
        "website": "",
    }
    payload.update(overrides)
    return payload


async def _count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(ConsultationRequest)) or 0)


# --- the public write ------------------------------------------------------


async def test_public_submission_stores_the_request(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    response = await client.post(CONSULTATIONS, json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "nueva"
    assert body["message"]

    # The promise the page makes, verified against the database rather than
    # against the response body.
    stored = await database_session.scalar(select(ConsultationRequest))
    assert stored is not None
    assert stored.full_name == "María Fernanda"
    assert stored.phone == "+57 300 123 4567"
    assert stored.email == "maria.fernanda@example.com"
    assert stored.area == "Derecho laboral"
    assert stored.consent_at is not None
    assert stored.privacy_notice_version


async def test_submission_is_normalised(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    """A name split across three lines is one name, not three."""

    await client.post(CONSULTATIONS, json=_payload(full_name="  María\n\t Fernanda  "))

    stored = await database_session.scalar(select(ConsultationRequest))
    assert stored is not None
    assert stored.full_name == "María Fernanda"


async def test_response_echoes_no_personal_data(client: AsyncClient) -> None:
    """The stored row must not come back to the person who sent it."""

    response = await client.post(CONSULTATIONS, json=_payload())
    raw = response.text

    assert "maria.fernanda@example.com" not in raw
    assert "despido" not in raw
    assert "María" not in raw
    assert "+57 300 123 4567" not in raw


async def test_consent_is_required(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    before = await _count(database_session)

    response = await client.post(CONSULTATIONS, json=_payload(consent=False))

    assert response.status_code == 422
    assert await _count(database_session) == before


async def test_filled_trap_is_rejected_without_storing(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    """A bot fills the field it cannot see. Nothing is stored, and the reply is
    the same 422 any other invalid field gets.

    FastAPI's error format echoes the offending value back inside `input`, so
    the trap value does appear in the body. That is the sender's own input
    travelling back to the sender, it tells a bot nothing it does not already
    know, and nothing of it reaches `audit_logs`, which never reads the body.
    """

    before = await _count(database_session)

    response = await client.post(
        CONSULTATIONS, json=_payload(website="http://spam.example")
    )

    assert response.status_code == 422
    assert "Solicitud no válida" in response.text
    assert await _count(database_session) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("area", "Derecho intergaláctico"),
        ("full_name", "A"),
        ("phone", "12345"),
        ("message", "corto"),
        ("email", "not-an-email"),
    ],
)
async def test_invalid_payloads_are_rejected(
    client: AsyncClient, database_session: AsyncSession, field: str, value: str
) -> None:
    before = await _count(database_session)

    response = await client.post(CONSULTATIONS, json=_payload(**{field: value}))

    assert response.status_code == 422
    assert await _count(database_session) == before


async def test_unknown_field_is_ignored_not_stored(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    """`consent_at` in the body would let a person forge when they agreed."""

    response = await client.post(
        CONSULTATIONS,
        json=_payload(consent_at="1999-01-01T00:00:00Z"),
    )

    assert response.status_code == 201
    stored = await database_session.scalar(select(ConsultationRequest))
    assert stored is not None
    assert stored.consent_at.year != 1999


# --- the rate limit --------------------------------------------------------


async def test_submissions_are_rate_limited_by_ip(client: AsyncClient) -> None:
    """Three an hour is the configured budget; the fourth is refused.

    This is the endpoint's real abuse control: it is unauthenticated and what it
    accepts is somebody's legal problem.
    """

    settings = get_settings()
    allowed = settings.contact_rate_limit_requests

    for _ in range(allowed):
        response = await client.post(CONSULTATIONS, json=_payload())
        assert response.status_code == 201

    refused = await client.post(CONSULTATIONS, json=_payload())
    assert refused.status_code == 429
    assert refused.headers.get("Retry-After")


async def test_reading_the_queue_is_not_rate_limited(
    client: AsyncClient, staff_token: str
) -> None:
    """Only the write is expensive. A lawyer paging through the queue at their
    own pace must not spend the public form's budget."""

    for _ in range(get_settings().contact_rate_limit_requests + 2):
        response = await client.get(CONSULTATIONS, headers=_auth(staff_token))
        assert response.status_code == 200


# --- the queue is not public ----------------------------------------------


async def test_queue_requires_credentials(client: AsyncClient) -> None:
    assert (await client.get(CONSULTATIONS)).status_code == 401


async def test_client_role_cannot_read_the_queue(
    client: AsyncClient, portal_token: str
) -> None:
    """These rows belong to nobody yet. A portal client is not that nobody."""

    response = await client.get(CONSULTATIONS, headers=_auth(portal_token))

    assert response.status_code == 403


async def test_staff_can_read_the_queue(
    client: AsyncClient, staff_token: str, database_session: AsyncSession
) -> None:
    await client.post(CONSULTATIONS, json=_payload())

    response = await client.get(CONSULTATIONS, headers=_auth(staff_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["area"] == "Derecho laboral"


async def test_queue_is_newest_first(
    client: AsyncClient, staff_token: str, database_session: AsyncSession
) -> None:
    """The request that arrived while nobody was looking is the one that decays.

    The instants are set explicitly because the column default is
    `server_default=now()`, and PostgreSQL's `now()` is the start of the
    transaction: anything written by the endpoint inside one transaction shares
    a timestamp and could not be ordered by arrival at all.
    """

    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    for offset, area in ((0, "Derecho civil"), (5, "Derecho laboral")):
        database_session.add(
            ConsultationRequest(
                full_name="Persona",
                phone="3000000000",
                email="persona@example.com",
                area=area,
                message="Consulta de prueba para ordenar la cola.",
                consent_at=base,
                privacy_notice_version="2026-10",
                created_at=base + timedelta(minutes=offset),
            )
        )
    await database_session.flush()

    response = await client.get(CONSULTATIONS, headers=_auth(staff_token))
    areas = [item["area"] for item in response.json()["items"]]

    assert areas == ["Derecho laboral", "Derecho civil"]


async def test_queue_paginates_without_repeating_a_row(
    client: AsyncClient, staff_token: str, database_session: AsyncSession
) -> None:
    """Rows sharing an instant must still page deterministically, or the same
    request can show up on two pages of the queue."""

    from datetime import UTC, datetime

    same_instant = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    for index in range(5):
        database_session.add(
            ConsultationRequest(
                full_name=f"Persona {index}",
                phone="3000000000",
                email=f"persona{index}@example.com",
                area="Derecho civil",
                message="Consulta de prueba para la paginación.",
                consent_at=same_instant,
                privacy_notice_version="2026-10",
                created_at=same_instant,
            )
        )
    await database_session.flush()

    first = await client.get(f"{CONSULTATIONS}?limit=2", headers=_auth(staff_token))
    second = await client.get(
        f"{CONSULTATIONS}?limit=2&skip=2", headers=_auth(staff_token)
    )

    first_ids = [item["id"] for item in first.json()["items"]]
    second_ids = [item["id"] for item in second.json()["items"]]
    assert first.json()["total"] == 5
    assert len(first_ids) == len(second_ids) == 2
    assert not set(first_ids) & set(second_ids)


async def test_queue_can_be_filtered(
    client: AsyncClient, staff_token: str
) -> None:
    await client.post(CONSULTATIONS, json=_payload(area="Derecho civil"))
    await client.post(CONSULTATIONS, json=_payload(area="Derecho laboral"))

    response = await client.get(
        f"{CONSULTATIONS}?status=nueva", headers=_auth(staff_token)
    )
    assert response.json()["total"] == 2

    by_status = await client.get(
        f"{CONSULTATIONS}?status=atendida", headers=_auth(staff_token)
    )
    assert by_status.json()["total"] == 0

    missing = await client.get(
        f"{CONSULTATIONS}?status=inventada", headers=_auth(staff_token)
    )
    assert missing.status_code == 422


async def test_single_request_needs_the_permission(
    client: AsyncClient, portal_token: str
) -> None:
    reference = uuid4()

    response = await client.get(
        f"{CONSULTATIONS}/{reference}", headers=_auth(portal_token)
    )

    assert response.status_code == 403


async def test_unknown_request_is_not_found(
    client: AsyncClient, staff_token: str
) -> None:
    response = await client.get(f"{CONSULTATIONS}/{uuid4()}", headers=_auth(staff_token))

    assert response.status_code == 404


# --- working the queue -----------------------------------------------------


async def test_updating_the_status_records_who_and_when(
    client: AsyncClient, staff_token: str, database_session: AsyncSession
) -> None:
    created = await client.post(CONSULTATIONS, json=_payload())
    reference = created.json()["reference"]

    response = await client.patch(
        f"{CONSULTATIONS}/{reference}",
        json={"status": "en_revision", "internal_notes": "Llamar por la mañana."},
        headers=_auth(staff_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "en_revision"

    stored = await database_session.get(ConsultationRequest, reference)
    assert stored is not None
    assert stored.handled_at is not None
    assert stored.handled_by is not None
    assert stored.internal_notes == "Llamar por la mañana."


async def test_back_to_nueva_clears_nothing_but_keeps_the_actor(
    client: AsyncClient, staff_token: str
) -> None:
    """Returning a request to the queue must not erase who had already touched
    it. The column is nullable, not reset to null."""

    reference = (
        await client.post(CONSULTATIONS, json=_payload())
    ).json()["reference"]

    await client.patch(
        f"{CONSULTATIONS}/{reference}", json={"status": "atendida"}, headers=_auth(staff_token)
    )
    response = await client.patch(
        f"{CONSULTATIONS}/{reference}", json={"status": "nueva"}, headers=_auth(staff_token)
    )

    assert response.status_code == 200
    assert response.json()["handled_by"] is not None


async def test_updating_a_missing_request_is_not_found(
    client: AsyncClient, staff_token: str
) -> None:
    response = await client.patch(
        f"{CONSULTATIONS}/{uuid4()}", json={"status": "atendida"}, headers=_auth(staff_token)
    )

    assert response.status_code == 404


async def test_invalid_status_is_rejected(
    client: AsyncClient, staff_token: str
) -> None:
    reference = (await client.post(CONSULTATIONS, json=_payload())).json()["reference"]

    response = await client.patch(
        f"{CONSULTATIONS}/{reference}", json={"status": "casi"}, headers=_auth(staff_token)
    )

    assert response.status_code == 422


async def test_updating_requires_the_permission(
    client: AsyncClient, portal_token: str
) -> None:
    reference = (await client.post(CONSULTATIONS, json=_payload())).json()["reference"]

    response = await client.patch(
        f"{CONSULTATIONS}/{reference}", json={"status": "atendida"}, headers=_auth(portal_token)
    )

    assert response.status_code == 403


# --- erasure ---------------------------------------------------------------


async def test_erasure_really_deletes(
    client: AsyncClient, admin_token: str, database_session: AsyncSession
) -> None:
    """A request that never became an expediente is a lead, not a legal record,
    and the person may ask for it to disappear. A soft delete would leave the
    legal problem sitting in the table."""

    reference = (
        await client.post(CONSULTATIONS, json=_payload())
    ).json()["reference"]

    response = await client.delete(f"{CONSULTATIONS}/{reference}", headers=_auth(admin_token))

    assert response.status_code == 204
    assert await database_session.get(ConsultationRequest, reference) is None


async def test_erasing_a_missing_request_is_not_found(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.delete(f"{CONSULTATIONS}/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404


async def test_erasure_is_not_granted_to_a_lawyer(
    client: AsyncClient, staff_token: str
) -> None:
    """Only an administrator erases. Reading a legal problem and deleting it are
    not the same power, and the default should be the more cautious one."""

    reference = (await client.post(CONSULTATIONS, json=_payload())).json()["reference"]

    response = await client.delete(f"{CONSULTATIONS}/{reference}", headers=_auth(staff_token))

    assert response.status_code == 403


async def test_erasure_requires_a_session(client: AsyncClient) -> None:
    assert (await client.delete(f"{CONSULTATIONS}/{uuid4()}")).status_code == 401


async def test_erasure_does_not_leak_the_deleted_body(
    client: AsyncClient, admin_token: str
) -> None:
    """The audit trail records that the deletion happened, never what it held."""

    reference = (
        await client.post(CONSULTATIONS, json=_payload())
    ).json()["reference"]

    response = await client.delete(f"{CONSULTATIONS}/{reference}", headers=_auth(admin_token))

    assert "maria.fernanda@example.com" not in response.text
    assert "despido" not in response.text
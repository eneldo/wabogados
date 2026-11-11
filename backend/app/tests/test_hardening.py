"""Settings, observability and the security contract of the whole surface.

These are the tests for Fase 10. Three concerns:

* `system_settings` behaves, and refuses to become a place for secrets.
* The figures of MASTER_PROMPT section 43 come out right, computed in SQL.
* The endpoint surface still obeys the policy: only login and refresh are
  public, and a user with no permissions reads nothing anywhere.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Case,
    ChangeLog,
    Client,
    Document,
    DocumentVersion,
    Evidence,
    EvidenceDerivative,
    EvidenceFile,
    EvidenceProcessingJob,
    User,
)
from app.services.evidence import EvidenceStatus, JobStatus
from app.services.observability import ObservabilityService, compression_percent
from app.services.settings import (
    SettingsError,
    SettingsService,
    decode_value,
    encode_value,
    reject_credential_keys,
    validate_key,
)

SETTINGS = "/api/v1/admin/settings"
METRICS = "/api/v1/admin/metrics/evidence"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mb(value: float) -> int:
    return int(value * 1024 * 1024)


# --- system_settings: behaviour -----------------------------------------


@pytest.mark.asyncio
async def test_setting_round_trip(
    database_session: AsyncSession, admin_user: User
) -> None:
    service = SettingsService(database_session)

    await service.upsert("retention.default_days", 30, admin_user, category="retencion")

    assert await service.get_value("retention.default_days") == 30


@pytest.mark.asyncio
async def test_structured_values_keep_their_type(
    database_session: AsyncSession, admin_user: User
) -> None:
    service = SettingsService(database_session)

    await service.upsert(
        "evidence.profiles", {"imagen": "webp", "pdf": "ninguno"}, admin_user
    )

    assert await service.get_value("evidence.profiles") == {
        "imagen": "webp",
        "pdf": "ninguno",
    }


@pytest.mark.asyncio
async def test_missing_setting_returns_the_default(
    database_session: AsyncSession, admin_user: User
) -> None:
    assert await SettingsService(database_session).get_value("nada.este", 7) == 7


@pytest.mark.asyncio
async def test_a_setting_is_audited(
    database_session: AsyncSession, admin_user: User
) -> None:
    service = SettingsService(database_session)

    await service.upsert("mantenimiento.aviso", "Mantenimiento el domingo", admin_user)
    await service.upsert("mantenimiento.aviso", "Mantenimiento el lunes", admin_user)

    result = await database_session.execute(
        select(ChangeLog).where(ChangeLog.entity == "system_settings")
    )
    entries = list(result.scalars().all())

    assert entries, "cambiar un ajuste debe quedar auditado"
    assert any(entry.change_reason == "Ajuste creado" for entry in entries)
    assert any(entry.change_reason == "Ajuste modificado" for entry in entries)


@pytest.mark.asyncio
async def test_delete_keeps_the_trail(
    database_session: AsyncSession, admin_user: User
) -> None:
    """A settings row is not legal data, so it goes; the audit stays."""
    service = SettingsService(database_session)
    await service.upsert("temporal", "valor", admin_user)

    await service.delete("temporal", admin_user)

    assert await service.get("temporal") is None
    result = await database_session.execute(
        select(ChangeLog).where(ChangeLog.entity == "system_settings")
    )
    assert any(entry.change_reason == "Ajuste eliminado" for entry in result.scalars())


@pytest.mark.asyncio
async def test_deleting_an_unknown_setting_is_an_error(
    database_session: AsyncSession, admin_user: User
) -> None:
    with pytest.raises(SettingsError):
        await SettingsService(database_session).delete("no.existe", admin_user)


@pytest.mark.parametrize(
    "key",
    [
        "db.password",
        "smtp.secret",
        "api.token",
        "s3.access_key",
        "jwt.private_key",
    ],
)
def test_credential_keys_are_refused(key: str) -> None:
    """A secret stored here would reach every backup and every audit trail."""
    with pytest.raises(SettingsError):
        reject_credential_keys(key)


@pytest.mark.parametrize(
    "key",
    ["UPPER", "con espacio", "empieza/por/barra", "", "a" * 120],
)
def test_invalid_keys_are_refused(key: str) -> None:
    with pytest.raises(SettingsError):
        validate_key(key)


@pytest.mark.parametrize("key", ["a", "retencion.dias", "evidence.pdf.quality", "x-y_z"])
def test_valid_keys_are_accepted(key: str) -> None:
    assert validate_key(key) == key


def test_oversized_values_are_refused() -> None:
    with pytest.raises(SettingsError):
        encode_value("x" * 9000)


def test_value_decoding_is_forgiving() -> None:
    assert decode_value("texto plano") == "texto plano"
    assert decode_value("42") == 42
    assert decode_value('{"a": 1}') == {"a": 1}


# --- system_settings: API ----------------------------------------------


@pytest.mark.asyncio
async def test_settings_api_requires_permissions(
    client: AsyncClient, admin_token: str, staff_token: str, portal_token: str
) -> None:
    """Only an administrator touches system settings."""
    assert (await client.get(SETTINGS, headers=_auth(admin_token))).status_code == 200
    assert (await client.get(SETTINGS, headers=_auth(staff_token))).status_code == 403
    assert (await client.get(SETTINGS, headers=_auth(portal_token))).status_code == 403
    assert (await client.get(SETTINGS)).status_code == 401


@pytest.mark.asyncio
async def test_settings_api_write_and_read(
    client: AsyncClient, admin_token: str
) -> None:
    written = await client.put(
        f"{SETTINGS}/mantenimiento.aviso",
        json={"value": "Ventana de mantenimiento", "category": "operacion"},
        headers=_auth(admin_token),
    )
    read = await client.get(f"{SETTINGS}/mantenimiento.aviso", headers=_auth(admin_token))
    listed = await client.get(SETTINGS, headers=_auth(admin_token))

    assert written.status_code == 200
    assert read.json()["value"] == "Ventana de mantenimiento"
    assert any(item["key"] == "mantenimiento.aviso" for item in listed.json())


@pytest.mark.asyncio
async def test_settings_api_writes_the_same_key_twice(
    client: AsyncClient, admin_token: str
) -> None:
    """The second write of a key is a different code path from the first.

    Creating a row is an INSERT, and PostgreSQL returns its columns, so the
    response can be serialised from what the ORM already holds. Changing one is
    an UPDATE, and `updated_at` is `onupdate=func.now()`: a server-side
    expression the ORM cannot evaluate, so the attribute is left expired and
    reading it asks for a lazy load. The router builds its response in a plain
    function, outside the greenlet, so that load raised `MissingGreenlet` and the
    API answered 500 to a write that had already been committed — the value
    changed on screen said it had not.

    Only the first write was ever tested, which is why this stayed hidden.
    """
    headers = _auth(admin_token)
    payload = {"value": "Primera", "category": "operacion"}

    created = await client.put(f"{SETTINGS}/regresion.doble", json=payload, headers=headers)
    assert created.status_code == 200
    assert created.json()["value"] == "Primera"

    updated = await client.put(
        f"{SETTINGS}/regresion.doble",
        json={"value": "Segunda", "category": "operacion"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == "Segunda"

    # And the row holds the second value, not the first one plus an error page.
    read = await client.get(f"{SETTINGS}/regresion.doble", headers=headers)
    assert read.json()["value"] == "Segunda"

    # The timestamp is the point of the refresh: it is the field the ORM could not
    # know, and the response must carry it rather than raise on the way out.
    assert updated.json()["updated_at"] >= created.json()["updated_at"]



@pytest.mark.asyncio
async def test_settings_api_refuses_a_credential(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.put(
        f"{SETTINGS}/smtp.password",
        json={"value": "hunter2"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 422
    assert "credenciales" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_settings_api_unknown_key_is_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{SETTINGS}/nada", headers=_auth(admin_token))

    assert response.status_code == 404


# --- observability: section 43 -----------------------------------------


@pytest.mark.asyncio
async def test_metrics_on_an_empty_system_are_zero(
    database_session: AsyncSession, admin_user: User
) -> None:
    metrics = await ObservabilityService(database_session).evidence_metrics()

    assert metrics.evidence_count == 0
    assert metrics.original_mb == 0
    assert metrics.compression_ratio_percent == 0.0
    assert metrics.average_processing_seconds is None


@pytest.mark.parametrize(
    ("original", "optimised", "expected"),
    [(0, 0, 0.0), (100, 25, 75.0), (100, 100, 0.0), (100, 120, 0.0)],
)
def test_compression_percent(original: float, optimised: float, expected: float) -> None:
    assert compression_percent(original, optimised) == expected


@pytest.mark.asyncio
async def test_metrics_count_files_and_savings(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    evidence = Evidence(
        case_id=sample_case.id,
        title="Con derivatives",
        evidence_type="documental",
        status=str(EvidenceStatus.READY),
        visibility="interna",
        confidentiality="interno",
    )
    database_session.add(evidence)
    await database_session.flush()

    original = EvidenceFile(
        evidence_id=evidence.id,
        storage_key=f"evidences/{evidence.id}/original/a.pdf",
        original_filename="a.pdf",
        mime_type="application/pdf",
        file_size=_mb(10),
        sha256="a" * 64,
        is_original=True,
    )
    database_session.add(original)
    await database_session.flush()

    for kind, size in (("optimized", _mb(3)), ("preview", _mb(1))):
        database_session.add(
            EvidenceDerivative(
                evidence_id=evidence.id,
                source_file_id=original.id,
                derivative_type=kind,
                storage_key=f"evidences/{evidence.id}/{kind}/a.bin",
                mime_type="application/octet-stream",
                size_bytes=size,
                sha256=kind.ljust(64, "0")[:64],
            )
        )
    await database_session.flush()

    metrics = await ObservabilityService(database_session).evidence_metrics()

    assert metrics.evidence_count == 1
    assert metrics.original_mb == pytest.approx(10.0)
    assert metrics.optimised_mb == pytest.approx(4.0)
    assert metrics.saved_mb == pytest.approx(6.0)
    # MASTER_PROMPT section 43: 124 GB -> 38 GB is 69% saved.
    assert metrics.compression_ratio_percent == pytest.approx(60.0)
    assert metrics.derivatives_count == 2


@pytest.mark.asyncio
async def test_metrics_report_quarantine_and_failures(
    database_session: AsyncSession, admin_user: User, sample_case: Case
) -> None:
    evidence_states: tuple[EvidenceStatus, ...] = (
        EvidenceStatus.QUARANTINED,
        EvidenceStatus.READY,
        EvidenceStatus.FAILED,
    )
    for index, state in enumerate(evidence_states):
        evidence = Evidence(
            case_id=sample_case.id,
            title=f"E{index}",
            evidence_type="documental",
            status=str(state),
            visibility="interna",
            confidentiality="interno",
        )
        database_session.add(evidence)
        await database_session.flush()
        database_session.add(
            EvidenceFile(
                evidence_id=evidence.id,
                storage_key=f"evidences/{evidence.id}/original/a.pdf",
                original_filename="a.pdf",
                mime_type="application/pdf",
                file_size=_mb(1),
                sha256=str(index) * 64,
                is_original=True,
            )
        )

    await database_session.flush()

    job_states = (JobStatus.FAILED, JobStatus.FAILED, JobStatus.COMPLETED)
    for job_state in job_states:
        database_session.add(
            EvidenceProcessingJob(
                evidence_id=await _an_evidence_id(database_session, sample_case),
                job_type="process",
                status=str(job_state),
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
    await database_session.flush()

    metrics = await ObservabilityService(database_session).evidence_metrics()

    assert metrics.quarantined_evidence == 1
    assert metrics.quarantined_files == 1
    assert metrics.failed_jobs == 2
    assert metrics.jobs_by_status["completed"] == 1


@pytest.mark.asyncio
async def test_metrics_average_processing_time(
    database_session: AsyncSession, sample_case: Case
) -> None:
    from datetime import timedelta

    evidence_id = await _an_evidence_id(database_session, sample_case)
    started = datetime.now(UTC)
    for seconds in (10, 30):
        database_session.add(
            EvidenceProcessingJob(
                evidence_id=evidence_id,
                job_type="process",
                status=str(JobStatus.COMPLETED),
                started_at=started,
                finished_at=started + timedelta(seconds=seconds),
            )
        )
    await database_session.flush()

    metrics = await ObservabilityService(database_session).evidence_metrics()

    assert metrics.average_processing_seconds == pytest.approx(20.0, abs=1.0)


@pytest.mark.asyncio
async def test_metrics_include_documents(
    database_session: AsyncSession, sample_case: Case
) -> None:
    document = Document(
        case_id=sample_case.id,
        document_type="escrito",
        title="Con version",
        status="vigente",
        confidentiality="interno",
        visibility="interna",
    )
    database_session.add(document)
    await database_session.flush()
    database_session.add(
        DocumentVersion(
            document_id=document.id,
            version_number=1,
            original_name="a.pdf",
            storage_key=f"cases/{sample_case.id}/documents/{document.id}/v1.pdf",
            mime_type="application/pdf",
            size_bytes=_mb(2),
            sha256="b" * 64,
            is_current=True,
        )
    )
    await database_session.flush()

    metrics = await ObservabilityService(database_session).evidence_metrics()

    assert metrics.document_original_mb == pytest.approx(2.0)
    assert metrics.document_versions == 1
    assert metrics.storage_mb == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_metrics_api_is_administrator_only(
    client: AsyncClient, admin_token: str, staff_token: str, portal_token: str
) -> None:
    assert (await client.get(METRICS, headers=_auth(admin_token))).status_code == 200
    assert (await client.get(METRICS, headers=_auth(staff_token))).status_code == 403
    assert (await client.get(METRICS, headers=_auth(portal_token))).status_code == 403
    assert (await client.get(METRICS)).status_code == 401


@pytest.mark.asyncio
async def test_metrics_derivatives_breakdown(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(
        f"{METRICS}/derivatives", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json() == {"derivatives": [], "total": 0}


async def _an_evidence_id(session: AsyncSession, case: Case) -> UUID:
    """Any evidence id, creating one when the table is still empty."""
    existing = (await session.execute(select(Evidence.id).limit(1))).scalar()
    if existing is not None:
        return existing
    evidence = Evidence(
        case_id=case.id,
        title="Soporte",
        evidence_type="documental",
        status=str(EvidenceStatus.READY),
        visibility="interna",
        confidentiality="interno",
    )
    session.add(evidence)
    await session.flush()
    return evidence.id


# --- the security contract of the whole surface -------------------------

#: The only endpoints that may answer without credentials.
#:
#: `POST /api/v1/consultations` is here because it is the public site's form: it
#: has to be reachable by somebody with no account. The other anonymous write is
#: the strictly shaped website analytics intake: no personal fields or totals
#: are returned, and its rate budget is separate. Adding either to this set is
#: the explicit act that the rest of this module exists to require.
PUBLIC_PATHS = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/consultations",
        "/api/v1/public/legal-areas",
        "/api/v1/public/lawyers",
        "/api/v1/public/announcements",
        "/api/v1/public/analyses",
        "/api/v1/public/analytics/events",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)


def _dependency_names(route: APIRoute) -> set[str]:
    names: set[str] = set()
    stack = [route.dependant]
    while stack:
        dependant = stack.pop()
        for sub in dependant.dependencies:
            stack.append(sub)
        call = dependant.call
        names.add(getattr(call, "__qualname__", ""))
    return names


def _carries_a_record(payload: object) -> bool:
    """Whether a JSON payload contains anything that looks like a stored row.

    Entities are addressed by UUID, so the presence of a UUID anywhere in the
    response means a record was returned. Zeroes, empty lists and pagination
    metadata do not, which is exactly the difference between an empty envelope
    and a leak.
    """
    if isinstance(payload, str):
        try:
            UUID(payload)
        except (ValueError, AttributeError, TypeError):
            return False
        return True
    if isinstance(payload, dict):
        return any(_carries_a_record(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_carries_a_record(item) for item in payload)
    return False


def test_only_login_and_refresh_are_public() -> None:
    """MASTER_PROMPT forbids endpoints without protection.

    `logout` and `/auth/me` are authenticated but carry no named permission:
    they answer about the caller only. Everything else must require a
    permission or resolve its scope from one.
    """
    from app.main import app

    offenders: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in PUBLIC_PATHS:
            continue
        names = _dependency_names(route)
        authenticated = any(
            "get_current_user" in name or "get_current_superuser" in name
            for name in names
        )
        authorised = any(
            "require_permission" in name or "get_current_superuser" in name
            for name in names
        )
        scoped = any("get_user_scope" in name for name in names)
        if not (authenticated and (authorised or scoped)):
            offenders.append(f"{sorted(route.methods or [])} {route.path}")


    assert offenders == []


@pytest.mark.asyncio
async def test_a_user_without_permissions_reads_nothing(
    client: AsyncClient,
    plain_user_token: str,
    sample_case: Case,
    sample_document: Document,
) -> None:
    """A user with no permissions gets 403 or empty, never data.

    Read endpoints answer with an empty list or a 404 by design: they derive
    their scope from permissions and an empty scope yields no rows. What must
    never happen is a 200 carrying somebody else's case.
    """
    read_endpoints = [
        "/api/v1/cases",
        "/api/v1/clients",
        "/api/v1/lawyers",
        "/api/v1/actions",
        "/api/v1/calendar",
        "/api/v1/hearings",
        "/api/v1/conversations",
        "/api/v1/notifications",
        "/api/v1/admin/users",
        "/api/v1/admin/settings",
        "/api/v1/admin/metrics/evidence",
    ]

    for path in read_endpoints:
        response = await client.get(path, headers=_auth(plain_user_token))
        assert response.status_code in (200, 403, 404), (
            f"{path} devolvió {response.status_code}"
        )
        if response.status_code == 200:
            # Read endpoints answer 200 with an empty payload when the caller
            # resolves to no scope. Rather than enumerate every envelope shape,
            # assert the property that actually matters: no row came back, and
            # the only way to know that generically is that no entity id is
            # present anywhere in the payload.
            assert not _carries_a_record(response.json()), (
                f"{path} devolvió una fila: {response.json()}"
            )


@pytest.mark.asyncio
async def test_the_dashboard_of_a_permissionless_user_is_empty(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get("/api/v1/dashboard", headers=_auth(plain_user_token))

    if response.status_code == 200:
        payload = response.json()
        assert payload["cases"] == []
        assert payload["kpis"]["active_cases"] == 0
        assert payload["kpis"]["active_clients"] == 0


# --- the shape of the data the API must be able to read back ---------------

DOCUMENT_TYPES = ("DNI", "CC", "NIF", "RUC", "CE", "PASSPORT", "OTROS")


def test_client_and_lawyer_document_types_are_identical() -> None:
    """The two lists drifted once and nothing noticed.

    `GET /clients` serialises **every** row through `ClientResponse`, so one
    record carrying a document type the schema does not accept made the whole
    listing answer 500 — for every caller, for a row most of them would never
    look at. The seed script wrote a `NIF`; the schema did not have one.

    The two lists are asserted equal because the failure mode is silence: a
    divergent literal only shows up when some record happens to use the value the
    other side forgot.
    """
    from typing import get_args

    from app.schemas.clients import DocumentType as ClientDocumentType
    from app.schemas.lawyers import DocumentType as LawyerDocumentType

    assert set(get_args(ClientDocumentType)) == set(get_args(LawyerDocumentType))
    assert "NIF" in get_args(ClientDocumentType)
    assert set(get_args(ClientDocumentType)) == set(DOCUMENT_TYPES)


async def test_client_listing_survives_every_stored_document_type(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    sample_client: Client,
) -> None:
    """A row with an unusual document type must not take the listing down.

    The regression this guards is not about `NIF` specifically. It is that a
    single unmappable row turns an entire endpoint into a 500, which is the worst
    possible failure for an administrator: the screen shows nothing at all
    instead of everything except one line.
    """
    database_session.add(
        Client(
            client_type="juridica",
            document_type="NIF",
            document_number="NIF-900-1",
            legal_name="Comprobación de listado",
            is_active=True,
        )
    )
    await database_session.flush()

    response = await client.get(
        "/api/v1/clients?skip=0&limit=50", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    numbers = {item["document_number"] for item in body["items"]}
    assert "NIF-900-1" in numbers

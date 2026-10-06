"""Retention policy tests.

The single most important property here is negative: the policy must never
delete content. PROJECT_RULES rule 5 forbids removing legal records, so these
tests assert both the positive behaviour (archiving) and the absence of the
destructive one (no deletions, legal hold respected).
"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import StorageTier
from app.models import Case, ChangeLog, Document, DocumentDownload
from app.schemas.documents import DocumentCreate
from app.services.documents import DocumentService
from app.services.integrity import IntegrityService
from app.services.retention import RetentionError, RetentionService
from app.services.storage_local import LocalStorage

PDF = b"%PDF-1.7\n1 0 obj\n<< /Catalogo >>\nendobj\n%%EOF"
DOCUMENTS = "/api/v1/documents"
NOW = datetime.now(UTC)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _settings(hot_days: int = 90) -> Settings:
    return Settings(storage_root=".tmp/test", retention_hot_days=hot_days)


def _payload(case_id: UUID, title: str) -> DocumentCreate:
    return DocumentCreate(case_id=case_id, document_type="contrato", title=title)


async def _document_with_versions(
    session: AsyncSession,
    case: Case,
    storage: LocalStorage,
    *,
    count: int = 2,
    age_days: int = 200,
) -> Document:
    service = DocumentService(session, storage)
    document = await service.create_document(_payload(case.id, "Contrato con historial"))
    created = NOW - timedelta(days=age_days)
    for index in range(count):
        payload = PDF + f" version {index}".encode()
        version = await service.add_version(
            document, payload, f"contrato-v{index}.pdf", declared_mime="application/pdf"
        )
        version.created_at = created + timedelta(minutes=index)
    await session.flush()
    return document


# --- Planning -----------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_ignores_the_current_version(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)

    candidates = await RetentionService(
        database_session, document_storage, _settings()
    ).plan(now=NOW)

    assert [c.version_id for c in candidates] != [document.versions[-1].id]


@pytest.mark.asyncio
async def test_plan_ignores_recent_versions(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    await _document_with_versions(
        database_session, sample_case, document_storage, age_days=5
    )

    candidates = await RetentionService(
        database_session, document_storage, _settings()
    ).plan(now=NOW)

    assert candidates == []


@pytest.mark.asyncio
async def test_plan_selects_superseded_old_versions(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)
    superseded = document.versions[0]

    candidates = await RetentionService(
        database_session, document_storage, _settings()
    ).plan(now=NOW)

    assert [c.version_id for c in candidates] == [superseded.id]
    assert candidates[0].age_days >= 199


@pytest.mark.asyncio
async def test_plan_respects_legal_hold(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)
    document.legal_hold = True
    document.legal_hold_reason = "Procedimiento judicial en curso"
    await database_session.flush()

    candidates = await RetentionService(
        database_session, document_storage, _settings()
    ).plan(now=NOW)

    assert candidates == []


@pytest.mark.asyncio
async def test_plan_is_empty_for_a_single_version(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    await _document_with_versions(
        database_session, sample_case, document_storage, count=1
    )

    candidates = await RetentionService(
        database_session, document_storage, _settings()
    ).plan(now=NOW)

    assert candidates == []


@pytest.mark.asyncio
async def test_plan_rejects_a_negative_configuration(
    database_session: AsyncSession, document_storage: LocalStorage
) -> None:
    service = RetentionService(database_session, document_storage, _settings(hot_days=-1))

    with pytest.raises(RetentionError):
        await service.plan(now=NOW)


# --- Applying ------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_archives_and_keeps_the_content(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)
    superseded = document.versions[0]
    original_key = superseded.storage_key
    assert await document_storage.exists(original_key) is True

    report = await RetentionService(
        database_session, document_storage, _settings()
    ).apply(now=NOW)

    assert report.archived == 1
    assert report.failed == 0
    assert superseded.tier == StorageTier.ARCHIVE.value
    assert superseded.tiered_at is not None
    # The decisive assertion: the bytes are still there.
    assert await document_storage.read(original_key) == PDF + b" version 0"
    assert document.versions[-1].tier == StorageTier.HOT.value


@pytest.mark.asyncio
async def test_apply_never_calls_delete(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    """A deleted key would mean the retention policy destroyed a legal record."""
    document = await _document_with_versions(database_session, sample_case, document_storage)
    keys = [version.storage_key for version in document.versions]

    deleted: list[str] = []
    original_delete = document_storage.delete

    async def spy(key: str) -> None:
        deleted.append(key)
        await original_delete(key)

    document_storage.delete = spy  # type: ignore[method-assign]
    await RetentionService(database_session, document_storage, _settings()).apply(now=NOW)

    assert deleted == []
    for key in keys:
        assert await document_storage.exists(key) is True


@pytest.mark.asyncio
async def test_apply_skips_legal_hold(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)
    document.legal_hold = True
    await database_session.flush()

    report = await RetentionService(
        database_session, document_storage, _settings()
    ).apply(now=NOW)

    assert report.archived == 0
    assert report.examined == 0
    assert all(version.tier == StorageTier.HOT.value for version in document.versions)


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)

    report = await RetentionService(database_session, document_storage, _settings()).apply(
        now=NOW, dry_run=True
    )

    assert report.dry_run is True
    assert report.examined == 1
    assert report.archived == 0
    assert all(version.tier == StorageTier.HOT.value for version in document.versions)


@pytest.mark.asyncio
async def test_apply_is_idempotent(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)
    service = RetentionService(database_session, document_storage, _settings())

    first = await service.apply(now=NOW)
    second = await service.apply(now=NOW)

    assert first.archived == 1
    assert second.archived == 0


@pytest.mark.asyncio
async def test_apply_records_the_reason_in_the_audit_trail(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await _document_with_versions(database_session, sample_case, document_storage)
    superseded = document.versions[0]

    await RetentionService(database_session, document_storage, _settings()).apply(now=NOW)

    entry = await database_session.scalar(
        select(ChangeLog).where(
            ChangeLog.entity == "document_retention",
            ChangeLog.entity_id == superseded.id,
        )
    )
    assert entry is not None
    assert entry.field_name == "tier"
    assert entry.old_value == StorageTier.HOT.value
    assert entry.new_value == StorageTier.ARCHIVE.value
    assert entry.change_reason is not None
    assert "superada" in entry.change_reason


@pytest.mark.asyncio
async def test_apply_counts_tiers(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)
    service = RetentionService(database_session, document_storage, _settings())
    await service.apply(now=NOW)

    totals = await service.count_by_tier()

    assert totals[StorageTier.HOT.value] == 1
    assert totals[StorageTier.ARCHIVE.value] == 1


@pytest.mark.asyncio
async def test_apply_reports_a_digest_mismatch_without_tiering(
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    """A corrupted file must fail loudly instead of being silently archived."""
    document = await _document_with_versions(database_session, sample_case, document_storage)
    superseded = document.versions[0]
    await document_storage.write(superseded.storage_key, b"contenido manipulado")

    report = await RetentionService(
        database_session, document_storage, _settings()
    ).apply(now=NOW)

    assert report.archived == 0
    assert report.failed == 1
    assert report.errors
    assert superseded.tier == StorageTier.HOT.value


# --- API -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_endpoint_requires_permission(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get(
        f"{DOCUMENTS}/retention/report", headers=_auth(plain_user_token)
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_report_endpoint_summarises(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{DOCUMENTS}/retention/report", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["hot_days"] == 90
    assert payload["eligible"] == 0
    assert payload["legal_holds"] == 0
    assert payload["total_by_tier"] == {}
    assert payload["native_tiers"] is False


@pytest.mark.asyncio
async def test_apply_endpoint_requires_permission(client: AsyncClient, staff_token: str) -> None:
    response = await client.post(f"{DOCUMENTS}/retention/apply", headers=_auth(staff_token))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_apply_endpoint_dry_run_is_safe(client: AsyncClient, admin_token: str) -> None:
    response = await client.post(
        f"{DOCUMENTS}/retention/apply?dry_run=true", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["archived"] == 0


@pytest.mark.asyncio
async def test_legal_hold_requires_a_reason(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    response = await client.patch(
        f"{DOCUMENTS}/{sample_document.id}/legal-hold",
        json={"active": True},
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_legal_hold_can_be_set_and_released(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    activated = await client.patch(
        f"{DOCUMENTS}/{sample_document.id}/legal-hold",
        json={"active": True, "reason": "Reclamacion pendiente de juicio"},
        headers=_auth(admin_token),
    )

    assert activated.status_code == 200
    assert activated.json()["legal_hold"] is True
    assert activated.json()["legal_hold_reason"] == "Reclamacion pendiente de juicio"
    assert activated.json()["legal_hold_at"] is not None

    released = await client.patch(
        f"{DOCUMENTS}/{sample_document.id}/legal-hold",
        json={"active": False},
        headers=_auth(admin_token),
    )

    assert released.status_code == 200
    assert released.json()["legal_hold"] is False
    assert released.json()["legal_hold_reason"] is None


@pytest.mark.asyncio
async def test_legal_hold_requires_permission(
    client: AsyncClient, staff_token: str, sample_document: Document
) -> None:
    response = await client.patch(
        f"{DOCUMENTS}/{sample_document.id}/legal-hold",
        json={"active": True, "reason": "x"},
        headers=_auth(staff_token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_legal_hold_on_unknown_document_is_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.patch(
        f"{DOCUMENTS}/{uuid4()}/legal-hold",
        json={"active": True, "reason": "x"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_version_response_exposes_the_tier(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    version = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("contrato.pdf", PDF, "application/pdf")},
        headers=_auth(admin_token),
    )

    detail = await client.get(f"{DOCUMENTS}/{sample_document.id}", headers=_auth(admin_token))

    assert version.status_code == 201
    assert version.json()["tier"] == StorageTier.HOT.value
    assert detail.json()["versions"][0]["tier"] == StorageTier.HOT.value
    assert detail.json()["legal_hold"] is False


@pytest.mark.asyncio
async def test_retention_routes_do_not_shadow_the_document_route(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    """/documents/retention/report must not be parsed as a document id."""
    report = await client.get(f"{DOCUMENTS}/retention/report", headers=_auth(admin_token))
    detail = await client.get(
        f"{DOCUMENTS}/{sample_document.id}", headers=_auth(admin_token)
    )

    assert report.status_code == 200
    assert "hot_days" in report.json()
    assert detail.status_code == 200
    assert detail.json()["id"] == str(sample_document.id)


@pytest.mark.asyncio
async def test_integrity_endpoint_requires_permission(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get(
        f"{DOCUMENTS}/integrity/latest", headers=_auth(plain_user_token)
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_integrity_endpoint_before_any_scan(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{DOCUMENTS}/integrity/latest", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_scan"] is None
    assert payload["total_versions"] == 0


@pytest.mark.asyncio
async def test_integrity_endpoint_reports_the_last_scan(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    sample_case: Case,
    document_storage: LocalStorage,
) -> None:
    document = await DocumentService(database_session, document_storage).create_document(
        _payload(sample_case.id, "Contrato verificado")
    )
    first = await DocumentService(database_session, document_storage).add_version(
        document, PDF, "v1.pdf", declared_mime="application/pdf"
    )
    await DocumentService(database_session, document_storage).add_version(
        document, PDF + b" v2", "v2.pdf", declared_mime="application/pdf"
    )
    await database_session.flush()
    await database_session.commit()

    service = IntegrityService(database_session, document_storage)
    await service.run()
    await database_session.commit()

    # The historical version is deliberately corrupted after the first scan.
    await document_storage.write(first.storage_key, b"X" * first.size_bytes)
    await service.run()
    await database_session.commit()

    response = await client.get(f"{DOCUMENTS}/integrity/latest", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_versions"] == 2
    scan = payload["last_scan"]
    assert scan is not None
    assert scan["status"] == "problems"
    assert scan["corrupted_count"] == 1
    assert scan["missing_count"] == 0
    assert len(scan["findings"]) == 1
    assert scan["findings"][0]["finding_type"] == "corrupted"
    assert scan["findings"][0]["version_id"] == str(first.id)


@pytest.mark.asyncio
async def test_integrity_endpoint_routes_before_the_document_route(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    """/documents/integrity/latest must not be parsed as a document id."""
    report = await client.get(f"{DOCUMENTS}/integrity/latest", headers=_auth(admin_token))
    detail = await client.get(
        f"{DOCUMENTS}/{sample_document.id}", headers=_auth(admin_token)
    )

    assert report.status_code == 200
    assert "total_versions" in report.json()
    assert detail.status_code == 200
    assert detail.json()["id"] == str(sample_document.id)


@pytest.mark.asyncio
async def test_downloads_still_work_after_archiving(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    document_storage: LocalStorage,
    database_session: AsyncSession,
) -> None:
    """An archived version must remain downloadable for the whole retention life."""
    service = DocumentService(database_session, document_storage)
    document = await service.create_document(_payload(sample_case.id, "Contrato archivable"))
    first = await service.add_version(
        document, PDF, "v1.pdf", declared_mime="application/pdf"
    )
    await service.add_version(
        document, PDF + b" v2", "v2.pdf", declared_mime="application/pdf"
    )
    first.created_at = NOW - timedelta(days=400)
    await database_session.flush()

    report = await RetentionService(
        database_session, document_storage, _settings()
    ).apply(now=NOW)
    await database_session.commit()

    download = await client.get(
        f"{DOCUMENTS}/{document.id}/versions/{first.id}/download",
        headers=_auth(admin_token),
    )

    assert report.archived == 1
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["x-content-sha256"] == sha256(PDF).hexdigest()

    audited = await database_session.scalar(
        select(func.count())
        .select_from(DocumentDownload)
        .where(DocumentDownload.version_id == first.id)
    )
    assert audited == 1

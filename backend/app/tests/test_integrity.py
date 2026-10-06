"""Integrity verification tests.

The properties that matter for a law firm, in order of severity:

1. Corruption is detected. A byte that changed on disk must be reported, not
   served.
2. Nothing is ever repaired. The verifier has no write path to content.
3. Missing content is reported rather than silently tolerated.
4. A run is recorded, so verification history exists for an auditor.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, DocumentVersion, IntegrityFinding, IntegrityScan
from app.schemas.documents import DocumentCreate
from app.services.documents import DocumentService
from app.services.integrity import (
    BLOCKING_FINDINGS,
    FindingType,
    IntegrityService,
    ScanMode,
    ScanStatus,
)
from app.services.storage import StorageError, StorageTier, StoredObject
from app.services.storage_local import LocalStorage

PDF = b"%PDF-1.7\n1 0 obj\n<< /Catalogo >>\nendobj\n%%EOF"


async def _document_with_versions(
    session: AsyncSession,
    case: Case,
    storage: LocalStorage,
    *,
    count: int = 2,
) -> list[DocumentVersion]:
    service = DocumentService(session, storage)
    document = await service.create_document(
        DocumentCreate(case_id=case.id, document_type="contrato", title="Contrato")
    )
    versions = []
    for index in range(count):
        versions.append(
            await service.add_version(
                document,
                PDF + f" version {index}".encode(),
                f"v{index}.pdf",
                declared_mime="application/pdf",
            )
        )
    await session.flush()
    return versions


# --- Detecting problems --------------------------------------------------


@pytest.mark.asyncio
async def test_clean_content_verifies(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)

    report = await IntegrityService(database_session, document_storage).run()

    assert report.checked == 2
    assert report.ok == 2
    assert report.healthy is True
    assert report.status == str(ScanStatus.OK)
    assert report.blocking == 0


@pytest.mark.asyncio
async def test_corrupted_content_is_detected(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    versions = await _document_with_versions(
        database_session, sample_case, document_storage
    )
    target = versions[0]
    # Simulate bit rot: the file stays the same length but changes.
    await document_storage.write(target.storage_key, b"X" * target.size_bytes)

    report = await IntegrityService(database_session, document_storage).run()

    assert report.corrupted == 1
    assert report.healthy is False
    assert report.status == str(ScanStatus.PROBLEMS)
    finding = next(f for f in report.findings if f.finding_type is FindingType.CORRUPTED)
    assert finding.version_id == target.id
    assert finding.expected_sha256 == target.sha256
    assert finding.actual_sha256 != target.sha256
    assert FindingType.CORRUPTED in BLOCKING_FINDINGS


@pytest.mark.asyncio
async def test_truncated_content_is_detected_by_size(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    versions = await _document_with_versions(
        database_session, sample_case, document_storage
    )
    target = versions[0]
    await document_storage.write(target.storage_key, b"%PDF truncado")

    report = await IntegrityService(database_session, document_storage).run()

    assert report.size_mismatch == 1
    assert report.corrupted == 0, "a size mismatch must not need the content read"


@pytest.mark.asyncio
async def test_missing_content_is_detected(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    versions = await _document_with_versions(
        database_session, sample_case, document_storage
    )
    target = versions[0]
    await document_storage.delete(target.storage_key)

    report = await IntegrityService(database_session, document_storage).run()

    assert report.missing == 1
    assert report.healthy is False
    finding = next(f for f in report.findings if f.finding_type is FindingType.MISSING)
    assert finding.version_id == target.id


@pytest.mark.asyncio
async def test_unreadable_content_is_reported_not_raised(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    async def exploding_read(key: str) -> bytes:
        raise StorageError("bucket no disponible")

    document_storage.read = exploding_read  # type: ignore[method-assign]
    await _document_with_versions(database_session, sample_case, document_storage)

    report = await IntegrityService(database_session, document_storage).run()

    assert report.unreadable == 2
    assert report.healthy is False
    assert all(f.detail for f in report.findings)


@pytest.mark.asyncio
async def test_orphan_object_is_detected_only_when_requested(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)
    stray = f"cases/{uuid4()}/documents/{uuid4()}/v9-huerfano.pdf"
    await document_storage.write(stray, b"contenido sin fila")

    without = await IntegrityService(database_session, document_storage).run()
    with_orphans = await IntegrityService(
        database_session, document_storage
    ).run(check_orphans=True)

    assert without.orphaned == 0
    assert with_orphans.orphaned == 1
    finding = next(f for f in with_orphans.findings if f.finding_type is FindingType.ORPHANED)
    assert finding.storage_key == stray
    assert finding.version_id is None


@pytest.mark.asyncio
async def test_partial_files_are_not_reported_as_orphans(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    """An interrupted write must not look like an intruder object."""
    await _document_with_versions(database_session, sample_case, document_storage)
    temporary = document_storage.root / "cases" / "x" / "documents" / "y" / ".v1.pdf.partial"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(b"basura")

    report = await IntegrityService(database_session, document_storage).run(check_orphans=True)

    assert report.orphaned == 0


# --- Read only guarantee --------------------------------------------------


@pytest.mark.asyncio
async def test_verification_never_writes_or_deletes(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    """A verifier that can modify content is a verifier you cannot trust."""
    writes: list[str] = []
    deletes: list[str] = []
    original_write = document_storage.write
    original_delete = document_storage.delete

    async def spy_write(
        key: str, content: bytes, *, tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        writes.append(key)
        return await original_write(key, content, tier=tier)

    async def spy_delete(key: str) -> None:
        deletes.append(key)
        await original_delete(key)

    document_storage.write = spy_write  # type: ignore[method-assign]
    document_storage.delete = spy_delete  # type: ignore[method-assign]
    await _document_with_versions(database_session, sample_case, document_storage)
    writes.clear()

    await IntegrityService(database_session, document_storage).run(check_orphans=True)

    assert writes == [], "verification must never write document content"
    assert deletes == [], "verification must never delete anything"


@pytest.mark.asyncio
async def test_verification_does_not_change_the_tier(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    tiers: list[str] = []
    original = document_storage.set_tier

    async def spy_set_tier(
        key: str, tier: StorageTier, *, expected_sha256: str | None = None
    ) -> bool:
        tiers.append(str(tier))
        return await original(key, tier, expected_sha256=expected_sha256)

    document_storage.set_tier = spy_set_tier  # type: ignore[method-assign]
    await _document_with_versions(database_session, sample_case, document_storage)

    await IntegrityService(database_session, document_storage).run(check_orphans=True)

    assert tiers == []


# --- Persistence of the run ----------------------------------------------


@pytest.mark.asyncio
async def test_run_is_recorded_with_its_findings(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    versions = await _document_with_versions(
        database_session, sample_case, document_storage
    )
    await document_storage.delete(versions[0].storage_key)

    service = IntegrityService(database_session, document_storage)
    await service.run()

    scan = await service.latest_scan()
    assert scan is not None
    assert scan.status == str(ScanStatus.PROBLEMS)
    assert scan.missing_count == 1
    assert scan.checked == 2
    assert scan.backend == "LocalStorage"
    assert scan.finished_at is not None
    assert scan.duration_seconds is not None
    assert len(scan.findings) == 1
    assert scan.findings[0].finding_type == str(FindingType.MISSING)

    stored = await database_session.scalar(
        select(func.count()).select_from(IntegrityFinding).where(
            IntegrityFinding.scan_id == scan.id
        )
    )
    assert stored == 1


@pytest.mark.asyncio
async def test_clean_run_stores_no_finding_rows(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)

    service = IntegrityService(database_session, document_storage)
    await service.run()

    total = await database_session.scalar(select(func.count()).select_from(IntegrityFinding))
    scan = await service.latest_scan()
    assert total == 0
    assert scan is not None
    assert scan.ok_count == 2


@pytest.mark.asyncio
async def test_scan_history_is_ordered_newest_first(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)
    service = IntegrityService(database_session, document_storage)

    await service.run()
    second = await service.run()

    latest = await service.latest_scan()
    assert latest is not None
    assert latest.checked == second.checked
    total = await database_session.scalar(select(func.count()).select_from(IntegrityScan))
    assert total == 2


@pytest.mark.asyncio
async def test_findings_are_retrievable_per_version(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    versions = await _document_with_versions(
        database_session, sample_case, document_storage
    )
    target = versions[0]
    await document_storage.write(target.storage_key, b"X" * target.size_bytes)
    service = IntegrityService(database_session, document_storage)

    await service.run()
    findings = await service.findings_for_version(target.id)

    assert len(findings) == 1
    assert findings[0].version_id == target.id
    assert findings[0].finding_type == str(FindingType.CORRUPTED)


@pytest.mark.asyncio
async def test_persist_can_be_disabled(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)

    await IntegrityService(database_session, document_storage).run(persist=False)

    total = await database_session.scalar(select(func.count()).select_from(IntegrityScan))
    assert total == 0


# --- Modes ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_sample_mode_checks_a_subset(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage, count=5)

    report = await IntegrityService(database_session, document_storage).run(
        mode=ScanMode.SAMPLE, sample=2
    )

    assert report.checked == 2
    assert report.mode == str(ScanMode.SAMPLE)
    assert report.detail is not None
    assert "muestra" in report.detail


@pytest.mark.asyncio
async def test_sample_mode_is_deterministic(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage, count=6)
    service = IntegrityService(database_session, document_storage)

    first = await service.run(mode=ScanMode.SAMPLE, sample=3, persist=False)
    second = await service.run(mode=ScanMode.SAMPLE, sample=3, persist=False)

    assert [f.storage_key for f in first.findings] == [
        f.storage_key for f in second.findings
    ]


@pytest.mark.asyncio
async def test_sample_mode_has_a_default_size(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage)

    report = await IntegrityService(database_session, document_storage).run(
        mode=ScanMode.SAMPLE
    )

    assert report.checked > 0


@pytest.mark.asyncio
async def test_full_mode_ignores_a_sample_size(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage, count=5)

    report = await IntegrityService(database_session, document_storage).run(
        mode=ScanMode.FULL, sample=1
    )

    assert report.checked == 5


@pytest.mark.asyncio
async def test_run_on_an_empty_store(
    database_session: AsyncSession, document_storage: LocalStorage
) -> None:
    report = await IntegrityService(database_session, document_storage).run()

    assert report.checked == 0
    assert report.healthy is True


@pytest.mark.asyncio
async def test_report_is_json_serialisable(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    import json

    await _document_with_versions(database_session, sample_case, document_storage)

    report = await IntegrityService(database_session, document_storage).run()
    payload = report.as_dict()

    assert json.loads(json.dumps(payload))["checked"] == 2
    assert "findings" not in report.as_dict(include_findings=False)


@pytest.mark.asyncio
async def test_total_versions_reports_the_inventory(
    database_session: AsyncSession, sample_case: Case, document_storage: LocalStorage
) -> None:
    await _document_with_versions(database_session, sample_case, document_storage, count=3)

    service = IntegrityService(database_session, document_storage)

    assert await service.total_versions() == 3


# --- Storage contract additions ------------------------------------------


@pytest.mark.asyncio
async def test_iter_keys_lists_every_stored_object(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    keys = [storage.build_key(uuid4(), uuid4(), 1, ".pdf") for _ in range(3)]
    for key in keys:
        await storage.write(key, PDF)

    listed = [key async for key in storage.iter_keys()]

    assert sorted(listed) == sorted(keys)


@pytest.mark.asyncio
async def test_iter_keys_respects_the_prefix(tmp_path: Path) -> None:
    """A prefix is a leading path segment, exactly like in S3."""
    storage = LocalStorage(tmp_path)
    inside = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    (tmp_path / "otra" / "carpeta").mkdir(parents=True)
    outside = tmp_path / "otra" / "carpeta" / "v1.pdf"
    outside.write_bytes(PDF)
    await storage.write(inside, PDF)

    everything = [key async for key in storage.iter_keys()]
    only_cases = [key async for key in storage.iter_keys(prefix="cases/")]
    only_other = [key async for key in storage.iter_keys(prefix="otra/")]
    missing = [key async for key in storage.iter_keys(prefix="evidencias/")]

    assert sorted(everything) == sorted([inside, "otra/carpeta/v1.pdf"])
    assert only_cases == [inside]
    assert only_other == ["otra/carpeta/v1.pdf"]
    assert missing == []


@pytest.mark.asyncio
async def test_iter_keys_on_a_missing_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "no-existe")

    assert [key async for key in storage.iter_keys()] == []


@pytest.mark.asyncio
async def test_stat_returns_none_for_a_missing_key(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    assert await storage.stat("cases/fantasma/v1.pdf") is None


@pytest.mark.asyncio
async def test_stat_reports_the_size(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF)

    stat = await storage.stat(key)

    assert stat is not None
    assert stat.size_bytes == len(PDF)
    assert stat.tier is StorageTier.HOT


def test_blocking_findings_cover_the_dangerous_cases() -> None:
    assert FindingType.MISSING in BLOCKING_FINDINGS
    assert FindingType.CORRUPTED in BLOCKING_FINDINGS
    assert FindingType.SIZE_MISMATCH in BLOCKING_FINDINGS
    assert FindingType.ORPHANED not in BLOCKING_FINDINGS
    assert FindingType.UNREADABLE not in BLOCKING_FINDINGS
    assert FindingType.OK not in BLOCKING_FINDINGS
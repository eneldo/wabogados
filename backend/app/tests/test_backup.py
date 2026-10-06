"""Backup and restore verification tests.

These run against a real PostgreSQL because the whole point of the feature is
that a real `pg_dump` can be restored. A mocked `pg_restore` would prove only
that the mock works.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.backup import (
    CRITICAL_TABLES,
    BackupError,
    BackupService,
    redact,
)

DATABASE_URL = "postgresql+asyncpg://wabogados:local-development-only@postgres-test:5432/wabogados_test"


@pytest.fixture
def service(tmp_path: Path) -> BackupService:
    return BackupService(DATABASE_URL, backup_dir=tmp_path / "backups")


# -- Secrets must never leak ---------------------------------------------


def test_redact_hides_the_password() -> None:
    redacted = redact(DATABASE_URL)

    assert "local-development-only" not in redacted
    assert ":***@" in redacted
    assert "wabogados_test" in redacted


def test_redact_keeps_the_usable_parts() -> None:
    redacted = redact(DATABASE_URL)

    assert redacted.startswith("postgresql+asyncpg://")
    assert "@postgres-test:5432/" in redacted


def test_redact_without_credentials() -> None:
    assert redact("postgresql+asyncpg://localhost/db") == "postgresql+asyncpg://localhost/db"


def test_redact_survives_a_malformed_url() -> None:
    assert redact("no-es-una-url") == "no-es-una-url"


# -- Dump ------------------------------------------------------------------


def test_dump_creates_a_file_with_a_digest(service: BackupService) -> None:
    result = service.dump(tag="prueba")

    assert result.path.is_file()
    assert result.size_bytes > 0
    assert len(result.sha256) == 64
    assert service.digest_of(result.path) == result.sha256
    assert "prueba" in result.path.name


def test_dump_name_is_timestamped_and_scoped(service: BackupService) -> None:
    result = service.dump()

    assert result.path.name.startswith("wabogados-")
    assert result.path.name.endswith(".dump")
    assert result.path.parent == service.backup_dir


def test_dump_tag_is_sanitised(service: BackupService) -> None:
    result = service.dump(tag="../../etc/passwd")

    assert ".." not in result.path.name
    assert "/" not in result.path.name


def test_dump_requires_the_url_to_be_defined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(BackupError):
        BackupService(None)


# -- Manifest --------------------------------------------------------------


def test_manifest_records_the_restoration_facts(service: BackupService) -> None:
    artifact = service.dump()
    manifest = service.write_manifest(
        artifact, {"alembic_revision": "d6e7f8a9b0c1", "storage_backend": "local"}
    )

    payload = json.loads(manifest.read_text())

    assert payload["sha256"] == artifact.sha256
    assert payload["alembic_revision"] == "d6e7f8a9b0c1"
    assert payload["storage_backend"] == "local"
    assert "local-development-only" not in json.dumps(payload)


# -- Prune -----------------------------------------------------------------


def test_prune_keeps_the_requested_number(service: BackupService) -> None:
    service.backup_dir.mkdir(parents=True, exist_ok=True)
    for index in range(5):
        (service.backup_dir / f"wabogados-2026010{index}T000000Z.dump").write_bytes(b"x")

    removed = service.prune(keep=2)

    remaining = sorted(path.name for path in service.backup_dir.glob("*.dump"))
    assert len(remaining) == 2
    assert len(removed) == 3


def test_prune_refuses_to_delete_everything(service: BackupService) -> None:
    with pytest.raises(BackupError):
        service.prune(keep=0)


def test_prune_on_an_empty_directory_is_safe(service: BackupService) -> None:
    service.backup_dir.mkdir(parents=True, exist_ok=True)

    assert service.prune(keep=3) == []


# -- Restore verification ---------------------------------------------------


@pytest.mark.asyncio
async def test_restore_verification_proves_the_backup_is_usable(
    service: BackupService,
) -> None:
    """The headline claim: a fresh dump restores and contains the real tables."""
    artifact = service.dump(tag="verificacion")

    report = await service.verify_restore(
        artifact.path, expected_sha256=artifact.sha256
    )

    assert report.restored is True, report.errors
    assert report.dump_digest_matches is True
    assert report.critical_tables_present is True, report.errors
    assert report.alembic_revision is not None
    assert report.table_count >= len(CRITICAL_TABLES)
    assert report.healthy is True, report.errors
    assert report.errors == []
    assert report.duration_seconds > 0


@pytest.mark.asyncio
async def test_restore_reports_the_row_counts(service: BackupService) -> None:
    artifact = service.dump()

    report = await service.verify_restore(artifact.path)

    assert set(CRITICAL_TABLES) <= set(report.row_counts)
    assert all(count >= 0 for count in report.row_counts.values())


@pytest.mark.asyncio
async def test_restore_rejects_a_tampered_dump(service: BackupService) -> None:
    artifact = service.dump()
    artifact.path.write_bytes(artifact.path.read_bytes() + b"corrupto")

    report = await service.verify_restore(
        artifact.path, expected_sha256=artifact.sha256
    )

    assert report.restored is False
    assert report.dump_digest_matches is False
    assert report.healthy is False
    assert any("digest" in error for error in report.errors)


@pytest.mark.asyncio
async def test_restore_of_a_missing_file_fails_cleanly(service: BackupService) -> None:
    report = await service.verify_restore(service.backup_dir / "no-existe.dump")

    assert report.restored is False
    assert report.healthy is False
    assert report.errors


@pytest.mark.asyncio
async def test_restore_drops_the_scratch_database(service: BackupService) -> None:
    """A verification run must not leave temporary databases behind."""
    artifact = service.dump()

    await service.verify_restore(artifact.path)

    assert service._connection_args()  # the scratch database was created and dropped
    leftovers = await _scratch_databases(service)
    assert leftovers == []


async def _scratch_databases(service: BackupService) -> list[str]:
    from sqlalchemy import text

    from app.db.session import SessionFactory

    async with SessionFactory() as session:
        rows = await session.execute(
            text(
                "SELECT datname FROM pg_database WHERE datname LIKE 'wabogados_verify_%'"
            )
        )
        return [str(row[0]) for row in rows.all()]


@pytest.mark.asyncio
async def test_report_is_json_serialisable(service: BackupService) -> None:
    artifact = service.dump()

    report = await service.verify_restore(artifact.path)
    payload = json.loads(json.dumps(report.as_dict()))

    assert payload["healthy"] is True
    assert payload["restored"] is True


@pytest.mark.asyncio
async def test_database_session_is_unaffected_by_the_verification(
    service: BackupService,
    database_session: AsyncSession,
) -> None:
    """Verification uses a scratch database, so the live one keeps working."""
    from sqlalchemy import text

    artifact = service.dump()
    await service.verify_restore(artifact.path)

    value = await database_session.scalar(text("SELECT 1"))

    assert value == 1


def test_critical_tables_cover_the_legal_record() -> None:
    assert "documents" in CRITICAL_TABLES
    assert "document_versions" in CRITICAL_TABLES
    assert "change_logs" in CRITICAL_TABLES
    assert "audit_logs" in CRITICAL_TABLES
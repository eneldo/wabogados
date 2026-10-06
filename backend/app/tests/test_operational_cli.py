"""Operational CLI tests.

The thin wrappers around the services are already covered indirectly, but the
argument handling and the exit codes are not: a scheduler alerts on those
numbers, so a regression there would silently stop alerting.
"""

import json
from pathlib import Path
from uuid import UUID

import pytest

from app.cli import (
    apply_retention,
    backup_database,
    import_documents_to_s3,
    remote_backup,
    verify_backup,
    verify_integrity,
)
from app.core.config import get_settings

# --- verify_integrity ----------------------------------------------------


def test_verify_integrity_defaults_to_a_full_scan() -> None:
    args = verify_integrity.parse_args([])

    assert args.mode == "full"
    assert args.sample is None
    assert args.check_orphans is False


def test_verify_integrity_accepts_sample_mode() -> None:
    args = verify_integrity.parse_args(["--mode", "sample", "--sample", "50"])

    assert args.mode == "sample"
    assert args.sample == 50


def test_verify_integrity_rejects_an_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        verify_integrity.parse_args(["--mode", "rapido"])


@pytest.mark.asyncio
async def test_verify_integrity_rejects_a_non_positive_sample() -> None:
    args = verify_integrity.parse_args(["--mode", "sample", "--sample", "0"])

    exit_code = await verify_integrity.run(args)

    assert exit_code == verify_integrity.EXIT_USAGE


def test_verify_integrity_exit_codes_are_distinct() -> None:
    codes = {
        verify_integrity.EXIT_OK,
        verify_integrity.EXIT_PROBLEMS,
        verify_integrity.EXIT_FAILED,
        verify_integrity.EXIT_USAGE,
    }
    assert len(codes) == 4


# --- verify_backup -------------------------------------------------------


def test_verify_backup_reads_the_digest_from_the_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "postgres.manifest.json"
    manifest.write_text(json.dumps({"sha256": "abc123"}), encoding="utf-8")

    args = verify_backup.parse_args(["--dump", "x.dump", "--manifest", str(manifest)])

    assert verify_backup._expected_digest(args) == "abc123"


def test_verify_backup_prefers_the_explicit_digest(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"sha256": "desde-manifiesto"}), encoding="utf-8")

    args = verify_backup.parse_args(
        ["--dump", "x.dump", "--manifest", str(manifest), "--sha256", " explicito "]
    )

    assert verify_backup._expected_digest(args) == "explicito"


def test_verify_backup_without_a_manifest_has_no_expected_digest() -> None:
    args = verify_backup.parse_args(["--dump", "x.dump"])

    assert verify_backup._expected_digest(args) is None


def test_verify_backup_ignores_a_manifest_without_a_digest(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"alembic_revision": "abc"}), encoding="utf-8")

    args = verify_backup.parse_args(["--dump", "x.dump", "--manifest", str(manifest)])

    assert verify_backup._expected_digest(args) is None


@pytest.mark.asyncio
async def test_verify_backup_rejects_a_missing_dump(tmp_path: Path) -> None:
    args = verify_backup.parse_args(["--dump", str(tmp_path / "no-existe.dump")])

    exit_code = await verify_backup.run(args)

    assert exit_code == verify_backup.EXIT_USAGE


@pytest.mark.asyncio
async def test_verify_backup_rejects_a_corrupt_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text("esto no es json", encoding="utf-8")
    dump = tmp_path / "x.dump"
    dump.write_bytes(b"x")

    args = verify_backup.parse_args(
        ["--dump", str(dump), "--manifest", str(manifest)]
    )

    exit_code = await verify_backup.run(args)

    assert exit_code == verify_backup.EXIT_USAGE


def test_verify_backup_requires_a_dump() -> None:
    with pytest.raises(SystemExit):
        verify_backup.parse_args([])


# --- backup_database -----------------------------------------------------


def test_backup_database_defaults() -> None:
    args = backup_database.parse_args([])

    assert args.skip_verify is False
    assert args.keep == 30
    assert args.backup_dir == Path(".tmp/backups")


def test_backup_database_accepts_the_documented_flags() -> None:
    args = backup_database.parse_args(
        ["--tag", "diaria", "--keep", "7", "--skip-verify", "--integrity", "--json"]
    )

    assert args.tag == "diaria"
    assert args.keep == 7
    assert args.skip_verify is True
    assert args.integrity is True
    assert args.json is True


# --- import_documents_to_s3 ----------------------------------------------


def test_import_cli_defaults(tmp_path: Path) -> None:
    args = import_documents_to_s3.parse_args(["--source-root", str(tmp_path)])

    assert args.dry_run is False
    assert args.limit == 1000
    assert args.rekey is False


def test_import_cli_accepts_dry_run_and_rekey() -> None:
    args = import_documents_to_s3.parse_args(["--dry-run", "--rekey"])

    assert args.dry_run is True
    assert args.rekey is True


@pytest.mark.asyncio
async def test_import_refuses_when_the_destination_is_not_s3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Migrating into local storage would rewrite every `storage_key` pointlessly."""
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

    args = import_documents_to_s3.parse_args(["--source-root", str(tmp_path)])
    exit_code = await import_documents_to_s3.run(args)

    get_settings.cache_clear()
    assert exit_code == 2


def test_import_report_is_serialisable() -> None:
    report = import_documents_to_s3.ImportReport(dry_run=True)

    payload = json.loads(json.dumps(report.as_dict()))

    assert payload["dry_run"] is True
    assert payload["imported"] == 0


# --- what the migration CLI must not get wrong ----------------------------


def test_import_cli_accepts_an_offset() -> None:
    """Without it, `--limit` alone re-processes the same first N rows forever."""
    args = import_documents_to_s3.parse_args(["--limit", "10", "--offset", "10"])

    assert args.offset == 10
    assert args.limit == 10


def test_import_defaults_to_no_offset() -> None:
    assert import_documents_to_s3.parse_args([]).offset == 0


def test_the_extension_comes_from_the_stored_key() -> None:
    """It used to invent `.bin`, which no later tool recognises as a PDF."""
    assert (
        import_documents_to_s3.extension_of(
            "cases/c1/documents/d1/v1-abcd1234.pdf"
        )
        == ".pdf"
    )
    assert import_documents_to_s3.extension_of("cases/c/documents/d/v1-ab.abc.webp") == ".webp"
    assert import_documents_to_s3.extension_of("media/m1/deadbeef") == ""


def test_a_key_without_a_dot_has_no_extension() -> None:
    assert import_documents_to_s3.extension_of("messages/c1/a1") == ""


def test_rekey_is_idempotent() -> None:
    """Re-running the migration must not mint a new key and rewrite the row.

    The token used to be `os.urandom(8)`, so every run produced a different key:
    the opposite of idempotent, and it silently multiplied objects in the bucket.
    """
    row_id = "b2c3d4e5-1111-2222-3333-444455556666"
    token = import_documents_to_s3.deterministic_token(row_id)

    assert import_documents_to_s3.deterministic_token(row_id) == token
    assert "-" not in token
    assert len(token) == 16


def test_different_rows_get_different_tokens() -> None:
    first = import_documents_to_s3.deterministic_token(
        "b2c3d4e5-1111-2222-3333-444455556666"
    )
    second = import_documents_to_s3.deterministic_token(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )

    assert first != second


def test_a_clean_run_exits_zero() -> None:
    report = import_documents_to_s3.ImportReport(
        examined=3, imported=2, skipped_existing=1
    )

    assert import_documents_to_s3.exit_code_for(report) == 0


def test_a_missing_local_file_fails_the_migration() -> None:
    """A deployment script must be able to tell a quiet run from a broken one."""
    report = import_documents_to_s3.ImportReport(examined=3, imported=1, missing_local=1)

    assert import_documents_to_s3.exit_code_for(report) == 4


def test_a_digest_mismatch_fails_the_migration() -> None:
    report = import_documents_to_s3.ImportReport(examined=1, digest_mismatch=1)

    assert import_documents_to_s3.exit_code_for(report) == 4


def test_a_rejected_write_fails_the_migration() -> None:
    report = import_documents_to_s3.ImportReport(examined=1, failed=1)

    assert import_documents_to_s3.exit_code_for(report) == 4


def test_the_exit_code_constants_are_distinct() -> None:
    codes = {
        import_documents_to_s3.EXIT_OK,
        import_documents_to_s3.EXIT_NOT_S3,
        import_documents_to_s3.EXIT_INCOMPLETE,
    }

    assert len(codes) == 3


def test_rekey_produces_a_stable_key_for_the_same_row() -> None:
    """End to end on the builder, because that is where the token is used."""
    from app.services.storage import build_key

    document_id = UUID("11111111-1111-1111-1111-111111111111")
    token = import_documents_to_s3.deterministic_token(
        "b2c3d4e5-1111-2222-3333-444455556666"
    )

    first = build_key(document_id, document_id, 2, ".pdf", token=token)
    second = build_key(document_id, document_id, 2, ".pdf", token=token)

    assert first == second
    assert first.endswith(".pdf")
    assert ".bin" not in first


def test_build_key_without_a_token_is_still_random() -> None:
    """Existing callers must keep the behaviour they had."""
    from app.services.storage import build_key

    document_id = UUID("11111111-1111-1111-1111-111111111111")

    assert build_key(document_id, document_id, 1, ".pdf") != build_key(
        document_id, document_id, 1, ".pdf"
    )


@pytest.mark.asyncio
async def test_remote_backup_status_reports_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "false")

    exit_code = await remote_backup.run(remote_backup.parse_args(["--status"]))
    output = capsys.readouterr().out

    get_settings.cache_clear()
    assert exit_code == remote_backup.EXIT_NOT_CONFIGURED
    assert "no sale del host" in output


@pytest.mark.asyncio
async def test_remote_backup_refuses_to_work_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A backup pipeline that quietly does nothing is worse than none."""
    get_settings.cache_clear()
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "false")

    exit_code = await remote_backup.run(
        remote_backup.parse_args(["--push", str(tmp_path)])
    )

    get_settings.cache_clear()
    assert exit_code == remote_backup.EXIT_NOT_CONFIGURED


def test_remote_backup_parses_a_push() -> None:
    args = remote_backup.parse_args(["--push", "backups/2026", "--pattern", "*"])

    assert args.push == Path("backups/2026")
    assert args.pattern == ["*"]


def test_remote_backup_no_verify_upload_is_available() -> None:
    args = remote_backup.parse_args(["--push", "x", "--no-verify-upload"])

    assert args.no_verify_upload is True


@pytest.mark.asyncio
async def test_remote_backup_requires_an_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "true")
    monkeypatch.setenv("BACKUP_REMOTE_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("BACKUP_REMOTE_ACCESS_KEY", "k")
    monkeypatch.setenv("BACKUP_REMOTE_SECRET_KEY", "s")
    get_settings.cache_clear()

    exit_code = await remote_backup.run(remote_backup.parse_args([]))

    get_settings.cache_clear()
    assert exit_code == remote_backup.EXIT_USAGE


# --- apply_retention -----------------------------------------------------


def test_apply_retention_defaults() -> None:
    args = apply_retention.parse_args([])

    assert args.dry_run is False
    assert args.limit == 500
    assert args.actor_id is None


def test_apply_retention_accepts_an_actor() -> None:
    args = apply_retention.parse_args(["--actor-id", "11111111-1111-1111-1111-111111111111"])

    assert args.actor_id is not None


def test_apply_retention_rejects_a_malformed_actor() -> None:
    with pytest.raises(SystemExit):
        apply_retention.parse_args(["--actor-id", "no-es-una-uuid"])
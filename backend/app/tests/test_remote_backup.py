"""Off site backup tests.

The property that justifies the whole feature: a copy that leaves the process is
not yet a backup. These tests use `moto` to emulate a second S3 location and
assert that a corrupted remote copy is detected rather than reported as success.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

from app.core.config import Settings
from app.services.remote_backup import (
    MANAGED_MARKER,
    RemoteBackup,
    RemoteBackupError,
    configuration_summary,
)

LOCAL_BUCKET = "wabogados-primary"
REMOTE_BUCKET = "wabogados-backups"
PAYLOAD = b"contenido de respaldo con contenido de respaldo"
OTHER = b"otro archivo"


@pytest.fixture
def s3_backend() -> Any:
    with mock_aws():
        import os

        os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=LOCAL_BUCKET)
        client.create_bucket(Bucket=REMOTE_BUCKET)
        yield client


@pytest.fixture
def remote(s3_backend: Any) -> RemoteBackup:
    return RemoteBackup(s3_backend, REMOTE_BUCKET, "wabogados")


@pytest.fixture
def dump(tmp_path: Path) -> Path:
    path = tmp_path / "postgres.dump"
    path.write_bytes(PAYLOAD)
    return path


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "backup_remote_enabled": True,
        "backup_remote_endpoint": "http://minio-backup:9000",
        "backup_remote_access_key": "backup-user",
        "backup_remote_secret_key": "backup-secret",
        "backup_remote_bucket": REMOTE_BUCKET,
        "backup_remote_prefix": "wabogados",
        "backup_remote_use_ssl": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# -- Configuration must fail loudly ---------------------------------------


def test_disabled_remote_is_an_explicit_error(s3_backend: Any) -> None:
    settings = _settings(backup_remote_enabled=False)

    with pytest.raises(RemoteBackupError) as excinfo:
        RemoteBackup.from_settings(settings)

    assert "no sale del host" in str(excinfo.value)


def test_missing_endpoint_is_rejected() -> None:
    with pytest.raises(RemoteBackupError):
        RemoteBackup.from_settings(_settings(backup_remote_endpoint=None))


def test_missing_credentials_are_rejected() -> None:
    with pytest.raises(RemoteBackupError):
        RemoteBackup.from_settings(_settings(backup_remote_access_key=None))

    with pytest.raises(RemoteBackupError):
        RemoteBackup.from_settings(_settings(backup_remote_secret_key=None))


def test_configuration_summary_hides_secrets() -> None:
    summary = configuration_summary(_settings())

    assert summary["enabled"] is True
    assert summary["credentials_present"] is True
    assert "backup-secret" not in json.dumps(summary)
    assert summary["bucket"] == REMOTE_BUCKET


def test_configuration_summary_when_absent() -> None:
    summary = configuration_summary(_settings(backup_remote_enabled=False))

    assert summary["enabled"] is False
    assert summary["credentials_present"] is True


# -- The off site target must actually be off site -------------------------


def test_backup_pointed_at_the_document_location_is_refused() -> None:
    """A backup in the document bucket protects nothing.

    `RESTORE.md` has always said the off site endpoint cannot be the server that
    holds the documents: one ransomware, one accidental `rm -rf`, and both copies
    of the same data disappear together. The rule existed only in prose, so the
    configuration that most defeats the whole feature was accepted.
    """
    settings = _settings(
        storage_backend="s3",
        s3_endpoint_url="https://minio-interno:9000",
        s3_bucket="wabogados-documents",
        backup_remote_endpoint="https://minio-interno:9000",
        backup_remote_bucket="wabogados-documents",
    )

    with pytest.raises(RemoteBackupError) as excinfo:
        RemoteBackup.from_settings(settings)

    assert "mismo" in str(excinfo.value)


def test_backup_on_another_bucket_of_the_same_server_is_allowed() -> None:
    """Different bucket, same server: unusual, but not the documented failure.

    The rule protects against the copy and the original dying together, which is
    what the same bucket means. Refusing every shared server would also refuse a
    legitimate setup, so this has to stay distinguishable.
    """
    settings = _settings(
        storage_backend="s3",
        s3_endpoint_url="https://minio-interno:9000",
        s3_bucket="wabogados-documents",
        backup_remote_endpoint="https://minio-interno:9000",
        backup_remote_bucket=REMOTE_BUCKET,
    )

    assert RemoteBackup.from_settings(settings).bucket == REMOTE_BUCKET


def test_local_storage_does_not_confuse_the_check() -> None:
    """With documents on disk there is no S3 to collide with."""
    settings = _settings(
        storage_backend="local",
        backup_remote_endpoint="https://s3.otro-proveedor.example",
        backup_remote_bucket=REMOTE_BUCKET,
    )

    assert RemoteBackup.from_settings(settings).bucket == REMOTE_BUCKET


def test_the_endpoint_comparison_ignores_a_trailing_slash() -> None:
    """`https://host` and `https://host/` are the same server.

    The difference is one character and it decides whether this check fires at
    all, which is exactly the kind of detail that makes a control optional.
    """
    settings = _settings(
        storage_backend="s3",
        s3_endpoint_url="https://minio-interno:9000",
        s3_bucket="wabogados-documents",
        backup_remote_endpoint="https://minio-interno:9000/",
        backup_remote_bucket="wabogados-documents",
    )

    with pytest.raises(RemoteBackupError):
        RemoteBackup.from_settings(settings)


# -- Transfer --------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_verifies_the_copy_by_reading_it_back(
    remote: RemoteBackup, dump: Path
) -> None:
    transfer = await remote.push_file(dump)

    assert transfer.verified is True
    assert transfer.verification_mode == "read-back"
    assert transfer.remote_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert transfer.healthy is True


@pytest.mark.asyncio
async def test_push_stores_the_digest_as_metadata(
    remote: RemoteBackup, s3_backend: Any, dump: Path
) -> None:
    transfer = await remote.push_file(dump)

    head = s3_backend.head_object(Bucket=REMOTE_BUCKET, Key=transfer.key)

    assert head["Metadata"]["sha256"] == transfer.local_sha256
    assert head["Metadata"]["wabogados-backup"] == "1"
    assert MANAGED_MARKER


@pytest.mark.asyncio
async def test_push_lands_under_the_configured_prefix(
    remote: RemoteBackup, dump: Path
) -> None:
    transfer = await remote.push_file(dump)

    assert transfer.key == f"wabogados/{dump.name}"


@pytest.mark.asyncio
async def test_push_rejects_a_missing_file(remote: RemoteBackup, tmp_path: Path) -> None:
    with pytest.raises(RemoteBackupError):
        await remote.push_file(tmp_path / "no-existe.dump")


@pytest.mark.asyncio
async def test_push_accepts_an_expected_digest(remote: RemoteBackup, dump: Path) -> None:
    digest = hashlib.sha256(PAYLOAD).hexdigest()

    transfer = await remote.push_file(dump, expected_sha256=digest)

    assert transfer.local_sha256 == digest
    assert transfer.verified is True


@pytest.mark.asyncio
async def test_a_corrupted_remote_copy_is_detected(
    remote: RemoteBackup, s3_backend: Any, dump: Path
) -> None:
    """The whole point: a bad copy must fail, not pass silently."""
    transfer = await remote.push_file(dump)
    # Simulate the remote returning different bytes than were sent.
    s3_backend.put_object(
        Bucket=REMOTE_BUCKET,
        Key=transfer.key,
        Body=OTHER,
        ContentMD5=_md5(OTHER),
        Metadata={"sha256": transfer.local_sha256, "wabogados-backup": "1"},
    )

    with pytest.raises(RemoteBackupError) as excinfo:
        await remote.verify_object(dump.name, transfer.local_sha256)

    assert "no coincide" in str(excinfo.value)


@pytest.mark.asyncio
async def test_metadata_only_mode_is_labelled_as_weaker(
    remote: RemoteBackup, dump: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("BACKUP_REMOTE_VERIFY_UPLOAD", "false")
    try:
        transfer = await remote.push_file(dump)
    finally:
        get_settings.cache_clear()

    assert transfer.verification_mode == "metadata-only"
    assert transfer.remote_sha256 is None
    assert "no se ha releído" in str(transfer.detail)


@pytest.mark.asyncio
async def test_push_directory_copies_every_file(remote: RemoteBackup, tmp_path: Path) -> None:
    (tmp_path / "postgres.dump").write_bytes(PAYLOAD)
    (tmp_path / "postgres.manifest.json").write_text('{"sha256": "x"}')
    (tmp_path / "objects").mkdir()
    (tmp_path / "objects" / "doc.pdf").write_bytes(OTHER)

    report = await remote.push_directory(tmp_path, patterns=("*",))

    assert report.healthy is True
    assert report.pushed == 2
    assert report.verified == 2
    assert report.failed == 0
    assert {t.name for t in report.transfers} == {
        "postgres.dump",
        "postgres.manifest.json",
    }


@pytest.mark.asyncio
async def test_push_directory_reports_a_missing_directory(
    remote: RemoteBackup, tmp_path: Path
) -> None:
    report = await remote.push_directory(tmp_path / "no-existe")

    assert report.healthy is False
    assert report.failed == 1
    assert report.errors


# -- Inspection and retrieval ----------------------------------------------


@pytest.mark.asyncio
async def test_verify_object_returns_the_digest(remote: RemoteBackup, dump: Path) -> None:
    await remote.push_file(dump)

    digest = await remote.verify_object(dump.name)

    assert digest == hashlib.sha256(PAYLOAD).hexdigest()


@pytest.mark.asyncio
async def test_verify_object_fails_on_an_unknown_name(remote: RemoteBackup) -> None:
    with pytest.raises(RemoteBackupError):
        await remote.verify_object("no-existe.dump")


@pytest.mark.asyncio
async def test_fetch_restores_the_exact_bytes(
    remote: RemoteBackup, dump: Path, tmp_path: Path
) -> None:
    await remote.push_file(dump)

    digest = await remote.fetch(dump.name, tmp_path / "restaurado.dump")

    assert digest == hashlib.sha256(PAYLOAD).hexdigest()
    assert (tmp_path / "restaurado.dump").read_bytes() == PAYLOAD


@pytest.mark.asyncio
async def test_fetch_rejects_a_digest_mismatch(
    remote: RemoteBackup, dump: Path, tmp_path: Path
) -> None:
    await remote.push_file(dump)
    destination = tmp_path / "restaurado.dump"

    with pytest.raises(RemoteBackupError):
        await remote.fetch(dump.name, destination, expected_sha256="0" * 64)

    assert not destination.exists(), "no debe escribir un archivo no verificado"


@pytest.mark.asyncio
async def test_list_backups_returns_what_was_pushed(
    remote: RemoteBackup, dump: Path
) -> None:
    await remote.push_file(dump)

    items = await remote.list_backups()

    assert [item.name for item in items] == [dump.name]
    assert items[0].size_bytes == len(PAYLOAD)


@pytest.mark.asyncio
async def test_list_backups_ignores_objects_outside_the_prefix(
    remote: RemoteBackup, s3_backend: Any, dump: Path
) -> None:
    await remote.push_file(dump)
    s3_backend.put_object(
        Bucket=REMOTE_BUCKET,
        Key="otro-sistema/ajeno.dump",
        Body=OTHER,
        ContentMD5=_md5(OTHER),
    )

    items = await remote.list_backups()

    assert [item.name for item in items] == [dump.name]


@pytest.mark.asyncio
async def test_ensure_bucket_creates_the_remote_bucket(s3_backend: Any) -> None:
    fresh = RemoteBackup(s3_backend, "bucket-nuevo", "wabogados")

    assert await fresh.ensure_bucket() is True
    assert await fresh.ensure_bucket() is False


# -- Retention -------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_keeps_the_newest(
    remote: RemoteBackup, s3_backend: Any, tmp_path: Path
) -> None:
    for index in range(4):
        path = tmp_path / f"dump-{index}.bin"
        path.write_bytes(PAYLOAD + str(index).encode())
        await remote.push_file(path)

    removed = await remote.prune(keep=2)

    remaining = {item.name for item in await remote.list_backups()}
    assert len(remaining) == 2
    assert len(removed) == 2


@pytest.mark.asyncio
async def test_prune_never_deletes_unmanaged_objects(
    remote: RemoteBackup, s3_backend: Any, dump: Path
) -> None:
    """Something this module did not write must survive retention."""
    await remote.push_file(dump)
    s3_backend.put_object(
        Bucket=REMOTE_BUCKET,
        Key="wabogados/ajeno-sin-marca.dump",
        Body=OTHER,
        ContentMD5=_md5(OTHER),
    )

    await remote.prune(keep=1)

    keys = {item.key for item in await remote.list_backups()}
    assert "wabogados/ajeno-sin-marca.dump" in keys


@pytest.mark.asyncio
async def test_prune_refuses_to_delete_everything(remote: RemoteBackup, dump: Path) -> None:
    await remote.push_file(dump)

    with pytest.raises(RemoteBackupError):
        await remote.prune(keep=0)


@pytest.mark.asyncio
async def test_prune_on_an_empty_remote_is_safe(remote: RemoteBackup) -> None:
    assert await remote.prune(keep=3) == []


def test_describe_marks_the_target(remote: RemoteBackup) -> None:
    assert remote.describe() == f"s3://{REMOTE_BUCKET}/wabogados"


def test_key_for_joins_the_prefix_without_doubling_slashes(
    s3_backend: Any,
) -> None:
    odd = RemoteBackup(s3_backend, REMOTE_BUCKET, "/wabogados/")

    assert odd.key_for("x.dump") == "wabogados/x.dump"


def _md5(content: bytes) -> str:
    import base64

    return base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode()
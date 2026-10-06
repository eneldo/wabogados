"""S3 storage backend contract tests.

`moto` emulates the S3 protocol in process, so these tests cover object
semantics (keys, missing objects, digests, storage classes) without a running
MinIO.

Two limits of this approach, stated so nobody mistakes it for full coverage:

- `moto` does not enforce IAM, so bucket privacy cannot be verified here. That
  control comes from the bucket having no public policy, not from these tests.
- `moto` does not validate `ContentMD5`, so a test cannot prove S3 rejects a
  corrupted transfer. The guard is asserted to be sent instead.
"""

import os
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from app.core.config import Settings
from app.services.storage import (
    StorageBackend,
    StorageError,
    StorageTier,
    initialize_storage,
)
from app.services.storage_local import LocalStorage
from app.services.storage_s3 import S3Storage, _content_md5

PDF = b"%PDF-1.7\n1 0 obj\n<< /Catalogo >>\nendobj\n%%EOF"
BUCKET = "wabogados-test"


def _settings(**overrides: object) -> Settings:
    base = {
        "storage_backend": "s3",
        "s3_endpoint_url": "http://localhost:9000",
        "s3_access_key": "test-key",
        "s3_secret_key": "test-secret",
        "s3_bucket": BUCKET,
        "s3_addressing_style": "path",
        "s3_use_ssl": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def s3_client() -> Iterator[Any]:
    with mock_aws():
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def storage(s3_client: Any) -> S3Storage:
    return S3Storage(s3_client, BUCKET)


def test_both_backends_satisfy_the_contract(storage: S3Storage, tmp_path: Path) -> None:
    local = LocalStorage(tmp_path)

    assert isinstance(storage, StorageBackend)
    assert isinstance(local, StorageBackend)


def test_both_backends_share_the_key_shape(tmp_path: Path) -> None:
    """Layout must match so switching backend does not orphan existing rows.

    The random component makes every key unique, so only the shape can match.
    """
    local = LocalStorage(tmp_path)
    case_id, document_id = uuid4(), uuid4()

    local_key = local.build_key(case_id, document_id, 3, ".pdf")
    from app.services.storage import build_key

    other_key = build_key(case_id, document_id, 3, ".pdf")

    local_prefix, other_prefix = local_key.rsplit("-", 1)[0], other_key.rsplit("-", 1)[0]
    assert local_prefix == other_prefix
    assert local_prefix.endswith("/v3")
    assert local_key.endswith(".pdf")
    assert ".." not in local_key
    assert local_key != other_key, "keys must be unique per call"


@pytest.mark.asyncio
async def test_s3_round_trip(storage: S3Storage) -> None:
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")

    stored = await storage.write(key, PDF)

    assert stored.sha256 == sha256(PDF).hexdigest()
    assert stored.size_bytes == len(PDF)
    assert await storage.read(key) == PDF
    assert await storage.exists(key) is True


@pytest.mark.asyncio
async def test_s3_missing_key_raises(storage: S3Storage) -> None:
    with pytest.raises(StorageError):
        await storage.read("cases/inexistente/v1.pdf")


@pytest.mark.asyncio
async def test_s3_exists_is_false_for_missing_key(storage: S3Storage) -> None:
    assert await storage.exists("cases/inexistente/v1.pdf") is False


@pytest.mark.asyncio
async def test_s3_delete_is_idempotent(storage: S3Storage) -> None:
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF)

    await storage.delete(key)
    await storage.delete(key)

    assert await storage.exists(key) is False


@pytest.mark.asyncio
async def test_s3_tier_change_keeps_the_object_readable(storage: S3Storage) -> None:
    """Archiving must not make a version temporarily undownloadable."""
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF)

    applied = await storage.set_tier(
        key, StorageTier.ARCHIVE, expected_sha256=sha256(PDF).hexdigest()
    )

    assert applied is True
    assert await storage.read(key) == PDF, "an archived version must stay retrievable"


@pytest.mark.asyncio
async def test_s3_tier_change_detects_corrupted_content(storage: S3Storage) -> None:
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF)

    with pytest.raises(StorageError):
        await storage.set_tier(key, StorageTier.ARCHIVE, expected_sha256="0" * 64)


@pytest.mark.asyncio
async def test_s3_tier_change_to_hot_is_a_no_op(storage: S3Storage) -> None:
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF)

    assert await storage.set_tier(key, StorageTier.HOT) is False


@pytest.mark.asyncio
async def test_ensure_bucket_creates_and_detects(s3_client: Any) -> None:
    storage = S3Storage(s3_client, BUCKET)

    assert await storage.ensure_bucket() is False, "the fixture bucket already exists"

    other = S3Storage(s3_client, "wabogados-nuevo")
    assert await other.ensure_bucket() is True
    assert await other.ensure_bucket() is False


@pytest.mark.asyncio
async def test_initialize_storage_enables_versioning(s3_client: Any) -> None:
    storage = S3Storage(s3_client, BUCKET)

    await initialize_storage(_settings(), storage=storage)

    response = s3_client.get_bucket_versioning(Bucket=BUCKET)
    assert response["Status"] == "Enabled"


@pytest.mark.asyncio
async def test_initialize_storage_creates_bucket_only_when_configured(
    s3_client: Any,
) -> None:
    bucket = "wabogados-startup"
    storage = S3Storage(s3_client, bucket)

    await initialize_storage(
        _settings(s3_bucket=bucket, s3_create_bucket=True), storage=storage
    )

    assert await storage.exists("missing") is False
    response = s3_client.get_bucket_versioning(Bucket=bucket)
    assert response["Status"] == "Enabled"


@pytest.mark.asyncio
async def test_initialize_storage_fails_when_bucket_is_missing(s3_client: Any) -> None:
    bucket = "wabogados-missing"
    storage = S3Storage(s3_client, bucket)

    with pytest.raises(StorageError):
        await initialize_storage(
            _settings(s3_bucket=bucket, s3_create_bucket=False), storage=storage
        )


def test_s3_requires_endpoint_and_credentials() -> None:
    with pytest.raises(StorageError):
        S3Storage.from_settings(_settings(s3_endpoint_url=None))

    with pytest.raises(StorageError):
        S3Storage.from_settings(_settings(s3_access_key=None))

    with pytest.raises(StorageError):
        S3Storage.from_settings(_settings(s3_secret_key=None))


@pytest.mark.parametrize(
    "storage_class", ["GLACIER", "DEEP_ARCHIVE", "glacier", "GLACIER_IR"]
)
def test_offline_storage_classes_are_refused(
    s3_client: Any, storage_class: str
) -> None:
    """A tier that hides the object would break the download guarantee."""
    with pytest.raises(StorageError) as excinfo:
        S3Storage(s3_client, BUCKET, storage_class)

    assert "ilegible" in str(excinfo.value)


def test_default_storage_class_stays_readable() -> None:
    from app.core.config import Settings

    settings = Settings()
    assert settings.s3_archive_storage_class not in S3Storage.OFFLINE_STORAGE_CLASSES


def test_s3_supports_native_tiers(storage: S3Storage) -> None:
    assert storage.supports_native_tiers() is True


def test_content_md5_is_sent_on_every_write(s3_client: Any) -> None:
    """S3 rejects a mismatched ContentMD5, so a truncated transfer fails.

    `moto` does not enforce this check, so the assertion here is that the guard
    is present in the request, not that a server would reject it.
    """
    storage = S3Storage(s3_client, BUCKET)
    recorded: dict[str, object] = {}
    original = s3_client.put_object

    def spy(**kwargs: object) -> object:
        recorded.update(kwargs)
        return original(**kwargs)

    s3_client.put_object = spy
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")

    import asyncio

    asyncio.run(storage.write(key, PDF))

    assert recorded["ContentMD5"] == _content_md5(PDF)
    assert recorded["Key"] == key

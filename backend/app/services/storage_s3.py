"""S3 compatible storage backend (MinIO, AWS S3).

`boto3` is synchronous, so every call is dispatched to a worker thread with
`anyio.to_thread.run_sync`. Blocking the event loop on a network round trip
would stall every concurrent request, which is unacceptable for downloads.

The backend verifies the digest of everything it writes and re-verifies content
after a tier change. Re-hashing a large object is expensive, but tiering is a
rare administrative operation and silently corrupting a legal document is far
more expensive than the extra read.
"""

import hashlib
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import anyio
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.constants import StorageTier
from app.services.storage import (
    StorageError,
    StoredObject,
    StoredStat,
    build_evidence_key,
    build_key,
)

logger = logging.getLogger(__name__)

NO_SUCH_KEY = "NoSuchKey"
NO_SUCH_BUCKET = "NoSuchBucket"


class S3Storage:
    """Store objects in an S3 compatible bucket using opaque generated keys."""

    # Storage classes that make an object unreadable until a restore completes.
    # Using one of these would break the guarantee that any version can be
    # downloaded at any moment, so the policy refuses them outright.
    OFFLINE_STORAGE_CLASSES = frozenset(
        {"GLACIER", "DEEP_ARCHIVE", "GLACIER_IR", "SNOW"}
    )

    def __init__(
        self,
        client: Any,
        bucket: str,
        archive_storage_class: str = "STANDARD_IA",
    ) -> None:
        normalised = archive_storage_class.upper()
        if normalised in self.OFFLINE_STORAGE_CLASSES:
            raise StorageError(
                f"La clase de almacenamiento {archive_storage_class} deja el objeto "
                "ilegible hasta restaurar; use STANDARD_IA o ONEZONE_IA"
            )
        self.client = client
        self.bucket = bucket
        self.archive_storage_class = normalised

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3Storage":
        import boto3

        if not settings.s3_endpoint_url:
            raise StorageError("S3_ENDPOINT_URL es obligatorio cuando STORAGE_BACKEND=s3")
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise StorageError(
                "S3_ACCESS_KEY y S3_SECRET_KEY son obligatorios cuando "
                "STORAGE_BACKEND=s3"
            )

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.s3_addressing_style},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        return cls(client, settings.s3_bucket, settings.s3_archive_storage_class)

    def build_key(
        self,
        case_id: UUID,
        document_id: UUID,
        version: int,
        extension: str,
        token: str | None = None,
    ) -> str:
        return build_key(case_id, document_id, version, extension, token=token)

    def build_evidence_key(
        self,
        case_id: UUID,
        evidence_id: UUID,
        area: str,
        stem: str,
        extension: str,
    ) -> str:
        return build_evidence_key(case_id, evidence_id, area, stem, extension)

    async def require_bucket(self) -> None:
        await self._call("head_bucket", Bucket=self.bucket)

    async def ensure_bucket(self) -> bool:
        """Create the bucket when it is missing. Returns True if it created it."""
        try:
            await self.require_bucket()
            return False
        except StorageError:
            pass

        try:
            await self._call("create_bucket", Bucket=self.bucket)
        except StorageError as error:
            # Losing a race with another replica is not an error.
            if "BucketAlreadyOwnedByYou" not in str(error):
                raise
            return False
        logger.info("Bucket de documentos creado: %s", self.bucket)
        return True

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        try:
            return await anyio.to_thread.run_sync(
                lambda: getattr(self.client, operation)(**kwargs)
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code in (NO_SUCH_KEY, NO_SUCH_BUCKET):
                raise StorageError("El archivo no existe en el almacenamiento") from error
            raise StorageError(f"Fallo de almacenamiento S3: {code or error}") from error
        except BotoCoreError as error:
            raise StorageError(f"Fallo de almacenamiento S3: {error}") from error

    async def write(
        self, key: str, content: bytes, *, tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        storage_class = self._storage_class_for(tier)
        await self._call(
            "put_object",
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentMD5=_content_md5(content),
            **({"StorageClass": storage_class} if storage_class else {}),
        )
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            tier=tier,
        )

    async def read(self, key: str) -> bytes:
        response = await self._call("get_object", Bucket=self.bucket, Key=key)
        body = response["Body"]
        return await anyio.to_thread.run_sync(body.read)

    async def exists(self, key: str) -> bool:
        try:
            await self._call("head_object", Bucket=self.bucket, Key=key)
        except StorageError:
            return False
        return True

    async def _iter_raw_keys(self, prefix: str) -> AsyncIterator[str]:
        """Yield every key using pagination, never loading the whole listing.

        A bucket with millions of objects must not be materialised in memory,
        so the continuation token is followed page by page.
        """
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "MaxKeys": 1000}
            if prefix:
                kwargs["Prefix"] = prefix
            if token:
                kwargs["ContinuationToken"] = token
            response = await self._call("list_objects_v2", **kwargs)
            for item in response.get("Contents", []):
                yield str(item["Key"])
            if not response.get("IsTruncated"):
                return
            token = response.get("NextContinuationToken")
            if not token:
                return

    async def iter_keys(self, *, prefix: str = "") -> AsyncIterator[str]:
        async for key in self._iter_raw_keys(prefix):
            yield key

    async def stat(self, key: str) -> StoredStat | None:
        try:
            response = await self._call("head_object", Bucket=self.bucket, Key=key)
        except StorageError:
            return None
        raw = str(response.get("StorageClass") or "STANDARD")
        return StoredStat(
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            tier=StorageTier.ARCHIVE if raw != "STANDARD" else StorageTier.HOT,
        )

    async def enable_versioning(self) -> bool:
        """Turn on bucket versioning. Cheap protection against deletion."""
        try:
            await self._call(
                "put_bucket_versioning",
                Bucket=self.bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )
        except StorageError:
            return False
        return True

    async def delete(self, key: str) -> None:
        """Remove an object. Only used to compensate a failed commit."""
        try:
            await self._call("delete_object", Bucket=self.bucket, Key=key)
        except StorageError as error:
            logger.warning("No se pudo compensar el objeto %s: %s", key, error)

    async def set_tier(
        self, key: str, tier: StorageTier, *, expected_sha256: str | None = None
    ) -> bool:
        """Change the remote storage class by copying the object onto itself.

        Returns False when the backend cannot transition storage classes, which
        is the case for MinIO on a single drive. The caller still records the
        tier in the database, so the policy stays auditable.
        """
        if tier is StorageTier.HOT:
            return False

        try:
            await self._call(
                "copy_object",
                Bucket=self.bucket,
                Key=key,
                CopySource={"Bucket": self.bucket, "Key": key},
                StorageClass=self.archive_storage_class,
                MetadataDirective="COPY",
            )
        except StorageError as error:
            # A backend that does not implement storage class transitions must
            # not break the policy: fall back to a logical tier only.
            logger.warning(
                "El backend no aplicó la clase de almacenamiento para %s: %s",
                key,
                error,
            )
            return False

        await self._verify_digest(key, expected_sha256)
        return True

    async def _verify_digest(self, key: str, expected_sha256: str | None) -> None:
        """Confirm the object is still readable and unchanged after the copy.

        Re-reading a large object is expensive, but tiering is a rare
        administrative operation and silently altering a legal document is far
        more expensive than the extra read.
        """
        content = await self.read(key)
        if expected_sha256 is not None:
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected_sha256:
                raise StorageError(
                    "El contenido almacenado no coincide con su hash registrado"
                )

    def supports_native_tiers(self) -> bool:
        return True

    def _storage_class_for(self, tier: StorageTier) -> str | None:
        if tier is StorageTier.ARCHIVE:
            return self.archive_storage_class
        return None


def _content_md5(content: bytes) -> str:
    """Return the base64 MD5 required by S3 as an integrity check on upload."""
    import base64

    return base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode()


__all__ = ["S3Storage"]

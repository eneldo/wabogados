"""Off site backup transfer and verification.

A backup that only exists on the same host as the data it protects is not a
backup. This module copies dumps and document objects to a second S3 compatible
location and, crucially, proves the copy is intact afterwards.

Why verification is not optional here: an upload that returns success proves the
bytes left the process, not that they arrived intact. A truncated transfer or a
misconfigured bucket fails silently and is discovered at restore time, which is
the worst moment. So `push` reads the object back and compares the SHA-256
unless the operator explicitly opts out.

The design rule from MASTER_PROMPT 44 still applies to this directory: nothing
here deletes document content. `prune` only ever removes objects this module
wrote, matched by an explicit manifest marker.
"""

import hashlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import anyio
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings
from app.services.backup import redact

logger = logging.getLogger(__name__)

#: Marker stored in object metadata. `prune` only considers objects carrying it,
#: so it can never delete something this module did not put there.
MANAGED_MARKER = "wabogados-backup=1"

MANIFEST_SUFFIX = ".manifest.json"


def _same_location(endpoint: str | None, other: str | None) -> bool:
    """Whether two endpoint strings address the same server.

    Normalised rather than compared literally, because `https://host` and
    `https://host/` are one server written two ways. A check that a trailing slash
    disables is a check an operator can turn off by accident, and this one exists
    to stop a configuration that looks correct.
    """
    if not endpoint or not other:
        return False
    return endpoint.strip().rstrip("/") == other.strip().rstrip("/")


def _refuse_the_document_location_as_backup_target(settings: Settings) -> None:
    """Refuse an off site target that is the document storage itself.

    The rule has been written in `RESTORE.md` since the module existed: the backup
    destination must not be the server that holds the documents, because one
    ransomware or one mistaken delete takes both copies of the same data at once.
    Enforcing it here matters more than usual today, because the decision to move
    to an S3 bucket at another provider is what makes this reachable: a copy
    configured by copying the document credentials is the most likely mistake.

    Only the **same bucket on the same server** is refused. A different bucket on
    the same server is a weaker arrangement but a legitimate one, and refusing it
    would train operators to ignore this error.
    """
    if settings.storage_backend != "s3":
        return
    if not settings.s3_endpoint_url:
        return
    if not _same_location(
        settings.backup_remote_endpoint, settings.s3_endpoint_url
    ):
        return
    if settings.backup_remote_bucket != settings.s3_bucket:
        return

    raise RemoteBackupError(
        "BACKUP_REMOTE_ENDPOINT apunta al mismo bucket que guarda los documentos "
        f"(s3://{settings.s3_bucket}). Una copia en el mismo sitio no protege de "
        "un incendio, un robo ni de un ransomware: desaparecen las dos copias a "
        "la vez. Configure un destino en otra cuenta u otro proveedor."
    )


class RemoteBackupError(Exception):
    """Raised when the off site copy cannot be completed or verified."""


@dataclass(frozen=True)
class RemoteObject:
    key: str
    size_bytes: int
    etag: str | None
    last_modified: datetime | None

    @property
    def name(self) -> str:
        return self.key.rsplit("/", 1)[-1]


@dataclass
class RemoteTransfer:
    """Result of pushing one file to the off site location."""

    name: str
    key: str
    size_bytes: int
    local_sha256: str
    remote_sha256: str | None = None
    verified: bool = False
    verification_mode: str = "read-back"
    skipped: bool = False
    detail: str | None = None

    @property
    def healthy(self) -> bool:
        return self.skipped or self.verified

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "key": self.key,
            "size_bytes": self.size_bytes,
            "local_sha256": self.local_sha256,
            "remote_sha256": self.remote_sha256,
            "verified": self.verified,
            "verification_mode": self.verification_mode,
            "skipped": self.skipped,
            "healthy": self.healthy,
            "detail": self.detail,
        }


@dataclass
class RemoteReport:
    """Outcome of an off site transfer run."""

    target: str
    pushed: int = 0
    skipped: int = 0
    failed: int = 0
    verified: int = 0
    metadata_only: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    errors: list[str] = field(default_factory=list)
    transfers: list[RemoteTransfer] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.failed == 0 and all(t.healthy for t in self.transfers)

    def as_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "pushed": self.pushed,
            "skipped": self.skipped,
            "failed": self.failed,
            "verified": self.verified,
            "metadata_only": self.metadata_only,
            "healthy": self.healthy,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "errors": self.errors,
            "transfers": [t.as_dict() for t in self.transfers],
        }


class RemoteBackup:
    """Copy backups to a second S3 compatible location and verify them."""

    def __init__(self, client: Any, bucket: str, prefix: str = "wabogados") -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "RemoteBackup":
        resolved = settings or get_settings()
        if not resolved.backup_remote_enabled:
            raise RemoteBackupError(
                "El respaldo externo está desactivado. Defina "
                "BACKUP_REMOTE_ENABLED=true y las credenciales. Una copia que no "
                "sale del host no protege de un incendio."
            )
        if not resolved.backup_remote_endpoint:
            raise RemoteBackupError("BACKUP_REMOTE_ENDPOINT es obligatorio")
        if not resolved.backup_remote_access_key or not resolved.backup_remote_secret_key:
            raise RemoteBackupError(
                "BACKUP_REMOTE_ACCESS_KEY y BACKUP_REMOTE_SECRET_KEY son obligatorios"
            )
        _refuse_the_document_location_as_backup_target(resolved)

        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=resolved.backup_remote_endpoint,
            aws_access_key_id=resolved.backup_remote_access_key,
            aws_secret_access_key=resolved.backup_remote_secret_key,
            region_name=resolved.backup_remote_region,
            use_ssl=resolved.backup_remote_use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": resolved.backup_remote_addressing_style},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        return cls(client, resolved.backup_remote_bucket, resolved.backup_remote_prefix)

    def describe(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}"

    def key_for(self, name: str) -> str:
        return f"{self.prefix}/{name}"

    # -- plumbing -----------------------------------------------------------

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        try:
            return await anyio.to_thread.run_sync(
                lambda: getattr(self.client, operation)(**kwargs)
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            raise RemoteBackupError(
                f"S3 remoto rechazó la operación {code or error}"
            ) from error
        except BotoCoreError as error:
            raise RemoteBackupError(f"Fallo del almacenamiento remoto: {error}") from error

    async def ensure_bucket(self) -> bool:
        """Create the remote bucket when missing. Returns True if created."""
        try:
            await self._call("head_bucket", Bucket=self.bucket)
            return False
        except RemoteBackupError:
            pass
        try:
            await self._call("create_bucket", Bucket=self.bucket)
        except RemoteBackupError as error:
            if "BucketAlreadyOwnedByYou" not in str(error):
                raise
            return False
        logger.info("Bucket remoto de respaldos creado: %s", self.bucket)
        return True

    # -- transfer -----------------------------------------------------------

    async def push_file(
        self, path: Any, *, expected_sha256: str | None = None
    ) -> RemoteTransfer:
        """Upload one file and, by default, read it back to verify the digest."""
        from pathlib import Path

        source = Path(path)
        if not source.is_file():
            raise RemoteBackupError(f"No existe el archivo a copiar: {source}")

        content = source.read_bytes()
        digest = expected_sha256 or hashlib.sha256(content).hexdigest()
        key = self.key_for(source.name)

        await self._call(
            "put_object",
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentMD5=_content_md5(content),
            Metadata={
                "sha256": digest,
                "wabogados-backup": "1",
                "created-at": datetime.now(UTC).isoformat(),
            },
        )

        transfer = RemoteTransfer(
            name=source.name,
            key=key,
            size_bytes=len(content),
            local_sha256=digest,
        )

        if not get_settings().backup_remote_verify_upload:
            # Explicitly weaker, and labelled as such in the output.
            transfer.verification_mode = "metadata-only"
            transfer.verified = True
            transfer.detail = (
                "Verificación por metadatos: no se ha releído el objeto remoto"
            )
            return transfer

        response = await self._call("get_object", Bucket=self.bucket, Key=key)
        body = response["Body"]
        remote_bytes = await anyio.to_thread.run_sync(body.read)
        remote_digest = hashlib.sha256(remote_bytes).hexdigest()
        transfer.remote_sha256 = remote_digest

        if remote_digest != digest:
            transfer.detail = (
                "El objeto remoto no coincide con el local: la copia NO es válida"
            )
            raise RemoteBackupError(
                f"La copia remota de {source.name} no coincide con el original "
                f"(local {digest[:12]}, remoto {remote_digest[:12]})"
            )

        transfer.verified = True
        return transfer

    async def push_manifest(self, manifest: Any) -> RemoteTransfer:
        """Upload a manifest, which is what makes a dump restorable."""
        from pathlib import Path

        return await self.push_file(Path(manifest))

    async def push_directory(
        self, directory: Any, *, patterns: tuple[str, ...] = ("*",)
    ) -> RemoteReport:
        """Upload the contents of a backup directory."""
        from pathlib import Path

        root = Path(directory)
        report = RemoteReport(target=self.describe())

        if not root.is_dir():
            report.errors.append(f"No existe el directorio {root}")
            report.failed += 1
            report.finished_at = datetime.now(UTC)
            return report

        names: list[Path] = []
        for pattern in patterns:
            names.extend(sorted(root.glob(pattern)))

        for candidate in names:
            if not candidate.is_file():
                continue
            try:
                transfer = await self.push_file(candidate)
            except RemoteBackupError as error:
                report.failed += 1
                report.errors.append(str(error))
                continue
            report.transfers.append(transfer)
            if transfer.skipped:
                report.skipped += 1
            else:
                report.pushed += 1
                report.verified += 1
                if transfer.verification_mode == "metadata-only":
                    report.metadata_only += 1

        report.finished_at = datetime.now(UTC)
        return report

    # -- inspection ---------------------------------------------------------

    async def verify_object(self, name: str, expected_sha256: str | None = None) -> str:
        """Re-read a remote object and compare it with the expected digest.

        Returns the digest actually read back, so the caller can report what was
        verified rather than a bare success flag.
        """
        key = self.key_for(name)
        response = await self._call("get_object", Bucket=self.bucket, Key=key)
        body = response["Body"]
        content = await anyio.to_thread.run_sync(body.read)
        digest = hashlib.sha256(content).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise RemoteBackupError(
                f"{name} remoto no coincide con el digest esperado "
                f"(esperado {expected_sha256[:12]}, leído {digest[:12]})"
            )
        return digest

    async def list_objects(self) -> AsyncIterator[RemoteObject]:
        """Enumerate the remote backups, paginated."""
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "MaxKeys": 1000}
            if self.prefix:
                kwargs["Prefix"] = f"{self.prefix}/"
            if token:
                kwargs["ContinuationToken"] = token
            response = await self._call("list_objects_v2", **kwargs)
            for item in response.get("Contents", []):
                yield RemoteObject(
                    key=str(item["Key"]),
                    size_bytes=int(item.get("Size", 0)),
                    etag=str(item["ETag"]).strip('"') if item.get("ETag") else None,
                    last_modified=item.get("LastModified"),
                )
            if not response.get("IsTruncated"):
                return
            token = response.get("NextContinuationToken")
            if not token:
                return

    async def list_backups(self) -> list[RemoteObject]:
        return [item async for item in self.list_objects()]

    async def fetch(
        self, name: str, destination: Any, *, expected_sha256: str | None = None
    ) -> str:
        """Download a remote backup and verify it before returning the path.

        Returns the digest of what was actually written to disk, so the caller
        can restore from it knowing it is intact.
        """
        from pathlib import Path

        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)

        response = await self._call("get_object", Bucket=self.bucket, Key=self.key_for(name))
        body = response["Body"]
        content = await anyio.to_thread.run_sync(body.read)
        digest = hashlib.sha256(content).hexdigest()

        if expected_sha256 and digest != expected_sha256:
            raise RemoteBackupError(
                f"La copia descargada de {name} no coincide con el digest esperado"
            )

        target.write_bytes(content)
        return digest

    # -- retention ----------------------------------------------------------

    async def prune(self, *, keep: int) -> list[str]:
        """Delete only managed objects beyond the newest ``keep`` ones.

        Two guards make this safe to run unattended: only objects carrying the
        management marker are candidates, and ``keep`` can never drop to zero.
        """
        if keep < 1:
            raise RemoteBackupError("Hay que conservar al menos una copia remota")

        objects = await self.list_backups()
        managed: list[RemoteObject] = []
        for item in objects:
            try:
                head = await self._call("head_object", Bucket=self.bucket, Key=item.key)
            except RemoteBackupError:
                continue
            if head.get("Metadata", {}).get("wabogados-backup") == "1":
                managed.append(item)

        managed.sort(key=lambda item: item.last_modified or datetime.min.replace(tzinfo=UTC))
        removed: list[str] = []
        for item in managed[:-keep] if len(managed) > keep else []:
            await self._call("delete_object", Bucket=self.bucket, Key=item.key)
            removed.append(item.key)
        if removed:
            logger.info("%d copias remotas antiguas eliminadas", len(removed))
        return removed


def _content_md5(content: bytes) -> str:
    import base64

    return base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode()


def configuration_summary(settings: Settings | None = None) -> dict[str, object]:
    """Describe the off site configuration without ever exposing secrets."""
    resolved = settings or get_settings()
    endpoint = resolved.backup_remote_endpoint or ""
    return {
        "enabled": resolved.backup_remote_enabled,
        "endpoint": redact(endpoint),
        "bucket": resolved.backup_remote_bucket,
        "prefix": resolved.backup_remote_prefix,
        "verify_upload": resolved.backup_remote_verify_upload,
        "keep": resolved.backup_remote_keep,
        "credentials_present": bool(
            resolved.backup_remote_access_key and resolved.backup_remote_secret_key
        ),
    }


__all__ = [
    "MANAGED_MARKER",
    "RemoteBackup",
    "RemoteBackupError",
    "RemoteObject",
    "RemoteReport",
    "RemoteTransfer",
    "configuration_summary",
]
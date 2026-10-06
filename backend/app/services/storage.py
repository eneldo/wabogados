"""Content storage abstraction for document and evidence files.

The domain only ever talks to `StorageBackend`. Two implementations exist:

- `LocalStorage`: a single directory, used for local development and tests.
- `S3Storage`: any S3 compatible service (MinIO, AWS S3) for production.

Two rules are enforced by the abstraction itself rather than by callers:

1. Keys are generated server side from UUIDs. The user supplied file name is
   never allowed to reach the path (MASTER_PROMPT, section 28).
2. Content is never deleted by the retention policy. Tiering only moves a
   version to cheaper storage; the bytes stay retrievable forever
   (PROJECT_RULES, rule 5).

Every write and every tier change is verifiable: the backend returns the stored
digest so a caller can compare it with the value it intended to store.
"""

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.constants import StorageTier

DEFAULT_EXTENSION = ".bin"


class StorageError(Exception):
    """Raised when a file cannot be stored, read back or moved between tiers."""


@dataclass(frozen=True)
class StoredObject:
    """Result of a write, carrying the digest actually persisted."""

    key: str
    size_bytes: int
    sha256: str
    tier: StorageTier = StorageTier.HOT


@dataclass(frozen=True)
class StoredStat:
    """Metadata about a stored object, obtained without reading its bytes."""

    key: str
    size_bytes: int
    tier: StorageTier = StorageTier.HOT


@runtime_checkable
class StorageBackend(Protocol):
    """Operations the domain needs from a content store.

    Every I/O method is asynchronous so that an implementation is free to move
    work off the event loop. `LocalStorage` is fast enough to run inline but
    keeps the same signature so the domain never branches on the backend.
    """

    def build_key(
        self,
        case_id: UUID,
        document_id: UUID,
        version: int,
        extension: str,
        token: str | None = None,
    ) -> str:
        """Return a key that contains no user controlled component."""
        ...

    def build_evidence_key(
        self,
        case_id: UUID,
        evidence_id: UUID,
        area: str,
        stem: str,
        extension: str,
    ) -> str:
        """Return an evidence key laid out as MASTER_PROMPT section 28 requires."""
        ...

    async def write(
        self, key: str, content: bytes, *, tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        """Store bytes and return the digest that was persisted."""
        ...

    async def read(self, key: str) -> bytes:
        """Return the stored bytes."""
        ...

    async def exists(self, key: str) -> bool:
        """Report whether the key is present."""
        ...

    def iter_keys(self, *, prefix: str = "") -> AsyncIterator[str]:
        """Yield every key present in the store, optionally under a prefix.

        Integrity verification needs this: comparing the database against a
        forward listing proves both that nothing was deleted and that nothing
        was added behind the application's back.
        """
        ...

    async def stat(self, key: str) -> StoredStat | None:
        """Return size and tier metadata without downloading the content."""
        ...

    async def delete(self, key: str) -> None:
        """Remove a key. Only for compensating a failed database commit."""
        ...

    async def set_tier(
        self, key: str, tier: StorageTier, *, expected_sha256: str | None = None
    ) -> bool:
        """Move a key to another tier and optionally re-verify its digest.

        Returns True when the backend applied a real storage class change.
        Returns False when the backend only records the tier logically, which is
        the case for MinIO single node deployments. The database is the source
        of truth for the tier either way.

        When `expected_sha256` is provided the object is read back and its
        digest compared, so a tier change can never silently alter content.
        """
        ...

    def supports_native_tiers(self) -> bool:
        """Whether this backend can apply real remote storage classes."""
        ...


def build_key(
    case_id: UUID,
    document_id: UUID,
    version: int,
    extension: str,
    token: str | None = None,
) -> str:
    """Opaque, reproducible key layout shared by every backend.

    Keeping the layout identical means switching `STORAGE_BACKEND` does not
    invalidate the `storage_key` already recorded in the database.

    `token` exists for the one caller that must produce the *same* key twice: the
    S3 migration. Left to chance it generates `os.urandom(8)`, so re-running the
    migration with `--rekey` minted a new key and rewrote the row every time,
    which is the opposite of idempotent.
    """
    import os

    suffix = token if token is not None else os.urandom(8).hex()
    return (
        f"cases/{case_id}/documents/{document_id}"
        f"/v{version}-{suffix}{extension}"
    )


#: Areas of an evidence, matching MASTER_PROMPT section 28.
EVIDENCE_AREAS: tuple[str, ...] = ("original", "optimized", "previews")


def build_evidence_key(
    case_id: UUID,
    evidence_id: UUID,
    area: str,
    stem: str,
    extension: str,
) -> str:
    """Key for evidence files, laid out as MASTER_PROMPT section 28 requires.

    ```
    evidences/case_uuid/evidence_uuid/original/file_uuid.pdf
                                /optimized/file_uuid.pdf
                                /previews/page_001.webp
    ```

    The file name is always a generated UUID. The extension comes from the
    detected MIME type, never from the uploaded name.
    """
    import os

    if area not in EVIDENCE_AREAS:
        raise ValueError(f"Área de evidencia desconocida: {area}")

    safe_stem = re.sub(r"[^A-Za-z0-9_-]", "", stem)[:64]
    if not safe_stem:
        safe_stem = os.urandom(8).hex()
    safe_extension = re.sub(r"[^A-Za-z0-9.]", "", extension)[:16]
    if not safe_extension.startswith("."):
        safe_extension = f".{safe_extension}"

    return f"evidences/{case_id}/{evidence_id}/{area}/{safe_stem}{safe_extension}"


def build_message_key(
    conversation_id: UUID,
    attachment_id: UUID,
    extension: str,
) -> str:
    """Key for a file attached to a message.

    ```
    messages/conversation_uuid/attachment_uuid.ext
    ```

    Both identifiers are generated server side. A chat attachment never uses the
    uploaded name in its path, exactly like documents and evidence.
    """
    safe_extension = "." + re.sub(r"[^A-Za-z0-9]", "", extension).lstrip(".")[:16]
    return f"messages/{conversation_id}/{attachment_id}{safe_extension}"


def build_media_key(media_id: UUID, extension: str) -> str:
    """Key for a file in the multimedia library.

    ```
    media/media_uuid/file_uuid.mp4
    ```

    One file per record: the library is a collection of assets, not a document with
    versions, and the immutable-evidence machinery of section 28 does not apply to
    it. The name is always a generated UUID and the extension comes from the
    detected MIME type, so nothing a user typed ever reaches the path.
    """
    import os

    safe_extension = "." + re.sub(r"[^A-Za-z0-9]", "", extension).lstrip(".")[:16]
    return f"media/{media_id}/{os.urandom(16).hex()}{safe_extension}"


#: Areas of a library derivative. Separate from the original's directory so a
#: thumbnail can never be mistaken for the asset it came from, and so a
#: regeneration writes over its own output instead of beside it.
MEDIA_DERIVATIVE_AREAS: tuple[str, ...] = ("thumbnails", "previews", "transcodes")


def build_media_derivative_key(
    media_id: UUID, area: str, name: str, extension: str
) -> str:
    """Key for a derived file of a library asset.

    ```
    media/media_uuid/thumbnails/name.jpg
                       /previews/name.webp
                       /transcodes/name.mp4
    ```

    `area` is checked rather than sanitised: a typo would otherwise create a new
    directory that no listing knows how to read, which is how a derivative ends up
    invisible rather than wrong.
    """
    if area not in MEDIA_DERIVATIVE_AREAS:
        raise ValueError(f"Área de derivado multimedia desconocida: {area}")

    safe_name = re.sub(r"[^A-Za-z0-9_-]", "", name)[:64] or "derivative"
    safe_extension = re.sub(r"[^A-Za-z0-9.]", "", extension)[:16]
    if not safe_extension.startswith("."):
        safe_extension = f".{safe_extension}"

    return f"media/{media_id}/{area}/{safe_name}{safe_extension}"


def build_storage(settings: Settings | None = None) -> StorageBackend:
    """Return the backend selected by configuration."""
    resolved = settings or get_settings()
    if resolved.storage_backend == "s3":
        from app.services.storage_s3 import S3Storage

        return S3Storage.from_settings(resolved)
    from app.services.storage_local import LocalStorage

    return LocalStorage(resolved.storage_root)


async def initialize_storage(
    settings: Settings | None = None, *, storage: StorageBackend | None = None
) -> None:
    resolved = settings or get_settings()
    if resolved.storage_backend != "s3":
        return

    from app.services.storage_s3 import S3Storage

    backend = storage or build_storage(resolved)
    if not isinstance(backend, S3Storage):
        raise StorageError("El backend configurado como S3 no es compatible")

    if resolved.s3_create_bucket:
        await backend.ensure_bucket()
    else:
        await backend.require_bucket()
    if not await backend.enable_versioning():
        raise StorageError("No se pudo habilitar el versionado del bucket S3")


__all__ = [
    "DEFAULT_EXTENSION",
    "EVIDENCE_AREAS",
    "StorageBackend",
    "StorageError",
    "StorageTier",
    "StoredObject",
    "StoredStat",
    "build_evidence_key",
    "build_key",
    "build_media_key",
    "build_message_key",
    "build_storage",
    "initialize_storage",
]

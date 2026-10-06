"""Local filesystem storage backend.

Kept as a separate module so the abstract contract lives in `storage.py` and
the two implementations never import each other. There is no cost to
concurrency here, so the I/O methods stay inline even though the contract is
asynchronous.
"""

import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from app.core.constants import StorageTier
from app.services.storage import (
    StorageError,
    StoredObject,
    StoredStat,
    build_evidence_key,
    build_key,
)


class LocalStorage:
    """Store bytes under a root directory using opaque generated keys."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        if root is None:
            from app.core.config import get_settings

            root = get_settings().storage_root
        self.root = Path(root)
        # Local storage has no real tiers, so the tier reported by `stat` is
        # always the recorded default. Integrity verification must not treat a
        # local deployment as if it had remote storage classes.
        self.tier = StorageTier.HOT

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

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if not candidate.is_relative_to(root):
            raise StorageError("Clave de almacenamiento fuera del directorio permitido")
        return candidate

    async def write(
        self, key: str, content: bytes, *, tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file and rename, so an interrupted write cannot
        # leave a truncated object that later looks like a valid document.
        temporary = path.with_name(f".{path.name}.partial")
        temporary.write_bytes(content)
        temporary.replace(path)
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            tier=tier,
        )

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError("El archivo no existe en el almacenamiento")
        return path.read_bytes()

    async def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageError:
            return False

    async def _iter_raw_keys(self, prefix: str) -> AsyncIterator[str]:
        """Yield keys without raising on a single unreadable path.

        A verification run must report a problem as a finding, not abort: an
        unreadable directory is a fact to record, not a reason to stop.
        """
        if not self.root.is_dir():
            return
        stack = [self.root]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_dir():
                    stack.append(entry)
                elif entry.is_file():
                    # Skip the temporary files left by an interrupted write.
                    if entry.name.endswith(".partial") or entry.name.startswith("."):
                        continue
                    key = entry.relative_to(self.root).as_posix()
                    if key.startswith(prefix):
                        yield key

    async def iter_keys(self, *, prefix: str = "") -> AsyncIterator[str]:
        async for key in self._iter_raw_keys(prefix):
            yield key

    async def stat(self, key: str) -> StoredStat | None:
        try:
            path = self._resolve(key)
        except StorageError:
            return None
        if not path.is_file():
            return None
        return StoredStat(key=key, size_bytes=path.stat().st_size, tier=self.tier)

    async def delete(self, key: str) -> None:
        """Remove a stored file. Only used to compensate a failed commit."""
        try:
            self._resolve(key).unlink(missing_ok=True)
        except StorageError:
            return

    async def set_tier(
        self, key: str, tier: StorageTier, *, expected_sha256: str | None = None
    ) -> bool:
        """Local storage has no remote tiers; the database records the tier.

        The digest is still verified so the retention policy behaves identically
        on every backend.
        """
        content = await self.read(key)
        if expected_sha256 is not None:
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected_sha256:
                raise StorageError(
                    "El contenido almacenado no coincide con su hash registrado"
                )
        return False

    def supports_native_tiers(self) -> bool:
        return False


__all__ = ["LocalStorage"]

"""Verify the files of a backup by digest, which a count cannot do.

`scripts/backup.sh` has always written `MANIFEST.sha256`, a `sha256sum`-format
listing of every file in the backup. Until this module existed **nothing read
it**. The only recorded fact about the objects was `objects.count`, a number
that cannot tell an intact original from a truncated one: copy half of every
file and the count is unchanged.

So this is the piece that makes the manifest load-bearing:

- `build_manifest` writes it in the same format `sha256sum` produces, so the
  shell script and this module agree on one format and an operator can still
  check it by hand with `sha256sum -c`.
- `verify_manifest` re-reads every listed file and compares digests. It reports
  **missing**, **corrupted** and **unlisted** files separately, because they mean
  different things: a missing original is data loss, a corrupted one is a failed
  transfer, and an unlisted one is usually harmless.

Files are hashed in chunks. An evidence original can be hundreds of megabytes
and reading one into memory to check it would be its own kind of accident.

A verification that reads nothing is not a pass: an empty manifest and a manifest
whose paths all escape the backup directory both report failure.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

logger = logging.getLogger(__name__)

#: Same name `scripts/backup.sh` writes.
MANIFEST_NAME = "MANIFEST.sha256"

#: 1 MiB. Large enough that syscall overhead disappears, small enough that a
#: 500 MB object is not a single allocation.
CHUNK_BYTES = 1024 * 1024

#: How many individual problems a report lists before summarising the rest.
MAX_REPORTED_ERRORS = 50


class ManifestError(Exception):
    """Raised when the manifest itself cannot be read."""


@dataclass
class ManifestReport:
    """What comparing a backup against its own manifest found."""

    manifest_path: Path
    total_count: int = 0
    verified_count: int = 0
    corrupted_count: int = 0
    missing_count: int = 0
    unlisted_count: int = 0
    malformed_count: int = 0
    bytes_verified: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """True only when the manifest proved something and nothing failed.

        A manifest with zero entries is a false pass: it would report a backup
        as verified when it contains nothing to verify.

        The verdict is driven by the counters, not by `errors`, because an
        unlisted file is reported in `errors` for visibility while being
        harmless by default. Anything that makes the backup unusable increments a
        counter.
        """
        return (
            self.total_count > 0
            and self.corrupted_count == 0
            and self.missing_count == 0
            and self.malformed_count == 0
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_path": str(self.manifest_path),
            "healthy": self.healthy,
            "total_count": self.total_count,
            "verified_count": self.verified_count,
            "corrupted_count": self.corrupted_count,
            "missing_count": self.missing_count,
            "unlisted_count": self.unlisted_count,
            "malformed_count": self.malformed_count,
            "bytes_verified": self.bytes_verified,
            "errors": list(self.errors),
        }


def digest_of(path: Path) -> str:
    """SHA-256 of a file, read in chunks rather than in one piece."""
    hasher = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            hasher.update(chunk)
    return hasher.hexdigest()


def iter_manifest_entries(manifest_path: Path) -> Iterator[tuple[int, str, str]]:
    """Yield `(line_number, digest, relative_path)` for each usable entry.

    A line that is not `<digest>  <path>` is yielded as an empty digest so the
    caller can count it as malformed instead of silently dropping it. Dropping it
    would mean a corrupted manifest verifies fewer files and reports success.
    """
    with manifest_path.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            # `sha256sum` separates the digest from the path with two spaces,
            # and escapes a path that contains a backslash or newline.
            digest, separator, relative = line.partition("  ")
            if not separator or len(digest.strip()) != 64:
                yield number, "", line.strip()
                continue
            yield number, digest.strip(), relative.strip()


def build_manifest(
    backup_dir: Path, manifest_path: Path | None = None
) -> Path:
    """Write a `sha256sum`-compatible manifest of every file in the backup.

    The manifest never lists itself: a file cannot contain its own digest.
    """
    target = manifest_path or (backup_dir / MANIFEST_NAME)
    entries: list[tuple[str, str]] = []
    for path in sorted(backup_dir.rglob("*")):
        if not path.is_file() or path == target:
            continue
        # Always POSIX separators. A manifest is a portable artefact: this file is
        # written on the machine that made the backup and read on whatever machine
        # performs the restore, and `str(Path.relative_to())` renders `\` on
        # Windows. A backup verified from Windows would report every single object
        # as missing, which reads exactly like total data loss.
        relative = path.relative_to(backup_dir).as_posix()
        entries.append((digest_of(path), relative))

    body = "".join(f"{digest}  {relative}\n" for digest, relative in entries)
    target.write_text(body, encoding="utf-8")
    logger.info("Manifiesto escrito: %s (%d archivos)", target, len(entries))
    return target


def verify_manifest(
    manifest_path: Path, *, strict_unlisted: bool = False
) -> ManifestReport:
    """Re-read every file the manifest lists and compare its digest.

    `strict_unlisted` turns a file present in the backup but absent from the
    manifest into a failure. The default only reports it: the usual cause is a
    log or a temporary file written after the manifest, and refusing every backup
    for that would train people to ignore the check.
    """
    if not manifest_path.is_file():
        raise ManifestError(f"No existe el manifiesto: {manifest_path}")

    backup_dir = manifest_path.parent
    report = ManifestReport(manifest_path=manifest_path)
    listed: set[Path] = set()

    if manifest_path.stat().st_size == 0:
        report.malformed_count += 1
        _add_error(
            report,
            "el manifiesto está vacío: no verifica nada y no puede dar por bueno "
            "un respaldo",
        )

    for number, digest, relative in iter_manifest_entries(manifest_path):
        if not digest:
            report.malformed_count += 1
            _add_error(report, f"línea {number} con formato inválido: {relative}")
            continue

        report.total_count += 1
        candidate = (backup_dir / relative).resolve()

        # A relative path may not point outside the backup it belongs to.
        if not candidate.is_relative_to(backup_dir.resolve()):
            report.malformed_count += 1
            _add_error(
                report,
                f"línea {number} apunta fuera del directorio de respaldo: {relative}",
            )
            continue

        listed.add(candidate)
        if not candidate.is_file():
            report.missing_count += 1
            _add_error(report, f"falta y no se puede restaurar: {relative}")
            continue

        actual = digest_of(candidate)
        if actual != digest:
            report.corrupted_count += 1
            _add_error(
                report,
                f"contenido alterado: {relative} "
                f"(esperado {digest[:12]}…, leído {actual[:12]}…)",
            )
            continue

        report.verified_count += 1
        report.bytes_verified += candidate.stat().st_size

    for path in sorted(backup_dir.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        if path.resolve() not in listed:
            report.unlisted_count += 1
            _add_error(report, f"no está en el manifiesto: {path.relative_to(backup_dir)}")
            if strict_unlisted:
                report.malformed_count += 1

    if report.healthy:
        logger.info(
            "Manifiesto verificado: %d archivos, %d bytes",
            report.verified_count,
            report.bytes_verified,
        )
    else:
        logger.warning(
            "Manifiesto con problemas: %d alterados, %d ausentes, %d sin listar",
            report.corrupted_count,
            report.missing_count,
            report.unlisted_count,
        )
    return report


def _add_error(report: ManifestReport, message: str) -> None:
    if len(report.errors) < MAX_REPORTED_ERRORS:
        report.errors.append(message)
    elif len(report.errors) == MAX_REPORTED_ERRORS:
        report.errors.append("... más problemas omitidos para no inundar la salida")


__all__ = [
    "CHUNK_BYTES",
    "MANIFEST_NAME",
    "MAX_REPORTED_ERRORS",
    "ManifestError",
    "ManifestReport",
    "build_manifest",
    "digest_of",
    "iter_manifest_entries",
    "verify_manifest",
]

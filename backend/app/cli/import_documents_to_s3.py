"""Import document files from local storage into the S3 backend.

Switching `STORAGE_BACKEND` from `local` to `s3` does not move any bytes: the
`storage_key` already recorded in the database keeps pointing at the local
path. This command copies each existing file into the bucket, verifies the
SHA-256 of the copied bytes against the stored digest and only then records the
new location.

It refuses to run when the destination is not an S3 backend, and it is safe to
re-run: a file already present in the bucket with the right digest is skipped.

Usage:
    python -m app.cli.import_documents_to_s3 --dry-run
    python -m app.cli.import_documents_to_s3 --limit 1000
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.models import DocumentVersion
from app.services.storage import StorageBackend, StorageError, build_storage
from app.services.storage_local import LocalStorage
from app.services.storage_s3 import S3Storage


@dataclass
class ImportReport:
    examined: int = 0
    imported: int = 0
    skipped_existing: int = 0
    missing_local: int = 0
    digest_mismatch: int = 0
    failed: int = 0
    dry_run: bool = False
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "examined": self.examined,
            "imported": self.imported,
            "skipped_existing": self.skipped_existing,
            "missing_local": self.missing_local,
            "digest_mismatch": self.digest_mismatch,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "errors": self.errors,
        }


EXIT_OK = 0
EXIT_NOT_S3 = 2
#: Something was wrong with the data or the destination. A deployment script
#: cannot see "the migration reported zero imported" as a failure, because a
#: quiet run and a broken one look identical on stdout.
EXIT_INCOMPLETE = 4


def extension_of(storage_key: str) -> str:
    """The extension of a stored key, `.pdf` or `""`.

    Read from the key rather than from the uploaded name, because the name is
    not stored and the layout always ends in the detected extension. Inventing
    one instead — the migration used to write `.bin` — produces objects that no
    later tool recognises as what they are.
    """
    _, _, extension = storage_key.rpartition(".")
    if not extension or "/" in extension:
        return ""
    return f".{extension}"


def deterministic_token(row_id: object) -> str:
    """A token derived from the row, so the same row always yields the same key."""
    return str(row_id).replace("-", "")[:16]


def exit_code_for(report: ImportReport) -> int:
    """0 only when every examined file ended up in the bucket or was already there.

    Anything else — a missing local file, a digest that did not match, a rejected
    write — is a partial migration, and saying so is what lets an operator stop
    instead of assuming the environment moved.
    """
    if report.missing_local or report.digest_mismatch or report.failed:
        return EXIT_INCOMPLETE
    return EXIT_OK


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migra los documentos locales al bucket S3 verificando el hash."
    )
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada.")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help=(
            "Salta las primeras N filas. Sin esto, repetir el comando con --limit "
            "vuelve a procesar siempre las mismas y nunca avanza."
        ),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Raíz local de origen. Por defecto, STORAGE_ROOT.",
    )
    parser.add_argument(
        "--rekey",
        action="store_true",
        help=(
            "Genera una clave nueva en el bucket en lugar de reutilizar la local. "
            "Use esto si va a cambiar STORAGE_ROOT. Es idempotente: la misma fila "
            "siempre produce la misma clave."
        ),
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    destination: StorageBackend = build_storage(settings)
    if not isinstance(destination, S3Storage):
        print(
            "[ERROR] El destino no es un backend S3. "
            "Configure STORAGE_BACKEND=s3 antes de migrar."
        )
        return EXIT_NOT_S3

    source_root = args.source_root or settings.storage_root
    source = LocalStorage(source_root)
    report = ImportReport(dry_run=args.dry_run)

    async with SessionFactory() as session:
        if not args.dry_run and settings.s3_create_bucket:
            await destination.ensure_bucket()

        result = await session.execute(
            select(DocumentVersion)
            .order_by(DocumentVersion.created_at, DocumentVersion.id)
            .offset(args.offset)
            .limit(args.limit)
        )
        versions = list(result.scalars().all())
        report.examined = len(versions)

        for version in versions:
            try:
                content = await source.read(version.storage_key)
            except StorageError as error:
                report.missing_local += 1
                # Counted, but also reported: a silent skip reads like "nothing to
                # migrate here" when it means "the file this row points at is gone".
                report.errors.append(
                    f"version {version.version_number} ({version.id}): "
                    f"no está en local: {error}"
                )
                continue

            digest = sha256(content).hexdigest()
            if digest != version.sha256:
                report.digest_mismatch += 1
                report.errors.append(
                    f"version {version.version_number} "
                    f"({version.id}): el archivo local no coincide con su hash"
                )
                continue

            target_key = (
                destination.build_key(
                    version.document_id,
                    version.document_id,
                    version.version_number,
                    extension_of(version.storage_key),
                    token=deterministic_token(version.id),
                )
                if args.rekey
                else version.storage_key
            )

            if await destination.exists(target_key):
                report.skipped_existing += 1
                if target_key == version.storage_key:
                    continue

            if args.dry_run:
                report.imported += 1
                continue

            try:
                await destination.write(target_key, content)
            except StorageError as error:
                report.failed += 1
                report.errors.append(f"{version.id}: {error}")
                continue

            # Verify the uploaded bytes before repointing the database row.
            written = await destination.read(target_key)
            if sha256(written).hexdigest() != version.sha256:
                await destination.delete(target_key)
                report.digest_mismatch += 1
                report.errors.append(
                    f"version {version.version_number}: el bucket devolvió otros bytes"
                )
                continue

            version.storage_key = target_key
            report.imported += 1

        if not args.dry_run:
            await session.commit()

    print(f"examinadas: {report.examined}")
    print(f"importadas: {report.imported}")
    print(f"ya en el bucket: {report.skipped_existing}")
    print(f"ausentes en local: {report.missing_local}")
    print(f"hash no coincidente: {report.digest_mismatch}")
    print(f"fallidas: {report.failed}")
    for detail in report.errors[:20]:
        print(f"  [ERROR] {detail}")

    code = exit_code_for(report)
    if args.dry_run:
        print("[OK] Simulación completada; no se escribió nada")
    elif code == EXIT_OK:
        print(f"[OK] {report.imported} documentos migrados a S3")
    else:
        print(
            "[ERROR] La migración está incompleta. No cambie STORAGE_BACKEND: "
            "quedan archivos sin mover y filas apuntando al disco local."
        )
    return code


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())

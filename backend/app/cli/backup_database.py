"""Create a backup and prove it can be restored.

The order is not arbitrary. Document content is written to storage *before* its
database row commits, so an object can exist without a row but never the other
way round. Backing up the database first and the objects afterwards can only
ever leave an extra object in the backup, never a row pointing at a missing
object. Doing it the other way round could produce a restorable backup with a
dangling reference.

Usage:
    python -m app.cli.backup_database
    python -m app.cli.backup_database --tag diario --keep 30
    python -m app.cli.backup_database --skip-verify
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionFactory
from app.services.backup import BackupError, BackupService
from app.services.integrity import IntegrityService, ScanMode

EXIT_OK = 0
EXIT_RESTORE_FAILED = 4
EXIT_ERROR = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Volca la base de datos y verifica que se puede restaurar."
    )
    parser.add_argument("--backup-dir", type=Path, default=Path(".tmp/backups"))
    parser.add_argument("--tag", default=None, help="Etiqueta para el nombre del archivo.")
    parser.add_argument("--keep", type=int, default=30, help="Copias conservadas.")
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="No verificar la restauración. No recomendado: deja la copia sin probar.",
    )
    parser.add_argument(
        "--integrity",
        action="store_true",
        help="Ejecutar también la verificación de integridad del almacenamiento.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


async def _current_revision() -> str | None:
    async with SessionFactory() as session:
        value = await session.scalar(text("SELECT version_num FROM alembic_version"))
        return str(value) if value else None


async def run(args: argparse.Namespace) -> int:
    summary: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "storage_backend": None,
    }

    service = BackupService(backup_dir=args.backup_dir)

    try:
        artifact = service.dump(tag=args.tag)
    except BackupError as error:
        print(f"[ERROR] No se pudo crear el volcado: {error}")
        return EXIT_ERROR

    revision = await _current_revision()
    manifest_path = service.write_manifest(
        artifact,
        {
            "alembic_revision": revision,
            "created_by": "python -m app.cli.backup_database",
        },
    )
    summary["dump"] = artifact.as_dict()
    summary["alembic_revision"] = revision
    summary["manifest"] = str(manifest_path)

    exit_code = EXIT_OK

    if not args.skip_verify:
        report = await service.verify_restore(
            artifact.path, expected_sha256=artifact.sha256
        )
        summary["restore"] = report.as_dict()
        if report.healthy:
            print(
                f"[OK] Restauración verificada en {report.duration_seconds}s: "
                f"{report.table_count} tablas, revisión {report.alembic_revision}"
            )
        else:
            print("[ERROR] La copia NO se pudo verificar. No es un respaldo válido.")
            for detail in report.errors:
                print(f"  - {detail}")
            exit_code = EXIT_RESTORE_FAILED

    if args.integrity:
        async with SessionFactory() as session:
            integrity = await IntegrityService(session).run(mode=ScanMode.SAMPLE, sample=200)
            await session.commit()
        summary["integrity"] = integrity.as_dict(include_findings=False)
        summary["storage_backend"] = integrity.backend
        if not integrity.healthy:
            print(
                f"[AVISO] La verificación de integridad detectó problemas: "
                f"{integrity.blocking} bloqueantes"
            )

    try:
        removed = service.prune(keep=args.keep)
        summary["pruned"] = [str(path) for path in removed]
        if removed:
            print(f"[OK] {len(removed)} copias antiguas eliminadas")
    except BackupError as error:
        print(f"[AVISO] No se pudo podar el histórico: {error}")

    summary["finished_at"] = datetime.now(UTC).isoformat()

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"\nCopia: {artifact.path}")
        print(f"SHA-256: {artifact.sha256}")
        print(f"Manifiesto: {manifest_path}")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
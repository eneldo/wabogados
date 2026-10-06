"""Verify that a database dump can actually be restored.

Used both by `backup_database` and by an operator restoring by hand. It restores
into a scratch database, inspects it, and drops it, so the live database is
never touched.

Usage:
    python -m app.cli.verify_backup --dump backups/postgres.dump
    python -m app.cli.verify_backup --dump backups/postgres.dump --sha256 abc123...
    python -m app.cli.verify_backup --dump backups/postgres.dump --keep-database
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.services.backup import BackupError, BackupService

EXIT_OK = 0
EXIT_FAILED = 4
EXIT_USAGE = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restaura un volcado en una base temporal y comprueba su contenido."
    )
    parser.add_argument("--dump", type=Path, required=True, help="Ruta al archivo .dump")
    parser.add_argument(
        "--sha256",
        default=None,
        help="Digest esperado. Si no coincide, el volcado no se restaura.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifiesto JSON del que leer el digest esperado.",
    )
    parser.add_argument(
        "--keep-database",
        action="store_true",
        help="No borrar la base temporal. Solo para depurar.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _expected_digest(args: argparse.Namespace) -> str | None:
    if args.sha256:
        digest: str = args.sha256
        return digest.strip()
    if args.manifest and args.manifest.is_file():
        payload: dict[str, object] = json.loads(
            args.manifest.read_text(encoding="utf-8")
        )
        value = payload.get("sha256")
        return str(value) if value else None
    return None


async def run(args: argparse.Namespace) -> int:
    service = BackupService()

    try:
        expected = _expected_digest(args)
    except (json.JSONDecodeError, OSError) as error:
        print(f"[ERROR] No se pudo leer el manifiesto: {error}")
        return EXIT_USAGE

    if not args.dump.is_file():
        print(f"[ERROR] No existe el volcado: {args.dump}")
        return EXIT_USAGE

    report = await service.verify_restore(
        args.dump,
        expected_sha256=expected,
        keep_database=args.keep_database,
    )

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"volcado:        {report.dump_path}")
        if report.dump_digest_matches is not None:
            estado = "correcto" if report.dump_digest_matches else "NO COINCIDE"
            print(f"digest:         {estado}")
        print(f"restaurado:     {report.restored}")
        print(f"revisión alembic: {report.alembic_revision}")
        print(f"tablas:         {report.table_count}")
        for table, count in sorted(report.row_counts.items()):
            print(f"  {table:<20} {count}")
        print(f"duración:       {report.duration_seconds}s")
        print(f"resultado:      {'OK' if report.healthy else 'FALLO'}")
        for detail in report.errors:
            print(f"  - {detail}")

    if report.healthy:
        print("\n[OK] El volcado se restaura y contiene las tablas críticas")
        return EXIT_OK

    print(
        "\n[ERROR] El volcado NO es restaurable. No lo considere una copia de seguridad."
    )
    return EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(run(parse_args(argv)))
    except BackupError as error:
        print(f"[ERROR] {error}")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
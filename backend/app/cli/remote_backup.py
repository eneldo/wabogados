"""Push backups to the off site location and prove the copy is intact.

Fails loudly when the off site target is not configured. A backup pipeline that
quietly does nothing is worse than no pipeline, because it looks like it works.

Usage:
    python -m app.cli.remote_backup --status
    python -m app.cli.remote_backup --push /backups/20261001T120000Z
    python -m app.cli.remote_backup --push /backups --pattern '*'
    python -m app.cli.remote_backup --verify postgres.dump
    python -m app.cli.remote_backup --fetch postgres.dump --into .tmp/restored.dump
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.remote_backup import (
    RemoteBackup,
    RemoteBackupError,
    configuration_summary,
)

EXIT_OK = 0
EXIT_NOT_CONFIGURED = 2
EXIT_FAILED = 4
EXIT_USAGE = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copia respaldos a una ubicación externa y verifica la copia por digest."
        )
    )
    parser.add_argument("--status", action="store_true", help="Solo mostrar configuración.")
    parser.add_argument("--push", type=Path, default=None, help="Archivo o directorio.")
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Patrón a copiar. Repetible. Por defecto '*'.",
    )
    parser.add_argument(
        "--verify", default=None, help="Releer un objeto remoto y comprobar su digest."
    )
    parser.add_argument("--fetch", default=None, help="Descargar un respaldo remoto.")
    parser.add_argument(
        "--into", type=Path, default=Path(".tmp/restored"), help="Destino de --fetch."
    )
    parser.add_argument("--sha256", default=None, help="Digest esperado.")
    parser.add_argument("--list", action="store_true", help="Listar respaldos remotos.")
    parser.add_argument("--prune", action="store_true", help="Aplicar la retención remota.")
    parser.add_argument(
        "--no-verify-upload",
        action="store_true",
        help=(
            "No releer el objeto tras subirlo. Más rápido y MENOS seguro: solo "
            "confía en los metadatos."
        ),
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _print_status(as_json: bool) -> None:
    summary = configuration_summary()
    if as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print(f"habilitado:        {summary['enabled']}")
    print(f"endpoint:          {summary['endpoint']}")
    print(f"bucket:            {summary['bucket']}")
    print(f"prefijo:           {summary['prefix']}")
    print(f"verifica subida:   {summary['verify_upload']}")
    print(f"copias conservadas:{summary['keep']:>4}")
    print(f"credenciales:      {'presentes' if summary['credentials_present'] else 'AUSENTES'}")
    if not summary["enabled"]:
        print(
            "\n[AVISO] El respaldo externo está desactivado. Una copia que no sale "
            "del host no protege de un incendio ni de un ransomware."
        )


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()

    if args.no_verify_upload:
        settings.backup_remote_verify_upload = False

    if args.status:
        _print_status(args.json)
        return EXIT_OK if settings.backup_remote_enabled else EXIT_NOT_CONFIGURED

    try:
        remote = RemoteBackup.from_settings(settings)
    except RemoteBackupError as error:
        print(f"[ERROR] {error}")
        return EXIT_NOT_CONFIGURED

    # Validate the requested action before touching the network: an empty
    # invocation should say so, not fail on a bucket call.
    if not any((args.verify, args.fetch, args.list, args.prune, args.push)):
        print("[ERROR] Indique --push, --verify, --fetch, --list o --prune")
        return EXIT_USAGE

    try:
        await remote.ensure_bucket()
        return await _dispatch(args, remote)
    except RemoteBackupError as error:
        print(f"[ERROR] {error}")
        return EXIT_FAILED


async def _dispatch(args: argparse.Namespace, remote: RemoteBackup) -> int:
    if args.verify:
        digest = await remote.verify_object(args.verify, args.sha256)
        print(f"[OK] {args.verify} remoto coincide ({digest[:12]})")
        return EXIT_OK

    if args.fetch:
        destination = args.into / args.fetch
        digest = await remote.fetch(args.fetch, destination, expected_sha256=args.sha256)
        print(f"[OK] Descargado {destination} ({digest[:12]})")
        return EXIT_OK

    if args.list:
        items = await remote.list_backups()
        if args.json:
            print(json.dumps([i.key for i in items], indent=2))
        else:
            print(f"{len(items)} respaldos en {remote.describe()}")
            for item in items:
                stamp = item.last_modified.isoformat() if item.last_modified else "-"
                print(f"  {stamp}  {item.size_bytes:>12}  {item.name}")
        return EXIT_OK

    if args.prune:
        removed = await remote.prune(keep=get_settings().backup_remote_keep)
        print(f"[OK] {len(removed)} respaldos remotos eliminados")
        return EXIT_OK

    assert args.push is not None, "action validated before dispatch"
    patterns = tuple(args.pattern) if args.pattern else ("*",)
    if args.push.is_file():
        patterns = (args.push.name,)
        directory = args.push.parent
    else:
        directory = args.push

    report = await remote.push_directory(directory, patterns=patterns)
    report.finished_at = report.finished_at or report.started_at

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"destino:      {report.target}")
        print(f"subidos:      {report.pushed}")
        print(f"omitidos:     {report.skipped}")
        print(f"verificados:  {report.verified}")
        print(f"solo metadata:{report.metadata_only}")
        print(f"fallidos:     {report.failed}")
        for detail in report.errors:
            print(f"  - {detail}")

    if report.healthy:
        print("\n[OK] Copia externa verificada por digest")
        return EXIT_OK

    print("\n[ERROR] La copia externa NO está verificada. No la considere válida.")
    return EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
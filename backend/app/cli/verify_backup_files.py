"""Check a backup's files against its own manifest.

The database dump has `verify_backup`, which proves it can be restored. The
objects had nothing: `objects.count` said how many there were, and a count
cannot tell an intact evidence original from a truncated one. This is the check
for those, and it reads the `MANIFEST.sha256` that `scripts/backup.sh` already
writes.

Read only. It never repairs and never deletes: a problem found here is a
decision for a person.

Usage:
    python -m app.cli.verify_backup_files --manifest backups/20260101T000000Z/MANIFEST.sha256
    python -m app.cli.verify_backup_files --manifest ... --objects-only
    python -m app.cli.verify_backup_files --manifest ... --json
"""

import argparse
import json
import sys
from pathlib import Path

from app.services.backup_manifest import (
    MANIFEST_NAME,
    ManifestError,
    verify_manifest,
)

EXIT_OK = 0
EXIT_FAILED = 4
EXIT_USAGE = 3

#: Paths whose contents are the database rather than an object. The dump is
#: already proven restorable by `verify_backup`, and re-hashing it here would
#: only repeat work.
DATABASE_PREFIXES = ("postgres.dump", "postgres.dump.sha256", "postgres.manifest.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica por digest los archivos de un respaldo."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=f"Ruta al {MANIFEST_NAME}. Por defecto, el del directorio actual.",
    )
    parser.add_argument(
        "--objects-only",
        action="store_true",
        help=(
            "Informar solo de los objetos. El volcado de PostgreSQL lo verifica "
            "verify_backup restaurándolo, que es una prueba más fuerte."
        ),
    )
    parser.add_argument(
        "--strict-unlisted",
        action="store_true",
        help="Fallar si hay archivos en el respaldo que no están en el manifiesto.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    manifest = args.manifest or (Path.cwd() / MANIFEST_NAME)
    try:
        report = verify_manifest(manifest, strict_unlisted=args.strict_unlisted)
    except ManifestError as error:
        print(f"[ERROR] {error}")
        return EXIT_USAGE

    payload = report.as_dict()

    # Kept as a list rather than read back out of `payload`: the dict is typed
    # `dict[str, object]`, so iterating it is exactly the kind of `Any` that hides
    # a mistake, and the narrowed view is what gets printed.
    problems: list[str] = list(report.errors)
    if args.objects_only:
        # The dump is already proven restorable by `verify_backup`, which
        # restores it; its absence here is not a second, separate fault.
        problems = [problem for problem in problems if not _is_database(problem)]

    if args.json:
        # Nothing else may be printed in this mode: a single human line after the
        # document makes the whole output unparseable, which is the only reason
        # anyone asked for JSON.
        payload["errors"] = problems
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"manifiesto:     {report.manifest_path}")
        print(f"archivos:       {report.total_count}")
        print(f"verificados:    {report.verified_count} ({report.bytes_verified} bytes)")
        if report.corrupted_count:
            print(f"ALTERADOS:      {report.corrupted_count}")
        if report.missing_count:
            print(f"AUSENTES:      {report.missing_count}")
        if report.malformed_count:
            print(f"MANIFIESTO:     {report.malformed_count} líneas inválidas")
        if report.unlisted_count:
            print(f"sin listar:     {report.unlisted_count}")
        for problem in problems:
            print(f"  - {problem}")
        print(f"resultado:      {'OK' if report.healthy else 'FALLO'}")

        if report.healthy:
            print("\n[OK] Cada archivo del respaldo coincide con su digest")
        else:
            print(
                "\n[ERROR] El respaldo NO está íntegro por digest. "
                "Un recuento de archivos no lo habría detectado."
            )

    return EXIT_OK if report.healthy else EXIT_FAILED


def _is_database(error: str) -> bool:
    return any(prefix in error for prefix in DATABASE_PREFIXES)


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

"""Apply the document version retention policy from the command line.

The policy only moves superseded versions to the archive tier. It never deletes
content, because PROJECT_RULES rule 5 forbids removing legal records.

Usage:
    python -m app.cli.apply_retention --dry-run
    python -m app.cli.apply_retention --limit 200
    python -m app.cli.apply_retention --actor-id <uuid>
"""

import argparse
import asyncio
import sys
from uuid import UUID

from app.db.session import SessionFactory
from app.services.retention import RetentionError, RetentionService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archiva versiones superadas. Nunca elimina contenido."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra lo que haría sin modificar nada.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Máximo de versiones a archivar en esta ejecución.",
    )
    parser.add_argument(
        "--actor-id",
        type=UUID,
        default=None,
        help="Usuario que se registra como autor de la traza.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    async with SessionFactory() as session:
        service = RetentionService(session)

        if not service.settings.retention_tiering_enabled and not args.dry_run:
            print(
                "[ERROR] RETENTION_TIERING_ENABLED está desactivado; "
                "no se archivará nada."
            )
            return 2

        try:
            report = await service.apply(
                dry_run=args.dry_run,
                limit=args.limit,
                actor_id=args.actor_id,
            )
        except RetentionError as error:
            print(f"[ERROR] {error}")
            return 3

        if not args.dry_run:
            await session.commit()

    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(f"{prefix}examinadas: {report.examined}")
    print(f"{prefix}archivadas:  {report.archived}")
    print(f"{prefix}fallidas:    {report.failed}")
    print(f"tier nativo en el backend: {report.native_tier_applied}")
    for detail in report.errors:
        print(f"  [ERROR] {detail}")
    if not args.dry_run and report.archived:
        print(f"[OK] {report.archived} versiones movidas al tier de archivo")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())

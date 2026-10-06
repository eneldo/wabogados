"""Verify that stored document content still matches the database.

Read only by construction: this command has no way to modify document content.
A finding is reported for a human to act on, and the exit code is non zero so
a scheduler can alert.

Usage:
    python -m app.cli.verify_integrity
    python -m app.cli.verify_integrity --mode sample --sample 500
    python -m app.cli.verify_integrity --check-orphans
    python -m app.cli.verify_integrity --json --output .tmp/integrity.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from app.db.session import SessionFactory
from app.services.integrity import (
    FindingType,
    IntegrityService,
    ScanMode,
    ScanReport,
    ScanStatus,
)

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_FAILED = 2
EXIT_USAGE = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verifica que el contenido almacenado sigue coincidiendo con la base de datos. "
            "Nunca modifica ni elimina contenido."
        )
    )
    parser.add_argument(
        "--mode",
        choices=[str(mode) for mode in ScanMode],
        default=str(ScanMode.FULL),
        help="full descarga todos los bytes; sample verifica un subconjunto.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Tamaño de la muestra en modo sample.",
    )
    parser.add_argument(
        "--check-orphans",
        action="store_true",
        help=(
            "Lista el almacenamiento y reporta objetos sin fila en la base de datos. "
            "Es la única forma de demostrar que no se ha añadido nada."
        ),
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=50,
        help="Máximo de hallazgos detallados a imprimir.",
    )
    parser.add_argument("--json", action="store_true", help="Salida en JSON.")
    parser.add_argument("--output", type=Path, default=None, help="Escribir el informe aquí.")
    parser.add_argument(
        "--actor-id", type=UUID, default=None, help="Usuario registrado como autor."
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    if args.sample is not None and args.sample < 1:
        print("[ERROR] --sample debe ser un entero positivo")
        return EXIT_USAGE

    async with SessionFactory() as session:
        service = IntegrityService(session)
        report = await service.run(
            mode=ScanMode(args.mode),
            sample=args.sample,
            check_orphans=args.check_orphans,
            actor_id=args.actor_id,
        )
        await session.commit()

    payload = report.as_dict()

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(report, args.max_findings)

    if report.status == str(ScanStatus.FAILED):
        return EXIT_FAILED
    if not report.healthy:
        return EXIT_PROBLEMS
    return EXIT_OK


def _print_human(report: ScanReport, max_findings: int) -> None:
    print(f"backend:       {report.backend}")
    print(f"modo:          {report.mode}")
    print(f"verificadas:   {report.checked}")
    print(f"correctas:     {report.ok}")
    print(f"ausentes:      {report.missing}")
    print(f"corruptas:     {report.corrupted}")
    print(f"tamaño:        {report.size_mismatch}")
    print(f"ilegibles:     {report.unreadable}")
    print(f"huérfanas:     {report.orphaned}")
    print(f"duración:      {report.duration_seconds}s")
    if report.detail:
        print(f"nota:          {report.detail}")

    problems = [f for f in report.findings if f.finding_type is not FindingType.OK]
    if not problems:
        print("\n[OK] El contenido almacenado coincide con la base de datos")
        return

    print(f"\n[PROBLEMAS] {len(problems)} hallazgos. No se ha modificado nada.")
    for finding in problems[:max_findings]:
        print(
            f"  - {finding.finding_type}: {finding.storage_key}"
            f" (documento {finding.document_id}, versión {finding.version_id})"
            f" {finding.detail or ''}"
        )
    if len(problems) > max_findings:
        print(f"  ... y {len(problems) - max_findings} más")

    print(
        "\nLa verificación NUNCA repara por diseño. Restaure desde una copia de "
        "seguridad tras revisar el hallazgo."
    )


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
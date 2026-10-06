"""Drain the evidence processing queue.

MASTER_PROMPT section 27 requires that heavy work does not block HTTP requests.
Large evidence is recorded as a queued job and processed here.

Docker Compose runs this CLI as the dedicated `evidence-worker` service. Other
deployment platforms must keep an equivalent long-running process active; see
`docs/evidencias.md`.

Usage:
    python -m app.cli.evidence_worker --once
    python -m app.cli.evidence_worker --loop --interval 30
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionFactory
from app.models import EvidenceProcessingJob
from app.services.evidence import EvidenceError, EvidenceService, JobStatus

EXIT_OK = 0
EXIT_FAILED = 4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Procesa los trabajos de evidencia en cola."
    )
    parser.add_argument(
        "--once", action="store_true", help="Procesar la cola actual y salir."
    )
    parser.add_argument(
        "--loop", action="store_true", help="Seguir vigilando la cola."
    )
    parser.add_argument("--interval", type=int, default=30, help="Segundos entre vueltas.")
    parser.add_argument("--limit", type=int, default=10, help="Trabajos por vuelta.")
    parser.add_argument("--worker", default="cli", help="Nombre del worker en la traza.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


async def process_once(worker: str, limit: int) -> tuple[int, int]:
    """Claim and process up to `limit` queued jobs.

    The claim and the result are written in the same transaction as the work, so
    two workers cannot pick up the same job: the row is selected with
    `FOR UPDATE SKIP LOCKED`.
    """
    processed = 0
    failed = 0

    for _ in range(limit):
        async with SessionFactory() as session:
            result = await session.execute(
                select(EvidenceProcessingJob)
                .where(
                EvidenceProcessingJob.status.in_(
                    (str(JobStatus.QUEUED), str(JobStatus.RUNNING))
                )
            )
                .order_by(EvidenceProcessingJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = result.scalars().first()
            if job is None:
                break

            service = EvidenceService(session)
            try:
                await service.run_queued_job(job, worker=worker)
                processed += 1
            except EvidenceError as error:
                failed += 1
                print(f"[ERROR] trabajo {job.id}: {error}")
            await session.commit()

    return processed, failed


async def run(args: argparse.Namespace) -> int:
    if not args.once and not args.loop:
        print("[ERROR] Indique --once o --loop")
        return EXIT_FAILED

    total_processed = 0
    total_failed = 0

    while True:
        processed, failed = await process_once(args.worker, args.limit)
        total_processed += processed
        total_failed += failed

        if args.json:
            print(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "processed": processed,
                        "failed": failed,
                    }
                )
            )
        elif processed or failed:
            print(f"[OK] {processed} procesados, {failed} fallidos")

        if args.once:
            break
        await asyncio.sleep(max(1, args.interval))

    if args.json:
        print(
            json.dumps(
                {"total_processed": total_processed, "total_failed": total_failed}
            )
        )
    return EXIT_OK if total_failed == 0 else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
"""Run the durable recovery outbox, separately from legal evidence processing."""

import argparse
import asyncio
import logging

from app.db.session import SessionFactory
from app.services.recovery_worker import RecoveryWorker

logger = logging.getLogger(__name__)


async def run(loop: bool, interval: float, limit: int) -> None:
    worker = RecoveryWorker(SessionFactory)
    while True:
        try:
            await worker.run_once(limit)
        except Exception:
            # Exception strings/tracebacks from providers can contain secrets.
            logger.error(
                "Recovery worker iteration failed; inspect service health (details redacted)"
            )
            if not loop:
                raise RuntimeError("Recovery worker failed (details redacted)") from None
        if not loop:
            return
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.interval <= 0 or not 1 <= args.limit <= 100:
        parser.error("Use un intervalo positivo y un límite entre 1 y 100")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.loop, args.interval, args.limit))


if __name__ == "__main__":
    main()

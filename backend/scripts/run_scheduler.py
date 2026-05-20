"""Run the APScheduler service in the foreground.

Press Ctrl+C to stop. Logs every job tick + outcome via loguru.

Usage:
    uv run python -m scripts.run_scheduler                  # default intervals from .env
    uv run python -m scripts.run_scheduler --once           # one full cycle, then exit
    uv run python -m scripts.run_scheduler --pipeline 5 \
        --sentiment 2 --summary-hour 23                     # custom intervals (min/min/hour)
"""

from __future__ import annotations

import argparse
import asyncio
import signal

from loguru import logger

from services.scheduler import build_scheduler, full_cycle


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true", help="run one full cycle and exit")
    p.add_argument("--pipeline", type=int, default=None, help="pipeline interval (minutes)")
    p.add_argument("--sentiment", type=int, default=10, help="sentiment interval (minutes)")
    p.add_argument("--summary-hour", type=int, default=None, help="hour of day (UTC) for daily summary")
    return p.parse_args()


async def _run_forever(args: argparse.Namespace) -> None:
    sched = build_scheduler(
        pipeline_minutes=args.pipeline,
        sentiment_minutes=args.sentiment,
        summary_hour=args.summary_hour,
    )
    sched.start()
    logger.info(
        "Scheduler started. Jobs: {}",
        [(j.id, str(j.trigger)) for j in sched.get_jobs()],
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    logger.info("Shutdown signal — stopping scheduler")
    sched.shutdown(wait=False)


async def _main(args: argparse.Namespace) -> None:
    if args.once:
        result = await full_cycle()
        logger.info("one-shot cycle done: {}", result)
        return
    await _run_forever(args)


if __name__ == "__main__":
    asyncio.run(_main(_args()))

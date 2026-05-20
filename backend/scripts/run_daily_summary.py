"""Compute market_summary rows for one date or all dates with data.

Usage:
    uv run python -m scripts.run_daily_summary                # backfill ALL dates
    uv run python -m scripts.run_daily_summary --date 2026-05-15
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from services.daily_summary import _parse_date, run_for_date


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", type=_parse_date, default=None, help="YYYY-MM-DD")
    return p.parse_args()


async def _main(args: argparse.Namespace) -> None:
    n = await run_for_date(args.date)
    logger.info("done — {} summary row(s) upserted", n)


if __name__ == "__main__":
    asyncio.run(_main(_args()))

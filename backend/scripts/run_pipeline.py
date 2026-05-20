"""Run the end-to-end Phase-1 pipeline for one or more tickers.

Usage:
    uv run python -m scripts.run_pipeline TSM
    uv run python -m scripts.run_pipeline TSM AAPL NVDA

Stops after the last ticker is processed. Safe to re-run — url_hash de-dupes
against existing rows so no duplicates are inserted.
"""

import asyncio
import sys

from loguru import logger

from services.pipeline import run_for_ticker


async def main(tickers: list[str]) -> None:
    for t in tickers:
        logger.info("▶ running pipeline for {}", t)
        await run_for_ticker(t)


if __name__ == "__main__":
    args = sys.argv[1:] or ["TSM"]
    asyncio.run(main(args))

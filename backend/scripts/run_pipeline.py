"""Run the end-to-end Phase-1 pipeline for one or more tickers (dev CLI).

Usage:
    uv run python -m scripts.run_pipeline <user_id> TSM
    uv run python -m scripts.run_pipeline <user_id> TSM AAPL NVDA

Stocks + analysis are per-user now, so this tool runs as a specific user and
loads that user's stored API keys. The user must already have the tickers in
their watchlist and their keys set in /settings.
"""

import asyncio
import sys

from loguru import logger

from services.pipeline import run_for_ticker
from services.settings_store import get_user_keys


async def main(user_id: int, tickers: list[str]) -> None:
    keys = await get_user_keys(user_id)
    for t in tickers:
        logger.info("▶ running pipeline for {} (user {})", t, user_id)
        await run_for_ticker(t, user_id=user_id, keys=keys)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m scripts.run_pipeline <user_id> <TICKER> [TICKER ...]")
    uid = int(sys.argv[1])
    asyncio.run(main(uid, sys.argv[2:]))

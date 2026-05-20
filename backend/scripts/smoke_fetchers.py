"""Smoke-test the 7 fetchers against live APIs.

Usage:  uv run python -m scripts.smoke_fetchers TSM AAPL
        (any ticker is fine; missing API keys cause silent skips with WARN logs.)
"""

import asyncio
import sys

from loguru import logger

from services.fetchers.alpha_vantage import AlphaVantageFetcher
from services.fetchers.finnhub import FinnhubFetcher
from services.fetchers.marketaux import MarketauxFetcher
from services.fetchers.newsapi import NewsApiFetcher
from services.fetchers.ptt import PttFetcher
from services.fetchers.stocktwits import StockTwitsFetcher

NEWS_FETCHERS = [MarketauxFetcher, FinnhubFetcher, NewsApiFetcher, AlphaVantageFetcher]
SOCIAL_FETCHERS = [StockTwitsFetcher, PttFetcher]


async def smoke(tickers: list[str]) -> None:
    primary = tickers[0]

    logger.info("=" * 60)
    logger.info("Smoke-testing 7 fetchers with ticker(s): {}", tickers)
    logger.info("=" * 60)

    results: dict[str, int] = {}

    for cls in NEWS_FETCHERS:
        f = cls()
        if not await f.ping():
            logger.warning("[skip] {} — missing credentials", f.source_name)
            results[f.source_name] = -1
            continue
        try:
            items = await f.fetch_news(primary)
            results[f.source_name] = len(items)
            for item in items[:2]:
                logger.info("  {} | {}", f.source_name, item.title[:80])
        except Exception as exc:  # noqa: BLE001
            logger.error("[error] {}: {}", f.source_name, exc)
            results[f.source_name] = -2

    for cls in SOCIAL_FETCHERS:
        f = cls()
        if not await f.ping():
            logger.warning("[skip] {} — missing credentials", f.source_name)
            results[f.source_name] = -1
            continue
        try:
            posts = await f.fetch_social(primary)
            results[f.source_name] = len(posts)
            for post in posts[:2]:
                logger.info("  {} | {}", f.source_name, (post.post_title or post.content[:80]))
        except Exception as exc:  # noqa: BLE001
            logger.error("[error] {}: {}", f.source_name, exc)
            results[f.source_name] = -2

    logger.info("=" * 60)
    for name, count in results.items():
        status = (
            "MISSING CREDS" if count == -1
            else "ERROR" if count == -2
            else f"{count} items"
        )
        logger.info("  {:<15} → {}", name, status)
    logger.info("=" * 60)


if __name__ == "__main__":
    args = sys.argv[1:] or ["TSM"]
    asyncio.run(smoke(args))

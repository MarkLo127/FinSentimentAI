from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

from .base import BaseFetcher, NewsItem

ENDPOINT = "https://www.alphavantage.co/query"


def _map_sentiment_label(av_label: str | None) -> str | None:
    """Alpha Vantage uses 5 buckets; collapse to our 3-label scheme."""
    if not av_label:
        return None
    norm = av_label.strip().lower()
    if "bullish" in norm:
        return "positive"
    if "bearish" in norm:
        return "negative"
    if "neutral" in norm:
        return "neutral"
    return None


class AlphaVantageFetcher(BaseFetcher):
    """Alpha Vantage NEWS_SENTIMENT — comes with its own sentiment scores,
    which we store as a baseline row in sentiment_results."""

    source_name = "alpha_vantage"

    def __init__(self, client: httpx.AsyncClient | None = None, limit: int = 15) -> None:
        self.api_key = get_settings().alpha_vantage_key
        self.limit = limit
        self._client = client

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=20.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_news(self, ticker: str) -> list[NewsItem]:
        if not self.api_key:
            logger.warning("ALPHA_VANTAGE_KEY missing; skipping")
            return []

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "limit": self.limit,
            "apikey": self.api_key,
        }
        client = await self._get()
        try:
            res = await client.get(ENDPOINT, params=params)
            res.raise_for_status()
            data = res.json()
        finally:
            if self._client is None:
                await client.aclose()

        # AV rate-limit error returns 200 with a "Information" message
        if "Information" in data or "Note" in data:
            logger.warning("alpha_vantage rate-limited: {}", data.get("Information") or data.get("Note"))
            return []

        items: list[NewsItem] = []
        for row in data.get("feed", []):
            published_at = None
            if (pub := row.get("time_published")):
                try:
                    # format: 20260515T103000
                    published_at = datetime.strptime(pub, "%Y%m%dT%H%M%S")
                except ValueError:
                    pass
            url = row.get("url")
            if not url:
                continue
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=row.get("title", ""),
                    url=url,
                    summary=row.get("summary"),
                    language="en",
                    published_at=published_at,
                    ticker=ticker,
                    baseline_sentiment_label=_map_sentiment_label(row.get("overall_sentiment_label")),
                    baseline_sentiment_score=row.get("overall_sentiment_score"),
                )
            )
        logger.info("alpha_vantage: {} items for {} (with baseline)", len(items), ticker)
        return items

    async def ping(self) -> bool:
        return bool(self.api_key)

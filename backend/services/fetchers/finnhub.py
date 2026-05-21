from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

from .base import BaseFetcher, NewsItem

ENDPOINT = "https://finnhub.io/api/v1/company-news"


class FinnhubFetcher(BaseFetcher):
    source_name = "finnhub"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        days_back: int = 7,
        *,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else get_settings().finnhub_api_key
        self.days_back = days_back
        self._client = client

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=15.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_news(self, ticker: str) -> list[NewsItem]:
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY missing; skipping")
            return []

        today = datetime.now(UTC).date()
        params = {
            "symbol": ticker,
            "from": (today - timedelta(days=self.days_back)).isoformat(),
            "to": today.isoformat(),
            "token": self.api_key,
        }
        client = await self._get()
        try:
            res = await client.get(ENDPOINT, params=params)
            res.raise_for_status()
            rows = res.json()
        finally:
            if self._client is None:
                await client.aclose()

        items: list[NewsItem] = []
        for row in rows[:20]:
            published_at = None
            if (ts := row.get("datetime")):
                try:
                    published_at = datetime.fromtimestamp(int(ts), tz=UTC)
                except (ValueError, OSError):
                    pass
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=row.get("headline", ""),
                    url=row.get("url", ""),
                    summary=row.get("summary"),
                    language="en",
                    published_at=published_at,
                    ticker=ticker,
                )
            )
        logger.info("finnhub: {} items for {}", len(items), ticker)
        return items

    async def ping(self) -> bool:
        return bool(self.api_key)

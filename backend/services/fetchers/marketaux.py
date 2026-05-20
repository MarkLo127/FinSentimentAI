from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

from .base import BaseFetcher, NewsItem

ENDPOINT = "https://api.marketaux.com/v1/news/all"


class MarketauxFetcher(BaseFetcher):
    source_name = "marketaux"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = get_settings().marketaux_api_key
        self._client = client

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=15.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_news(self, ticker: str) -> list[NewsItem]:
        if not self.api_key:
            logger.warning("MARKETAUX_API_KEY missing; skipping")
            return []

        params = {
            "symbols": ticker,
            "filter_entities": "true",
            "language": "en",
            "api_token": self.api_key,
            "limit": 10,
        }
        client = await self._get()
        try:
            res = await client.get(ENDPOINT, params=params)
            res.raise_for_status()
            data = res.json().get("data", [])
        finally:
            if self._client is None:
                await client.aclose()

        items: list[NewsItem] = []
        for row in data:
            published_at = None
            if (pub := row.get("published_at")):
                try:
                    published_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except ValueError:
                    pass
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=row.get("title", ""),
                    url=row["url"],
                    summary=row.get("snippet") or row.get("description"),
                    language=row.get("language", "en"),
                    published_at=published_at,
                    ticker=ticker,
                )
            )
        logger.info("marketaux: {} items for {}", len(items), ticker)
        return items

    async def ping(self) -> bool:
        return bool(self.api_key)

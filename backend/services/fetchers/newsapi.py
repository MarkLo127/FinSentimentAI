from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

from .base import BaseFetcher, NewsItem

ENDPOINT = "https://newsapi.org/v2/everything"


class NewsApiFetcher(BaseFetcher):
    source_name = "newsapi"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = get_settings().newsapi_key
        self._client = client

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=15.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_news(self, ticker: str) -> list[NewsItem]:
        if not self.api_key:
            logger.warning("NEWSAPI_KEY missing; skipping")
            return []

        params = {
            "q": ticker,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 15,
            "apiKey": self.api_key,
        }
        client = await self._get()
        try:
            res = await client.get(ENDPOINT, params=params)
            res.raise_for_status()
            data = res.json()
        finally:
            if self._client is None:
                await client.aclose()

        items: list[NewsItem] = []
        for row in data.get("articles", []):
            published_at = None
            if (pub := row.get("publishedAt")):
                try:
                    published_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
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
                    summary=row.get("description"),
                    language="en",
                    published_at=published_at,
                    ticker=ticker,
                )
            )
        logger.info("newsapi: {} items for {}", len(items), ticker)
        return items

    async def ping(self) -> bool:
        return bool(self.api_key)

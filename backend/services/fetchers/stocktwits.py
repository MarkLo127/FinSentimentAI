from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseFetcher, SocialPost

ENDPOINT_TEMPLATE = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"


class StockTwitsFetcher(BaseFetcher):
    """StockTwits — no API key needed, rate-limited to 200/hour.

    Importantly, each message carries an optional ``entities.sentiment.basic``
    field with the user-selected ``Bullish``/``Bearish`` label. We persist it to
    ``platform_metadata.sentiment`` so it can later serve as ground truth for
    evaluating our FinBERT outputs (see Phase 2 M2 acceptance criteria).
    """

    source_name = "stocktwits"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=5))
    async def fetch_social(self, ticker: str | None = None) -> list[SocialPost]:
        if not ticker:
            return []

        # As of 2026-05 the public api.stocktwits.com endpoint is fronted by
        # Cloudflare bot-mitigation and returns 403 to plain HTTP clients. We
        # send a real browser UA in case the protection ever relaxes; otherwise
        # the fetcher returns [] and logs a one-line warning so the rest of the
        # pipeline keeps working.
        url = ENDPOINT_TEMPLATE.format(ticker=ticker)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        client = await self._get()
        try:
            res = await client.get(url, headers=headers)
            if res.status_code == 404:
                logger.info("stocktwits: no symbol {}", ticker)
                return []
            if res.status_code == 403:
                logger.warning(
                    "stocktwits: 403 (Cloudflare protection); skipping {}",
                    ticker,
                )
                return []
            res.raise_for_status()
            data = res.json()
        finally:
            if self._client is None:
                await client.aclose()

        posts: list[SocialPost] = []
        for msg in data.get("messages", []):
            published_at = None
            if (pub := msg.get("created_at")):
                try:
                    published_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except ValueError:
                    pass

            metadata: dict = {"id": msg.get("id")}
            entities = msg.get("entities") or {}
            sentiment = (entities.get("sentiment") or {}).get("basic")
            if sentiment:
                metadata["sentiment"] = sentiment.lower()  # "bullish" / "bearish"

            user = msg.get("user") or {}
            post_url = f"https://stocktwits.com/{user.get('username', 'unknown')}/message/{msg.get('id')}"

            posts.append(
                SocialPost(
                    platform=self.source_name,
                    content=msg.get("body", ""),
                    post_url=post_url,
                    author=user.get("username"),
                    published_at=published_at,
                    ticker=ticker,
                    platform_metadata=metadata,
                )
            )
        logger.info("stocktwits: {} posts for {}", len(posts), ticker)
        return posts

    async def ping(self) -> bool:
        return True  # no key required

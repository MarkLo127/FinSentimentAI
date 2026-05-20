from __future__ import annotations

import re

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

from .base import BaseFetcher, SocialPost

# PTT JSON endpoint (ptt.cc/bbs/Stock/index.json) returns 404 as of 2026.
# We use Jina Reader to render the HTML index, then fetch each article via Jina.
PTT_INDEX_URL = "https://www.ptt.cc/bbs/Stock/index.html"
JINA_PREFIX = "https://r.jina.ai/"

# Match article URLs inside Jina-rendered markdown. PTT titles often contain
# their own [tags] (e.g. "[標的]"), which breaks bracket-balanced regex — so
# we match the URL directly and grab the title via a second pass.
ARTICLE_URL_RE = re.compile(
    r"\((?P<url>https://www\.ptt\.cc/bbs/Stock/M\.\d+\.A\.[A-F0-9]+\.html)\)"
)
TITLE_BEFORE_URL_RE = re.compile(
    r"\[(?P<title>[^\n]+?)\]\((?P<url>https://www\.ptt\.cc/bbs/Stock/M\.\d+\.A\.[A-F0-9]+\.html)\)"
)


class PttFetcher(BaseFetcher):
    """PTT Stock board via Jina Reader (the official JSON endpoint is dead in 2026)."""

    source_name = "ptt"

    def __init__(self, client: httpx.AsyncClient | None = None, post_limit: int = 5) -> None:
        self.jina_key = get_settings().jina_api_key
        self.post_limit = post_limit
        self._client = client

    def _jina_headers(self) -> dict[str, str]:
        h = {"X-Return-Format": "markdown"}
        if self.jina_key:
            h["Authorization"] = f"Bearer {self.jina_key}"
        return h

    async def _get(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0)

    async def _jina_fetch(self, client: httpx.AsyncClient, target_url: str) -> str:
        res = await client.get(JINA_PREFIX + target_url, headers=self._jina_headers())
        res.raise_for_status()
        return res.text

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_social(self, ticker: str | None = None) -> list[SocialPost]:
        client = await self._get()
        try:
            index_md = await self._jina_fetch(client, PTT_INDEX_URL)

            # Build a lookup of title-before-url where possible (greedy, ignores nested brackets)
            title_by_url: dict[str, str] = {}
            for m in TITLE_BEFORE_URL_RE.finditer(index_md):
                title_by_url.setdefault(m.group("url"), m.group("title"))

            seen: set[str] = set()
            article_urls: list[tuple[str, str]] = []
            for m in ARTICLE_URL_RE.finditer(index_md):
                url = m.group("url")
                if url in seen:
                    continue
                seen.add(url)
                article_urls.append((title_by_url.get(url, ""), url))
                if len(article_urls) >= self.post_limit:
                    break

            posts: list[SocialPost] = []
            for title, art_url in article_urls:
                try:
                    body_md = await self._jina_fetch(client, art_url)
                except httpx.HTTPError as exc:
                    logger.warning("ptt: skip {} ({})", art_url, exc)
                    continue
                # Crude push/boo count if visible in the markdown
                metadata = {
                    "push": body_md.count("推 "),
                    "boo": body_md.count("噓 "),
                }
                posts.append(
                    SocialPost(
                        platform=self.source_name,
                        content=body_md[:8000],
                        post_url=art_url,
                        post_title=title,
                        ticker=ticker,
                        platform_metadata=metadata,
                    )
                )
        finally:
            if self._client is None:
                await client.aclose()

        logger.info("ptt: {} posts (via Jina fallback)", len(posts))
        return posts

    async def ping(self) -> bool:
        return True  # Jina works without a key (lower rate limit)

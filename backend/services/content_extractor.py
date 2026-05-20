"""Three-layer fallback content extractor for news URLs.

Layer 1 — Jina Reader API (https://r.jina.ai/{url})
    * Free, 500 req/min with API key
    * Handles JS-rendered pages
    * Returns clean markdown

Layer 2 — trafilatura (local Python lib)
    * No API quota, fully offline
    * Good for static HTML pages
    * Fails on JS-rendered SPAs

Layer 3 — API-provided snippet
    * Always available (from the news API itself)
    * Short (~150-500 chars), marked so the UI can show a "summary only" warning

The pipeline calls ``fetch_full_content`` once per news URL and persists the
result + which layer succeeded into ``news.fetched_via``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx
import trafilatura
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

FetchedVia = Literal["jina", "trafilatura", "snippet"]

JINA_PREFIX = "https://r.jina.ai/"
MIN_CONTENT_CHARS = 500
JINA_TIMEOUT = 30.0
TRAFILATURA_TIMEOUT = 15.0


@dataclass(slots=True)
class ExtractedContent:
    text: str
    fetched_via: FetchedVia
    length: int


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=8))
async def _try_jina(client: httpx.AsyncClient, url: str, jina_key: str) -> str | None:
    headers = {"X-Return-Format": "markdown"}
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"

    res = await client.get(JINA_PREFIX + url, headers=headers, timeout=JINA_TIMEOUT)
    if res.status_code != 200:
        logger.debug("jina layer: HTTP {} for {}", res.status_code, url)
        return None
    return res.text


def _trafilatura_sync(html: str) -> str | None:
    return trafilatura.extract(html, include_comments=False, include_tables=False)


async def _try_trafilatura(client: httpx.AsyncClient, url: str) -> str | None:
    res = await client.get(
        url,
        timeout=TRAFILATURA_TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
        follow_redirects=True,
    )
    if res.status_code != 200 or not res.text:
        return None
    return await asyncio.to_thread(_trafilatura_sync, res.text)


async def fetch_full_content(
    url: str,
    fallback_snippet: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> ExtractedContent:
    """Extract clean full-text from a news URL using three-layer fallback.

    Always returns an ExtractedContent — never raises. The caller persists
    ``fetched_via`` so the frontend can flag snippet-fallback rows.
    """
    settings = get_settings()
    owns_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True)

    try:
        # Layer 1: Jina Reader
        try:
            text = await _try_jina(client, url, settings.jina_api_key)
            if text and len(text) >= MIN_CONTENT_CHARS:
                return ExtractedContent(text=text, fetched_via="jina", length=len(text))
        except Exception as exc:  # noqa: BLE001
            logger.debug("jina layer failed for {}: {}", url, exc)

        # Layer 2: trafilatura on raw HTML
        try:
            text = await _try_trafilatura(client, url)
            if text and len(text) >= MIN_CONTENT_CHARS:
                return ExtractedContent(text=text, fetched_via="trafilatura", length=len(text))
        except Exception as exc:  # noqa: BLE001
            logger.debug("trafilatura layer failed for {}: {}", url, exc)

        # Layer 3: snippet fallback
        snippet = fallback_snippet or ""
        logger.warning("extractor: falling back to snippet for {} ({} chars)", url, len(snippet))
        return ExtractedContent(text=snippet, fetched_via="snippet", length=len(snippet))
    finally:
        if owns_client:
            await client.aclose()

"""Auto-fill stock metadata (name / exchange / sector) for a bare ticker.

Used by POST /api/stocks when the user only supplies a symbol. Calls Finnhub's
/stock/profile2 endpoint (free tier, 60 req/min) and degrades gracefully when
the API key is missing or the symbol is unknown."""

from __future__ import annotations

import httpx
from loguru import logger

from config import get_settings

ENDPOINT = "https://finnhub.io/api/v1/stock/profile2"


async def lookup_stock_profile(symbol: str) -> dict[str, str | None]:
    """Return {name, exchange, sector} for symbol. Each field may be None.

    Never raises — failures yield an empty dict so callers can fall back to
    user-supplied or symbol-derived defaults."""
    api_key = get_settings().finnhub_api_key
    if not api_key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                ENDPOINT, params={"symbol": symbol, "token": api_key}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("stock profile lookup failed for {}: {}", symbol, e)
        return {}
    if not data or not data.get("name"):
        return {}
    return {
        # DB caps: name VARCHAR(100), exchange VARCHAR(20), sector VARCHAR(50).
        # Finnhub sometimes returns verbose exchange names like
        # "NASDAQ NMS - GLOBAL MARKET" — take only the first token to keep
        # the display tidy and within the column limit.
        "name": _trim(data.get("name"), 100),
        "exchange": _short_exchange(data.get("exchange"), 20),
        "sector": _trim(data.get("finnhubIndustry"), 50),
    }


def _trim(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    v = value.strip()
    return v[:limit] if v else None


def _short_exchange(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    # "NASDAQ NMS - GLOBAL MARKET" → "NASDAQ"; "NEW YORK STOCK EXCHANGE" stays
    # "NEW YORK STOCK EXCH" (truncated). First-token heuristic is good enough
    # for the major Finnhub-supported exchanges.
    first = v.split()[0]
    return first[:limit]

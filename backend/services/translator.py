"""On-demand translation of a news article's title + body via Claude Haiku.

Used by `GET /api/news/{news_id}/translation/{lang}`. Skips the heavy
sentiment SYSTEM_PROMPT cache (cache miss every time anyway because each
article body is unique), keeping the prompt minimal so cost stays in the
~$0.005-0.015 per article range."""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic
from loguru import logger

from config import get_settings
from models.news import News

LANG_NAME = {
    "zh-TW": "Traditional Chinese (zh-TW, 繁體中文)",
    "en": "English",
}


class TranslationError(RuntimeError):
    """Raised when Claude returns a response we can't parse as JSON."""


def _strip_code_fence(raw: str) -> str:
    """Tolerate ```json ... ``` wrappers Claude sometimes adds."""
    raw = raw.strip()
    if raw.startswith("```"):
        # drop the opening fence (optionally with 'json' tag) and the closing
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


async def translate_news(
    news: News, target_lang: str, client: AsyncAnthropic | None = None
) -> tuple[str, str]:
    """Translate (title, body) into ``target_lang``. Returns the translated
    pair. Raises ``TranslationError`` on JSON parse failure."""
    if target_lang not in LANG_NAME:
        raise ValueError(f"unsupported target language: {target_lang}")

    settings = get_settings()
    if client is None:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    body = (news.full_content or news.summary or "")[:40000]
    prompt = (
        f"Translate the following financial news article to "
        f"{LANG_NAME[target_lang]}. Preserve all numbers, ticker symbols, "
        "company names (in their canonical form for the target language — "
        "e.g., Apple Inc. ↔ 蘋果公司, TSMC ↔ 台積電), dates, and quoted "
        "speech exactly. Use idiomatic financial vocabulary.\n\n"
        "Return STRICT JSON with two keys and NOTHING ELSE — no preamble, "
        "no markdown fence, no commentary:\n"
        '{"title": "<translated title>", "body": "<translated body>"}\n\n'
        f"TITLE: {news.title}\n\n"
        f"BODY:\n{body}"
    )

    # The Anthropic SDK refuses non-streaming requests whose max_tokens could
    # take >10 min — for a 90K-char article translating into Chinese, that
    # threshold is easy to hit. Stream and accumulate the text deltas.
    chunks: list[str] = []
    async with client.messages.stream(
        model=settings.anthropic_model,
        # Output is roughly the same byte count as the input body, but tokens
        # tend to be denser for Chinese — leave headroom.
        max_tokens=32000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            chunks.append(text)
    raw = "".join(chunks)
    cleaned = _strip_code_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning(
            "translation parse failed for news {} → {}: {}",
            news.id,
            target_lang,
            exc,
        )
        raise TranslationError(f"failed to parse Claude response as JSON: {exc}") from exc

    title = parsed.get("title")
    body_out = parsed.get("body")
    if not isinstance(title, str) or not isinstance(body_out, str):
        raise TranslationError("response missing 'title' or 'body' string fields")

    return title.strip(), body_out.strip()

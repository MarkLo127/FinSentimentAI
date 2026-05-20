"""Smoke-test the Claude-based sentiment analyzer against real DB content.

Pulls one English news row and one PTT Chinese comment from the existing
DB (populated by Week 4's pipeline run) and analyzes them. Reports cache
hit / miss across the calls so we can verify Haiku 4.5 prompt caching is
working as designed.

Usage: uv run python -m scripts.smoke_sentiment
"""

from __future__ import annotations

import asyncio
import json

from loguru import logger
from sqlalchemy import select

from database import SessionLocal
from models.comment import Comment
from models.news import News
from services.sentiment_analyzer import get_analyzer


def _truncate(text: str, n: int = 80) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


async def main() -> None:
    analyzer = get_analyzer()

    async with SessionLocal() as session:
        # Pick the longest English news row for richest analysis
        eng_news = (
            await session.execute(
                select(News)
                .where(News.source.in_(("marketaux", "finnhub", "newsapi", "alpha_vantage")))
                .where(News.fetched_via.in_(("jina", "trafilatura")))
                .order_by(News.content_length.desc().nulls_last())
                .limit(1)
            )
        ).scalar_one_or_none()

        # Pick a PTT post (Chinese)
        ptt_post = (
            await session.execute(
                select(Comment).where(Comment.platform == "ptt").limit(1)
            )
        ).scalar_one_or_none()

        # Pick a StockTwits post (English short-form social) — also a chance
        # to compare against the user-supplied bullish/bearish baseline.
        st_post = (
            await session.execute(
                select(Comment).where(Comment.platform == "stocktwits").limit(1)
            )
        ).scalar_one_or_none()

    samples = []
    if eng_news:
        samples.append(
            (
                "EN news",
                {
                    "title": eng_news.title,
                    "content": eng_news.full_content or eng_news.summary or "",
                    "source": eng_news.source,
                    "ticker": "TSM",
                    "extra": f"fetched_via={eng_news.fetched_via} len={eng_news.content_length}",
                },
            )
        )
    if ptt_post:
        samples.append(
            (
                "ZH PTT",
                {
                    "title": ptt_post.post_title,
                    "content": ptt_post.content,
                    "source": "ptt",
                    "ticker": "2330",
                    "extra": f"metadata={ptt_post.platform_metadata}",
                },
            )
        )
    if st_post:
        samples.append(
            (
                "EN StockTwits",
                {
                    "title": None,
                    "content": st_post.content,
                    "source": "stocktwits",
                    "ticker": "TSM",
                    "extra": f"user_label={st_post.platform_metadata}",
                },
            )
        )

    logger.info("=" * 70)
    logger.info("Running sentiment on {} samples — first call warms cache", len(samples))
    logger.info("=" * 70)

    for idx, (label, payload) in enumerate(samples, 1):
        extra = payload.pop("extra")
        result, usage = await analyzer.analyze(**payload)
        logger.info(
            "\n[{}/{}] {} | {}\n  TITLE: {}\n  BODY : {}\n  EXTRA: {}",
            idx,
            len(samples),
            label,
            payload["source"],
            _truncate(payload["title"] or "(none)"),
            _truncate(payload["content"], 120),
            extra,
        )
        logger.info(
            "  → label={} conf={:.2f} clickbait={}",
            result.label,
            result.confidence,
            result.is_clickbait,
        )
        logger.info("    drivers   en: {}", result.key_drivers_en)
        logger.info("    drivers   zh: {}", result.key_drivers_zh)
        logger.info("    reasoning en: {}", _truncate(result.reasoning_en, 200))
        logger.info("    reasoning zh: {}", _truncate(result.reasoning_zh, 200))
        logger.info(
            "    USAGE     : input={} output={} cache_create={} cache_read={}",
            usage["input_tokens"],
            usage["output_tokens"],
            usage["cache_creation_input_tokens"],
            usage["cache_read_input_tokens"],
        )

    logger.info("=" * 70)
    logger.info("Done. Expected pattern:")
    logger.info("  call 1 → cache_create > 0, cache_read = 0  (cold cache)")
    logger.info("  call 2 → cache_create = 0, cache_read > 0  (warm hit)")
    logger.info("  call 3 → cache_create = 0, cache_read > 0  (still warm)")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

"""Backfill Claude Haiku 4.5 sentiment over all news + social posts that
don't yet have a ``model_version='claude-haiku-4-5'`` row.

The Alpha Vantage baseline rows (``model_version='alpha_vantage_v1'``) are
left alone — they live alongside ours and feed ``compare_baselines.py``.

Concurrency strategy
--------------------
We fire 5 requests in parallel via an asyncio.Semaphore. The first batch
pays cache-write cost (Anthropic only marks the prefix readable AFTER the
first response begins streaming), but the remaining 116 rows hit the warm
cache for ~90% input-cost savings.

Usage
-----
    uv run python -m scripts.backfill_sentiment            # backfill everything
    uv run python -m scripts.backfill_sentiment --limit 5  # smoke a small batch
    uv run python -m scripts.backfill_sentiment --dry-run  # show count, don't call API
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import and_, delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.comment import Comment
from models.news import News
from models.sentiment import SentimentResult
from models.stock import Stock
from services.sentiment_analyzer import SentimentAnalyzer, build_analyzer, get_analyzer

CLAUDE_MODEL_VERSION = "claude-haiku-4-5"
CONCURRENCY = 5


@dataclass
class BackfillStats:
    news_total: int = 0
    news_done: int = 0
    news_failed: int = 0
    comment_total: int = 0
    comment_done: int = 0
    comment_failed: int = 0
    cache_create_tokens: int = 0
    cache_read_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def log(self) -> None:
        logger.info("=" * 60)
        logger.info("Backfill summary:")
        logger.info(
            "  news    : {}/{} done ({} failed)",
            self.news_done,
            self.news_total,
            self.news_failed,
        )
        logger.info(
            "  comments: {}/{} done ({} failed)",
            self.comment_done,
            self.comment_total,
            self.comment_failed,
        )
        logger.info("  cache_create_tokens = {}", self.cache_create_tokens)
        logger.info("  cache_read_tokens   = {}", self.cache_read_tokens)
        logger.info("  input_tokens (uncached) = {}", self.input_tokens)
        logger.info("  output_tokens = {}", self.output_tokens)
        # Rough cost estimate: Haiku 4.5 $1/$5 per 1M; cache write $1.25, read $0.10
        cost = (
            self.input_tokens * 1.0 / 1_000_000
            + self.cache_create_tokens * 1.25 / 1_000_000
            + self.cache_read_tokens * 0.10 / 1_000_000
            + self.output_tokens * 5.0 / 1_000_000
        )
        logger.info("  estimated cost ≈ ${:.4f}", cost)
        logger.info("=" * 60)


async def _pending_news(
    session: AsyncSession, limit: int | None, force: bool, user_id: int | None
) -> list[News]:
    stmt = select(News).where(News.full_content.isnot(None)).order_by(News.id)
    if user_id is not None:
        # Only this user's news (their stocks). Keeps one user's refresh from
        # spending their Claude key on another user's unanalyzed rows.
        owned = select(Stock.id).where(Stock.user_id == user_id)
        stmt = stmt.where(News.stock_id.in_(owned))
    if not force:
        # Default: only fetch rows that don't yet have a Claude analysis
        has_claude = (
            select(SentimentResult.id)
            .where(SentimentResult.news_id == News.id)
            .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
        )
        stmt = stmt.where(~exists(has_claude))
    if limit:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def _pending_comments(
    session: AsyncSession, limit: int | None, force: bool, user_id: int | None
) -> list[Comment]:
    stmt = select(Comment).order_by(Comment.id)
    if user_id is not None:
        owned = select(Stock.id).where(Stock.user_id == user_id)
        stmt = stmt.where(Comment.stock_id.in_(owned))
    if not force:
        has_claude = (
            select(SentimentResult.id)
            .where(SentimentResult.comment_id == Comment.id)
            .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
        )
        stmt = stmt.where(~exists(has_claude))
    if limit:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def _purge_existing_claude_results(
    session: AsyncSession, news_ids: list[int], comment_ids: list[int]
) -> int:
    """Wipe existing Claude analyses for the given rows so --force can rerun
    them cleanly (otherwise we'd just stack duplicate sentiment_results)."""
    deleted = 0
    if news_ids:
        res = await session.execute(
            delete(SentimentResult)
            .where(SentimentResult.news_id.in_(news_ids))
            .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
        )
        deleted += res.rowcount or 0
    if comment_ids:
        res = await session.execute(
            delete(SentimentResult)
            .where(SentimentResult.comment_id.in_(comment_ids))
            .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
        )
        deleted += res.rowcount or 0
    if deleted:
        logger.info("--force: purged {} existing Claude sentiment rows", deleted)
    return deleted


async def _analyze_news(
    analyzer: SentimentAnalyzer,
    session: AsyncSession,
    news: News,
    stats: BackfillStats,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        try:
            result, usage = await analyzer.analyze(
                content=news.full_content or news.summary or "",
                title=news.title,
                source=news.source,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("news {} failed: {}", news.id, exc)
            stats.news_failed += 1
            return

        session.add(
            SentimentResult(
                news_id=news.id,
                stock_id=news.stock_id,
                sentiment_label=result.label,
                confidence=result.confidence,
                analyzed_text=(news.full_content or "")[:2000],
                model_version=CLAUDE_MODEL_VERSION,
                analysis_metadata={
                    "is_clickbait": result.is_clickbait,
                    "title_zh": result.title_zh,
                    "title_en": result.title_en,
                    "key_drivers_zh": result.key_drivers_zh,
                    "key_drivers_en": result.key_drivers_en,
                    "reasoning_zh": result.reasoning_zh,
                    "reasoning_en": result.reasoning_en,
                    # flat aliases used by daily_summary.py top-keyword aggregation
                    # (defaults to English drivers for cross-language pivot tables)
                    "key_drivers": result.key_drivers_en,
                    "reasoning": result.reasoning_en,
                    "fetched_via": news.fetched_via,
                    "source": news.source,
                },
            )
        )
        stats.news_done += 1
        stats.cache_create_tokens += usage["cache_creation_input_tokens"]
        stats.cache_read_tokens += usage["cache_read_input_tokens"]
        stats.input_tokens += usage["input_tokens"]
        stats.output_tokens += usage["output_tokens"]

        if stats.news_done % 10 == 0:
            logger.info(
                "  news progress: {}/{} (cache_read={})",
                stats.news_done,
                stats.news_total,
                stats.cache_read_tokens,
            )


async def _analyze_comment(
    analyzer: SentimentAnalyzer,
    session: AsyncSession,
    comment: Comment,
    stats: BackfillStats,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        try:
            result, usage = await analyzer.analyze(
                content=comment.content,
                title=comment.post_title,
                source=comment.platform,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("comment {} failed: {}", comment.id, exc)
            stats.comment_failed += 1
            return

        session.add(
            SentimentResult(
                comment_id=comment.id,
                stock_id=comment.stock_id,
                sentiment_label=result.label,
                confidence=result.confidence,
                analyzed_text=comment.content[:2000],
                model_version=CLAUDE_MODEL_VERSION,
                analysis_metadata={
                    "is_clickbait": result.is_clickbait,
                    "title_zh": result.title_zh,
                    "title_en": result.title_en,
                    "key_drivers_zh": result.key_drivers_zh,
                    "key_drivers_en": result.key_drivers_en,
                    "reasoning_zh": result.reasoning_zh,
                    "reasoning_en": result.reasoning_en,
                    "key_drivers": result.key_drivers_en,
                    "reasoning": result.reasoning_en,
                    "platform": comment.platform,
                    "platform_metadata": comment.platform_metadata,
                },
            )
        )
        stats.comment_done += 1
        stats.cache_create_tokens += usage["cache_creation_input_tokens"]
        stats.cache_read_tokens += usage["cache_read_input_tokens"]
        stats.input_tokens += usage["input_tokens"]
        stats.output_tokens += usage["output_tokens"]

        if stats.comment_done % 10 == 0:
            logger.info(
                "  comment progress: {}/{} (cache_read={})",
                stats.comment_done,
                stats.comment_total,
                stats.cache_read_tokens,
            )


async def run(
    *,
    limit: int | None,
    dry_run: bool,
    force: bool = False,
    user_id: int | None = None,
    anthropic_key: str | None = None,
) -> BackfillStats:
    stats = BackfillStats()
    # Per-user flow passes the user's own key; CLI/global flow falls back to env.
    analyzer = build_analyzer(anthropic_key) if anthropic_key is not None else get_analyzer()
    sem = asyncio.Semaphore(CONCURRENCY)

    async with SessionLocal() as session:
        pending_news = await _pending_news(session, limit, force, user_id)
        pending_comments = await _pending_comments(session, limit, force, user_id)
        stats.news_total = len(pending_news)
        stats.comment_total = len(pending_comments)

        logger.info(
            "Pending: {} news + {} comments to analyze (force={})",
            stats.news_total,
            stats.comment_total,
            force,
        )
        if dry_run:
            stats.log()
            return stats

        if force:
            # Delete existing rows up front so each new analysis cleanly
            # replaces the old one (instead of stacking duplicate analyses).
            await _purge_existing_claude_results(
                session,
                [n.id for n in pending_news],
                [c.id for c in pending_comments],
            )
            await session.commit()

        # Warm the cache with one sequential call first, so the remaining
        # parallel batch hits the cache instead of all paying writes.
        if pending_news:
            await _analyze_news(analyzer, session, pending_news[0], stats, sem)
            pending_news = pending_news[1:]
        elif pending_comments:
            await _analyze_comment(analyzer, session, pending_comments[0], stats, sem)
            pending_comments = pending_comments[1:]

        tasks = [
            _analyze_news(analyzer, session, n, stats, sem) for n in pending_news
        ] + [
            _analyze_comment(analyzer, session, c, stats, sem) for c in pending_comments
        ]
        if tasks:
            await asyncio.gather(*tasks)

        await session.commit()

    stats.log()
    return stats


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None, help="cap rows per category for testing")
    p.add_argument("--dry-run", action="store_true", help="show count only, don't call API")
    p.add_argument(
        "--force",
        action="store_true",
        help="re-analyze rows that already have a Claude sentiment_result "
        "(deletes old rows first so the result count stays at one per item)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run(limit=args.limit, dry_run=args.dry_run, force=args.force))

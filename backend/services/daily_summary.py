"""Roll up Claude sentiment into per-stock per-day market_summary rows.

Formula (per plan §7.3):
    sentiment_score = (Σ positive_conf − Σ negative_conf) / total_count
                      where total_count includes neutrals in the denominator.

Date assignment:
    For news + comments: ``date(fetched_at)`` — i.e. the day we ingested
    the article, NOT its publish date. This makes the dashboard's "today"
    counts add up to what the user sees in /news (which is also ordered by
    fetch time), instead of older news disappearing into yesterday's bucket
    just because they were published earlier.

Source filter:
    Only ``model_version='claude-haiku-4-5'`` rows feed the score. The
    Alpha Vantage baseline rows are excluded (they're a comparison signal,
    not the primary one).

Top keywords:
    We reuse the LLM's ``key_drivers`` from analysis_metadata rather than
    re-running jieba/rake on raw text. Each driver is a curated short
    phrase like "raised FY guidance" / "法人連續買超" — much higher signal
    density than algorithmic frequency analysis. We dedupe case-insensitively
    and order by source-article confidence, capped at 10.

UPSERT:
    On (stock_id, summary_date) conflict we overwrite — this makes the job
    safely re-runnable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from loguru import logger
from sqlalchemy import case, cast, func, select
from sqlalchemy.dialects.postgresql import DATE, insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.comment import Comment
from models.market_summary import MarketSummary
from models.news import News
from models.sentiment import SentimentResult

CLAUDE = "claude-haiku-4-5"


@dataclass
class StockDayBucket:
    stock_id: int | None
    summary_date: date
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_conf_sum: float = 0.0
    negative_conf_sum: float = 0.0

    @property
    def total(self) -> int:
        return self.positive_count + self.negative_count + self.neutral_count

    @property
    def score(self) -> float | None:
        if self.total == 0:
            return None
        return round((self.positive_conf_sum - self.negative_conf_sum) / self.total, 4)


async def _aggregate_news(
    session: AsyncSession, target_date: date | None
) -> dict[tuple[int | None, date], StockDayBucket]:
    """Return {(stock_id, date) → bucket} aggregated over news rows."""
    # Date the article by when *we* fetched it, not when it was published —
    # matches what users see in /news (ordered by fetched_at) so the daily
    # counts in the dashboard sum up correctly.
    pub_date = cast(News.fetched_at, DATE).label("d")
    stmt = (
        select(
            News.stock_id,
            pub_date,
            SentimentResult.sentiment_label,
            SentimentResult.confidence,
        )
        .join(SentimentResult, SentimentResult.news_id == News.id)
        .where(SentimentResult.model_version == CLAUDE)
    )
    if target_date is not None:
        stmt = stmt.where(pub_date == target_date)

    buckets: dict[tuple[int | None, date], StockDayBucket] = {}
    for stock_id, d, label, conf in (await session.execute(stmt)).all():
        key = (stock_id, d)
        b = buckets.setdefault(key, StockDayBucket(stock_id=stock_id, summary_date=d))
        if label == "positive":
            b.positive_count += 1
            b.positive_conf_sum += conf
        elif label == "negative":
            b.negative_count += 1
            b.negative_conf_sum += conf
        else:
            b.neutral_count += 1
    return buckets


async def _aggregate_comments(
    session: AsyncSession,
    target_date: date | None,
    buckets: dict[tuple[int | None, date], StockDayBucket],
) -> dict[tuple[int | None, date], StockDayBucket]:
    pub_date = cast(Comment.fetched_at, DATE).label("d")
    stmt = (
        select(
            Comment.stock_id,
            pub_date,
            SentimentResult.sentiment_label,
            SentimentResult.confidence,
        )
        .join(SentimentResult, SentimentResult.comment_id == Comment.id)
        .where(SentimentResult.model_version == CLAUDE)
    )
    if target_date is not None:
        stmt = stmt.where(pub_date == target_date)

    for stock_id, d, label, conf in (await session.execute(stmt)).all():
        key = (stock_id, d)
        b = buckets.setdefault(key, StockDayBucket(stock_id=stock_id, summary_date=d))
        if label == "positive":
            b.positive_count += 1
            b.positive_conf_sum += conf
        elif label == "negative":
            b.negative_count += 1
            b.negative_conf_sum += conf
        else:
            b.neutral_count += 1
    return buckets


async def _top_keywords_for(
    session: AsyncSession, stock_id: int | None, d: date, limit: int = 10
) -> list[str]:
    """Pull ``key_drivers`` from the day's highest-confidence articles and
    return up to ``limit`` unique drivers (case-insensitive dedupe)."""
    pub_date_news = cast(News.fetched_at, DATE)
    pub_date_cmt = cast(Comment.fetched_at, DATE)

    # News side
    news_stmt = (
        select(
            SentimentResult.analysis_metadata["key_drivers"].label("drivers"),
            SentimentResult.confidence,
        )
        .join(News, News.id == SentimentResult.news_id)
        .where(SentimentResult.model_version == CLAUDE)
        .where(pub_date_news == d)
    )
    if stock_id is None:
        news_stmt = news_stmt.where(News.stock_id.is_(None))
    else:
        news_stmt = news_stmt.where(News.stock_id == stock_id)
    news_stmt = news_stmt.order_by(SentimentResult.confidence.desc())

    cmt_stmt = (
        select(
            SentimentResult.analysis_metadata["key_drivers"].label("drivers"),
            SentimentResult.confidence,
        )
        .join(Comment, Comment.id == SentimentResult.comment_id)
        .where(SentimentResult.model_version == CLAUDE)
        .where(pub_date_cmt == d)
    )
    if stock_id is None:
        cmt_stmt = cmt_stmt.where(Comment.stock_id.is_(None))
    else:
        cmt_stmt = cmt_stmt.where(Comment.stock_id == stock_id)
    cmt_stmt = cmt_stmt.order_by(SentimentResult.confidence.desc())

    seen: set[str] = set()
    out: list[str] = []
    for stmt in (news_stmt, cmt_stmt):
        for drivers, _conf in (await session.execute(stmt)).all():
            if not drivers:
                continue
            for raw in drivers:
                if not isinstance(raw, str):
                    continue
                key = raw.lower().strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(raw.strip())
                if len(out) >= limit:
                    return out
    return out


async def _upsert(
    session: AsyncSession, bucket: StockDayBucket, top_keywords: list[str]
) -> None:
    stmt = (
        pg_insert(MarketSummary)
        .values(
            stock_id=bucket.stock_id,
            summary_date=bucket.summary_date,
            sentiment_score=bucket.score,
            positive_count=bucket.positive_count,
            negative_count=bucket.negative_count,
            neutral_count=bucket.neutral_count,
            total_count=bucket.total,
            top_keywords=top_keywords or None,
        )
        .on_conflict_do_update(
            constraint="uq_market_stock_date",
            set_={
                "sentiment_score": bucket.score,
                "positive_count": bucket.positive_count,
                "negative_count": bucket.negative_count,
                "neutral_count": bucket.neutral_count,
                "total_count": bucket.total,
                "top_keywords": top_keywords or None,
            },
        )
    )
    await session.execute(stmt)


async def run_for_date(target_date: date | None = None) -> int:
    """Compute and UPSERT summaries for every (stock, date) that has data.

    Pass ``target_date=None`` to roll up EVERY date present in the data
    (useful for backfilling history).
    Returns the number of rows upserted.
    """
    async with SessionLocal() as session:
        buckets = await _aggregate_news(session, target_date)
        buckets = await _aggregate_comments(session, target_date, buckets)

        n = 0
        for bucket in buckets.values():
            top = await _top_keywords_for(session, bucket.stock_id, bucket.summary_date)
            await _upsert(session, bucket, top)
            n += 1
            logger.info(
                "  stock_id={} date={} score={} pos={} neg={} neu={} (top {} kw)",
                bucket.stock_id,
                bucket.summary_date,
                bucket.score,
                bucket.positive_count,
                bucket.negative_count,
                bucket.neutral_count,
                len(top),
            )

        await session.commit()
    logger.info("upserted {} market_summary rows", n)
    return n


async def run_for_stock_date(stock_id: int, target_date: date) -> StockDayBucket | None:
    """Single (stock, date) variant — used by tests and ad-hoc inspection."""
    async with SessionLocal() as session:
        # Reuse the bulk path for correctness, then return just the matching bucket
        buckets = await _aggregate_news(session, target_date)
        buckets = await _aggregate_comments(session, target_date, buckets)
        bucket = buckets.get((stock_id, target_date))
        if bucket is None:
            return None
        top = await _top_keywords_for(session, stock_id, target_date)
        await _upsert(session, bucket, top)
        await session.commit()
        return bucket


# ------------------------------------------------------------------ helpers
def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

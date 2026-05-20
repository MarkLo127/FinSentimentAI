"""APScheduler-based periodic runner that ties Phase 1 + 2 together.

Three jobs, all idempotent (re-runnable without producing duplicates):

  ``pipeline_cycle``   every 30 min  — fetch news + social for monitored
                                       tickers, persist, dedupe by url_hash.
  ``sentiment_cycle``  every 10 min  — run Claude over any unanalysed rows
                                       (cache-warm path; cheap).
  ``daily_summary``    23:00 UTC     — finalize today's market_summary rows.

The chain is deliberately decoupled: each job persists its own output and
the next job picks up unanalysed work via a left-join. Restart safety is
free — a crash mid-cycle just leaves rows for the next tick.

Usage:
    uv run python -m scripts.run_scheduler
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from sqlalchemy import select

from config import get_settings
from database import SessionLocal
from models.stock import Stock
from services import daily_summary
from services.pipeline import run_for_ticker
from services.settings_store import overlay_db_into_env
from scripts.backfill_sentiment import run as run_backfill


async def _active_tickers() -> list[str]:
    """Source the auto-fetch watchlist from the ``stocks`` table — i.e. only
    tickers the user explicitly added via the UI. This replaces the old
    ``.env MONITORED_TICKERS`` path so there are no hidden auto-fetches."""
    async with SessionLocal() as db:
        rows = await db.execute(select(Stock.symbol).order_by(Stock.id))
        return list(rows.scalars().all())


async def pipeline_cycle() -> dict[str, Any]:
    """Fetch + extract + persist for every ticker in the user's watchlist."""
    # Pick up any keys the operator set via the UI since the last tick.
    try:
        await overlay_db_into_env()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[pipeline_cycle] overlay skipped: {}", exc)
    tickers = await _active_tickers()
    logger.info("[pipeline_cycle] start tickers={}", tickers)
    summary: dict[str, Any] = {}
    for ticker in tickers:
        try:
            stats = await run_for_ticker(ticker)
            summary[ticker] = {
                "new_news": stats.new_news_rows,
                "new_comments": stats.new_comment_rows,
                "new_baseline": stats.new_baseline_rows,
                "dedup_skipped": stats.skipped_duplicates,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("[pipeline_cycle] ticker={} failed: {}", ticker, exc)
            summary[ticker] = {"error": repr(exc)}
    logger.info("[pipeline_cycle] done summary={}", summary)
    return summary


async def sentiment_cycle() -> dict[str, Any]:
    """Analyze any news/comments that don't yet have a Claude sentiment row."""
    try:
        await overlay_db_into_env()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sentiment_cycle] overlay skipped: {}", exc)
    logger.info("[sentiment_cycle] start")
    try:
        stats = await run_backfill(limit=None, dry_run=False)
        out = {
            "news_done": stats.news_done,
            "comment_done": stats.comment_done,
            "failed": stats.news_failed + stats.comment_failed,
            "cache_read": stats.cache_read_tokens,
            "cache_create": stats.cache_create_tokens,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("[sentiment_cycle] failed: {}", exc)
        out = {"error": repr(exc)}
    logger.info("[sentiment_cycle] done {}", out)
    return out


async def daily_summary_cycle(target_date: date | None = None) -> dict[str, Any]:
    """Re-roll today's summary (and yesterday's, just in case late news lands)."""
    today = target_date or datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    logger.info("[daily_summary_cycle] start dates={} {}", yesterday, today)
    out: dict[str, Any] = {}
    for d in (yesterday, today):
        try:
            n = await daily_summary.run_for_date(d)
            out[str(d)] = n
        except Exception as exc:  # noqa: BLE001
            logger.exception("[daily_summary_cycle] date={} failed: {}", d, exc)
            out[str(d)] = {"error": repr(exc)}
    logger.info("[daily_summary_cycle] done {}", out)
    return out


async def full_cycle() -> dict[str, Any]:
    """Convenience for manual triggers and tests — runs all three in order."""
    p = await pipeline_cycle()
    s = await sentiment_cycle()
    d = await daily_summary_cycle()
    return {"pipeline": p, "sentiment": s, "summary": d}


def build_scheduler(
    *,
    pipeline_minutes: int | None = None,
    sentiment_minutes: int = 10,
    summary_hour: int | None = None,
) -> AsyncIOScheduler:
    settings = get_settings()
    pipeline_minutes = pipeline_minutes or settings.news_fetch_interval_minutes
    summary_hour = summary_hour if summary_hour is not None else settings.daily_summary_hour

    sched = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,        # collapse missed runs into one
            "max_instances": 1,      # never overlap with previous tick
            "misfire_grace_time": 300,
        },
    )
    sched.add_job(
        pipeline_cycle,
        trigger=IntervalTrigger(minutes=pipeline_minutes),
        id="pipeline_cycle",
        replace_existing=True,
        next_run_time=datetime.now(UTC),  # kick off immediately on start
    )
    sched.add_job(
        sentiment_cycle,
        trigger=IntervalTrigger(minutes=sentiment_minutes),
        id="sentiment_cycle",
        replace_existing=True,
        next_run_time=datetime.now(UTC) + timedelta(seconds=30),
    )
    sched.add_job(
        daily_summary_cycle,
        trigger=CronTrigger(hour=summary_hour, minute=0, timezone="UTC"),
        id="daily_summary",
        replace_existing=True,
    )
    return sched

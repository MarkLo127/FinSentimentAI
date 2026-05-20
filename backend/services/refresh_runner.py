"""Background runner for on-demand stock refresh.

Lifecycle:

    POST /api/stocks/{symbol}/refresh
        ↓
    create RefreshJob (state="queued")
        ↓
    asyncio.create_task(run_refresh_job(job_id, symbol))   # detached task
        ↓
    HTTP 202 returns immediately with job_id
        ↓
    Browser polls GET /api/refresh-jobs/{job_id} every 2s

The detached task owns its own DB session (does NOT reuse the request's),
so it survives long after the HTTP handler returns. A loose
``asyncio.Semaphore`` caps concurrent runs to keep Anthropic / Jina rate
limits sane.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.refresh_job import RefreshJob
from services import daily_summary
from services.pipeline import run_for_ticker
from scripts.backfill_sentiment import run as run_backfill

# Cap concurrent refreshes globally so we don't blow Anthropic / Jina rate
# limits when several stocks are searched in quick succession.
_REFRESH_SEMAPHORE = asyncio.Semaphore(2)


async def _set_state(
    db: AsyncSession, job_id: int, *, state: str, stage: str | None = None, **fields
) -> None:
    """Atomically update job state + optional stage + arbitrary stat fields."""
    payload: dict = {"state": state}
    if stage is not None:
        payload["progress_stage"] = stage
    payload.update(fields)
    await db.execute(update(RefreshJob).where(RefreshJob.id == job_id).values(**payload))
    await db.commit()


async def run_refresh_job(job_id: int, symbol: str) -> None:
    """Detached task body — never awaited by the request handler."""
    async with _REFRESH_SEMAPHORE:
        async with SessionLocal() as db:
            try:
                await _set_state(
                    db,
                    job_id,
                    state="running",
                    stage="fetching",
                    started_at=datetime.now(UTC),
                )

                try:
                    p_stats = await run_for_ticker(symbol)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("[refresh job {}] pipeline failed", job_id)
                    await _set_state(
                        db,
                        job_id,
                        state="failed",
                        stage=None,
                        error=f"pipeline failed: {exc!r}",
                        completed_at=datetime.now(UTC),
                    )
                    return

                await _set_state(
                    db,
                    job_id,
                    state="running",
                    stage="analyzing",
                    new_news=p_stats.new_news_rows,
                    new_comments=p_stats.new_comment_rows,
                )

                s_stats = await run_backfill(limit=None, dry_run=False)

                await _set_state(
                    db,
                    job_id,
                    state="running",
                    stage="summarizing",
                    sentiment_analyzed=s_stats.news_done + s_stats.comment_done,
                )

                today = datetime.now(UTC).date()
                for d in (today - timedelta(days=1), today):
                    try:
                        await daily_summary.run_for_date(d)
                    except Exception:  # noqa: BLE001
                        logger.warning("[refresh job {}] daily_summary({}) failed", job_id, d)

                await _set_state(
                    db,
                    job_id,
                    state="succeeded",
                    stage=None,
                    completed_at=datetime.now(UTC),
                )
                logger.info("[refresh job {}] done for {}", job_id, symbol)
            except Exception as exc:  # noqa: BLE001 — last-resort guard
                logger.exception("[refresh job {}] unexpected error", job_id)
                await _set_state(
                    db,
                    job_id,
                    state="failed",
                    error=f"unexpected: {exc!r}",
                    completed_at=datetime.now(UTC),
                )


async def reap_stale_jobs(stale_minutes: int = 30) -> int:
    """At backend startup, mark any 'running' jobs older than ``stale_minutes``
    as failed — these are leftovers from a crashed/restarted container.

    Returns the number of jobs reaped.
    """
    threshold = datetime.now(UTC) - timedelta(minutes=stale_minutes)
    async with SessionLocal() as db:
        stale = (
            await db.execute(
                select(RefreshJob.id).where(
                    (RefreshJob.state == "running") & (RefreshJob.started_at < threshold)
                )
            )
        ).scalars().all()
        if not stale:
            return 0
        await db.execute(
            update(RefreshJob)
            .where(RefreshJob.id.in_(stale))
            .values(
                state="failed",
                error="reaped: backend restarted while job was running",
                completed_at=datetime.now(UTC),
            )
        )
        await db.commit()
        return len(stale)

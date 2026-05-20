from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, desc, func, select
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.refresh_job import RefreshJob
from schemas.refresh import RefreshJobPublic

router = APIRouter(prefix="/api/refresh-jobs", tags=["refresh-jobs"])


async def _annotate_run_numbers(
    db: AsyncSession, jobs: Iterable[RefreshJob]
) -> list[RefreshJobPublic]:
    """For each job, compute its 1-based ordinal among same-symbol jobs
    created on the same UTC date. Lets the UI show "今日第 N 次分析"."""
    jobs = list(jobs)
    if not jobs:
        return []

    today_utc = datetime.now(UTC).date()
    symbols = {j.symbol for j in jobs}

    # One query per request returns the chronological list of today's job
    # ids per symbol; we then rank each input job within its list.
    created_date = cast(RefreshJob.created_at, DATE)
    stmt = (
        select(RefreshJob.id, RefreshJob.symbol, RefreshJob.created_at)
        .where(RefreshJob.symbol.in_(symbols))
        .where(created_date == today_utc)
        .order_by(RefreshJob.symbol, RefreshJob.created_at)
    )
    rows = (await db.execute(stmt)).all()

    rank_by_id: dict[int, int] = {}
    counter: dict[str, int] = {}
    for row in rows:
        counter[row.symbol] = counter.get(row.symbol, 0) + 1
        rank_by_id[row.id] = counter[row.symbol]

    out: list[RefreshJobPublic] = []
    for job in jobs:
        pub = RefreshJobPublic.model_validate(job)
        pub.today_run_number = rank_by_id.get(job.id, 1)
        out.append(pub)
    return out


@router.get("/{job_id}", response_model=RefreshJobPublic)
async def get_refresh_job(
    job_id: int, db: AsyncSession = Depends(get_db)
) -> RefreshJobPublic:
    job = (
        await db.execute(select(RefreshJob).where(RefreshJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, f"Refresh job {job_id} not found")
    [annotated] = await _annotate_run_numbers(db, [job])
    return annotated


@router.get("", response_model=list[RefreshJobPublic])
async def list_refresh_jobs(
    symbol: str | None = Query(None, description="Filter to one symbol"),
    state: str | None = Query(None, description="queued | running | succeeded | failed"),
    active: bool = Query(
        False,
        description="Shortcut for state IN (queued, running); overrides `state`",
    ),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[RefreshJobPublic]:
    """Recent refresh jobs, newest first. Use ``symbol`` to resume polling
    after a browser reload (frontend pattern: on mount, call with
    ``symbol=&limit=1`` and if the returned job is still running, poll it).
    Use ``active=true`` for the global indicator strip."""
    stmt = select(RefreshJob).order_by(desc(RefreshJob.created_at)).limit(limit)
    if symbol:
        stmt = stmt.where(RefreshJob.symbol == symbol.upper())
    if active:
        stmt = stmt.where(RefreshJob.state.in_(("queued", "running")))
    elif state:
        stmt = stmt.where(RefreshJob.state == state)
    rows = (await db.execute(stmt)).scalars().all()
    return await _annotate_run_numbers(db, rows)


# `func` is imported above only to keep the lint clean when DATE-cast helpers
# are extended later; silence unused-warning explicitly:
_ = func

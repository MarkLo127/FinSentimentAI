"""Tests for the scheduler cycle functions.

Each cycle wraps an existing well-tested module (pipeline, backfill,
daily_summary). The tests below verify the orchestration shape:
exceptions are caught, results are propagated, and the trigger order
in build_scheduler() is correct.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from services import scheduler  # noqa: E402
from scripts.backfill_sentiment import BackfillStats  # noqa: E402


class _FakePipelineStats:
    new_news_rows = 5
    new_comment_rows = 3
    new_baseline_rows = 1
    skipped_duplicates = 7


@pytest.mark.asyncio
async def test_pipeline_cycle_iterates_monitored_tickers(monkeypatch):
    monkeypatch.setenv("MONITORED_TICKERS", "TSM, AAPL ,NVDA")
    get_settings = scheduler.get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    mock = AsyncMock(return_value=_FakePipelineStats())
    with patch.object(scheduler, "run_for_ticker", mock):
        out = await scheduler.pipeline_cycle()
    assert mock.await_count == 3
    assert set(out.keys()) == {"TSM", "AAPL", "NVDA"}
    assert out["TSM"]["new_news"] == 5
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pipeline_cycle_isolates_per_ticker_failures(monkeypatch):
    monkeypatch.setenv("MONITORED_TICKERS", "GOOD,BAD")
    scheduler.get_settings.cache_clear()  # type: ignore[attr-defined]

    async def mixed(ticker: str):
        if ticker == "BAD":
            raise RuntimeError("synthetic failure")
        return _FakePipelineStats()

    with patch.object(scheduler, "run_for_ticker", AsyncMock(side_effect=mixed)):
        out = await scheduler.pipeline_cycle()
    assert "new_news" in out["GOOD"]
    assert "error" in out["BAD"]
    scheduler.get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_sentiment_cycle_returns_aggregate_stats():
    fake = BackfillStats(
        news_total=4,
        news_done=4,
        comment_total=2,
        comment_done=2,
        cache_create_tokens=100,
        cache_read_tokens=900,
    )
    with patch.object(scheduler, "run_backfill", AsyncMock(return_value=fake)):
        out = await scheduler.sentiment_cycle()
    assert out == {
        "news_done": 4,
        "comment_done": 2,
        "failed": 0,
        "cache_read": 900,
        "cache_create": 100,
    }


@pytest.mark.asyncio
async def test_sentiment_cycle_traps_failures():
    with patch.object(scheduler, "run_backfill", AsyncMock(side_effect=ValueError("boom"))):
        out = await scheduler.sentiment_cycle()
    assert "error" in out


@pytest.mark.asyncio
async def test_daily_summary_cycle_covers_today_and_yesterday():
    calls: list = []

    async def fake_run(d):
        calls.append(d)
        return 7

    with patch.object(scheduler.daily_summary, "run_for_date", fake_run):
        out = await scheduler.daily_summary_cycle()
    assert len(calls) == 2  # yesterday + today
    assert all(v == 7 for v in out.values())


def test_build_scheduler_registers_three_jobs():
    sched = scheduler.build_scheduler(
        pipeline_minutes=5, sentiment_minutes=2, summary_hour=23
    )
    ids = {j.id for j in sched.get_jobs()}
    assert ids == {"pipeline_cycle", "sentiment_cycle", "daily_summary"}
    # No background thread should be live (we never called .start())
    assert not sched.running

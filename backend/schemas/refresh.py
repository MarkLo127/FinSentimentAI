from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RefreshJobPublic(BaseModel):
    """Response shape for refresh job endpoints — polled by the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    state: Literal["queued", "running", "succeeded", "failed"]
    progress_stage: str | None
    started_at: datetime | None
    completed_at: datetime | None
    new_news: int
    new_comments: int
    sentiment_analyzed: int
    error: str | None
    created_at: datetime
    # 1-based rank of this job among same-symbol jobs created on the same
    # local-UTC date. Populated by the router (computed at query time);
    # 1 means "first analysis of the day", 2 means "second analysis", etc.
    today_run_number: int = 1
    # Computed: this job's ordinal among the same symbol's jobs created today
    # (1 = first run, 2 = second, …). Lets the UI show "今日第 N 次分析" so
    # repeat refreshes on the same day are visible.
    today_run_number: int = 1


class StockCreate(BaseModel):
    """Payload for POST /api/stocks.

    Name is optional — when omitted, the backend looks the symbol up via
    Finnhub's profile API and falls back to symbol-as-name if that fails."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    sector: str | None = None


class StockImpact(BaseModel):
    """Pre-delete impact report — counts the rows that hard-delete will touch."""

    news_count: int
    comment_count: int
    sentiment_count: int
    market_summary_count: int

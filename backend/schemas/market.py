from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MarketHistoryPoint(BaseModel):
    """One day of market-wide sentiment (aggregated across all monitored stocks)."""

    summary_date: date
    sentiment_score: float | None
    positive_count: int
    negative_count: int
    neutral_count: int
    total_count: int


class MarketTodayResponse(BaseModel):
    today: MarketHistoryPoint
    yesterday: MarketHistoryPoint | None
    change: float | None  # today.sentiment_score - yesterday.sentiment_score


class StockTrendingItem(BaseModel):
    """One row of the 'top movers' ranking.

    ``positive/negative/neutral_count`` and ``total_count`` are *today's*
    distribution from ``market_summary``. ``news_count`` is the lifetime
    count of news rows for this stock — that's what the UI shows in the
    "篇數" column so the count matches what users see in news listings."""

    symbol: str
    name: str
    sentiment_score: float | None
    positive_count: int
    negative_count: int
    neutral_count: int
    total_count: int
    news_count: int = 0
    summary_date: date
    top_keywords: list[str] | None = None

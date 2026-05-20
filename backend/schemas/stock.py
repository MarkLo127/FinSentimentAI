from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class StockListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    exchange: str | None
    sector: str | None


class StockSentimentPoint(BaseModel):
    """One day of sentiment for one stock."""

    summary_date: date
    sentiment_score: float | None
    positive_count: int
    negative_count: int
    neutral_count: int
    total_count: int


class StockDetailResponse(BaseModel):
    stock: StockListItem
    sentiment_today: float | None = Field(
        default=None, description="Latest available sentiment_score for this stock"
    )
    trend: list[StockSentimentPoint] = Field(default_factory=list)
    top_keywords: list[str] = Field(default_factory=list)

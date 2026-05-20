from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class SentimentSnippet(BaseModel):
    """Compact sentiment summary embedded in a news/comment row.

    Bilingual fields (``*_zh`` / ``*_en``) are populated from
    ``analysis_metadata`` so list views can show the user's UI-language
    title without an extra round-trip."""

    model_config = ConfigDict(from_attributes=True)

    sentiment_label: Literal["positive", "negative", "neutral"]
    confidence: float
    model_version: str
    is_clickbait: bool | None = None
    key_drivers: list[str] | None = None
    title_zh: str | None = None
    title_en: str | None = None
    key_drivers_zh: list[str] | None = None
    key_drivers_en: list[str] | None = None


class NewsListItem(BaseModel):
    """Row shape for /api/news list views (no full body)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int | None
    title: str
    url: str
    source: str
    language: str
    summary: str | None
    fetched_via: str | None
    content_length: int | None
    published_at: datetime | None
    fetched_at: datetime
    sentiment: SentimentSnippet | None = None


class NewsDetailResponse(BaseModel):
    """Detail view — includes full body and the full sentiment payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int | None
    stock_symbol: str | None
    title: str
    url: str
    source: str
    language: str
    summary: str | None
    full_content: str | None
    fetched_via: str | None
    content_length: int | None
    published_at: datetime | None
    fetched_at: datetime
    sentiment: SentimentSnippet | None
    analysis_metadata: dict[str, Any] | None = None

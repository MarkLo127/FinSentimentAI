from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NewsItem:
    """新聞型來源（marketaux / finnhub / newsapi / alpha_vantage）統一格式。"""

    source: str  # one of NEWS_SOURCES
    title: str
    url: str
    summary: str | None = None
    language: str = "en"
    published_at: datetime | None = None
    ticker: str | None = None  # 觸發本次抓取的 ticker（若有）
    # Alpha Vantage 自帶情緒分數，存入 sentiment_results 作 baseline
    baseline_sentiment_label: str | None = None
    baseline_sentiment_score: float | None = None

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class SocialPost:
    """社群來源（ptt / stocktwits）統一格式。"""

    platform: str  # one of SOCIAL_PLATFORMS
    content: str
    post_url: str
    post_title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    ticker: str | None = None
    platform_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.post_url.encode("utf-8")).hexdigest()


class BaseFetcher(ABC):
    """Abstract base for all 7 data-source fetchers.

    Subclasses implement either ``fetch_news`` (returning NewsItem list) or
    ``fetch_social`` (returning SocialPost list). The pipeline dispatches by
    return type, so each subclass overrides exactly one.
    """

    source_name: str  # set by subclass

    async def fetch_news(self, ticker: str) -> Sequence[NewsItem]:
        raise NotImplementedError

    async def fetch_social(self, ticker: str | None = None) -> Sequence[SocialPost]:
        raise NotImplementedError

    @abstractmethod
    async def ping(self) -> bool:
        """Quick connectivity check used by smoke_fetchers.py."""

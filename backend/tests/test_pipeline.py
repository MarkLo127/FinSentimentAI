"""Pipeline tests using an in-memory SQLite DB (drops Postgres-specific JSONB/ARRAY).

These tests focus on the orchestration logic — fetchers and extractor are
patched out so we exercise dedupe, persistence, baseline insertion, and the
news-vs-social split independently.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from database import Base  # noqa: E402
from models.comment import Comment  # noqa: E402
from models.news import News  # noqa: E402
from models.sentiment import SentimentResult  # noqa: E402
from models.stock import Stock  # noqa: E402
from models.user import User  # noqa: E402
from services.content_extractor import ExtractedContent  # noqa: E402
from services.fetchers.base import NewsItem, SocialPost  # noqa: E402
from services.settings_store import UserKeys  # noqa: E402

# Stock/news are now per-user; tests run the pipeline as this fixed user id.
TEST_USER_ID = 1
# All fetchers fed with a non-empty key so they don't short-circuit on "missing".
TEST_KEYS = UserKeys(
    anthropic="k", marketaux="k", finnhub="k", newsapi="k", alpha_vantage="k", jina="k"
)


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:", future=True)


@pytest_asyncio.fixture
async def db_session():
    engine = _make_engine()
    async with engine.begin() as conn:
        # SQLite doesn't support JSONB / ARRAY — for tests we map to JSON / String list
        from sqlalchemy import JSON, String
        from sqlalchemy.dialects import postgresql

        # Force fallback for SQLite
        Comment.__table__.c.platform_metadata.type = JSON()
        SentimentResult.__table__.c.analysis_metadata.type = JSON()
        from models.market_summary import MarketSummary

        MarketSummary.__table__.c.top_keywords.type = JSON()
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessionmaker() as s:
        s.add(User(id=TEST_USER_ID, username="t", email="t@t.io", password_hash="x"))
        s.add(Stock(user_id=TEST_USER_ID, symbol="TSM", name="TSMC", exchange="NYSE"))
        await s.commit()
        yield s, engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_persists_news_and_dedupes(db_session, monkeypatch):
    session, engine = db_session

    fake_news = [
        NewsItem(source="marketaux", title="A", url="https://example.com/1", summary="s1",
                 published_at=datetime(2026, 5, 15, tzinfo=UTC), ticker="TSM"),
        NewsItem(source="marketaux", title="A dup", url="https://example.com/1", summary="dup",
                 ticker="TSM"),
        NewsItem(source="finnhub", title="B", url="https://example.com/2", summary="s2",
                 ticker="TSM"),
    ]

    from services import pipeline as P

    async def _fake_extract(url, fallback_snippet=None, *, client=None, jina_key=None):
        return ExtractedContent(text="full text " * 100, fetched_via="jina", length=1000)

    monkeypatch.setattr(P, "fetch_full_content", _fake_extract)
    monkeypatch.setattr(P, "SessionLocal", lambda: _SessionWrapper(session))

    async def _fn(self, ticker):
        return fake_news if isinstance(self, P.MarketauxFetcher) or isinstance(self, P.FinnhubFetcher) else []

    # Make all news fetchers a no-op except marketaux/finnhub
    for cls in P.NEWS_FETCHERS:
        monkeypatch.setattr(cls, "fetch_news", AsyncMock(return_value=fake_news if cls.source_name in ("marketaux",) else []))
    for cls in P.SOCIAL_FETCHERS:
        monkeypatch.setattr(cls, "fetch_social", AsyncMock(return_value=[]))

    stats = await P.run_for_ticker("TSM", user_id=TEST_USER_ID, keys=TEST_KEYS)

    # 3 items in, 2 unique URLs → 2 inserted, 1 deduped
    assert stats.fetched_news == 3
    assert stats.new_news_rows == 2
    assert stats.skipped_duplicates >= 1
    assert stats.via_jina == 2

    rows = (await session.execute(select(News))).scalars().all()
    assert len(rows) == 2
    assert {r.url for r in rows} == {"https://example.com/1", "https://example.com/2"}
    assert all(r.fetched_via == "jina" for r in rows)


@pytest.mark.asyncio
async def test_pipeline_persists_alpha_vantage_baseline(db_session, monkeypatch):
    session, engine = db_session
    from services import pipeline as P

    av_item = NewsItem(
        source="alpha_vantage",
        title="AV news",
        url="https://example.com/av",
        summary="sum",
        ticker="TSM",
        baseline_sentiment_label="positive",
        baseline_sentiment_score=0.42,
    )

    async def _fake_extract(url, fallback_snippet=None, *, client=None, jina_key=None):
        return ExtractedContent(text="x" * 1000, fetched_via="jina", length=1000)

    monkeypatch.setattr(P, "fetch_full_content", _fake_extract)
    monkeypatch.setattr(P, "SessionLocal", lambda: _SessionWrapper(session))

    for cls in P.NEWS_FETCHERS:
        monkeypatch.setattr(cls, "fetch_news",
                            AsyncMock(return_value=[av_item] if cls.source_name == "alpha_vantage" else []))
    for cls in P.SOCIAL_FETCHERS:
        monkeypatch.setattr(cls, "fetch_social", AsyncMock(return_value=[]))

    stats = await P.run_for_ticker("TSM", user_id=TEST_USER_ID, keys=TEST_KEYS)
    assert stats.new_news_rows == 1
    assert stats.new_baseline_rows == 1

    sentiments = (await session.execute(select(SentimentResult))).scalars().all()
    assert len(sentiments) == 1
    assert sentiments[0].model_version == "alpha_vantage_v1"
    assert sentiments[0].sentiment_label == "positive"
    assert sentiments[0].confidence == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_pipeline_persists_social_without_extractor(db_session, monkeypatch):
    """Social posts must NOT go through the content extractor."""
    session, engine = db_session
    from services import pipeline as P

    post = SocialPost(
        platform="stocktwits",
        content="TSM to the moon",
        post_url="https://stocktwits.com/u/message/1",
        author="trader42",
        platform_metadata={"sentiment": "bullish"},
        ticker="TSM",
    )

    extractor_calls = 0

    async def _fake_extract(url, fallback_snippet=None, *, client=None, jina_key=None):
        nonlocal extractor_calls
        extractor_calls += 1
        return ExtractedContent(text="x" * 1000, fetched_via="jina", length=1000)

    monkeypatch.setattr(P, "fetch_full_content", _fake_extract)
    monkeypatch.setattr(P, "SessionLocal", lambda: _SessionWrapper(session))

    for cls in P.NEWS_FETCHERS:
        monkeypatch.setattr(cls, "fetch_news", AsyncMock(return_value=[]))
    for cls in P.SOCIAL_FETCHERS:
        monkeypatch.setattr(cls, "fetch_social",
                            AsyncMock(return_value=[post] if cls.source_name == "stocktwits" else []))

    stats = await P.run_for_ticker("TSM", user_id=TEST_USER_ID, keys=TEST_KEYS)
    assert stats.new_comment_rows == 1
    assert extractor_calls == 0  # social posts bypass extractor

    comments = (await session.execute(select(Comment))).scalars().all()
    assert len(comments) == 1
    assert comments[0].platform == "stocktwits"
    assert comments[0].platform_metadata == {"sentiment": "bullish"}


class _SessionWrapper:
    """Wraps a session so the pipeline can use ``async with SessionLocal() as s``
    against our test session without it being closed between tests."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False

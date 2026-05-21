"""End-to-end pipeline: fetch → extract → dedupe → persist.

Used by:
  - APScheduler (Week 8)
  - Manual CLI: ``uv run python -m scripts.run_pipeline TSM``

Stages:
  1. Fan out across all 7 fetchers in parallel.
  2. For news items: extract full content via 3-layer fallback.
     For social posts: skip (content is already complete).
  3. Dedupe by url_hash against the DB and within the batch.
  4. Bulk-insert ``news`` / ``comments`` rows.
  5. For Alpha Vantage rows that carry a baseline sentiment label,
     insert a corresponding ``sentiment_results`` row tagged
     ``model_version='alpha_vantage_v1'`` — this is the API-provided baseline
     used in Week 6 to compare against our own FinBERT outputs.

The pipeline DOES NOT run FinBERT/Chinese sentiment here — that's Week 5/6's
job. We only fill ``news.fetched_via`` and persist raw data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.comment import Comment
from models.news import News
from models.sentiment import SentimentResult
from models.stock import Stock
from services.content_extractor import fetch_full_content
from services.fetchers.alpha_vantage import AlphaVantageFetcher
from services.fetchers.base import BaseFetcher, NewsItem, SocialPost
from services.fetchers.finnhub import FinnhubFetcher
from services.fetchers.marketaux import MarketauxFetcher
from services.fetchers.newsapi import NewsApiFetcher
from services.fetchers.ptt import PttFetcher
from services.fetchers.stocktwits import StockTwitsFetcher
from services.settings_store import UserKeys

NEWS_FETCHERS: list[type[BaseFetcher]] = [
    MarketauxFetcher,
    FinnhubFetcher,
    NewsApiFetcher,
    AlphaVantageFetcher,
]
SOCIAL_FETCHERS: list[type[BaseFetcher]] = [
    StockTwitsFetcher,
    PttFetcher,
]


@dataclass
class PipelineStats:
    fetched_news: int = 0
    fetched_social: int = 0
    new_news_rows: int = 0
    new_comment_rows: int = 0
    new_baseline_rows: int = 0
    skipped_duplicates: int = 0
    via_jina: int = 0
    via_trafilatura: int = 0
    via_snippet: int = 0

    def log(self) -> None:
        logger.info("=" * 60)
        logger.info("Pipeline stats:")
        for f in self.__dataclass_fields__:
            logger.info("  {:<24} = {}", f, getattr(self, f))
        logger.info("=" * 60)


async def _fetch_all_news(ticker: str, keys: UserKeys) -> list[NewsItem]:
    # Each news fetcher gets the user's own key for its source; a fetcher with
    # a blank key logs a warning and returns [] (see fetcher.fetch_news).
    key_for = {
        "marketaux": keys.marketaux,
        "finnhub": keys.finnhub,
        "newsapi": keys.newsapi,
        "alpha_vantage": keys.alpha_vantage,
    }
    news_fetchers = [cls(api_key=key_for[cls.source_name]) for cls in NEWS_FETCHERS]
    results = await asyncio.gather(
        *(f.fetch_news(ticker) for f in news_fetchers),
        return_exceptions=True,
    )
    items: list[NewsItem] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("news fetcher error: {}", r)
            continue
        items.extend(r)
    return items


async def _fetch_all_social(ticker: str) -> list[SocialPost]:
    results = await asyncio.gather(
        *(cls().fetch_social(ticker) for cls in SOCIAL_FETCHERS),
        return_exceptions=True,
    )
    posts: list[SocialPost] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("social fetcher error: {}", r)
            continue
        posts.extend(r)
    return posts


async def _get_stock_id(session: AsyncSession, ticker: str, user_id: int) -> int | None:
    row = await session.execute(
        select(Stock.id).where(Stock.symbol == ticker, Stock.user_id == user_id)
    )
    return row.scalar_one_or_none()


async def _existing_news_hashes(
    session: AsyncSession, hashes: list[str], stock_id: int | None
) -> set[str]:
    if not hashes:
        return set()
    rows = await session.execute(
        select(News.url_hash)
        .where(News.url_hash.in_(hashes))
        .where(News.stock_id == stock_id)
    )
    return set(rows.scalars().all())


async def _existing_comment_hashes(
    session: AsyncSession, hashes: list[str], stock_id: int | None
) -> set[str]:
    if not hashes:
        return set()
    rows = await session.execute(
        select(Comment.url_hash)
        .where(Comment.url_hash.in_(hashes))
        .where(Comment.stock_id == stock_id)
    )
    return set(rows.scalars().all())


async def _persist_news(
    session: AsyncSession,
    items: list[NewsItem],
    stock_id: int | None,
    stats: PipelineStats,
    client: httpx.AsyncClient,
    jina_key: str,
) -> list[tuple[NewsItem, int]]:
    # Dedupe within batch and against DB (scoped to this stock — the same
    # url_hash may legitimately exist under a different user's stock).
    by_hash: dict[str, NewsItem] = {}
    for item in items:
        if not item.url:
            continue
        by_hash.setdefault(item.url_hash, item)
    stats.skipped_duplicates += len(items) - len(by_hash)

    existing = await _existing_news_hashes(session, list(by_hash), stock_id)
    new_items = [it for h, it in by_hash.items() if h not in existing]
    stats.skipped_duplicates += len(existing)

    inserted: list[tuple[NewsItem, int]] = []
    for item in new_items:
        extracted = await fetch_full_content(
            item.url, fallback_snippet=item.summary, client=client, jina_key=jina_key
        )
        if extracted.fetched_via == "jina":
            stats.via_jina += 1
        elif extracted.fetched_via == "trafilatura":
            stats.via_trafilatura += 1
        else:
            stats.via_snippet += 1

        # ON CONFLICT DO NOTHING covers the race between our pre-check above and
        # a concurrent pipeline (e.g. scheduler tick overlapping a user-triggered
        # /refresh) inserting the same url_hash. Returns the new row id when an
        # insert actually happened, NULL when the conflict skipped it.
        stmt = (
            pg_insert(News)
            .values(
                stock_id=stock_id,
                title=item.title,
                url=item.url,
                url_hash=item.url_hash,
                source=item.source,
                language=item.language,
                summary=item.summary,
                full_content=extracted.text or None,
                fetched_via=extracted.fetched_via,
                content_length=extracted.length or None,
                published_at=item.published_at,
            )
            .on_conflict_do_nothing(index_elements=["stock_id", "url_hash"])
            .returning(News.id)
        )
        new_id = (await session.execute(stmt)).scalar_one_or_none()
        if new_id is None:
            stats.skipped_duplicates += 1
            continue
        inserted.append((item, new_id))
        stats.new_news_rows += 1

    return inserted


async def _persist_baselines(
    session: AsyncSession,
    inserted: list[tuple[NewsItem, int]],
    stock_id: int | None,
    stats: PipelineStats,
) -> None:
    """Insert Alpha Vantage baseline sentiment rows (model_version='alpha_vantage_v1')."""
    for item, news_id in inserted:
        if item.source != "alpha_vantage" or not item.baseline_sentiment_label:
            continue
        session.add(
            SentimentResult(
                news_id=news_id,
                stock_id=stock_id,
                sentiment_label=item.baseline_sentiment_label,
                confidence=abs(item.baseline_sentiment_score or 0.0),
                analyzed_text=None,
                model_version="alpha_vantage_v1",
            )
        )
        stats.new_baseline_rows += 1


async def _persist_social(
    session: AsyncSession,
    posts: list[SocialPost],
    stock_id: int | None,
    stats: PipelineStats,
) -> None:
    by_hash: dict[str, SocialPost] = {}
    for p in posts:
        if not p.post_url:
            continue
        by_hash.setdefault(p.url_hash, p)
    stats.skipped_duplicates += len(posts) - len(by_hash)

    existing = await _existing_comment_hashes(session, list(by_hash), stock_id)
    new_posts = [p for h, p in by_hash.items() if h not in existing]
    stats.skipped_duplicates += len(existing)

    for post in new_posts:
        # Use UPSERT to be extra-safe against concurrent runs hitting the same url_hash
        stmt = (
            pg_insert(Comment)
            .values(
                stock_id=stock_id,
                platform=post.platform,
                post_title=post.post_title,
                content=post.content,
                author=post.author,
                post_url=post.post_url,
                url_hash=post.url_hash,
                platform_metadata=post.platform_metadata or None,
                published_at=post.published_at,
            )
            .on_conflict_do_nothing(index_elements=["stock_id", "url_hash"])
            .returning(Comment.id)
        )
        result = await session.execute(stmt)
        if result.first() is not None:
            stats.new_comment_rows += 1


async def run_for_ticker(ticker: str, *, user_id: int, keys: UserKeys) -> PipelineStats:
    stats = PipelineStats()

    news_task = _fetch_all_news(ticker, keys)
    social_task = _fetch_all_social(ticker)
    news_items, social_posts = await asyncio.gather(news_task, social_task)
    stats.fetched_news = len(news_items)
    stats.fetched_social = len(social_posts)
    logger.info(
        "Fetched {} news + {} social posts for {}", len(news_items), len(social_posts), ticker
    )

    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        async with SessionLocal() as session:
            stock_id = await _get_stock_id(session, ticker, user_id)
            if stock_id is None:
                logger.warning(
                    "ticker {} not in user {}'s watchlist — rows will have NULL stock_id",
                    ticker,
                    user_id,
                )

            inserted = await _persist_news(
                session, news_items, stock_id, stats, http_client, keys.jina
            )
            await _persist_baselines(session, inserted, stock_id, stats)
            await _persist_social(session, social_posts, stock_id, stats)

            await session.commit()

    stats.log()
    return stats

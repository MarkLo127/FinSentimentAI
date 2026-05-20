from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from database import get_db
from models.news import News
from models.news_translation import NewsTranslation
from models.sentiment import SentimentResult
from models.stock import Stock
from schemas.news import NewsDetailResponse, NewsListItem, SentimentSnippet
from services.translator import TranslationError, translate_news

CLAUDE_MODEL_VERSION = "claude-haiku-4-5"

router = APIRouter(prefix="/api/news", tags=["news"])


def _to_snippet(s: SentimentResult | None) -> SentimentSnippet | None:
    if s is None:
        return None
    meta = s.analysis_metadata or {}
    return SentimentSnippet(
        sentiment_label=s.sentiment_label,
        confidence=s.confidence,
        model_version=s.model_version,
        is_clickbait=meta.get("is_clickbait"),
        key_drivers=meta.get("key_drivers"),
        title_zh=meta.get("title_zh"),
        title_en=meta.get("title_en"),
        key_drivers_zh=meta.get("key_drivers_zh"),
        key_drivers_en=meta.get("key_drivers_en"),
    )


@router.get("", response_model=list[NewsListItem])
async def list_news(
    limit: int = Query(20, ge=1, le=100),
    symbol: str | None = Query(None, description="Filter to one stock symbol"),
    q: str | None = Query(None, description="Substring match on title"),
    db: AsyncSession = Depends(get_db),
) -> list[NewsListItem]:
    """Latest news with attached Claude sentiment (when available).

    When a news has been re-analyzed (multiple ``sentiment_results`` rows),
    we attach only the **latest** analysis — otherwise the JOIN would
    produce one output row per analysis run, breaking sentiment filters and
    counts. We compute the latest id via a correlated subquery."""
    latest_sentiment_id = (
        select(func.max(SentimentResult.id))
        .where(SentimentResult.news_id == News.id)
        .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
        .correlate(News)
        .scalar_subquery()
    )
    s = aliased(SentimentResult)
    stmt = (
        select(News, s)
        .outerjoin(s, s.id == latest_sentiment_id)
        # Hide orphan news whose stock was deleted (or was never linked); FK
        # CASCADE prevents new orphans, but legacy rows linger in the DB.
        .where(News.stock_id.is_not(None))
        .order_by(desc(News.published_at), desc(News.fetched_at))
        .limit(limit)
    )
    if symbol:
        # Sub-select stock id to keep the join cheap
        stock_id = (
            await db.execute(select(Stock.id).where(Stock.symbol == symbol.upper()))
        ).scalar_one_or_none()
        if stock_id is None:
            return []
        stmt = stmt.where(News.stock_id == stock_id)
    if q:
        # Match the term against (a) the news title, OR (b) the news's linked
        # stock symbol/name. This makes "TSM" surface every article about
        # Taiwan Semiconductor, not just headlines that literally contain "TSM".
        pattern = f"%{q}%"
        matching_stock_ids = (
            await db.execute(
                select(Stock.id).where(
                    or_(Stock.symbol.ilike(pattern), Stock.name.ilike(pattern))
                )
            )
        ).scalars().all()
        if matching_stock_ids:
            stmt = stmt.where(
                or_(News.title.ilike(pattern), News.stock_id.in_(matching_stock_ids))
            )
        else:
            stmt = stmt.where(News.title.ilike(pattern))

    rows = (await db.execute(stmt)).all()
    out: list[NewsListItem] = []
    for news, sentiment in rows:
        out.append(
            NewsListItem(
                id=news.id,
                stock_id=news.stock_id,
                title=news.title,
                url=news.url,
                source=news.source,
                language=news.language,
                summary=news.summary,
                fetched_via=news.fetched_via,
                content_length=news.content_length,
                published_at=news.published_at,
                fetched_at=news.fetched_at,
                sentiment=_to_snippet(sentiment),
            )
        )
    return out


@router.get("/{news_id}", response_model=NewsDetailResponse)
async def get_news(news_id: int, db: AsyncSession = Depends(get_db)) -> NewsDetailResponse:
    news = (await db.execute(select(News).where(News.id == news_id))).scalar_one_or_none()
    if news is None:
        raise HTTPException(404, f"News {news_id} not found")
    sentiment = (
        await db.execute(
            select(SentimentResult)
            .where(SentimentResult.news_id == news_id)
            .where(SentimentResult.model_version == CLAUDE_MODEL_VERSION)
            .order_by(desc(SentimentResult.analyzed_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    symbol = None
    if news.stock_id:
        symbol = (
            await db.execute(select(Stock.symbol).where(Stock.id == news.stock_id))
        ).scalar_one_or_none()
    return NewsDetailResponse(
        id=news.id,
        stock_id=news.stock_id,
        stock_symbol=symbol,
        title=news.title,
        url=news.url,
        source=news.source,
        language=news.language,
        summary=news.summary,
        full_content=news.full_content,
        fetched_via=news.fetched_via,
        content_length=news.content_length,
        published_at=news.published_at,
        fetched_at=news.fetched_at,
        sentiment=_to_snippet(sentiment),
        analysis_metadata=sentiment.analysis_metadata if sentiment else None,
    )


@router.get("/{news_id}/translation/{lang}")
async def get_news_translation(
    news_id: int, lang: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Return cached title+body translation for the article into ``lang``;
    populate the cache on first request. Idempotent — concurrent requests
    converge to one DB row via the unique (news_id, target_language) index."""
    if lang not in ("zh-TW", "en"):
        raise HTTPException(422, "lang must be 'zh-TW' or 'en'")

    cached = (
        await db.execute(
            select(NewsTranslation)
            .where(NewsTranslation.news_id == news_id)
            .where(NewsTranslation.target_language == lang)
        )
    ).scalar_one_or_none()
    if cached is not None:
        return {
            "title": cached.translated_title,
            "body": cached.translated_body,
            "cached": True,
        }

    news = (
        await db.execute(select(News).where(News.id == news_id))
    ).scalar_one_or_none()
    if news is None:
        raise HTTPException(404, f"News {news_id} not found")

    try:
        title, body = await translate_news(news, lang)
    except TranslationError as exc:
        raise HTTPException(502, f"translation failed: {exc}") from exc

    row = NewsTranslation(
        news_id=news_id,
        target_language=lang,
        translated_title=title,
        translated_body=body,
        model_version=CLAUDE_MODEL_VERSION,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        # Race: another request inserted the same (news_id, lang) concurrently.
        # The translation we computed is still valid; just return it.
        await db.rollback()
    return {"title": title, "body": body, "cached": False}

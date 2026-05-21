from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.market_summary import MarketSummary
from models.news import News
from models.stock import Stock
from models.user import User
from schemas.market import MarketHistoryPoint, MarketTodayResponse, StockTrendingItem
from services.auth import current_user

router = APIRouter(prefix="/api/market", tags=["market"])


def _user_stock_ids(user_id: int):
    return select(Stock.id).where(Stock.user_id == user_id)


async def _aggregate_for_date(
    db: AsyncSession, target: date, user_id: int
) -> MarketHistoryPoint | None:
    """Aggregate market_summary rows across the user's stocks for one date."""
    stmt = (
        select(
            func.coalesce(func.sum(MarketSummary.positive_count), 0).label("pos"),
            func.coalesce(func.sum(MarketSummary.negative_count), 0).label("neg"),
            func.coalesce(func.sum(MarketSummary.neutral_count), 0).label("neu"),
            # Weighted average score by total_count
            func.coalesce(
                func.sum(MarketSummary.sentiment_score * MarketSummary.total_count)
                / func.nullif(func.sum(MarketSummary.total_count), 0),
                None,
            ).label("score"),
        )
        .where(MarketSummary.summary_date == target)
        .where(MarketSummary.stock_id.in_(_user_stock_ids(user_id)))
    )
    row = (await db.execute(stmt)).one()
    total = (row.pos or 0) + (row.neg or 0) + (row.neu or 0)
    if total == 0:
        return None
    return MarketHistoryPoint(
        summary_date=target,
        sentiment_score=float(row.score) if row.score is not None else None,
        positive_count=row.pos,
        negative_count=row.neg,
        neutral_count=row.neu,
        total_count=total,
    )


@router.get("/today", response_model=MarketTodayResponse)
async def market_today(
    user: Annotated[User, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
) -> MarketTodayResponse:
    """Today's overall sentiment + yesterday for change calculation.

    Falls back to the most recent two days with data if today/yesterday have none
    (useful out-of-hours or on weekends).
    """
    # Find the two most-recent distinct dates with any of the user's summaries
    dates_stmt = (
        select(MarketSummary.summary_date)
        .where(MarketSummary.stock_id.in_(_user_stock_ids(user.id)))
        .group_by(MarketSummary.summary_date)
        .order_by(desc(MarketSummary.summary_date))
        .limit(2)
    )
    dates = list((await db.execute(dates_stmt)).scalars().all())
    if not dates:
        # No data for this user — return a zero today
        today = date.today()
        return MarketTodayResponse(
            today=MarketHistoryPoint(
                summary_date=today,
                sentiment_score=None,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                total_count=0,
            ),
            yesterday=None,
            change=None,
        )

    today_point = await _aggregate_for_date(db, dates[0], user.id)
    yesterday_point = (
        await _aggregate_for_date(db, dates[1], user.id) if len(dates) > 1 else None
    )
    change = None
    if today_point and yesterday_point and today_point.sentiment_score is not None and yesterday_point.sentiment_score is not None:
        change = round(today_point.sentiment_score - yesterday_point.sentiment_score, 4)
    return MarketTodayResponse(
        today=today_point, yesterday=yesterday_point, change=change
    )


@router.get("/history", response_model=list[MarketHistoryPoint])
async def market_history(
    user: Annotated[User, Depends(current_user)],
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[MarketHistoryPoint]:
    """Daily aggregated sentiment for the past N days (oldest first)."""
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            MarketSummary.summary_date.label("d"),
            func.coalesce(func.sum(MarketSummary.positive_count), 0).label("pos"),
            func.coalesce(func.sum(MarketSummary.negative_count), 0).label("neg"),
            func.coalesce(func.sum(MarketSummary.neutral_count), 0).label("neu"),
            func.coalesce(
                func.sum(MarketSummary.sentiment_score * MarketSummary.total_count)
                / func.nullif(func.sum(MarketSummary.total_count), 0),
                None,
            ).label("score"),
        )
        .where(MarketSummary.summary_date >= cutoff)
        .where(MarketSummary.stock_id.in_(_user_stock_ids(user.id)))
        .group_by(MarketSummary.summary_date)
        .order_by(MarketSummary.summary_date)
    )
    out: list[MarketHistoryPoint] = []
    for row in (await db.execute(stmt)).all():
        total = row.pos + row.neg + row.neu
        out.append(
            MarketHistoryPoint(
                summary_date=row.d,
                sentiment_score=float(row.score) if row.score is not None else None,
                positive_count=row.pos,
                negative_count=row.neg,
                neutral_count=row.neu,
                total_count=total,
            )
        )
    return out


@router.get("/trending", response_model=list[StockTrendingItem])
async def market_trending(
    user: Annotated[User, Depends(current_user)],
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[StockTrendingItem]:
    """Top of the user's stocks by absolute sentiment_score on the latest date."""
    latest_date = (
        await db.execute(
            select(func.max(MarketSummary.summary_date)).where(
                MarketSummary.stock_id.in_(_user_stock_ids(user.id))
            )
        )
    ).scalar_one_or_none()
    if latest_date is None:
        return []

    # Lifetime news count per stock — used by UI as the "篇數" column so the
    # number matches what users see in /news?symbol=X. We keep total_count
    # (today's pos+neg+neu) as a separate field for charts that legitimately
    # care about the daily distribution.
    news_count_sq = (
        select(News.stock_id, func.count(News.id).label("news_count"))
        .where(News.stock_id.is_not(None))
        .group_by(News.stock_id)
        .subquery()
    )

    stmt = (
        select(
            Stock.symbol,
            Stock.name,
            MarketSummary.sentiment_score,
            MarketSummary.positive_count,
            MarketSummary.negative_count,
            MarketSummary.neutral_count,
            MarketSummary.total_count,
            MarketSummary.summary_date,
            MarketSummary.top_keywords,
            func.coalesce(news_count_sq.c.news_count, 0).label("news_count"),
        )
        .join(Stock, Stock.id == MarketSummary.stock_id)
        .outerjoin(news_count_sq, news_count_sq.c.stock_id == Stock.id)
        .where(MarketSummary.summary_date == latest_date)
        .where(Stock.user_id == user.id)
        .order_by(desc(func.abs(MarketSummary.sentiment_score)))
        .limit(limit)
    )
    return [
        StockTrendingItem(
            symbol=row.symbol,
            name=row.name,
            sentiment_score=row.sentiment_score,
            positive_count=row.positive_count,
            negative_count=row.negative_count,
            neutral_count=row.neutral_count,
            total_count=row.total_count,
            news_count=row.news_count,
            summary_date=row.summary_date,
            top_keywords=row.top_keywords,
        )
        for row in (await db.execute(stmt)).all()
    ]

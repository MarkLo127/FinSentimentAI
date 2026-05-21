from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.comment import Comment
from models.market_summary import MarketSummary
from models.news import News
from models.refresh_job import RefreshJob
from models.sentiment import SentimentResult
from models.stock import Stock
from models.user import User
from schemas.refresh import RefreshJobPublic, StockCreate, StockImpact
from schemas.stock import StockDetailResponse, StockListItem, StockSentimentPoint
from services.auth import current_user
from services.refresh_runner import run_refresh_job
from services.stock_lookup import lookup_stock_profile

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=list[StockListItem])
async def list_stocks(
    user: Annotated[User, Depends(current_user)],
    q: str | None = Query(None, description="Fuzzy match on symbol or name"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[Stock]:
    stmt = select(Stock).where(Stock.user_id == user.id).order_by(Stock.id).limit(limit)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Stock.symbol.ilike(pattern), Stock.name.ilike(pattern)))
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StockListItem)
async def create_stock(
    payload: StockCreate,
    user: Annotated[User, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
) -> Stock:
    symbol = payload.symbol.strip().upper()
    if not symbol or not symbol.replace("_", "").isalnum():
        raise HTTPException(422, "symbol must be alphanumeric (US tickers) or digits (TW tickers)")

    name = (payload.name or "").strip()
    exchange = (payload.exchange or "").strip() or None
    sector = (payload.sector or "").strip() or None

    # If the caller didn't supply a name (or anything other than the symbol),
    # try to enrich from Finnhub. Fallback: use the symbol itself as the name
    # so the row still satisfies our NOT NULL constraint and shows something
    # meaningful in the UI.
    if not name or name == symbol:
        profile = await lookup_stock_profile(symbol)
        name = profile.get("name") or symbol
        exchange = exchange or profile.get("exchange")
        sector = sector or profile.get("sector")

    stock = Stock(
        user_id=user.id,
        symbol=symbol,
        name=name,
        exchange=exchange,
        sector=sector,
    )
    db.add(stock)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Stock {symbol} already exists") from None
    await db.refresh(stock)
    return stock


@router.get("/{symbol}/impact", response_model=StockImpact)
async def stock_impact(
    symbol: str,
    user: Annotated[User, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
) -> StockImpact:
    """Pre-delete impact report — counts rows that hard-delete will touch."""
    stock = (
        await db.execute(
            select(Stock).where(Stock.symbol == symbol.upper(), Stock.user_id == user.id)
        )
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(404, f"Stock {symbol} not found")

    news_count = (
        await db.execute(
            select(func.count(News.id)).where(News.stock_id == stock.id)
        )
    ).scalar_one()
    comment_count = (
        await db.execute(
            select(func.count(Comment.id)).where(Comment.stock_id == stock.id)
        )
    ).scalar_one()
    sentiment_count = (
        await db.execute(
            select(func.count(SentimentResult.id)).where(
                SentimentResult.stock_id == stock.id
            )
        )
    ).scalar_one()
    summary_count = (
        await db.execute(
            select(func.count(MarketSummary.id)).where(
                MarketSummary.stock_id == stock.id
            )
        )
    ).scalar_one()
    return StockImpact(
        news_count=news_count,
        comment_count=comment_count,
        sentiment_count=sentiment_count,
        market_summary_count=summary_count,
    )


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(
    symbol: str,
    user: Annotated[User, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard delete: removes the stock + all related news, comments, sentiment,
    and market_summary rows. ``ON DELETE CASCADE`` on sentiment_results.news_id
    + sentiment_results.comment_id handles the analyses; market_summary CASCADEs
    on stock_id directly. We explicitly DELETE news + comments first so the
    SET-NULL FK from sentiment.stock_id doesn't leave dangling rows."""
    stock = (
        await db.execute(
            select(Stock).where(Stock.symbol == symbol.upper(), Stock.user_id == user.id)
        )
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(404, f"Stock {symbol} not found")

    # 1. delete news → sentiment.news_id CASCADE cleans up
    await db.execute(delete(News).where(News.stock_id == stock.id))
    # 2. delete comments → sentiment.comment_id CASCADE cleans up
    await db.execute(delete(Comment).where(Comment.stock_id == stock.id))
    # 3. delete any sentiment rows that linked only via stock_id (orphaned)
    await db.execute(
        delete(SentimentResult).where(SentimentResult.stock_id == stock.id)
    )
    # 4. delete the stock itself → market_summary CASCADEs
    await db.execute(delete(Stock).where(Stock.id == stock.id))
    await db.commit()


@router.get("/{symbol}", response_model=StockDetailResponse)
async def get_stock(
    symbol: str,
    user: Annotated[User, Depends(current_user)],
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> StockDetailResponse:
    stock = (
        await db.execute(
            select(Stock).where(Stock.symbol == symbol.upper(), Stock.user_id == user.id)
        )
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(404, f"Stock {symbol} not found")

    cutoff = date.today() - timedelta(days=days)
    trend_rows = (
        await db.execute(
            select(MarketSummary)
            .where(MarketSummary.stock_id == stock.id)
            .where(MarketSummary.summary_date >= cutoff)
            .order_by(MarketSummary.summary_date)
        )
    ).scalars().all()

    trend = [
        StockSentimentPoint(
            summary_date=r.summary_date,
            sentiment_score=r.sentiment_score,
            positive_count=r.positive_count,
            negative_count=r.negative_count,
            neutral_count=r.neutral_count,
            total_count=r.total_count,
        )
        for r in trend_rows
    ]

    latest = trend_rows[-1] if trend_rows else None
    return StockDetailResponse(
        stock=StockListItem.model_validate(stock),
        sentiment_today=latest.sentiment_score if latest else None,
        trend=trend,
        top_keywords=(latest.top_keywords if latest else None) or [],
    )


@router.post(
    "/{symbol}/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RefreshJobPublic,
)
async def refresh_stock(
    symbol: str,
    user: Annotated[User, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
) -> RefreshJobPublic:
    """Kick off an on-demand pipeline+sentiment+summary run in the background.

    Returns 202 immediately with a job_id; the browser polls
    GET /api/refresh-jobs/{job_id} for progress. Closing the browser does NOT
    cancel the work (asyncio.create_task is detached from the request)."""
    from datetime import UTC, datetime as _dt
    from sqlalchemy import cast as _cast, func as _func
    from sqlalchemy.dialects.postgresql import DATE as _DATE

    symbol = symbol.upper()
    stock = (
        await db.execute(
            select(Stock).where(Stock.symbol == symbol, Stock.user_id == user.id)
        )
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(404, f"Stock {symbol} not found in watchlist")

    # De-dupe: if a job for this user+symbol is already queued/running, return it.
    existing = (
        await db.execute(
            select(RefreshJob)
            .where(RefreshJob.symbol == symbol)
            .where(RefreshJob.user_id == user.id)
            .where(RefreshJob.state.in_(("queued", "running")))
            .order_by(RefreshJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    target_job: RefreshJob
    if existing is not None:
        target_job = existing
    else:
        target_job = RefreshJob(symbol=symbol, state="queued", user_id=user.id)
        db.add(target_job)
        await db.commit()
        await db.refresh(target_job)
        # Detach from the request — survives the HTTP response returning.
        asyncio.create_task(run_refresh_job(target_job.id, symbol, user.id))

    # Compute today_run_number for the response.
    today_utc = _dt.now(UTC).date()
    same_day_count = (
        await db.execute(
            select(_func.count(RefreshJob.id))
            .where(RefreshJob.symbol == symbol)
            .where(RefreshJob.user_id == user.id)
            .where(_cast(RefreshJob.created_at, _DATE) == today_utc)
            .where(RefreshJob.created_at <= target_job.created_at)
        )
    ).scalar_one()
    pub = RefreshJobPublic.model_validate(target_job)
    pub.today_run_number = int(same_day_count) or 1
    return pub

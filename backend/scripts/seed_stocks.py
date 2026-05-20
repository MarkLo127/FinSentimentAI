"""Seed initial stocks into the database.

Run with:  uv run python -m scripts.seed_stocks
"""

import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import SessionLocal
from models.stock import Stock

SEED_STOCKS: list[dict[str, str | None]] = [
    {"symbol": "2330", "name": "台積電", "exchange": "TWSE", "sector": "Semiconductors"},
    {"symbol": "2454", "name": "聯發科", "exchange": "TWSE", "sector": "Semiconductors"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor ADR", "exchange": "NYSE", "sector": "Semiconductors"},
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Consumer Electronics"},
    {"symbol": "MSFT", "name": "Microsoft", "exchange": "NASDAQ", "sector": "Software"},
    {"symbol": "NVDA", "name": "NVIDIA", "exchange": "NASDAQ", "sector": "Semiconductors"},
    {"symbol": "TSLA", "name": "Tesla", "exchange": "NASDAQ", "sector": "Automotive"},
    {"symbol": "GOOGL", "name": "Alphabet", "exchange": "NASDAQ", "sector": "Internet"},
    {"symbol": "AMZN", "name": "Amazon", "exchange": "NASDAQ", "sector": "E-commerce"},
    {"symbol": "META", "name": "Meta Platforms", "exchange": "NASDAQ", "sector": "Internet"},
]


async def seed() -> None:
    async with SessionLocal() as session:
        stmt = (
            pg_insert(Stock)
            .values(SEED_STOCKS)
            .on_conflict_do_nothing(index_elements=["symbol"])
        )
        await session.execute(stmt)
        await session.commit()

        result = await session.execute(select(Stock).order_by(Stock.id))
        rows = result.scalars().all()
        logger.info("Seeded {} stocks total in DB", len(rows))
        for s in rows:
            logger.info("  {} | {} | {}", s.symbol, s.name, s.exchange)


if __name__ == "__main__":
    asyncio.run(seed())

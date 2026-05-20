from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String

from database import Base


class MarketSummary(Base):
    """每日股票情緒總結（每個 stock_id + summary_date 一筆）。"""

    __tablename__ = "market_summary"
    __table_args__ = (
        UniqueConstraint("stock_id", "summary_date", name="uq_market_stock_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True, nullable=True
    )
    summary_date: Mapped[date] = mapped_column(Date, index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    top_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# 4 個新聞型來源
NEWS_SOURCES = ("marketaux", "finnhub", "newsapi", "alpha_vantage")

# 三層 fallback 標籤
FETCHED_VIA = ("jina", "trafilatura", "snippet")


class News(Base):
    __tablename__ = "news"
    # url_hash is unique *per stock* (i.e. per user, since stocks are per-user):
    # the same public article can legitimately exist under two different users'
    # watchlist stocks, each with its own independent sentiment analysis.
    __table_args__ = (
        UniqueConstraint("stock_id", "url_hash", name="uq_news_stock_url_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(20))  # marketaux | finnhub | newsapi | alpha_vantage
    language: Mapped[str] = mapped_column(String(10), default="en")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_via: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # jina | trafilatura | snippet
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# 2 個社群來源
SOCIAL_PLATFORMS = ("ptt", "stocktwits")


class Comment(Base):
    """社群貼文（PTT / StockTwits）— 內文本來就完整，不需 Jina。"""

    __tablename__ = "comments"
    # url_hash is unique *per stock* (per user) — see News for rationale.
    __table_args__ = (
        UniqueConstraint("stock_id", "url_hash", name="uq_comments_stock_url_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True, nullable=True
    )
    platform: Mapped[str] = mapped_column(String(20))  # ptt | stocktwits
    post_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), index=True)
    platform_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # StockTwits: {"sentiment": "bullish", "id": 123}
    # PTT:        {"push": 12, "boo": 3}
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

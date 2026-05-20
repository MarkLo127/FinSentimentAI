from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# 統一情緒標籤
SENTIMENT_LABELS = ("positive", "negative", "neutral")

# 已知 model_version 列舉（用字串而非 Enum，方便擴充）
MODEL_VERSIONS = (
    "ProsusAI/finbert",
    "uer/roberta-base-finetuned-chinanews-chinese",
    "alpha_vantage_v1",  # 第三方 baseline，非我們的模型
)


class SentimentResult(Base):
    """情緒分析結果。同一筆 news/comment 可有多筆，用 model_version 區分。"""

    __tablename__ = "sentiment_results"
    __table_args__ = (
        CheckConstraint(
            "(news_id IS NOT NULL AND comment_id IS NULL) OR "
            "(news_id IS NULL AND comment_id IS NOT NULL)",
            name="chk_sentiment_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int | None] = mapped_column(
        ForeignKey("news.id", ondelete="CASCADE"), index=True, nullable=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True, nullable=True
    )
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"), index=True, nullable=True
    )
    sentiment_label: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    analyzed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(
        String(80), default="claude-haiku-4-5", index=True
    )
    # LLM-specific structured output (key_drivers, is_clickbait, reasoning).
    # NULL for non-LLM rows like alpha_vantage_v1 baselines.
    analysis_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String

from database import Base


class NewsTranslation(Base):
    """Lazy on-demand translation cache for one news article into one
    target language. Populated by `GET /api/news/{id}/translation/{lang}` on
    first request; subsequent requests are pure DB reads."""

    __tablename__ = "news_translations"
    __table_args__ = (
        UniqueConstraint(
            "news_id", "target_language", name="uq_news_translation_lang"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news.id", ondelete="CASCADE"), index=True
    )
    target_language: Mapped[str] = mapped_column(String(10))  # 'zh-TW' | 'en'
    translated_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    translated_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

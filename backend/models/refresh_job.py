from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

REFRESH_STATES = ("queued", "running", "succeeded", "failed")
PROGRESS_STAGES = ("fetching", "analyzing", "summarizing")


class RefreshJob(Base):
    """Tracks an on-demand pipeline+sentiment+summary run for one ticker.

    Replaces the previous synchronous POST /api/stocks/{symbol}/refresh —
    that endpoint now writes a row here, fires asyncio.create_task, and
    returns 202 immediately. The browser polls GET /api/refresh-jobs/{id}
    for state transitions, so closing the tab no longer aborts the work.
    """

    __tablename__ = "refresh_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    state: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    new_news: Mapped[int] = mapped_column(Integer, default=0)
    new_comments: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

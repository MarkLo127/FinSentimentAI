from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AppSetting(Base):
    """Per-user key/value store for runtime-mutable settings — the API keys
    each user pastes through the /settings UI. ``value`` is Fernet-encrypted
    at rest (see services/crypto.py); the composite (user_id, key) PK keeps
    every user's keys isolated."""

    __tablename__ = "app_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # Fernet ciphertext
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

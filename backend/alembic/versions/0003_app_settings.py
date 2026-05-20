"""app_settings: DB-backed runtime API-key overrides

Why: lets the operator paste keys through the UI instead of editing .env +
restarting the container. Backend and scheduler both read this table at
each pipeline tick (and on startup) and overlay the values into os.environ
so the existing pydantic-settings code path picks them up unchanged.

Revision ID: 0003_app_settings
Revises: 0002_sentiment_metadata
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_app_settings"
down_revision: str | None = "0002_sentiment_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("app_settings")

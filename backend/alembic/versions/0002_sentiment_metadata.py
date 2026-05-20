"""sentiment_results: add analysis_metadata JSONB for LLM rich output

Stores key_drivers, is_clickbait, reasoning from Claude Haiku analysis.
Existing alpha_vantage_v1 baseline rows leave this NULL.

Revision ID: 0002_sentiment_metadata
Revises: 0001_initial
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_sentiment_metadata"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sentiment_results",
        sa.Column("analysis_metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sentiment_results", "analysis_metadata")

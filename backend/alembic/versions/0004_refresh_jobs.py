"""create refresh_jobs table for async on-demand stock refresh

Revision ID: 0004_refresh_jobs
Revises: 0003_app_settings
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_refresh_jobs"
down_revision: str | None = "0003_app_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("progress_stage", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_news", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sentiment_analyzed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_refresh_jobs_symbol", "refresh_jobs", ["symbol"])
    op.create_index("idx_refresh_jobs_state", "refresh_jobs", ["state"])
    op.create_index(
        "idx_refresh_jobs_created_at",
        "refresh_jobs",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("refresh_jobs")

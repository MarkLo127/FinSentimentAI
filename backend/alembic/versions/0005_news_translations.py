"""create news_translations cache table for on-demand article translation

Revision ID: 0005_news_translations
Revises: 0004_refresh_jobs
Create Date: 2026-05-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_news_translations"
down_revision: str | None = "0004_refresh_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_translations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "news_id",
            sa.Integer,
            sa.ForeignKey("news.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_language", sa.String(10), nullable=False),
        sa.Column("translated_title", sa.String(500), nullable=True),
        sa.Column("translated_body", sa.Text, nullable=True),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "news_id", "target_language", name="uq_news_translation_lang"
        ),
    )
    op.create_index(
        "idx_news_translations_news_id", "news_translations", ["news_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_news_translations_news_id", table_name="news_translations")
    op.drop_table("news_translations")

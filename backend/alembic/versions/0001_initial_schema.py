"""initial schema: users, stocks, news, comments, sentiment_results, market_summary

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("symbol", name="uq_stocks_symbol"),
    )
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"])

    op.create_table(
        "news",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "stock_id",
            sa.Integer,
            sa.ForeignKey("stocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("full_content", sa.Text, nullable=True),
        sa.Column("fetched_via", sa.String(20), nullable=True),
        sa.Column("content_length", sa.Integer, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("url", name="uq_news_url"),
        sa.UniqueConstraint("url_hash", name="uq_news_url_hash"),
    )
    op.create_index("idx_news_stock_id", "news", ["stock_id"])
    op.create_index(
        "idx_news_published_at", "news", [sa.text("published_at DESC")]
    )
    op.create_index("idx_news_url_hash", "news", ["url_hash"])
    op.create_index("idx_news_source", "news", ["source"])
    op.create_index("idx_news_fetched_via", "news", ["fetched_via"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "stock_id",
            sa.Integer,
            sa.ForeignKey("stocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("post_title", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("author", sa.String(100), nullable=True),
        sa.Column("post_url", sa.Text, nullable=True),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("platform_metadata", JSONB, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("url_hash", name="uq_comments_url_hash"),
    )
    op.create_index("idx_comments_stock_id", "comments", ["stock_id"])
    op.create_index(
        "idx_comments_published_at", "comments", [sa.text("published_at DESC")]
    )
    op.create_index("idx_comments_platform", "comments", ["platform"])

    op.create_table(
        "sentiment_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "news_id",
            sa.Integer,
            sa.ForeignKey("news.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "comment_id",
            sa.Integer,
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "stock_id",
            sa.Integer,
            sa.ForeignKey("stocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sentiment_label", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("analyzed_text", sa.Text, nullable=True),
        sa.Column(
            "model_version",
            sa.String(80),
            nullable=False,
            server_default="ProsusAI/finbert",
        ),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(news_id IS NOT NULL AND comment_id IS NULL) OR "
            "(news_id IS NULL AND comment_id IS NOT NULL)",
            name="chk_sentiment_source",
        ),
    )
    op.create_index("idx_sentiment_news_id", "sentiment_results", ["news_id"])
    op.create_index("idx_sentiment_comment_id", "sentiment_results", ["comment_id"])
    op.create_index("idx_sentiment_stock_id", "sentiment_results", ["stock_id"])
    op.create_index("idx_sentiment_label", "sentiment_results", ["sentiment_label"])
    op.create_index("idx_sentiment_model_version", "sentiment_results", ["model_version"])

    op.create_table(
        "market_summary",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "stock_id",
            sa.Integer,
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("summary_date", sa.Date, nullable=False),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column(
            "positive_count", sa.Integer, server_default="0", nullable=False
        ),
        sa.Column(
            "negative_count", sa.Integer, server_default="0", nullable=False
        ),
        sa.Column(
            "neutral_count", sa.Integer, server_default="0", nullable=False
        ),
        sa.Column("total_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("top_keywords", ARRAY(sa.String), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "stock_id", "summary_date", name="uq_market_stock_date"
        ),
    )
    op.create_index(
        "idx_market_date", "market_summary", [sa.text("summary_date DESC")]
    )
    op.create_index(
        "idx_market_stock_date", "market_summary", ["stock_id", "summary_date"]
    )


def downgrade() -> None:
    op.drop_table("market_summary")
    op.drop_table("sentiment_results")
    op.drop_table("comments")
    op.drop_table("news")
    op.drop_table("stocks")
    op.drop_table("users")

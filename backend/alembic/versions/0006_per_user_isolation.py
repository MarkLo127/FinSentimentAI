"""per-user isolation: scope stocks/refresh_jobs/app_settings to a user,
make news/comments url_hash unique per-stock, encrypt+per-user API keys

Revision ID: 0006_per_user_isolation
Revises: 0005_news_translations
Create Date: 2026-05-21

Backfill policy (decided with the operator):
  - Existing stocks / refresh_jobs are assigned to the lowest-id user
    (the first registered account, e.g. ``deploytest``). Rows that cannot
    be owned (no users at all) are deleted.
  - app_settings is wiped and rebuilt with a composite (user_id, key) PK.
    The old global keys were placeholder values; each user re-enters their
    own keys through the /settings UI, now stored Fernet-encrypted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_per_user_isolation"
down_revision: str | None = "0005_news_translations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── stocks: add owner, switch unique(symbol) → unique(user_id, symbol) ──
    op.add_column(
        "stocks",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE stocks SET user_id = (SELECT MIN(id) FROM users) "
        "WHERE user_id IS NULL"
    )
    op.execute("DELETE FROM stocks WHERE user_id IS NULL")
    op.alter_column("stocks", "user_id", nullable=False)
    op.create_index("ix_stocks_user_id", "stocks", ["user_id"])
    op.drop_constraint("uq_stocks_symbol", "stocks", type_="unique")
    op.create_unique_constraint(
        "uq_stocks_user_symbol", "stocks", ["user_id", "symbol"]
    )

    # ── news: url_hash unique per-stock (same article allowed across users) ──
    op.drop_constraint("uq_news_url", "news", type_="unique")
    op.drop_constraint("uq_news_url_hash", "news", type_="unique")
    op.create_unique_constraint(
        "uq_news_stock_url_hash", "news", ["stock_id", "url_hash"]
    )

    # ── comments: same per-stock url_hash uniqueness ──
    op.drop_constraint("uq_comments_url_hash", "comments", type_="unique")
    op.create_unique_constraint(
        "uq_comments_stock_url_hash", "comments", ["stock_id", "url_hash"]
    )

    # ── refresh_jobs: add owner ──
    op.add_column(
        "refresh_jobs",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE refresh_jobs SET user_id = (SELECT MIN(id) FROM users) "
        "WHERE user_id IS NULL"
    )
    op.execute("DELETE FROM refresh_jobs WHERE user_id IS NULL")
    op.alter_column("refresh_jobs", "user_id", nullable=False)
    op.create_index("ix_refresh_jobs_user_id", "refresh_jobs", ["user_id"])

    # ── app_settings: wipe + rebuild with composite (user_id, key) PK ──
    op.drop_table("app_settings")
    op.create_table(
        "app_settings",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),  # Fernet ciphertext
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # app_settings back to global single-key store
    op.drop_table("app_settings")
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.drop_index("ix_refresh_jobs_user_id", table_name="refresh_jobs")
    op.drop_column("refresh_jobs", "user_id")

    op.drop_constraint("uq_comments_stock_url_hash", "comments", type_="unique")
    op.create_unique_constraint("uq_comments_url_hash", "comments", ["url_hash"])

    op.drop_constraint("uq_news_stock_url_hash", "news", type_="unique")
    op.create_unique_constraint("uq_news_url_hash", "news", ["url_hash"])
    op.create_unique_constraint("uq_news_url", "news", ["url"])

    op.drop_constraint("uq_stocks_user_symbol", "stocks", type_="unique")
    op.create_unique_constraint("uq_stocks_symbol", "stocks", ["symbol"])
    op.drop_index("ix_stocks_user_id", table_name="stocks")
    op.drop_column("stocks", "user_id")

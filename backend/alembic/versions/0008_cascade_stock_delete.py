"""news/comments/sentiment_results.stock_id FK: SET NULL → CASCADE

Revision ID: 0008_cascade_stock_delete
Revises: 0007_google_auth
Create Date: 2026-06-09

Why
---
The original schema set ``ondelete=SET NULL`` on the three children of
``stocks``, leaving orphan rows after a stock deletion (per-user UI couldn't
see them; they accumulated forever). The intended semantics for a per-user
hard delete is "remove the stock and everything it produced," so CASCADE
is the right behavior. The application-level cascade in
``routers/stocks.delete_stock`` becomes redundant after this, but is left
in place as a belt-and-braces safeguard against partially-attached
sentiment rows (e.g. the Alpha Vantage baseline path).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_cascade_stock_delete"
down_revision: str | None = "0007_google_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHANGES = [
    ("news", "news_stock_id_fkey"),
    ("comments", "comments_stock_id_fkey"),
    ("sentiment_results", "sentiment_results_stock_id_fkey"),
]


def upgrade() -> None:
    for table, fk in _CHANGES:
        op.drop_constraint(fk, table, type_="foreignkey")
        op.create_foreign_key(
            fk, table, "stocks", ["stock_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table, fk in _CHANGES:
        op.drop_constraint(fk, table, type_="foreignkey")
        op.create_foreign_key(
            fk, table, "stocks", ["stock_id"], ["id"], ondelete="SET NULL"
        )

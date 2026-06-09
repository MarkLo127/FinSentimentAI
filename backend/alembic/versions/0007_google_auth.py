"""users: add google_sub + make password_hash nullable for Google sign-in

Revision ID: 0007_google_auth
Revises: 0006_per_user_isolation
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_google_auth"
down_revision: str | None = "0006_per_user_isolation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("google_sub", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_users_google_sub", "users", ["google_sub"], unique=True
    )
    op.alter_column("users", "password_hash", nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", nullable=False)
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")

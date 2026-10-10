"""Harden authentication timestamps for PostgreSQL.

Revision ID: 002_auth_timestamps
Revises: 001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_auth_timestamps"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing naive timestamps are historical UTC values. PostgreSQL therefore
    # receives an explicit UTC interpretation during conversion.
    for table, columns in {
        "users": ["last_failed_login", "locked_until", "last_password_change", "created_at", "updated_at", "last_login"],
        "refresh_tokens": ["revoked_at", "created_at", "expires_at", "last_used_at"],
    }.items():
        for column in columns:
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMPTZ "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
            )

    op.execute(
        sa.text(
            "UPDATE users SET updated_at = COALESCE(updated_at, created_at, NOW()) "
            "WHERE updated_at IS NULL"
        )
    )
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def downgrade() -> None:
    op.alter_column("users", "updated_at", server_default=None, nullable=True)
    for table, columns in {
        "users": ["last_failed_login", "locked_until", "last_password_change", "created_at", "updated_at", "last_login"],
        "refresh_tokens": ["revoked_at", "created_at", "expires_at", "last_used_at"],
    }.items():
        for column in columns:
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
            )

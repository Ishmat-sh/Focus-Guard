"""Persist observed duration alongside daily weighted scores.

Revision ID: 0004_analytics_precision
Revises: 0003_features
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_analytics_precision"
down_revision = "0003_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("daily_summaries")
    }
    if "observed_seconds" not in columns:
        op.add_column(
            "daily_summaries",
            sa.Column("observed_seconds", sa.Float, nullable=False, server_default="0"),
        )


def downgrade() -> None:
    raise RuntimeError(
        "Removing analytics duration can invalidate saved summaries; restore from backup"
    )

"""Add devices and opt-in sync metadata.

Revision ID: 0006_devices_sync_metadata
Revises: 0005_insight_feedback
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_devices_sync_metadata"
down_revision = "0005_insight_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "devices" not in tables:
        op.create_table(
            "devices",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("device_id", sa.Text, nullable=False),
            sa.Column("name", sa.Text),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.Column("last_seen_at", sa.Float),
            sa.UniqueConstraint("user_id", "device_id", name="uq_devices_user_device"),
        )
    if "sync_state" not in tables:
        op.create_table(
            "sync_state",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("device_id", sa.Text, nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("last_synced_at", sa.Float),
            sa.Column("last_error", sa.Text),
            sa.UniqueConstraint("user_id", "device_id", name="uq_sync_state_user_device"),
        )

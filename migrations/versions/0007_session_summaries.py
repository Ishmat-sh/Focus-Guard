"""Persist time-weighted per-session focus summaries.

Revision ID: 0007_session_summaries
Revises: 0006_devices_sync_metadata
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_session_summaries"
down_revision = "0006_devices_sync_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "session_summaries" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "session_summaries",
            sa.Column(
                "session_id",
                sa.Integer,
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("observed_seconds", sa.Float, nullable=False),
            sa.Column("focused_seconds", sa.Float, nullable=False),
            sa.Column("distracted_seconds", sa.Float, nullable=False),
            sa.Column("drifting_seconds", sa.Float, nullable=False),
            sa.Column("fatigued_seconds", sa.Float, nullable=False),
            sa.Column("focus_percentage", sa.Float, nullable=False),
            sa.Column("distraction_percentage", sa.Float, nullable=False),
            sa.Column("average_focus_score", sa.Float),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.CheckConstraint("observed_seconds >= 0"),
            sa.CheckConstraint("focused_seconds >= 0"),
            sa.CheckConstraint("distracted_seconds >= 0"),
            sa.CheckConstraint("drifting_seconds >= 0"),
            sa.CheckConstraint("fatigued_seconds >= 0"),
            sa.CheckConstraint("focus_percentage BETWEEN 0 AND 100"),
            sa.CheckConstraint("distraction_percentage BETWEEN 0 AND 100"),
        )


def downgrade() -> None:
    if "session_summaries" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("session_summaries")

"""Add analytics, browser context, coaching, and optional biometric storage.

Revision ID: 0003_features
Revises: 0002_collection
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_features"
down_revision = "0002_collection"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "daily_summaries" not in _tables():
        op.create_table(
            "daily_summaries",
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("summary_date", sa.Text, primary_key=True),
            sa.Column("total_focus_seconds", sa.Float, nullable=False),
            sa.Column("average_score", sa.Float),
            sa.Column("distraction_count", sa.Integer, nullable=False),
            sa.Column("session_count", sa.Integer, nullable=False),
        )
    if "hourly_activity" not in _tables():
        op.create_table(
            "hourly_activity",
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("activity_date", sa.Text, primary_key=True),
            sa.Column("hour_utc", sa.Integer, primary_key=True),
            sa.Column("average_score", sa.Float),
            sa.Column("focus_seconds", sa.Float, nullable=False),
            sa.Column("sample_count", sa.Integer, nullable=False),
            sa.CheckConstraint("hour_utc BETWEEN 0 AND 23"),
        )
    if "focus_streaks" not in _tables():
        op.create_table(
            "focus_streaks",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("started_at", sa.Float, nullable=False),
            sa.Column("ended_at", sa.Float, nullable=False),
            sa.Column("duration_seconds", sa.Float, nullable=False),
            sa.UniqueConstraint("session_id", "started_at"),
        )
    if "app_usage" not in _tables():
        op.create_table(
            "app_usage",
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("usage_date", sa.Text, primary_key=True),
            sa.Column("app_name", sa.Text, primary_key=True),
            sa.Column("app_category", sa.Text, primary_key=True),
            sa.Column("duration_seconds", sa.Float, nullable=False),
        )
    if "app_category_rules" not in _tables():
        op.create_table(
            "app_category_rules",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rule_type", sa.Text, nullable=False),
            sa.Column("rule_value", sa.Text, nullable=False),
            sa.Column("category", sa.Text, nullable=False),
            sa.UniqueConstraint("user_id", "rule_type", "rule_value"),
            sa.CheckConstraint("rule_type IN ('app', 'domain')"),
            sa.CheckConstraint("category IN ('productive', 'neutral', 'distracting')"),
        )
    if "browser_context" not in _tables():
        op.create_table(
            "browser_context",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recorded_at", sa.Float, nullable=False),
            sa.Column("elapsed_seconds", sa.Float, nullable=False),
            sa.Column("domain", sa.Text, nullable=False),
            sa.Column("category", sa.Text, nullable=False),
            sa.CheckConstraint("category IN ('productive', 'neutral', 'distracting', 'unknown')"),
        )
    if "insights" not in _tables():
        op.create_table(
            "insights",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("insight_type", sa.Text, nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("generated_at", sa.Float, nullable=False),
            sa.Column("dismissed", sa.Integer, nullable=False, server_default="0"),
            sa.Column("source", sa.Text, nullable=False, server_default="rules"),
            sa.UniqueConstraint("session_id", "insight_type"),
            sa.CheckConstraint("dismissed IN (0, 1)"),
            sa.CheckConstraint("source IN ('rules', 'ai')"),
        )
    if "biometrics" not in _tables():
        op.create_table(
            "biometrics",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recorded_at", sa.Float, nullable=False),
            sa.Column("heart_rate", sa.Float, nullable=False),
            sa.Column("hrv", sa.Float),
            sa.Column("source_device", sa.Text, nullable=False),
            sa.CheckConstraint("heart_rate > 0"),
            sa.CheckConstraint("hrv IS NULL OR hrv >= 0"),
        )
    existing_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("browser_context")
    }
    if "idx_browser_context_session_time" not in existing_indexes:
        op.create_index(
            "idx_browser_context_session_time",
            "browser_context",
            ["session_id", "recorded_at"],
        )
    existing_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("insights")
    }
    if "idx_insights_user_session" not in existing_indexes:
        op.create_index(
            "idx_insights_user_session",
            "insights",
            ["user_id", "session_id", "dismissed"],
        )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading analytics and session features can lose user-generated data; restore from a backup"
    )

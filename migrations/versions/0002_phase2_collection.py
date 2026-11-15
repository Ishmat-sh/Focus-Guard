"""Add consent-gated feature collection and model registry.

Revision ID: 0002_collection
Revises: 0001_phase1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_collection"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    telemetry_columns = _columns("telemetry")
    if "elapsed_seconds" not in telemetry_columns:
        op.add_column("telemetry", sa.Column("elapsed_seconds", sa.Float))
    if "features_json" not in telemetry_columns:
        op.add_column("telemetry", sa.Column("features_json", sa.Text))

    if "schema_migrations" not in _tables():
        op.create_table(
            "schema_migrations",
            sa.Column("version", sa.Integer, primary_key=True),
            sa.Column("applied_at", sa.Float, nullable=False),
        )
    if "collection_consents" not in _tables():
        op.create_table(
            "collection_consents",
            sa.Column(
                "session_id",
                sa.Integer,
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("consented_at", sa.Float, nullable=False),
        )
    if "feature_windows" not in _tables():
        op.create_table(
            "feature_windows",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "session_id",
                sa.Integer,
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("start_elapsed_seconds", sa.Float, nullable=False),
            sa.Column("end_elapsed_seconds", sa.Float, nullable=False),
            sa.Column("schema_version", sa.Integer, nullable=False),
            sa.Column("features_json", sa.Text, nullable=False),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.UniqueConstraint("session_id", "start_elapsed_seconds"),
            sa.CheckConstraint("start_elapsed_seconds >= 0"),
            sa.CheckConstraint("end_elapsed_seconds > start_elapsed_seconds"),
        )
    if "labels" not in _tables():
        op.create_table(
            "labels",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "session_id",
                sa.Integer,
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("start_elapsed_seconds", sa.Float, nullable=False),
            sa.Column("end_elapsed_seconds", sa.Float, nullable=False),
            sa.Column("label", sa.Text, nullable=False),
            sa.Column(
                "source",
                sa.Text,
                nullable=False,
                server_default="self_reported",
            ),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.CheckConstraint(
                "label IN ('focused', 'drifting', 'distracted', 'fatigued')"
            ),
            sa.CheckConstraint(
                "source IN ('self_reported', 'rule_based', 'imported')"
            ),
            sa.CheckConstraint("start_elapsed_seconds >= 0"),
            sa.CheckConstraint("end_elapsed_seconds > start_elapsed_seconds"),
        )
    if "model_versions" not in _tables():
        op.create_table(
            "model_versions",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("version", sa.Text, nullable=False),
            sa.Column("trained_at", sa.Float),
            sa.Column("metrics_json", sa.Text),
            sa.Column("file_path", sa.Text),
            sa.Column("is_active", sa.Integer, nullable=False, server_default="0"),
            sa.UniqueConstraint("name", "version"),
            sa.CheckConstraint("is_active IN (0, 1)"),
        )
    if "user_privacy_settings" not in _tables():
        op.create_table(
            "user_privacy_settings",
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("retention_days", sa.Integer),
            sa.CheckConstraint(
                "retention_days IS NULL OR retention_days BETWEEN 1 AND 3650"
            ),
        )
    op.create_index(
        "idx_telemetry_session_elapsed",
        "telemetry",
        ["session_id", "elapsed_seconds"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_labels_session_range",
        "labels",
        ["session_id", "start_elapsed_seconds", "end_elapsed_seconds"],
        if_not_exists=True,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading collection data could delete user labels; restore from a backup instead"
    )

"""Create or recognize the Phase 1 SQLite schema without losing existing data.

Revision ID: 0001_phase1
Revises:
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_phase1"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    if "users" not in _tables():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("email", sa.Text, nullable=False, unique=True),
            sa.Column("password", sa.Text, nullable=False),
            sa.Column(
                "must_change_password",
                sa.Integer,
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "created_at",
                sa.Float,
                nullable=False,
                server_default=sa.text("(strftime('%s', 'now'))"),
            ),
        )
    if "sessions" not in _tables():
        op.create_table(
            "sessions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("started_at", sa.Float, nullable=False),
            sa.Column("ended_at", sa.Float),
            sa.Column("elapsed_seconds", sa.Float, nullable=False),
            sa.Column("state", sa.Text, nullable=False),
        )
    if "user_id" not in _columns("sessions"):
        if op.get_bind().dialect.name == "sqlite":
            op.execute(
                "ALTER TABLE sessions "
                "ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        else:
            op.add_column(
                "sessions",
                sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            )
    _add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    if "telemetry" not in _tables():
        op.create_table(
            "telemetry",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "session_id",
                sa.Integer,
                sa.ForeignKey("sessions.id"),
                nullable=False,
            ),
            sa.Column("recorded_at", sa.Float, nullable=False),
            sa.Column("score", sa.Float, nullable=False),
            sa.Column("state", sa.Text, nullable=False),
            sa.Column("app_name", sa.Text),
            sa.Column("app_category", sa.Text),
            sa.Column("face_present", sa.Integer, nullable=False),
        )
    if "admins" not in _tables():
        op.create_table(
            "admins",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("username", sa.Text, nullable=False, unique=True),
            sa.Column("password", sa.Text, nullable=False),
            sa.Column("email", sa.Text),
            sa.Column(
                "created_at",
                sa.Float,
                nullable=False,
                server_default=sa.text("(strftime('%s', 'now'))"),
            ),
        )
    if "user_tokens" not in _tables():
        op.create_table(
            "user_tokens",
            sa.Column("token_hash", sa.Text, primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.Float, nullable=False),
        )


def downgrade() -> None:
    raise RuntimeError(
        "The Phase 1 baseline is intentionally irreversible to protect existing user data"
    )

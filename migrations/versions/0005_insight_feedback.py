"""Add feedback to coaching insights.

Revision ID: 0005_insight_feedback
Revises: 0004_analytics_precision
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_insight_feedback"
down_revision = "0004_analytics_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("insights")}
    if "feedback" not in columns:
        op.add_column(
            "insights",
            sa.Column(
                "feedback",
                sa.Text(),
                sa.CheckConstraint(
                    "feedback IS NULL OR feedback IN ('helpful', 'not_helpful')",
                    name="ck_insights_feedback",
                ),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("insights")}
    if "feedback" in columns:
        with op.batch_alter_table("insights") as batch_op:
            batch_op.drop_column("feedback")

"""Add activity log table.

Revision ID: 20260111_add_activity_log
Revises: 20260110_unify_agent_to_party
Create Date: 2026-01-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260111_add_activity_log"
down_revision = "20260110_unify_agent_to_party"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_activity_log_action", "activity_log", ["action"])
    op.create_index("ix_activity_log_entity", "activity_log", ["entity_type", "entity_id"])
    op.create_index("ix_activity_log_user_id", "activity_log", ["user_id"])
    op.create_index("ix_activity_log_user_email", "activity_log", ["user_email"])
    op.create_index("ix_activity_log_created_at", "activity_log", ["created_at"])
    op.create_index(
        "ix_activity_log_action_created",
        "activity_log",
        ["action", "created_at"],
    )
    op.create_index(
        "ix_activity_log_user_created",
        "activity_log",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_log_user_created", table_name="activity_log")
    op.drop_index("ix_activity_log_action_created", table_name="activity_log")
    op.drop_index("ix_activity_log_created_at", table_name="activity_log")
    op.drop_index("ix_activity_log_user_email", table_name="activity_log")
    op.drop_index("ix_activity_log_user_id", table_name="activity_log")
    op.drop_index("ix_activity_log_entity", table_name="activity_log")
    op.drop_index("ix_activity_log_action", table_name="activity_log")
    op.drop_table("activity_log")

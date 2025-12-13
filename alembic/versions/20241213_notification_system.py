"""Add notification and webhook system tables.

Creates:
- webhook_configs: Webhook endpoint configurations
- webhook_deliveries: Delivery attempt records
- notification_preferences: User notification settings
- notifications: In-app notifications
- email_queue: Outgoing email queue

Revision ID: 20241213_notification_system
Revises: 20241213_performance_indexes
Create Date: 2024-12-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241213_notification_system"
down_revision: Union[str, None] = "20241213_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # WEBHOOK CONFIGS
    # ==========================================================================
    op.create_table(
        "webhook_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("method", sa.String(10), server_default="POST"),
        sa.Column("auth_type", sa.String(50), nullable=True),
        sa.Column("auth_header", sa.String(100), nullable=True),
        sa.Column("auth_value_encrypted", sa.Text(), nullable=True),
        sa.Column("custom_headers", postgresql.JSON(), nullable=True),
        sa.Column("event_types", postgresql.JSON(), server_default="[]"),
        sa.Column("filters", postgresql.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.sql.expression.true()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.sql.expression.false()),
        sa.Column("max_retries", sa.Integer(), server_default="3"),
        sa.Column("retry_delay_seconds", sa.Integer(), server_default="60"),
        sa.Column("signing_secret", sa.String(255), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("failure_count", sa.Integer(), server_default="0"),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_configs_active_events", "webhook_configs", ["is_active", "is_deleted"])

    # ==========================================================================
    # WEBHOOK DELIVERIES
    # ==========================================================================
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("webhook_configs.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSON(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_status_retry", "webhook_deliveries", ["status", "next_retry_at"])
    op.create_index("ix_webhook_deliveries_event", "webhook_deliveries", ["event_type", "event_id"])

    # ==========================================================================
    # NOTIFICATION PREFERENCES
    # ==========================================================================
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.sql.expression.true()),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.sql.expression.true()),
        sa.Column("sms_enabled", sa.Boolean(), server_default=sa.sql.expression.false()),
        sa.Column("slack_enabled", sa.Boolean(), server_default=sa.sql.expression.false()),
        sa.Column("threshold_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("threshold_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_notification_prefs_user_event",
        "notification_preferences",
        ["user_id", "event_type"],
        unique=True
    )

    # ==========================================================================
    # NOTIFICATIONS (IN-APP)
    # ==========================================================================
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("extra_data", postgresql.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.sql.expression.false(), index=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read", "created_at"])

    # ==========================================================================
    # EMAIL QUEUE
    # ==========================================================================
    op.create_table(
        "email_queue",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("to_name", sa.String(255), nullable=True),
        sa.Column("cc_emails", postgresql.JSON(), nullable=True),
        sa.Column("bcc_emails", postgresql.JSON(), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", index=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="5"),
    )
    op.create_index("ix_email_queue_pending", "email_queue", ["status", "priority", "created_at"])


def downgrade() -> None:
    op.drop_table("email_queue")
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_configs")

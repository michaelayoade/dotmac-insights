"""add omni core tables (channels, conversations, messages)

Revision ID: 20240920_add_omni_core
Revises: 20240920_add_agents_and_teams
Create Date: 2024-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240920_add_omni_core"
down_revision = "20240920_add_agents_and_teams"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "omni_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("webhook_secret", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_channels_name", "omni_channels", ["name"], unique=True)
    op.create_index("ix_omni_channels_type", "omni_channels", ["type"])

    op.create_table(
        "omni_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("handle", sa.String(length=255), nullable=False),
        sa.Column("channel_type", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_participants_handle", "omni_participants", ["handle"])
    op.create_index("ix_omni_participants_channel_type", "omni_participants", ["channel_type"])
    op.create_index("ix_omni_participants_customer_id", "omni_participants", ["customer_id"])

    op.create_table(
        "omni_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("omni_channels.id"), nullable=False),
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_conversations_channel_id", "omni_conversations", ["channel_id"])
    op.create_index("ix_omni_conversations_external_thread_id", "omni_conversations", ["external_thread_id"])
    op.create_index("ix_omni_conversations_ticket_id", "omni_conversations", ["ticket_id"])
    op.create_index("ix_omni_conversations_customer_id", "omni_conversations", ["customer_id"])

    op.create_table(
        "omni_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("omni_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=True),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("omni_participants.id"), nullable=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("omni_channels.id"), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("delivery_status", sa.String(length=50), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_messages_conversation_id", "omni_messages", ["conversation_id"])
    op.create_index("ix_omni_messages_ticket_id", "omni_messages", ["ticket_id"])
    op.create_index("ix_omni_messages_customer_id", "omni_messages", ["customer_id"])
    op.create_index("ix_omni_messages_participant_id", "omni_messages", ["participant_id"])
    op.create_index("ix_omni_messages_agent_id", "omni_messages", ["agent_id"])
    op.create_index("ix_omni_messages_channel_id", "omni_messages", ["channel_id"])
    op.create_index("ix_omni_messages_provider_message_id", "omni_messages", ["provider_message_id"])
    op.create_index("ix_omni_messages_created_at", "omni_messages", ["created_at"])

    op.create_table(
        "omni_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("omni_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_attachments_message_id", "omni_attachments", ["message_id"])

    op.create_table(
        "omni_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("omni_channels.id"), nullable=True),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_omni_webhook_events_channel_id", "omni_webhook_events", ["channel_id"])
    op.create_index("ix_omni_webhook_events_provider_event_id", "omni_webhook_events", ["provider_event_id"])
    op.create_index("ix_omni_webhook_events_processed", "omni_webhook_events", ["processed"])
    op.create_index("ix_omni_webhook_events_received_at", "omni_webhook_events", ["received_at"])


def downgrade():
    op.drop_table("omni_webhook_events")
    op.drop_table("omni_attachments")
    op.drop_table("omni_messages")
    op.drop_table("omni_conversations")
    op.drop_table("omni_participants")
    op.drop_table("omni_channels")

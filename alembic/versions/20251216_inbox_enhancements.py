"""Add inbox enhancements - routing rules, contacts, conversation fields

Revision ID: 20251216_inbox_enhancements
Revises: 20251216_add_crm_tables
Create Date: 2025-12-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251216_inbox_enhancements"
# Depends on CRM base tables
down_revision = "crm_001"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to omni_conversations
    op.add_column("omni_conversations", sa.Column("lead_id", sa.Integer(), sa.ForeignKey("erpnext_leads.id"), nullable=True))
    op.add_column("omni_conversations", sa.Column("priority", sa.String(length=20), nullable=True, server_default="medium"))
    op.add_column("omni_conversations", sa.Column("assigned_agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=True))
    op.add_column("omni_conversations", sa.Column("assigned_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True))
    op.add_column("omni_conversations", sa.Column("assigned_at", sa.DateTime(), nullable=True))
    op.add_column("omni_conversations", sa.Column("is_starred", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))
    op.add_column("omni_conversations", sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("omni_conversations", sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("omni_conversations", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("omni_conversations", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("omni_conversations", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("omni_conversations", sa.Column("contact_company", sa.String(length=255), nullable=True))
    op.add_column("omni_conversations", sa.Column("first_response_at", sa.DateTime(), nullable=True))
    op.add_column("omni_conversations", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("omni_conversations", sa.Column("snoozed_until", sa.DateTime(), nullable=True))

    # Create indexes for new columns
    op.create_index("ix_omni_conversations_lead_id", "omni_conversations", ["lead_id"])
    op.create_index("ix_omni_conversations_assigned_agent_id", "omni_conversations", ["assigned_agent_id"])
    op.create_index("ix_omni_conversations_assigned_team_id", "omni_conversations", ["assigned_team_id"])
    op.create_index("ix_omni_conversations_contact_email", "omni_conversations", ["contact_email"])
    op.create_index("ix_omni_conversations_status", "omni_conversations", ["status"])
    op.create_index("ix_omni_conversations_last_message_at", "omni_conversations", ["last_message_at"])

    # Create inbox_routing_rules table
    op.create_table(
        "inbox_routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("action_value", sa.String(length=255), nullable=True),
        sa.Column("action_config", sa.JSON(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inbox_routing_rules_priority", "inbox_routing_rules", ["priority"])
    op.create_index("ix_inbox_routing_rules_is_active", "inbox_routing_rules", ["is_active"])

    # Create inbox_contacts table
    op.create_table(
        "inbox_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("erpnext_leads.id"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("total_conversations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_contact_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inbox_contacts_name", "inbox_contacts", ["name"])
    op.create_index("ix_inbox_contacts_email", "inbox_contacts", ["email"])
    op.create_index("ix_inbox_contacts_phone", "inbox_contacts", ["phone"])
    op.create_index("ix_inbox_contacts_company", "inbox_contacts", ["company"])
    op.create_index("ix_inbox_contacts_customer_id", "inbox_contacts", ["customer_id"])
    op.create_index("ix_inbox_contacts_lead_id", "inbox_contacts", ["lead_id"])
    op.create_index("ix_inbox_contacts_last_contact_at", "inbox_contacts", ["last_contact_at"])


def downgrade():
    op.drop_table("inbox_contacts")
    op.drop_table("inbox_routing_rules")

    op.drop_index("ix_omni_conversations_last_message_at", "omni_conversations")
    op.drop_index("ix_omni_conversations_status", "omni_conversations")
    op.drop_index("ix_omni_conversations_contact_email", "omni_conversations")
    op.drop_index("ix_omni_conversations_assigned_team_id", "omni_conversations")
    op.drop_index("ix_omni_conversations_assigned_agent_id", "omni_conversations")
    op.drop_index("ix_omni_conversations_lead_id", "omni_conversations")

    op.drop_column("omni_conversations", "snoozed_until")
    op.drop_column("omni_conversations", "resolved_at")
    op.drop_column("omni_conversations", "first_response_at")
    op.drop_column("omni_conversations", "contact_company")
    op.drop_column("omni_conversations", "contact_email")
    op.drop_column("omni_conversations", "contact_name")
    op.drop_column("omni_conversations", "tags")
    op.drop_column("omni_conversations", "message_count")
    op.drop_column("omni_conversations", "unread_count")
    op.drop_column("omni_conversations", "is_starred")
    op.drop_column("omni_conversations", "assigned_at")
    op.drop_column("omni_conversations", "assigned_team_id")
    op.drop_column("omni_conversations", "assigned_agent_id")
    op.drop_column("omni_conversations", "priority")
    op.drop_column("omni_conversations", "lead_id")

"""Unify Agent identity into Party system.

This migration:
1. Adds party_id columns to tables that referenced agents
2. Adds support_agent role type to ref_party_role_types
3. Creates Party records for agents without employees
4. Creates PartyRole(role="support_agent") for all agents
5. Migrates all agent_id references to party_id
6. Drops the agents table

Revision ID: 20260110_unify_agent_to_party
Revises: 20260108_add_finance_validation_issues
Create Date: 2026-01-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

revision = "20260110_unify_agent_to_party"
down_revision = "20260108_add_finance_validation_issues"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # STEP 1: Add support_agent role type to ref_party_role_types
    # =========================================================================
    op.execute("""
        INSERT INTO ref_party_role_types (code, label, category, description, sort_order, is_active)
        VALUES ('support_agent', 'Support Agent', 'operations', 'Agent providing customer support services', 50, true)
        ON CONFLICT (code) DO NOTHING
    """)

    # =========================================================================
    # STEP 2: Add party_id columns to all tables that reference agents
    # =========================================================================

    # team_members: add party_id (will replace agent_id)
    op.add_column(
        "team_members",
        sa.Column("party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_team_members_party_id", "team_members", ["party_id"])
    op.create_foreign_key(
        "fk_team_members_party_id",
        "team_members",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # omni_conversations: add assigned_party_id (will replace assigned_agent_id)
    op.add_column(
        "omni_conversations",
        sa.Column("assigned_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_omni_conversations_assigned_party_id", "omni_conversations", ["assigned_party_id"])
    op.create_foreign_key(
        "fk_omni_conversations_assigned_party_id",
        "omni_conversations",
        "parties",
        ["assigned_party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # omni_messages: add party_id (will replace agent_id)
    op.add_column(
        "omni_messages",
        sa.Column("party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_omni_messages_party_id", "omni_messages", ["party_id"])
    op.create_foreign_key(
        "fk_omni_messages_party_id",
        "omni_messages",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # canned_responses: add party_id (will replace agent_id)
    op.add_column(
        "canned_responses",
        sa.Column("party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_canned_responses_party_id", "canned_responses", ["party_id"])
    op.create_foreign_key(
        "fk_canned_responses_party_id",
        "canned_responses",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # csat_responses: add party_id for agent (will replace agent_id)
    # Note: already has party_id for customer, we add agent_party_id
    op.add_column(
        "csat_responses",
        sa.Column("agent_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_csat_responses_agent_party_id", "csat_responses", ["agent_party_id"])
    op.create_foreign_key(
        "fk_csat_responses_agent_party_id",
        "csat_responses",
        "parties",
        ["agent_party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # kb_article_feedback: add party_id for agent (will replace agent_id)
    # Note: already has party_id for customer feedback, we add agent_party_id
    op.add_column(
        "kb_article_feedback",
        sa.Column("agent_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_kb_article_feedback_agent_party_id", "kb_article_feedback", ["agent_party_id"])
    op.create_foreign_key(
        "fk_kb_article_feedback_agent_party_id",
        "kb_article_feedback",
        "parties",
        ["agent_party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # unified_tickets: add assigned_to_party_id (will replace assigned_to_id -> employees)
    op.add_column(
        "unified_tickets",
        sa.Column("assigned_to_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_unified_tickets_assigned_to_party_id", "unified_tickets", ["assigned_to_party_id"])
    op.create_foreign_key(
        "fk_unified_tickets_assigned_to_party_id",
        "unified_tickets",
        "parties",
        ["assigned_to_party_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =========================================================================
    # STEP 3: Migrate existing agent data to Party system
    # =========================================================================

    # 3a. For agents WITH employee_id: Get party_id from employee
    # Create PartyRole for each
    op.execute("""
        INSERT INTO party_roles (party_id, role, status, metadata, created_at, updated_at)
        SELECT
            e.party_id,
            'support_agent',
            CASE WHEN a.is_active THEN 'active' ELSE 'inactive' END,
            jsonb_build_object(
                'domains', COALESCE(a.domains::jsonb, '{}'::jsonb),
                'skills', COALESCE(a.skills::jsonb, '{}'::jsonb),
                'channel_caps', COALESCE(a.channel_caps::jsonb, '[]'::jsonb),
                'routing_weight', COALESCE(a.routing_weight, 1),
                'capacity', COALESCE(a.capacity, 10),
                'legacy_agent_id', a.id
            ),
            NOW(),
            NOW()
        FROM agents a
        JOIN employees e ON a.employee_id = e.id
        WHERE e.party_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    # 3b. For agents WITHOUT employee_id: Create new Party records
    op.execute("""
        WITH new_parties AS (
            INSERT INTO parties (type, status, name, primary_email, created_at, updated_at)
            SELECT
                'person',
                CASE WHEN a.is_active THEN 'active' ELSE 'inactive' END,
                COALESCE(a.display_name, a.email, 'Agent ' || a.id::text),
                a.email,
                NOW(),
                NOW()
            FROM agents a
            WHERE a.employee_id IS NULL
            RETURNING id, primary_email
        )
        INSERT INTO party_roles (party_id, role, status, metadata, created_at, updated_at)
        SELECT
            np.id,
            'support_agent',
            'active',
            jsonb_build_object(
                'domains', COALESCE(a.domains::jsonb, '{}'::jsonb),
                'skills', COALESCE(a.skills::jsonb, '{}'::jsonb),
                'channel_caps', COALESCE(a.channel_caps::jsonb, '[]'::jsonb),
                'routing_weight', COALESCE(a.routing_weight, 1),
                'capacity', COALESCE(a.capacity, 10),
                'legacy_agent_id', a.id
            ),
            NOW(),
            NOW()
        FROM new_parties np
        JOIN agents a ON a.email = np.primary_email
        WHERE a.employee_id IS NULL
    """)

    # Create a temporary mapping table for agent_id -> party_id lookup
    op.execute("""
        CREATE TEMPORARY TABLE agent_party_map AS
        SELECT
            a.id as agent_id,
            COALESCE(e.party_id, p.id) as party_id
        FROM agents a
        LEFT JOIN employees e ON a.employee_id = e.id
        LEFT JOIN parties p ON p.primary_email = a.email AND a.employee_id IS NULL
    """)

    # =========================================================================
    # STEP 4: Migrate FK references from agent_id to party_id
    # =========================================================================

    # team_members
    op.execute("""
        UPDATE team_members tm
        SET party_id = apm.party_id
        FROM agent_party_map apm
        WHERE tm.agent_id = apm.agent_id
    """)

    # omni_conversations
    op.execute("""
        UPDATE omni_conversations oc
        SET assigned_party_id = apm.party_id
        FROM agent_party_map apm
        WHERE oc.assigned_agent_id = apm.agent_id
    """)

    # omni_messages
    op.execute("""
        UPDATE omni_messages om
        SET party_id = apm.party_id
        FROM agent_party_map apm
        WHERE om.agent_id = apm.agent_id
    """)

    # canned_responses
    op.execute("""
        UPDATE canned_responses cr
        SET party_id = apm.party_id
        FROM agent_party_map apm
        WHERE cr.agent_id = apm.agent_id
    """)

    # csat_responses
    op.execute("""
        UPDATE csat_responses csr
        SET agent_party_id = apm.party_id
        FROM agent_party_map apm
        WHERE csr.agent_id = apm.agent_id
    """)

    # kb_article_feedback
    op.execute("""
        UPDATE kb_article_feedback kaf
        SET agent_party_id = apm.party_id
        FROM agent_party_map apm
        WHERE kaf.agent_id = apm.agent_id
    """)

    # unified_tickets: migrate from assigned_to_id (employee) to assigned_to_party_id
    op.execute("""
        UPDATE unified_tickets ut
        SET assigned_to_party_id = e.party_id
        FROM employees e
        WHERE ut.assigned_to_id = e.id
          AND e.party_id IS NOT NULL
    """)

    # =========================================================================
    # STEP 5: Drop old FK constraints and columns
    # =========================================================================

    # team_members: drop agent_id FK and column
    op.drop_constraint("team_members_agent_id_fkey", "team_members", type_="foreignkey")
    op.drop_index("ix_team_members_agent_id", table_name="team_members")
    op.drop_column("team_members", "agent_id")

    # omni_conversations: drop assigned_agent_id FK and column
    op.drop_constraint("omni_conversations_assigned_agent_id_fkey", "omni_conversations", type_="foreignkey")
    op.drop_index("ix_omni_conversations_assigned_agent_id", table_name="omni_conversations")
    op.drop_column("omni_conversations", "assigned_agent_id")

    # omni_messages: drop agent_id FK and column
    op.drop_constraint("omni_messages_agent_id_fkey", "omni_messages", type_="foreignkey")
    op.drop_index("ix_omni_messages_agent_id", table_name="omni_messages")
    op.drop_column("omni_messages", "agent_id")

    # canned_responses: drop agent_id FK and column
    op.drop_constraint("canned_responses_agent_id_fkey", "canned_responses", type_="foreignkey")
    op.drop_index("ix_canned_responses_agent_id", table_name="canned_responses")
    op.drop_column("canned_responses", "agent_id")

    # csat_responses: drop agent_id FK and column
    op.drop_constraint("csat_responses_agent_id_fkey", "csat_responses", type_="foreignkey")
    op.drop_index("ix_csat_responses_agent_id", table_name="csat_responses")
    op.drop_column("csat_responses", "agent_id")

    # kb_article_feedback: drop agent_id FK and column
    op.drop_constraint("kb_article_feedback_agent_id_fkey", "kb_article_feedback", type_="foreignkey")
    op.drop_index("ix_kb_article_feedback_agent_id", table_name="kb_article_feedback")
    op.drop_column("kb_article_feedback", "agent_id")

    # unified_tickets: drop assigned_to_id FK and column (was FK to employees)
    op.drop_constraint("unified_tickets_assigned_to_id_fkey", "unified_tickets", type_="foreignkey")
    op.drop_index("ix_unified_tickets_assigned_to_id", table_name="unified_tickets")
    op.drop_column("unified_tickets", "assigned_to_id")

    # =========================================================================
    # STEP 6: Handle routing_round_robin_state dependency
    # =========================================================================
    # Drop FK from routing_round_robin_state to agents
    op.drop_constraint(
        "routing_round_robin_state_last_agent_id_fkey",
        "routing_round_robin_state",
        type_="foreignkey"
    )
    # Add new FK to parties
    op.add_column(
        "routing_round_robin_state",
        sa.Column("last_party_id", sa.BigInteger(), nullable=True),
    )
    # Migrate data
    op.execute("""
        UPDATE routing_round_robin_state rrs
        SET last_party_id = apm.party_id
        FROM agent_party_map apm
        WHERE rrs.last_agent_id = apm.agent_id
    """)
    op.create_foreign_key(
        "routing_round_robin_state_last_party_id_fkey",
        "routing_round_robin_state",
        "parties",
        ["last_party_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("routing_round_robin_state", "last_agent_id")

    # =========================================================================
    # STEP 7: Drop the agents table and temp table
    # =========================================================================
    op.execute("DROP TABLE IF EXISTS agent_party_map")
    op.drop_table("agents")


def downgrade() -> None:
    # Recreate agents table
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("domains", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("channel_caps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("routing_weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agents_employee_id", "agents", ["employee_id"])
    op.create_index("ix_agents_email", "agents", ["email"])

    # Re-add agent_id columns
    op.add_column("team_members", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_team_members_agent_id", "team_members", ["agent_id"])
    op.create_foreign_key(
        "team_members_agent_id_fkey", "team_members", "agents", ["agent_id"], ["id"], ondelete="CASCADE"
    )

    op.add_column("omni_conversations", sa.Column("assigned_agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_omni_conversations_assigned_agent_id", "omni_conversations", ["assigned_agent_id"])
    op.create_foreign_key(
        "omni_conversations_assigned_agent_id_fkey", "omni_conversations", "agents",
        ["assigned_agent_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("omni_messages", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_omni_messages_agent_id", "omni_messages", ["agent_id"])
    op.create_foreign_key(
        "omni_messages_agent_id_fkey", "omni_messages", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("canned_responses", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_canned_responses_agent_id", "canned_responses", ["agent_id"])
    op.create_foreign_key(
        "canned_responses_agent_id_fkey", "canned_responses", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("csat_responses", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_csat_responses_agent_id", "csat_responses", ["agent_id"])
    op.create_foreign_key(
        "csat_responses_agent_id_fkey", "csat_responses", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("kb_article_feedback", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.create_index("ix_kb_article_feedback_agent_id", "kb_article_feedback", ["agent_id"])
    op.create_foreign_key(
        "kb_article_feedback_agent_id_fkey", "kb_article_feedback", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("unified_tickets", sa.Column("assigned_to_id", sa.Integer(), nullable=True))
    op.create_index("ix_unified_tickets_assigned_to_id", "unified_tickets", ["assigned_to_id"])
    op.create_foreign_key(
        "unified_tickets_assigned_to_id_fkey", "unified_tickets", "employees",
        ["assigned_to_id"], ["id"], ondelete="SET NULL"
    )

    # Drop new party_id columns
    op.drop_constraint("fk_team_members_party_id", "team_members", type_="foreignkey")
    op.drop_index("ix_team_members_party_id", table_name="team_members")
    op.drop_column("team_members", "party_id")

    op.drop_constraint("fk_omni_conversations_assigned_party_id", "omni_conversations", type_="foreignkey")
    op.drop_index("ix_omni_conversations_assigned_party_id", table_name="omni_conversations")
    op.drop_column("omni_conversations", "assigned_party_id")

    op.drop_constraint("fk_omni_messages_party_id", "omni_messages", type_="foreignkey")
    op.drop_index("ix_omni_messages_party_id", table_name="omni_messages")
    op.drop_column("omni_messages", "party_id")

    op.drop_constraint("fk_canned_responses_party_id", "canned_responses", type_="foreignkey")
    op.drop_index("ix_canned_responses_party_id", table_name="canned_responses")
    op.drop_column("canned_responses", "party_id")

    op.drop_constraint("fk_csat_responses_agent_party_id", "csat_responses", type_="foreignkey")
    op.drop_index("ix_csat_responses_agent_party_id", table_name="csat_responses")
    op.drop_column("csat_responses", "agent_party_id")

    op.drop_constraint("fk_kb_article_feedback_agent_party_id", "kb_article_feedback", type_="foreignkey")
    op.drop_index("ix_kb_article_feedback_agent_party_id", table_name="kb_article_feedback")
    op.drop_column("kb_article_feedback", "agent_party_id")

    op.drop_constraint("fk_unified_tickets_assigned_to_party_id", "unified_tickets", type_="foreignkey")
    op.drop_index("ix_unified_tickets_assigned_to_party_id", table_name="unified_tickets")
    op.drop_column("unified_tickets", "assigned_to_party_id")

    # Remove support_agent role type
    op.execute("DELETE FROM ref_party_role_types WHERE code = 'support_agent'")

"""Support automation, SLA policies, and routing infrastructure.

Revision ID: 20241213_support_automation_sla
Revises: 20240914_ticket_deps_expense
Create Date: 2024-12-13

This migration creates:
- automation_rules: Trigger-based automation rules
- automation_logs: Execution logs for automation rules
- business_calendars: Business hours definitions
- business_calendar_holidays: Holiday exceptions
- sla_policies: SLA policy definitions
- sla_targets: Specific SLA targets per priority
- sla_breach_logs: SLA breach records
- routing_rules: Automatic ticket assignment rules
- routing_round_robin_state: State tracking for round-robin assignment
"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '20241213_support_automation_sla'
down_revision: Union[str, None] = '20240914_ticket_deps_expense'
branch_labels: Union[str, Sequence[str], None] = ('support_automation',)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set()
    inspector = None
    bind = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind:
            inspector = sa.inspect(bind)
            try:
                existing_tables = set(inspector.get_table_names())
            except Exception:
                existing_tables = set()

    def has_table(name: str) -> bool:
        if name in existing_tables:
            return True
        if inspector:
            try:
                return inspector.has_table(name)
            except Exception:
                pass
        if bind:
            try:
                for candidate in (name, f"public.{name}"):
                    res = bind.execute(sa.text("SELECT to_regclass(:n)"), {"n": candidate}).scalar()
                    if res:
                        return True
            except Exception:
                return False
        return False

    # If the primary table is already present, assume migration applied.
    if has_table('automation_rules'):
        return

    # =========================================================================
    # AUTOMATION RULES
    # =========================================================================
    if not has_table('automation_rules'):
        op.create_table(
            'automation_rules',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(255), nullable=False, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('trigger', sa.String(50), nullable=False, index=True),
            sa.Column('conditions', postgresql.JSON(), nullable=True),
            sa.Column('actions', postgresql.JSON(), nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True, index=True),
            sa.Column('priority', sa.Integer(), default=100, index=True),
            sa.Column('stop_processing', sa.Boolean(), default=False),
            sa.Column('max_executions_per_hour', sa.Integer(), nullable=True),
            sa.Column('execution_count', sa.Integer(), default=0),
            sa.Column('last_executed_at', sa.DateTime(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # =========================================================================
    # AUTOMATION LOGS
    # =========================================================================
    if not has_table('automation_logs'):
        op.create_table(
            'automation_logs',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('rule_id', sa.Integer(), sa.ForeignKey('automation_rules.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('trigger', sa.String(50), nullable=False, index=True),
            sa.Column('conditions_matched', postgresql.JSON(), nullable=True),
            sa.Column('actions_executed', postgresql.JSON(), nullable=True),
            sa.Column('success', sa.Boolean(), default=True, index=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        )
        op.create_index('ix_automation_logs_rule_created', 'automation_logs', ['rule_id', 'created_at'])

    # =========================================================================
    # BUSINESS CALENDARS
    # =========================================================================
    if not has_table('business_calendars'):
        op.create_table(
            'business_calendars',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(255), unique=True, nullable=False, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('calendar_type', sa.String(20), default='standard'),
            sa.Column('timezone', sa.String(50), default='UTC'),
            sa.Column('schedule', postgresql.JSON(), nullable=True),
            sa.Column('is_default', sa.Boolean(), default=False, index=True),
            sa.Column('is_active', sa.Boolean(), default=True, index=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # =========================================================================
    # BUSINESS CALENDAR HOLIDAYS
    # =========================================================================
    if not has_table('business_calendar_holidays'):
        op.create_table(
            'business_calendar_holidays',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('calendar_id', sa.Integer(), sa.ForeignKey('business_calendars.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('holiday_date', sa.Date(), nullable=False, index=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('is_recurring', sa.Boolean(), default=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

        # Unique constraint for calendar + date
        op.create_unique_constraint('uq_calendar_holiday_date', 'business_calendar_holidays', ['calendar_id', 'holiday_date'])

    # =========================================================================
    # SLA POLICIES
    # =========================================================================
    if not has_table('sla_policies'):
        op.create_table(
            'sla_policies',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(255), unique=True, nullable=False, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('calendar_id', sa.Integer(), sa.ForeignKey('business_calendars.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('conditions', postgresql.JSON(), nullable=True),
            sa.Column('is_default', sa.Boolean(), default=False, index=True),
            sa.Column('priority', sa.Integer(), default=100, index=True),
            sa.Column('is_active', sa.Boolean(), default=True, index=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # =========================================================================
    # SLA TARGETS
    # =========================================================================
    if not has_table('sla_targets'):
        op.create_table(
            'sla_targets',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('policy_id', sa.Integer(), sa.ForeignKey('sla_policies.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('target_type', sa.String(30), nullable=False, index=True),
            sa.Column('priority', sa.String(20), nullable=True, index=True),
            sa.Column('target_hours', sa.Numeric(10, 2), nullable=False),
            sa.Column('warning_threshold_pct', sa.Integer(), default=80),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

        # Unique constraint for policy + type + priority
        op.create_unique_constraint('uq_sla_target_policy_type_priority', 'sla_targets', ['policy_id', 'target_type', 'priority'])

    # =========================================================================
    # SLA BREACH LOGS
    # =========================================================================
    op.create_table(
        'sla_breach_logs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('sla_policies.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('target_type', sa.String(30), nullable=False, index=True),
        sa.Column('target_hours', sa.Numeric(10, 2), nullable=False),
        sa.Column('actual_hours', sa.Numeric(10, 2), nullable=False),
        sa.Column('breached_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('was_warned', sa.Boolean(), default=False),
        sa.Column('warned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Index for breach reporting
    op.create_index('ix_sla_breach_logs_breached_at', 'sla_breach_logs', ['breached_at'])
    op.create_index('ix_sla_breach_logs_ticket_type', 'sla_breach_logs', ['ticket_id', 'target_type'])

    # =========================================================================
    # ROUTING RULES
    # =========================================================================
    op.create_table(
        'routing_rules',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('strategy', sa.String(30), default='round_robin'),
        sa.Column('conditions', postgresql.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), default=100, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('fallback_team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # =========================================================================
    # ROUTING ROUND ROBIN STATE
    # =========================================================================
    op.create_table(
        'routing_round_robin_state',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), unique=True, nullable=False, index=True),
        sa.Column('last_agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # =========================================================================
    # SEED DATA
    # =========================================================================
    # Create default 24x7 business calendar
    op.execute("""
        INSERT INTO business_calendars (name, description, calendar_type, timezone, schedule, is_default, is_active, created_at, updated_at)
        VALUES (
            '24x7 Support',
            'Round-the-clock support coverage',
            '24x7',
            'UTC',
            NULL,
            true,
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT DO NOTHING
    """)

    # Create standard business hours calendar
    op.execute("""
        INSERT INTO business_calendars (name, description, calendar_type, timezone, schedule, is_default, is_active, created_at, updated_at)
        VALUES (
            'Standard Business Hours',
            'Monday-Friday 9:00-17:00',
            'standard',
            'Africa/Lagos',
            '{"mon": {"start": "09:00", "end": "17:00"}, "tue": {"start": "09:00", "end": "17:00"}, "wed": {"start": "09:00", "end": "17:00"}, "thu": {"start": "09:00", "end": "17:00"}, "fri": {"start": "09:00", "end": "17:00"}, "sat": null, "sun": null}',
            false,
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT DO NOTHING
    """)

    # Create default SLA policy
    op.execute("""
        INSERT INTO sla_policies (name, description, calendar_id, conditions, is_default, priority, is_active, created_at, updated_at)
        VALUES (
            'Default SLA Policy',
            'Default SLA targets for all tickets',
            (SELECT id FROM business_calendars WHERE name = '24x7 Support' LIMIT 1),
            NULL,
            true,
            999,
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT DO NOTHING
    """)

    # Create default SLA targets
    op.execute("""
        INSERT INTO sla_targets (policy_id, target_type, priority, target_hours, warning_threshold_pct, created_at, updated_at)
        SELECT
            p.id,
            t.target_type,
            t.priority,
            t.target_hours,
            80,
            NOW(),
            NOW()
        FROM sla_policies p
        CROSS JOIN (VALUES
            ('first_response', 'urgent', 1.0),
            ('first_response', 'high', 4.0),
            ('first_response', 'medium', 8.0),
            ('first_response', 'low', 24.0),
            ('resolution', 'urgent', 4.0),
            ('resolution', 'high', 24.0),
            ('resolution', 'medium', 72.0),
            ('resolution', 'low', 168.0)
        ) AS t(target_type, priority, target_hours)
        WHERE p.name = 'Default SLA Policy'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('routing_round_robin_state')
    op.drop_table('routing_rules')
    op.drop_table('sla_breach_logs')
    op.drop_table('sla_targets')
    op.drop_table('sla_policies')
    op.drop_table('business_calendar_holidays')
    op.drop_table('business_calendars')
    op.drop_table('automation_logs')
    op.drop_table('automation_rules')

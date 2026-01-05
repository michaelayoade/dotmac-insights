"""Add MikroTik provisioning fields and logs table.

Revision ID: mikrotik_provisioning_001
Revises: fix_enum_case_001
Create Date: 2026-01-01

This migration adds:
1. New fields to subscriptions table for MikroTik provisioning
2. ProvisioningLog table for audit trail of all provisioning operations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'mikrotik_provisioning_001'
down_revision = 'fix_enum_case_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add provisioning fields and logs table."""

    # Create enum types for provisioning
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE provisioningaction AS ENUM (
                'create', 'update', 'delete', 'disconnect', 'suspend', 'unsuspend'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE provisioningstatus AS ENUM (
                'pending', 'success', 'failed', 'retrying'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Add new columns to subscriptions table
    # access_method: PPPoE, Hotspot, DHCP, IPoE, Static
    op.add_column(
        'subscriptions',
        sa.Column('access_method', sa.String(50), nullable=True),
    )

    # PPPoE/Hotspot credentials
    op.add_column(
        'subscriptions',
        sa.Column('ppp_username', sa.String(100), nullable=True),
    )
    op.add_column(
        'subscriptions',
        sa.Column('ppp_password', sa.String(100), nullable=True),
    )

    # Provisioning state tracking
    op.add_column(
        'subscriptions',
        sa.Column('provisioned_at', sa.DateTime, nullable=True),
    )
    op.add_column(
        'subscriptions',
        sa.Column('provisioning_error', sa.Text, nullable=True),
    )

    # Add index on ppp_username for fast lookups
    op.create_index(
        'ix_subscriptions_ppp_username',
        'subscriptions',
        ['ppp_username'],
        unique=False,
    )

    # Create provisioning_logs table
    # Use postgresql.ENUM with create_type=False since enums are already created above
    action_enum = postgresql.ENUM(
        'create', 'update', 'delete', 'disconnect', 'suspend', 'unsuspend',
        name='provisioningaction', create_type=False
    )
    status_enum = postgresql.ENUM(
        'pending', 'success', 'failed', 'retrying',
        name='provisioningstatus', create_type=False
    )

    op.create_table(
        'provisioning_logs',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('subscription_id', sa.Integer, sa.ForeignKey('subscriptions.id'), nullable=False, index=True),
        sa.Column('router_id', sa.Integer, sa.ForeignKey('routers.id'), nullable=False, index=True),
        sa.Column(
            'action',
            action_enum,
            nullable=False,
            index=True,
        ),
        sa.Column('access_method', sa.String(50), nullable=False),
        sa.Column(
            'status',
            status_enum,
            default='pending',
            nullable=False,
            index=True,
        ),
        sa.Column('request_data', sa.Text, nullable=True),
        sa.Column('response_data', sa.Text, nullable=True),
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('started_at', sa.DateTime, default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('triggered_by', sa.String(100), nullable=True),
    )

    # Add indexes for common queries
    op.create_index(
        'ix_provisioning_logs_subscription_action',
        'provisioning_logs',
        ['subscription_id', 'action'],
    )
    op.create_index(
        'ix_provisioning_logs_started_at',
        'provisioning_logs',
        ['started_at'],
    )


def downgrade():
    """Remove provisioning fields and logs table."""

    # Drop provisioning_logs table
    op.drop_index('ix_provisioning_logs_started_at', table_name='provisioning_logs')
    op.drop_index('ix_provisioning_logs_subscription_action', table_name='provisioning_logs')
    op.drop_table('provisioning_logs')

    # Drop subscriptions columns
    op.drop_index('ix_subscriptions_ppp_username', table_name='subscriptions')
    op.drop_column('subscriptions', 'provisioning_error')
    op.drop_column('subscriptions', 'provisioned_at')
    op.drop_column('subscriptions', 'ppp_password')
    op.drop_column('subscriptions', 'ppp_username')
    op.drop_column('subscriptions', 'access_method')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS provisioningstatus')
    op.execute('DROP TYPE IF EXISTS provisioningaction')

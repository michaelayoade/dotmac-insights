"""Add Chatwoot metrics snapshot table

Revision ID: chatwoot_metrics_001
Revises: chatwoot_sync_001
Create Date: 2026-01-02 10:30:00.000000

Creates chatwoot_metric_snapshots table for storing synced
report metrics from Chatwoot at various aggregation levels.
"""
from alembic import op
import sqlalchemy as sa


revision = 'chatwoot_metrics_001'
down_revision = 'chatwoot_sync_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chatwoot_metric_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        # Time dimensions
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        # Entity dimensions
        sa.Column('metric_level', sa.String(20), nullable=False),
        # Foreign keys
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inbox_id', sa.Integer(), sa.ForeignKey('omni_channels.id', ondelete='SET NULL'), nullable=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True),
        # Chatwoot IDs
        sa.Column('chatwoot_agent_id', sa.Integer(), nullable=True),
        sa.Column('chatwoot_inbox_id', sa.Integer(), nullable=True),
        sa.Column('chatwoot_team_id', sa.Integer(), nullable=True),
        # Conversation metrics
        sa.Column('conversations_count', sa.Integer(), default=0, nullable=False),
        sa.Column('incoming_messages_count', sa.Integer(), default=0, nullable=False),
        sa.Column('outgoing_messages_count', sa.Integer(), default=0, nullable=False),
        sa.Column('resolved_count', sa.Integer(), default=0, nullable=False),
        # Time metrics
        sa.Column('avg_first_response_time', sa.Integer(), nullable=True),
        sa.Column('avg_resolution_time', sa.Integer(), nullable=True),
        # CSAT metrics
        sa.Column('csat_total_responses', sa.Integer(), default=0, nullable=False),
        sa.Column('csat_positive_responses', sa.Integer(), default=0, nullable=False),
        sa.Column('csat_score', sa.Numeric(5, 2), nullable=True),
        # Raw JSON
        sa.Column('raw_metrics', sa.JSON(), nullable=True),
        # Audit
        sa.Column('synced_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for common query patterns
    op.create_index('ix_chatwoot_metrics_period_type', 'chatwoot_metric_snapshots', ['period_type'])
    op.create_index('ix_chatwoot_metrics_period_start', 'chatwoot_metric_snapshots', ['period_start'])
    op.create_index('ix_chatwoot_metrics_metric_level', 'chatwoot_metric_snapshots', ['metric_level'])
    op.create_index('ix_chatwoot_metrics_agent_id', 'chatwoot_metric_snapshots', ['agent_id'])
    op.create_index('ix_chatwoot_metrics_inbox_id', 'chatwoot_metric_snapshots', ['inbox_id'])
    op.create_index('ix_chatwoot_metrics_team_id', 'chatwoot_metric_snapshots', ['team_id'])
    op.create_index('ix_chatwoot_metrics_chatwoot_agent_id', 'chatwoot_metric_snapshots', ['chatwoot_agent_id'])

    # Composite indexes for dashboard queries
    op.create_index(
        'ix_chatwoot_metrics_level_period',
        'chatwoot_metric_snapshots',
        ['metric_level', 'period_type', 'period_start']
    )
    op.create_index(
        'ix_chatwoot_metrics_agent_period',
        'chatwoot_metric_snapshots',
        ['agent_id', 'period_start']
    )


def downgrade() -> None:
    op.drop_index('ix_chatwoot_metrics_agent_period', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_level_period', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_chatwoot_agent_id', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_team_id', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_inbox_id', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_agent_id', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_metric_level', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_period_start', table_name='chatwoot_metric_snapshots')
    op.drop_index('ix_chatwoot_metrics_period_type', table_name='chatwoot_metric_snapshots')
    op.drop_table('chatwoot_metric_snapshots')

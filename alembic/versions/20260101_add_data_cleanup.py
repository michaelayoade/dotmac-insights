"""Add data cleanup and normalization tables.

Revision ID: data_cleanup_001
Revises: mikrotik_provisioning_001
Create Date: 2026-01-01

This migration adds:
1. cleanup_rules table for saved cleanup configurations
2. cleanup_scans table for scan jobs
3. cleanup_issues table for detected data quality issues
4. cleanup_jobs table for cleanup execution tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'data_cleanup_001'
down_revision = 'mikrotik_provisioning_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add data cleanup tables and enums."""

    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupentitytype AS ENUM (
                'customer', 'contact', 'subscription', 'supplier',
                'employee', 'invoice', 'payment'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupactiontype AS ENUM (
                'normalize', 'merge', 'delete', 'set_default',
                'set_null', 'link', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupissuestatue AS ENUM (
                'open', 'in_progress', 'resolved', 'ignored'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupjobstatus AS ENUM (
                'pending', 'previewing', 'preview_ready',
                'executing', 'completed', 'failed', 'rolled_back'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupscanstatus AS ENUM (
                'pending', 'running', 'completed', 'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupissuestatus AS ENUM (
                'open', 'in_progress', 'resolved', 'ignored'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleanupisstyetype AS ENUM (
                'duplicate', 'invalid_format', 'missing_required',
                'invalid_value', 'orphaned', 'inconsistent', 'stale'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE issueseverity AS ENUM (
                'critical', 'high', 'medium', 'low'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Create cleanup_rules table
    entity_type_enum = postgresql.ENUM(
        'customer', 'contact', 'subscription', 'supplier',
        'employee', 'invoice', 'payment',
        name='cleanupentitytype', create_type=False
    )
    action_type_enum = postgresql.ENUM(
        'normalize', 'merge', 'delete', 'set_default',
        'set_null', 'link', 'custom',
        name='cleanupactiontype', create_type=False
    )
    issue_type_enum = postgresql.ENUM(
        'duplicate', 'invalid_format', 'missing_required',
        'invalid_value', 'orphaned', 'inconsistent', 'stale',
        name='cleanupisstyetype', create_type=False
    )
    severity_enum = postgresql.ENUM(
        'critical', 'high', 'medium', 'low',
        name='issueseverity', create_type=False
    )
    issue_status_enum = postgresql.ENUM(
        'open', 'in_progress', 'resolved', 'ignored',
        name='cleanupissuestatus', create_type=False
    )
    scan_status_enum = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed',
        name='cleanupscanstatus', create_type=False
    )
    job_status_enum = postgresql.ENUM(
        'pending', 'previewing', 'preview_ready',
        'executing', 'completed', 'failed', 'rolled_back',
        name='cleanupjobstatus', create_type=False
    )

    op.create_table(
        'cleanup_rules',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('entity_type', entity_type_enum, nullable=False, index=True),
        sa.Column('issue_type', issue_type_enum, nullable=False, index=True),
        sa.Column('detection_config', postgresql.JSON, nullable=True),
        sa.Column('action_type', action_type_enum, nullable=False),
        sa.Column('action_config', postgresql.JSON, nullable=True),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True, index=True),
        sa.Column('created_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create cleanup_scans table
    op.create_table(
        'cleanup_scans',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('entity_types', postgresql.JSON, nullable=False),
        sa.Column('issue_types', postgresql.JSON, nullable=True),
        sa.Column('status', scan_status_enum, default='pending', nullable=False, index=True),
        sa.Column('progress_pct', sa.Integer, default=0),
        sa.Column('current_step', sa.String(255), nullable=True),
        sa.Column('issues_found', sa.Integer, default=0),
        sa.Column('records_scanned', sa.Integer, default=0),
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('started_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('started_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
    )

    # Create cleanup_jobs table first (needed for FK in cleanup_issues)
    op.create_table(
        'cleanup_jobs',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('rule_id', sa.Integer, sa.ForeignKey('cleanup_rules.id'), nullable=True, index=True),
        sa.Column('entity_type', entity_type_enum, nullable=False, index=True),
        sa.Column('issue_ids', postgresql.JSON, nullable=True),
        sa.Column('record_ids', postgresql.JSON, nullable=False),
        sa.Column('action_type', action_type_enum, nullable=False),
        sa.Column('action_config', postgresql.JSON, nullable=True),
        sa.Column('status', job_status_enum, default='pending', nullable=False, index=True),
        sa.Column('records_processed', sa.Integer, default=0),
        sa.Column('records_changed', sa.Integer, default=0),
        sa.Column('records_failed', sa.Integer, default=0),
        sa.Column('changes_log', postgresql.JSON, nullable=True),
        sa.Column('preview_data', postgresql.JSON, nullable=True),
        sa.Column('is_rollbackable', sa.Boolean, default=True),
        sa.Column('rollback_data', postgresql.JSON, nullable=True),
        sa.Column('rolled_back_at', sa.DateTime, nullable=True),
        sa.Column('rolled_back_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )

    # Create cleanup_issues table
    op.create_table(
        'cleanup_issues',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('scan_id', sa.Integer, sa.ForeignKey('cleanup_scans.id'), nullable=False, index=True),
        sa.Column('issue_type', issue_type_enum, nullable=False, index=True),
        sa.Column('severity', severity_enum, nullable=False, index=True),
        sa.Column('entity_type', entity_type_enum, nullable=False, index=True),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('record_ids', postgresql.JSON, nullable=False),
        sa.Column('record_count', sa.Integer, nullable=False),
        sa.Column('sample_values', postgresql.JSON, nullable=True),
        sa.Column('status', issue_status_enum, default='open', nullable=False, index=True),
        sa.Column('resolution_job_id', sa.Integer, sa.ForeignKey('cleanup_jobs.id'), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('resolved_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Add indexes for common queries
    op.create_index(
        'ix_cleanup_issues_scan_status',
        'cleanup_issues',
        ['scan_id', 'status'],
    )
    op.create_index(
        'ix_cleanup_issues_entity_field',
        'cleanup_issues',
        ['entity_type', 'field_name'],
    )
    op.create_index(
        'ix_cleanup_jobs_status_created',
        'cleanup_jobs',
        ['status', 'created_at'],
    )


def downgrade():
    """Remove data cleanup tables and enums."""

    # Drop indexes
    op.drop_index('ix_cleanup_jobs_status_created', table_name='cleanup_jobs')
    op.drop_index('ix_cleanup_issues_entity_field', table_name='cleanup_issues')
    op.drop_index('ix_cleanup_issues_scan_status', table_name='cleanup_issues')

    # Drop tables in reverse order (respecting FKs)
    op.drop_table('cleanup_issues')
    op.drop_table('cleanup_jobs')
    op.drop_table('cleanup_scans')
    op.drop_table('cleanup_rules')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS cleanupjobstatus')
    op.execute('DROP TYPE IF EXISTS cleanupscanstatus')
    op.execute('DROP TYPE IF EXISTS cleanupissuestatus')
    op.execute('DROP TYPE IF EXISTS issueseverity')
    op.execute('DROP TYPE IF EXISTS cleanupisstyetype')
    op.execute('DROP TYPE IF EXISTS cleanupactiontype')
    op.execute('DROP TYPE IF EXISTS cleanupentitytype')
    op.execute('DROP TYPE IF EXISTS cleanupissuestatue')

"""Add data migration tool tables

Revision ID: 20251224_add_migration_tool_tables
Revises: 20251223_add_project_pm_features
Create Date: 2025-12-24

Creates tables for the data migration tool:
- migration_jobs: Tracks migration job metadata and progress
- migration_records: Individual record status within a migration
- migration_rollback_logs: Audit trail for rollback operations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20251224_add_migration_tool_tables"
down_revision: Union[str, None] = "20251223_add_scheduled_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create migration_status enum
    migration_status = postgresql.ENUM(
        'pending', 'uploaded', 'mapped', 'validating', 'validated',
        'running', 'completed', 'failed', 'cancelled', 'rolled_back',
        name='migrationstatus',
        create_type=False
    )
    migration_status.create(op.get_bind(), checkfirst=True)

    # Create source_type enum
    source_type = postgresql.ENUM(
        'csv', 'json', 'excel',
        name='sourcetype',
        create_type=False
    )
    source_type.create(op.get_bind(), checkfirst=True)

    # Create dedup_strategy enum
    dedup_strategy = postgresql.ENUM(
        'skip', 'update', 'merge',
        name='dedupstrategy',
        create_type=False
    )
    dedup_strategy.create(op.get_bind(), checkfirst=True)

    # Create record_action enum
    record_action = postgresql.ENUM(
        'created', 'updated', 'skipped', 'failed',
        name='recordaction',
        create_type=False
    )
    record_action.create(op.get_bind(), checkfirst=True)

    # Create entity_type enum
    entity_type = postgresql.ENUM(
        'contacts', 'customers', 'employees',
        'invoices', 'payments', 'credit_notes', 'suppliers',
        'purchase_invoices', 'journal_entries', 'accounts', 'bank_transactions',
        'leads', 'opportunities',
        'projects', 'tasks',
        'tickets',
        'departments', 'designations', 'leave_applications', 'attendance',
        'items', 'warehouses', 'stock_entries',
        'expenses', 'expense_claims',
        'service_orders',
        'assets',
        name='entitytype',
        create_type=False
    )
    entity_type.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # MIGRATION JOBS TABLE
    # =========================================================================
    op.create_table(
        'migration_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entity_type', entity_type, nullable=False),
        sa.Column('source_type', source_type, nullable=True),
        sa.Column('status', migration_status, nullable=False, server_default='pending'),

        # Progress tracking
        sa.Column('total_rows', sa.Integer(), server_default='0'),
        sa.Column('processed_rows', sa.Integer(), server_default='0'),
        sa.Column('created_records', sa.Integer(), server_default='0'),
        sa.Column('updated_records', sa.Integer(), server_default='0'),
        sa.Column('skipped_records', sa.Integer(), server_default='0'),
        sa.Column('failed_records', sa.Integer(), server_default='0'),

        # Configuration (JSON)
        sa.Column('field_mapping', postgresql.JSONB(), nullable=True),
        sa.Column('cleaning_rules', postgresql.JSONB(), nullable=True),
        sa.Column('dedup_strategy', dedup_strategy, nullable=True),
        sa.Column('dedup_fields', postgresql.JSONB(), nullable=True),

        # File handling
        sa.Column('source_file_path', sa.String(500), nullable=True),
        sa.Column('source_file_hash', sa.String(64), nullable=True),
        sa.Column('source_columns', postgresql.JSONB(), nullable=True),
        sa.Column('sample_rows', postgresql.JSONB(), nullable=True),

        # Validation results
        sa.Column('validation_result', postgresql.JSONB(), nullable=True),

        # Error tracking
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),

        # Audit
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_migration_jobs_id', 'migration_jobs', ['id'])
    op.create_index('ix_migration_jobs_entity_type', 'migration_jobs', ['entity_type'])
    op.create_index('ix_migration_jobs_status', 'migration_jobs', ['status'])
    op.create_index('ix_migration_jobs_created_at', 'migration_jobs', ['created_at'])

    # =========================================================================
    # MIGRATION RECORDS TABLE
    # =========================================================================
    op.create_table(
        'migration_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('migration_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),

        # Data snapshots (JSON)
        sa.Column('source_data', postgresql.JSONB(), nullable=True),
        sa.Column('transformed_data', postgresql.JSONB(), nullable=True),

        # Result tracking
        sa.Column('target_record_id', sa.Integer(), nullable=True),
        sa.Column('target_record_type', sa.String(100), nullable=True),
        sa.Column('action', record_action, nullable=True),

        # For rollback
        sa.Column('previous_data', postgresql.JSONB(), nullable=True),
        sa.Column('can_rollback', sa.Boolean(), server_default='true'),

        # Error tracking
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('validation_errors', postgresql.JSONB(), nullable=True),
        sa.Column('validation_warnings', postgresql.JSONB(), nullable=True),

        # Timestamps
        sa.Column('processed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_migration_records_id', 'migration_records', ['id'])
    op.create_index('ix_migration_records_job_id', 'migration_records', ['job_id'])
    op.create_index('ix_migration_records_job_action', 'migration_records', ['job_id', 'action'])
    op.create_index('ix_migration_records_job_row', 'migration_records', ['job_id', 'row_number'])

    # =========================================================================
    # MIGRATION ROLLBACK LOGS TABLE
    # =========================================================================
    op.create_table(
        'migration_rollback_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('migration_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('record_id', sa.Integer(), sa.ForeignKey('migration_records.id', ondelete='SET NULL'), nullable=True),

        # What was rolled back
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('target_record_id', sa.Integer(), nullable=False),

        # Action taken
        sa.Column('rollback_action', sa.String(50), nullable=False),
        sa.Column('previous_data', postgresql.JSONB(), nullable=True),

        # Audit
        sa.Column('rolled_back_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('rolled_back_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index('ix_migration_rollback_logs_id', 'migration_rollback_logs', ['id'])
    op.create_index('ix_migration_rollback_logs_job_id', 'migration_rollback_logs', ['job_id'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('migration_rollback_logs')
    op.drop_table('migration_records')
    op.drop_table('migration_jobs')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS entitytype')
    op.execute('DROP TYPE IF EXISTS recordaction')
    op.execute('DROP TYPE IF EXISTS dedupstrategy')
    op.execute('DROP TYPE IF EXISTS sourcetype')
    op.execute('DROP TYPE IF EXISTS migrationstatus')

"""add_cleaning_operations

Revision ID: 20260103_cleaning_ops
Revises: 20260103_cpe_tracking
Create Date: 2026-01-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260103_cleaning_ops'
down_revision: Union[str, None] = '20260103_cpe_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cleaning_operations table for data cleaner service."""
    op.create_table(
        'cleaning_operations',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Unique operation identifier (UUID)
        sa.Column('operation_id', sa.String(36), unique=True, nullable=False, index=True),

        # Operation type: bulk_update, normalize, merge, link
        sa.Column(
            'operation_type',
            sa.String(20),
            nullable=False,
            index=True,
        ),

        # Status: pending, executing, completed, failed, rolled_back
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            default='pending',
            index=True,
        ),

        # Target table name
        sa.Column('table_name', sa.String(100), nullable=False, index=True),

        # Execution counts
        sa.Column('records_affected', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),

        # Operation configuration (filters, updates planned, etc.)
        sa.Column('operation_config', postgresql.JSONB(), default={}, nullable=True),

        # Changes log: list of {record_id, before, after, changed_fields}
        sa.Column('changes_log', postgresql.JSONB(), default=[], nullable=True),

        # Rollback data: {record_id: {full snapshot before change}}
        sa.Column('rollback_data', postgresql.JSONB(), default={}, nullable=True),

        # Errors: list of {record_id, error, field}
        sa.Column('errors', postgresql.JSONB(), default=[], nullable=True),

        # Summary metadata (operation-specific info for display)
        sa.Column('summary', postgresql.JSONB(), default={}, nullable=True),

        # Rollback state
        sa.Column('is_rolled_back', sa.Boolean(), default=False),
        sa.Column('rolled_back_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'rolled_back_by_id',
            sa.BigInteger(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),

        # Audit timestamps
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # User who created the operation
        sa.Column(
            'created_by_id',
            sa.BigInteger(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )

    # Composite indexes for common queries
    op.create_index(
        'ix_cleaning_ops_status_created',
        'cleaning_operations',
        ['status', 'created_at'],
    )
    op.create_index(
        'ix_cleaning_ops_table_created',
        'cleaning_operations',
        ['table_name', 'created_at'],
    )
    op.create_index(
        'ix_cleaning_ops_type_status',
        'cleaning_operations',
        ['operation_type', 'status'],
    )


def downgrade() -> None:
    """Drop cleaning_operations table."""
    op.drop_index('ix_cleaning_ops_type_status', table_name='cleaning_operations')
    op.drop_index('ix_cleaning_ops_table_created', table_name='cleaning_operations')
    op.drop_index('ix_cleaning_ops_status_created', table_name='cleaning_operations')
    op.drop_table('cleaning_operations')

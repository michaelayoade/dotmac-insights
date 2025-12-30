"""Add scheduled_tasks table for delayed Celery task tracking

Revision ID: 20251223_add_scheduled_tasks
Revises: 20251223_add_workflow_tasks
Create Date: 2025-12-23

Creates scheduled_tasks table to track Celery tasks scheduled for future execution:
- Tracks celery_task_id for cancellation support
- Records execution status and results
- Links to source entities for context
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20251223_add_scheduled_tasks"
down_revision: Union[str, None] = "20251223_add_workflow_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_tasks',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True),

        # Celery reference
        sa.Column('celery_task_id', sa.String(255), unique=True, nullable=False, comment='Celery AsyncResult ID'),
        sa.Column('task_name', sa.String(255), nullable=False, comment='Celery task name (e.g., scheduled.send_reminder)'),

        # Schedule
        sa.Column('scheduled_for', sa.DateTime(), nullable=False, comment='When the task should execute'),
        sa.Column('executed_at', sa.DateTime(), nullable=True, comment='When the task actually executed'),

        # Status
        sa.Column('status', sa.String(50), server_default='scheduled', nullable=False, comment='scheduled, executed, cancelled, failed'),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),

        # Context
        sa.Column('source_type', sa.String(50), nullable=True, comment='Entity type this task relates to'),
        sa.Column('source_id', sa.Integer(), nullable=True, comment='Entity ID this task relates to'),
        sa.Column('payload', postgresql.JSONB(), nullable=True, comment='Task arguments/kwargs'),
        sa.Column('result', postgresql.JSONB(), nullable=True, comment='Task return value'),
        sa.Column('error', sa.Text(), nullable=True, comment='Error message if failed'),

        # Audit
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )

    # Indexes for common queries
    op.create_index(
        'ix_scheduled_tasks_status_scheduled_for',
        'scheduled_tasks',
        ['status', 'scheduled_for'],
        postgresql_where=sa.text("status = 'scheduled'")
    )
    op.create_index(
        'ix_scheduled_tasks_source',
        'scheduled_tasks',
        ['source_type', 'source_id'],
        postgresql_where=sa.text("source_type IS NOT NULL")
    )
    op.create_index(
        'ix_scheduled_tasks_celery_task_id',
        'scheduled_tasks',
        ['celery_task_id'],
        unique=True
    )
    op.create_index(
        'ix_scheduled_tasks_task_name',
        'scheduled_tasks',
        ['task_name', 'status']
    )


def downgrade() -> None:
    op.drop_index('ix_scheduled_tasks_task_name', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_celery_task_id', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_source', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_status_scheduled_for', table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')

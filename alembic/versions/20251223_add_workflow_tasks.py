"""Add workflow_tasks table for unified task management

Revision ID: 20251223_add_workflow_tasks
Revises: 20251223_add_project_pm_features
Create Date: 2025-12-23

Creates workflow_tasks table to aggregate human tasks from all modules:
- Approval requests from accounting workflows
- Support tickets assigned to agents
- Expense claims pending approval
- Performance scorecards awaiting review
- Inbox conversations assigned to agents
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20251223_add_workflow_tasks"
down_revision: Union[str, None] = "20251223_add_project_pm_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflow_tasks',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True),

        # Polymorphic source reference
        sa.Column('source_type', sa.String(50), nullable=False, comment='approval, ticket, expense_claim, cash_advance, scorecard, conversation'),
        sa.Column('source_id', sa.Integer(), nullable=False),

        # Task details
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('action_url', sa.String(500), nullable=True, comment='URL to take action on this task'),

        # Assignment (one of these should be set)
        sa.Column('assignee_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assignee_employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assignee_team_id', sa.Integer(), nullable=True, comment='Reference to teams table'),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('assigned_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Priority and timing
        sa.Column('priority', sa.String(20), server_default='medium', nullable=False, comment='low, medium, high, urgent'),
        sa.Column('due_at', sa.DateTime(), nullable=True),

        # Status
        sa.Column('status', sa.String(50), server_default='pending', nullable=False, comment='pending, in_progress, completed, cancelled'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Context
        sa.Column('module', sa.String(50), nullable=False, comment='accounting, support, expenses, performance, inbox, hr, projects'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, comment='Additional context data'),

        # Audit
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Indexes for common queries
    op.create_index(
        'ix_workflow_tasks_assignee_user',
        'workflow_tasks',
        ['assignee_user_id', 'status', 'due_at'],
        postgresql_where=sa.text("assignee_user_id IS NOT NULL")
    )
    op.create_index(
        'ix_workflow_tasks_assignee_employee',
        'workflow_tasks',
        ['assignee_employee_id', 'status', 'due_at'],
        postgresql_where=sa.text("assignee_employee_id IS NOT NULL")
    )
    op.create_index(
        'ix_workflow_tasks_source',
        'workflow_tasks',
        ['source_type', 'source_id']
    )
    op.create_index(
        'ix_workflow_tasks_module_status',
        'workflow_tasks',
        ['module', 'status']
    )
    op.create_index(
        'ix_workflow_tasks_due_at',
        'workflow_tasks',
        ['due_at'],
        postgresql_where=sa.text("status = 'pending' AND due_at IS NOT NULL")
    )

    # Unique constraint: one task per source per user
    op.create_unique_constraint(
        'uq_workflow_tasks_source_user',
        'workflow_tasks',
        ['source_type', 'source_id', 'assignee_user_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_workflow_tasks_source_user', 'workflow_tasks', type_='unique')
    op.drop_index('ix_workflow_tasks_due_at', table_name='workflow_tasks')
    op.drop_index('ix_workflow_tasks_module_status', table_name='workflow_tasks')
    op.drop_index('ix_workflow_tasks_source', table_name='workflow_tasks')
    op.drop_index('ix_workflow_tasks_assignee_employee', table_name='workflow_tasks')
    op.drop_index('ix_workflow_tasks_assignee_user', table_name='workflow_tasks')
    op.drop_table('workflow_tasks')

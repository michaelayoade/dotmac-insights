"""Add sync_schedules table

Revision ID: 20251224_add_sync_schedules
Revises: 20251224_add_migration_tool_tables
Create Date: 2025-12-24

Creates the sync_schedules table for user-configurable sync scheduling
through the admin UI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251224_add_sync_schedules"
down_revision: Union[str, None] = "20251224_add_migration_tool_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sync_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('kwargs', sa.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(length=50), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by_id'], ['employees.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sync_schedules_id'), 'sync_schedules', ['id'], unique=False)
    op.create_index(op.f('ix_sync_schedules_is_enabled'), 'sync_schedules', ['is_enabled'], unique=False)
    op.create_index(op.f('ix_sync_schedules_next_run_at'), 'sync_schedules', ['next_run_at'], unique=False)
    op.create_index(op.f('ix_sync_schedules_name'), 'sync_schedules', ['name'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_sync_schedules_name'), table_name='sync_schedules')
    op.drop_index(op.f('ix_sync_schedules_next_run_at'), table_name='sync_schedules')
    op.drop_index(op.f('ix_sync_schedules_is_enabled'), table_name='sync_schedules')
    op.drop_index(op.f('ix_sync_schedules_id'), table_name='sync_schedules')
    op.drop_table('sync_schedules')

"""Add sync cursors, DLQ, and indexes

Revision ID: d0b112dba8ae
Revises: b477cc6d91d3
Create Date: 2025-12-09 10:58:20.118123

"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0b112dba8ae'
down_revision: Union[str, None] = 'b477cc6d91d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sync_cursors table if it doesn't exist
    conn = op.get_bind()
    if context.is_offline_mode():
        existing_tables = []
    else:
        inspector = sa.inspect(conn)
        existing_tables = inspector.get_table_names()

    if 'sync_cursors' not in existing_tables:
        op.create_table(
            'sync_cursors',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('source', sa.Enum('SPLYNX', 'ERPNEXT', 'CHATWOOT', name='syncsource'), nullable=False),
            sa.Column('entity_type', sa.String(100), nullable=False),
            sa.Column('last_sync_timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_modified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_id', sa.String(100), nullable=True),
            sa.Column('last_page', sa.Integer(), nullable=True),
            sa.Column('cursor_value', sa.Text(), nullable=True),
            sa.Column('records_synced', sa.Integer(), default=0),
            sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_sync_cursors_id', 'sync_cursors', ['id'])
        op.create_index('ix_sync_cursors_source', 'sync_cursors', ['source'])
        op.create_index('ix_sync_cursors_entity_type', 'sync_cursors', ['entity_type'])
        op.create_unique_constraint('uix_sync_cursor_source_entity', 'sync_cursors', ['source', 'entity_type'])

    if 'failed_sync_records' not in existing_tables:
        op.create_table(
            'failed_sync_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('source', sa.Enum('SPLYNX', 'ERPNEXT', 'CHATWOOT', name='syncsource'), nullable=False),
            sa.Column('entity_type', sa.String(100), nullable=False),
            sa.Column('external_id', sa.String(255), nullable=True),
            sa.Column('payload', sa.Text(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=False),
            sa.Column('error_type', sa.String(255), nullable=True),
            sa.Column('retry_count', sa.Integer(), default=0),
            sa.Column('max_retries', sa.Integer(), default=3),
            sa.Column('last_retry_at', sa.DateTime(), nullable=True),
            sa.Column('next_retry_at', sa.DateTime(), nullable=True),
            sa.Column('is_resolved', sa.Boolean(), default=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_failed_sync_records_id', 'failed_sync_records', ['id'])
        op.create_index('ix_failed_sync_records_source', 'failed_sync_records', ['source'])
        op.create_index('ix_failed_sync_records_entity_type', 'failed_sync_records', ['entity_type'])
        op.create_index('ix_failed_sync_records_external_id', 'failed_sync_records', ['external_id'])
        op.create_index('ix_failed_sync_records_is_resolved', 'failed_sync_records', ['is_resolved'])
        op.create_index('ix_failed_sync_records_next_retry_at', 'failed_sync_records', ['next_retry_at'])
        op.create_index('ix_failed_sync_records_created_at', 'failed_sync_records', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    conn = op.get_bind()
    if context.is_offline_mode():
        existing_tables = ['failed_sync_records', 'sync_cursors']
    else:
        inspector = sa.inspect(conn)
        existing_tables = inspector.get_table_names()

    if 'failed_sync_records' in existing_tables:
        op.drop_table('failed_sync_records')

    if 'sync_cursors' in existing_tables:
        op.drop_table('sync_cursors')

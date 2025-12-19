"""Add unified_ticket_id backlinks to legacy tables

Revision ID: add_unified_ticket_backlinks
Revises: m8n9o0p1q2r3
Create Date: 2024-12-18

Adds unified_ticket_id foreign key columns to tickets and conversations
tables for dual-write sync and reconciliation.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_unified_ticket_backlinks'
down_revision = 'm8n9o0p1q2r3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unified_ticket_id to tickets table
    op.add_column(
        'tickets',
        sa.Column('unified_ticket_id', sa.Integer(), nullable=True)
    )
    op.create_index(
        'ix_tickets_unified_ticket_id',
        'tickets',
        ['unified_ticket_id']
    )
    op.create_foreign_key(
        'fk_tickets_unified_ticket_id',
        'tickets',
        'unified_tickets',
        ['unified_ticket_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add unified_ticket_id to conversations table
    op.add_column(
        'conversations',
        sa.Column('unified_ticket_id', sa.Integer(), nullable=True)
    )
    op.create_index(
        'ix_conversations_unified_ticket_id',
        'conversations',
        ['unified_ticket_id']
    )
    op.create_foreign_key(
        'fk_conversations_unified_ticket_id',
        'conversations',
        'unified_tickets',
        ['unified_ticket_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove from conversations
    op.drop_constraint('fk_conversations_unified_ticket_id', 'conversations', type_='foreignkey')
    op.drop_index('ix_conversations_unified_ticket_id', 'conversations')
    op.drop_column('conversations', 'unified_ticket_id')

    # Remove from tickets
    op.drop_constraint('fk_tickets_unified_ticket_id', 'tickets', type_='foreignkey')
    op.drop_index('ix_tickets_unified_ticket_id', 'tickets')
    op.drop_column('tickets', 'unified_ticket_id')

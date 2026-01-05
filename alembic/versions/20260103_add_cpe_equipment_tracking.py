"""add CPE equipment tracking fields

Revision ID: 20260103_cpe_tracking
Revises: 20260103_quote_sub
Create Date: 2026-01-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260103_cpe_tracking'
down_revision: Union[str, None] = '20260103_quote_sub'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add item_id FK to serial_numbers
    op.add_column('serial_numbers', sa.Column('item_id', sa.Integer(), nullable=True))
    op.create_index('ix_serial_numbers_item_id', 'serial_numbers', ['item_id'])
    op.create_foreign_key(
        'fk_serial_numbers_item_id', 'serial_numbers', 'items',
        ['item_id'], ['id'], ondelete='SET NULL'
    )

    # Add subscription reservation fields
    op.add_column('serial_numbers', sa.Column('reserved_for_subscription_id', sa.Integer(), nullable=True))
    op.add_column('serial_numbers', sa.Column('issued_to_party_id', sa.BigInteger(), nullable=True))
    op.add_column('serial_numbers', sa.Column('reserved_at', sa.DateTime(), nullable=True))
    op.add_column('serial_numbers', sa.Column('issued_at', sa.DateTime(), nullable=True))
    op.add_column('serial_numbers', sa.Column('returned_at', sa.DateTime(), nullable=True))
    op.add_column('serial_numbers', sa.Column('return_notes', sa.Text(), nullable=True))

    op.create_index('ix_serial_numbers_reserved_for_subscription_id', 'serial_numbers', ['reserved_for_subscription_id'])
    op.create_index('ix_serial_numbers_issued_to_party_id', 'serial_numbers', ['issued_to_party_id'])

    op.create_foreign_key(
        'fk_serial_numbers_subscription', 'serial_numbers', 'subscriptions',
        ['reserved_for_subscription_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_serial_numbers_party', 'serial_numbers', 'parties',
        ['issued_to_party_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_serial_numbers_party', 'serial_numbers', type_='foreignkey')
    op.drop_constraint('fk_serial_numbers_subscription', 'serial_numbers', type_='foreignkey')
    op.drop_index('ix_serial_numbers_issued_to_party_id', 'serial_numbers')
    op.drop_index('ix_serial_numbers_reserved_for_subscription_id', 'serial_numbers')
    op.drop_column('serial_numbers', 'return_notes')
    op.drop_column('serial_numbers', 'returned_at')
    op.drop_column('serial_numbers', 'issued_at')
    op.drop_column('serial_numbers', 'reserved_at')
    op.drop_column('serial_numbers', 'issued_to_party_id')
    op.drop_column('serial_numbers', 'reserved_for_subscription_id')
    op.drop_constraint('fk_serial_numbers_item_id', 'serial_numbers', type_='foreignkey')
    op.drop_index('ix_serial_numbers_item_id', 'serial_numbers')
    op.drop_column('serial_numbers', 'item_id')

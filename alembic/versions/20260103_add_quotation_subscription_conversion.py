"""add quotation subscription conversion fields

Revision ID: 20260103_quote_sub
Revises: 20260103_asset_router
Create Date: 2026-01-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260103_quote_sub'
down_revision: Union[str, None] = '20260103_asset_router'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tariff link and subscription fields to quotation_items
    op.add_column(
        'quotation_items',
        sa.Column('tariff_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'quotation_items',
        sa.Column('is_recurring', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column(
        'quotation_items',
        sa.Column('billing_cycle', sa.String(50), nullable=True)
    )
    op.create_index('ix_quotation_items_tariff_id', 'quotation_items', ['tariff_id'])
    op.create_foreign_key(
        'fk_quotation_items_tariff_id', 'quotation_items', 'tariffs',
        ['tariff_id'], ['id'], ondelete='SET NULL'
    )

    # Add party and subscription conversion fields to quotations
    op.add_column('quotations', sa.Column('party_id', sa.BigInteger(), nullable=True))
    op.add_column('quotations', sa.Column('converted_subscription_id', sa.Integer(), nullable=True))
    op.add_column('quotations', sa.Column('converted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_quotations_party_id', 'quotations', ['party_id'])
    op.create_index('ix_quotations_converted_subscription_id', 'quotations', ['converted_subscription_id'])
    op.create_foreign_key(
        'fk_quotations_party_id', 'quotations', 'parties',
        ['party_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_quotations_converted_subscription_id', 'quotations', 'subscriptions',
        ['converted_subscription_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_quotations_converted_subscription_id', 'quotations', type_='foreignkey')
    op.drop_constraint('fk_quotations_party_id', 'quotations', type_='foreignkey')
    op.drop_index('ix_quotations_converted_subscription_id', 'quotations')
    op.drop_index('ix_quotations_party_id', 'quotations')
    op.drop_column('quotations', 'converted_at')
    op.drop_column('quotations', 'converted_subscription_id')
    op.drop_column('quotations', 'party_id')
    op.drop_constraint('fk_quotation_items_tariff_id', 'quotation_items', type_='foreignkey')
    op.drop_index('ix_quotation_items_tariff_id', 'quotation_items')
    op.drop_column('quotation_items', 'billing_cycle')
    op.drop_column('quotation_items', 'is_recurring')
    op.drop_column('quotation_items', 'tariff_id')

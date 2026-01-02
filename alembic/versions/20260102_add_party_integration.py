"""Add party integration to subscriptions and pops

This migration adds party_id to subscriptions and payment_subscriptions,
and org_party_id to pops as part of the party system integration.

IMPORTANT: This is a breaking change migration. Before running:
1. Ensure all customers have corresponding parties
2. Run data migration script to populate party_id from customer_id
3. Only then make party_id NOT NULL and drop customer_id

Revision ID: party_integration_001
Revises: d1b9312c04ad
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'party_integration_001'
down_revision: Union[str, None] = 'd1b9312c04ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 1: Add party_id columns (nullable initially for data migration)

    # Add party_id to subscriptions
    op.add_column('subscriptions',
        sa.Column('party_id', sa.BigInteger(), nullable=True)
    )
    op.create_index('ix_subscriptions_party_id', 'subscriptions', ['party_id'])
    op.create_foreign_key(
        'fk_subscriptions_party_id',
        'subscriptions', 'parties',
        ['party_id'], ['id'],
        ondelete='CASCADE'
    )

    # Add party_id to payment_subscriptions
    op.add_column('payment_subscriptions',
        sa.Column('party_id', sa.BigInteger(), nullable=True)
    )
    op.create_index('ix_payment_subscriptions_party_id', 'payment_subscriptions', ['party_id'])
    op.create_foreign_key(
        'fk_payment_subscriptions_party_id',
        'payment_subscriptions', 'parties',
        ['party_id'], ['id'],
        ondelete='CASCADE'
    )

    # Add org_party_id to pops
    op.add_column('pops',
        sa.Column('org_party_id', sa.BigInteger(), nullable=True)
    )
    op.create_index('ix_pops_org_party_id', 'pops', ['org_party_id'])
    op.create_foreign_key(
        'fk_pops_org_party_id',
        'pops', 'parties',
        ['org_party_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add subscriber role type if not exists
    op.execute("""
        INSERT INTO ref_party_role_types (code, label, category, sort_order, is_active)
        VALUES ('subscriber', 'Subscriber', 'services', 50, true)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    # Remove org_party_id from pops
    op.drop_constraint('fk_pops_org_party_id', 'pops', type_='foreignkey')
    op.drop_index('ix_pops_org_party_id', table_name='pops')
    op.drop_column('pops', 'org_party_id')

    # Remove party_id from payment_subscriptions
    op.drop_constraint('fk_payment_subscriptions_party_id', 'payment_subscriptions', type_='foreignkey')
    op.drop_index('ix_payment_subscriptions_party_id', table_name='payment_subscriptions')
    op.drop_column('payment_subscriptions', 'party_id')

    # Remove party_id from subscriptions
    op.drop_constraint('fk_subscriptions_party_id', 'subscriptions', type_='foreignkey')
    op.drop_index('ix_subscriptions_party_id', table_name='subscriptions')
    op.drop_column('subscriptions', 'party_id')

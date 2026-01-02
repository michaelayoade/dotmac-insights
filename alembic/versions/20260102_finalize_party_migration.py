"""Finalize party migration - make party_id NOT NULL and drop customer_id

IMPORTANT: Only run this AFTER data migration is complete!
Ensure all subscriptions and payment_subscriptions have party_id populated.

To populate party_id from customer_id, run:
    UPDATE subscriptions s
    SET party_id = c.party_id
    FROM customers c
    WHERE s.customer_id = c.id AND s.party_id IS NULL;

    UPDATE payment_subscriptions ps
    SET party_id = c.party_id
    FROM customers c
    WHERE ps.customer_id = c.id AND ps.party_id IS NULL;

Revision ID: party_integration_002
Revises: party_integration_001
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'party_integration_002'
down_revision: Union[str, None] = 'party_integration_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 2: Make party_id NOT NULL and drop customer_id

    # Subscriptions: make party_id NOT NULL
    op.alter_column('subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=False
    )

    # Subscriptions: drop customer_id
    op.drop_constraint('subscriptions_customer_id_fkey', 'subscriptions', type_='foreignkey')
    op.drop_index('ix_subscriptions_customer_id', table_name='subscriptions')
    op.drop_column('subscriptions', 'customer_id')

    # Payment subscriptions: make party_id NOT NULL
    op.alter_column('payment_subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=False
    )

    # Payment subscriptions: drop customer_id and update index
    op.drop_constraint('payment_subscriptions_customer_id_fkey', 'payment_subscriptions', type_='foreignkey')
    op.drop_index('ix_payment_sub_customer_status', table_name='payment_subscriptions')
    op.drop_column('payment_subscriptions', 'customer_id')

    # Create new party_status index for payment_subscriptions
    op.create_index(
        'ix_payment_sub_party_status',
        'payment_subscriptions',
        ['party_id', 'status']
    )


def downgrade() -> None:
    # This is a destructive migration - downgrade requires data restoration
    # Re-add customer_id columns

    # Payment subscriptions: drop new index
    op.drop_index('ix_payment_sub_party_status', table_name='payment_subscriptions')

    # Payment subscriptions: add back customer_id
    op.add_column('payment_subscriptions',
        sa.Column('customer_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'payment_subscriptions_customer_id_fkey',
        'payment_subscriptions', 'customers',
        ['customer_id'], ['id']
    )
    op.create_index(
        'ix_payment_sub_customer_status',
        'payment_subscriptions',
        ['customer_id', 'status']
    )

    # Payment subscriptions: make party_id nullable again
    op.alter_column('payment_subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=True
    )

    # Subscriptions: add back customer_id
    op.add_column('subscriptions',
        sa.Column('customer_id', sa.Integer(), nullable=True)
    )
    op.create_index('ix_subscriptions_customer_id', 'subscriptions', ['customer_id'])
    op.create_foreign_key(
        'subscriptions_customer_id_fkey',
        'subscriptions', 'customers',
        ['customer_id'], ['id']
    )

    # Subscriptions: make party_id nullable again
    op.alter_column('subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=True
    )

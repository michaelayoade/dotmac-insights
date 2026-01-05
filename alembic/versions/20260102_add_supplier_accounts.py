"""add supplier_accounts table and purchase_invoice FK

Revision ID: supplier_accounts_001
Revises: acct_ops_settings_001
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'supplier_accounts_001'
down_revision: Union[str, None] = 'acct_ops_settings_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create supplier_accounts table
    op.create_table(
        'supplier_accounts',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('party_id', sa.BigInteger(), nullable=False),
        sa.Column('account_number', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('supplier_id', sa.BigInteger(), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('currency', sa.Text(), nullable=False, server_default='NGN'),
        sa.Column('outstanding_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('external_ids', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['party_id'], ['parties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('account_number'),
    )

    # Create indexes
    op.create_index('ix_supplier_accounts_party', 'supplier_accounts', ['party_id'])
    op.create_index('ix_supplier_accounts_status', 'supplier_accounts', ['status'])
    op.create_index('ix_supplier_accounts_supplier', 'supplier_accounts', ['supplier_id'])

    # Add supplier_account_id FK to purchase_invoices
    op.add_column(
        'purchase_invoices',
        sa.Column('supplier_account_id', sa.BigInteger(), nullable=True)
    )
    op.create_index(
        'ix_purchase_invoices_supplier_account',
        'purchase_invoices',
        ['supplier_account_id']
    )
    op.create_foreign_key(
        'fk_purchase_invoices_supplier_account',
        'purchase_invoices',
        'supplier_accounts',
        ['supplier_account_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove FK and column from purchase_invoices
    op.drop_constraint('fk_purchase_invoices_supplier_account', 'purchase_invoices', type_='foreignkey')
    op.drop_index('ix_purchase_invoices_supplier_account', table_name='purchase_invoices')
    op.drop_column('purchase_invoices', 'supplier_account_id')

    # Drop indexes
    op.drop_index('ix_supplier_accounts_supplier', table_name='supplier_accounts')
    op.drop_index('ix_supplier_accounts_status', table_name='supplier_accounts')
    op.drop_index('ix_supplier_accounts_party', table_name='supplier_accounts')

    # Drop table
    op.drop_table('supplier_accounts')

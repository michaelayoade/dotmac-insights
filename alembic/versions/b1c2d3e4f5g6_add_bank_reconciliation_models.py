"""add_bank_reconciliation_models

Revision ID: b1c2d3e4f5g6
Revises: 9389be4f5ff6
Create Date: 2025-12-12 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, None] = '9389be4f5ff6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bank_transaction_payments table (reconciliation allocations)
    op.create_table(
        'bank_transaction_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bank_transaction_id', sa.Integer(), nullable=False),
        sa.Column('payment_document', sa.String(length=100), nullable=True),
        sa.Column('payment_entry', sa.String(length=255), nullable=True),
        sa.Column('allocated_amount', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('idx', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('erpnext_name', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['bank_transaction_id'], ['bank_transactions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bank_transaction_payments_id'), 'bank_transaction_payments', ['id'], unique=False)
    op.create_index(op.f('ix_bank_transaction_payments_bank_transaction_id'), 'bank_transaction_payments', ['bank_transaction_id'], unique=False)
    op.create_index(op.f('ix_bank_transaction_payments_payment_entry'), 'bank_transaction_payments', ['payment_entry'], unique=False)

    # Create bank_reconciliations table
    op.create_table(
        'bank_reconciliations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('erpnext_id', sa.String(length=100), nullable=True),
        sa.Column('bank_account', sa.String(length=255), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=True),
        sa.Column('to_date', sa.Date(), nullable=True),
        sa.Column('bank_statement_opening_balance', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('bank_statement_closing_balance', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('account_opening_balance', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('total_credits', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('total_debits', sa.Numeric(precision=18, scale=6), nullable=True, server_default='0'),
        sa.Column('status', sa.Enum('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='bankreconciliationstatus'), nullable=True, server_default='DRAFT'),
        sa.Column('docstatus', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bank_reconciliations_id'), 'bank_reconciliations', ['id'], unique=False)
    op.create_index(op.f('ix_bank_reconciliations_erpnext_id'), 'bank_reconciliations', ['erpnext_id'], unique=True)
    op.create_index(op.f('ix_bank_reconciliations_bank_account'), 'bank_reconciliations', ['bank_account'], unique=False)
    op.create_index(op.f('ix_bank_reconciliations_status'), 'bank_reconciliations', ['status'], unique=False)


def downgrade() -> None:
    # Drop bank_reconciliations table
    op.drop_index(op.f('ix_bank_reconciliations_status'), table_name='bank_reconciliations')
    op.drop_index(op.f('ix_bank_reconciliations_bank_account'), table_name='bank_reconciliations')
    op.drop_index(op.f('ix_bank_reconciliations_erpnext_id'), table_name='bank_reconciliations')
    op.drop_index(op.f('ix_bank_reconciliations_id'), table_name='bank_reconciliations')
    op.drop_table('bank_reconciliations')

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS bankreconciliationstatus")

    # Drop bank_transaction_payments table
    op.drop_index(op.f('ix_bank_transaction_payments_payment_entry'), table_name='bank_transaction_payments')
    op.drop_index(op.f('ix_bank_transaction_payments_bank_transaction_id'), table_name='bank_transaction_payments')
    op.drop_index(op.f('ix_bank_transaction_payments_id'), table_name='bank_transaction_payments')
    op.drop_table('bank_transaction_payments')

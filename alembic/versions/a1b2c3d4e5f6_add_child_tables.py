"""add_child_tables

Revision ID: a1b2c3d4e5f6
# Chain after the latest head to avoid branching
Revises: f1a2b3c4d5e6
Create Date: 2025-12-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '49cb88c33c38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # ============= INVOICE ITEMS =============
    if 'invoice_items' not in existing_tables:
        op.create_table(
            'invoice_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('price_list_rate', sa.Numeric(18, 6), default=0),
            sa.Column('discount_percentage', sa.Numeric(18, 6), default=0),
            sa.Column('discount_amount', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('warehouse', sa.String(255), nullable=True),
            sa.Column('income_account', sa.String(255), nullable=True),
            sa.Column('expense_account', sa.String(255), nullable=True),
            sa.Column('cost_center', sa.String(255), nullable=True),
            sa.Column('sales_order', sa.String(255), nullable=True),
            sa.Column('delivery_note', sa.String(255), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= PURCHASE INVOICE ITEMS =============
    if 'purchase_invoice_items' not in existing_tables:
        op.create_table(
            'purchase_invoice_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('purchase_invoice_id', sa.Integer(), sa.ForeignKey('purchase_invoices.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('price_list_rate', sa.Numeric(18, 6), default=0),
            sa.Column('discount_percentage', sa.Numeric(18, 6), default=0),
            sa.Column('discount_amount', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('warehouse', sa.String(255), nullable=True),
            sa.Column('expense_account', sa.String(255), nullable=True),
            sa.Column('cost_center', sa.String(255), nullable=True),
            sa.Column('purchase_order', sa.String(255), nullable=True),
            sa.Column('purchase_receipt', sa.String(255), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= SALES ORDER ITEMS =============
    if 'sales_order_items' not in existing_tables:
        op.create_table(
            'sales_order_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('sales_order_id', sa.Integer(), sa.ForeignKey('sales_orders.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('price_list_rate', sa.Numeric(18, 6), default=0),
            sa.Column('discount_percentage', sa.Numeric(18, 6), default=0),
            sa.Column('discount_amount', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('delivered_qty', sa.Numeric(18, 6), default=0),
            sa.Column('billed_amt', sa.Numeric(18, 6), default=0),
            sa.Column('warehouse', sa.String(255), nullable=True),
            sa.Column('delivery_date', sa.DateTime(), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= PURCHASE ORDER ITEMS =============
    if 'purchase_order_items' not in existing_tables:
        op.create_table(
            'purchase_order_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('purchase_order_id', sa.Integer(), sa.ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('price_list_rate', sa.Numeric(18, 6), default=0),
            sa.Column('discount_percentage', sa.Numeric(18, 6), default=0),
            sa.Column('discount_amount', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('received_qty', sa.Numeric(18, 6), default=0),
            sa.Column('billed_amt', sa.Numeric(18, 6), default=0),
            sa.Column('warehouse', sa.String(255), nullable=True),
            sa.Column('schedule_date', sa.DateTime(), nullable=True),
            sa.Column('expense_account', sa.String(255), nullable=True),
            sa.Column('cost_center', sa.String(255), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= QUOTATION ITEMS =============
    if 'quotation_items' not in existing_tables:
        op.create_table(
            'quotation_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('price_list_rate', sa.Numeric(18, 6), default=0),
            sa.Column('discount_percentage', sa.Numeric(18, 6), default=0),
            sa.Column('discount_amount', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= JOURNAL ENTRY ACCOUNTS =============
    if 'journal_entry_accounts' not in existing_tables:
        op.create_table(
            'journal_entry_accounts',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('account', sa.String(255), nullable=True, index=True),
            sa.Column('account_type', sa.String(100), nullable=True),
            sa.Column('party_type', sa.String(100), nullable=True),
            sa.Column('party', sa.String(255), nullable=True, index=True),
            sa.Column('debit', sa.Numeric(18, 6), default=0),
            sa.Column('credit', sa.Numeric(18, 6), default=0),
            sa.Column('debit_in_account_currency', sa.Numeric(18, 6), default=0),
            sa.Column('credit_in_account_currency', sa.Numeric(18, 6), default=0),
            sa.Column('exchange_rate', sa.Numeric(18, 6), default=1),
            sa.Column('reference_type', sa.String(100), nullable=True),
            sa.Column('reference_name', sa.String(255), nullable=True),
            sa.Column('reference_due_date', sa.DateTime(), nullable=True),
            sa.Column('cost_center', sa.String(255), nullable=True),
            sa.Column('project', sa.String(255), nullable=True),
            sa.Column('bank_account', sa.String(255), nullable=True),
            sa.Column('cheque_no', sa.String(100), nullable=True),
            sa.Column('cheque_date', sa.DateTime(), nullable=True),
            sa.Column('user_remark', sa.Text(), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= PAYMENT REFERENCES =============
    if 'payment_references' not in existing_tables:
        op.create_table(
            'payment_references',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('reference_doctype', sa.String(100), nullable=True, index=True),
            sa.Column('reference_name', sa.String(255), nullable=True, index=True),
            sa.Column('total_amount', sa.Numeric(18, 6), default=0),
            sa.Column('outstanding_amount', sa.Numeric(18, 6), default=0),
            sa.Column('allocated_amount', sa.Numeric(18, 6), default=0),
            sa.Column('exchange_rate', sa.Numeric(18, 6), default=1),
            sa.Column('exchange_gain_loss', sa.Numeric(18, 6), default=0),
            sa.Column('due_date', sa.DateTime(), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )

    # ============= DEBIT NOTE ITEMS =============
    if 'debit_note_items' not in existing_tables:
        op.create_table(
            'debit_note_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('debit_note_id', sa.Integer(), sa.ForeignKey('debit_notes.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_code', sa.String(255), nullable=True, index=True),
            sa.Column('item_name', sa.String(255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('qty', sa.Numeric(18, 6), default=0),
            sa.Column('stock_qty', sa.Numeric(18, 6), default=0),
            sa.Column('uom', sa.String(50), nullable=True),
            sa.Column('stock_uom', sa.String(50), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
            sa.Column('rate', sa.Numeric(18, 6), default=0),
            sa.Column('amount', sa.Numeric(18, 6), default=0),
            sa.Column('net_amount', sa.Numeric(18, 6), default=0),
            sa.Column('expense_account', sa.String(255), nullable=True),
            sa.Column('cost_center', sa.String(255), nullable=True),
            sa.Column('purchase_invoice', sa.String(255), nullable=True),
            sa.Column('purchase_invoice_item', sa.String(255), nullable=True),
            sa.Column('idx', sa.Integer(), default=0),
        )


def downgrade() -> None:
    op.drop_table('debit_note_items')
    op.drop_table('payment_references')
    op.drop_table('journal_entry_accounts')
    op.drop_table('quotation_items')
    op.drop_table('purchase_order_items')
    op.drop_table('sales_order_items')
    op.drop_table('purchase_invoice_items')
    op.drop_table('invoice_items')

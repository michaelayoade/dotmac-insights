"""add_inventory_models

Revision ID: f1a2b3c4d5e6
Revises: e8f9a1b2c3d4
Create Date: 2025-12-12 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
# Chain after tax models to keep a single linear history.
down_revision: Union[str, None] = 'e8f9a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= WAREHOUSES =============
    op.create_table(
        'warehouses',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('warehouse_name', sa.String(255), nullable=False, index=True),
        sa.Column('parent_warehouse', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('warehouse_type', sa.String(100), nullable=True),
        sa.Column('account', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_warehouses_warehouse_name', 'warehouses', ['warehouse_name'])

    # ============= STOCK ENTRIES =============
    op.create_table(
        'stock_entries',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('stock_entry_type', sa.String(100), nullable=True, index=True),
        sa.Column('purpose', sa.String(100), nullable=True),
        sa.Column('posting_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('posting_time', sa.String(20), nullable=True),
        sa.Column('from_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('to_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('total_incoming_value', sa.Numeric(18, 6), default=0),
        sa.Column('total_outgoing_value', sa.Numeric(18, 6), default=0),
        sa.Column('value_difference', sa.Numeric(18, 6), default=0),
        sa.Column('total_amount', sa.Numeric(18, 6), default=0),
        sa.Column('work_order', sa.String(255), nullable=True),
        sa.Column('purchase_order', sa.String(255), nullable=True),
        sa.Column('sales_order', sa.String(255), nullable=True),
        sa.Column('delivery_note', sa.String(255), nullable=True),
        sa.Column('purchase_receipt', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('is_opening', sa.Boolean(), default=False),
        sa.Column('is_return', sa.Boolean(), default=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_stock_entries_stock_entry_type', 'stock_entries', ['stock_entry_type'])
    op.create_index('ix_stock_entries_posting_date', 'stock_entries', ['posting_date'])
    op.create_index('ix_stock_entries_from_warehouse', 'stock_entries', ['from_warehouse'])
    op.create_index('ix_stock_entries_to_warehouse', 'stock_entries', ['to_warehouse'])

    # Stock Entry Details (child table)
    op.create_table(
        'stock_entry_details',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('stock_entry_id', sa.Integer(), sa.ForeignKey('stock_entries.id'), nullable=False, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('stock_uom', sa.String(50), nullable=True),
        sa.Column('conversion_factor', sa.Numeric(18, 6), default=1),
        sa.Column('qty', sa.Numeric(18, 6), default=0),
        sa.Column('transfer_qty', sa.Numeric(18, 6), default=0),
        sa.Column('s_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('t_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('basic_rate', sa.Numeric(18, 6), default=0),
        sa.Column('basic_amount', sa.Numeric(18, 6), default=0),
        sa.Column('valuation_rate', sa.Numeric(18, 6), default=0),
        sa.Column('amount', sa.Numeric(18, 6), default=0),
        sa.Column('batch_no', sa.String(255), nullable=True),
        sa.Column('serial_no', sa.Text(), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_stock_entry_details_stock_entry_id', 'stock_entry_details', ['stock_entry_id'])
    op.create_index('ix_stock_entry_details_item_code', 'stock_entry_details', ['item_code'])
    op.create_index('ix_stock_entry_details_s_warehouse', 'stock_entry_details', ['s_warehouse'])
    op.create_index('ix_stock_entry_details_t_warehouse', 'stock_entry_details', ['t_warehouse'])

    # ============= STOCK LEDGER ENTRIES =============
    op.create_table(
        'stock_ledger_entries',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('posting_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('posting_time', sa.String(20), nullable=True),
        sa.Column('actual_qty', sa.Numeric(18, 6), default=0),
        sa.Column('qty_after_transaction', sa.Numeric(18, 6), default=0),
        sa.Column('incoming_rate', sa.Numeric(18, 6), default=0),
        sa.Column('outgoing_rate', sa.Numeric(18, 6), default=0),
        sa.Column('valuation_rate', sa.Numeric(18, 6), default=0),
        sa.Column('stock_value', sa.Numeric(18, 6), default=0),
        sa.Column('stock_value_difference', sa.Numeric(18, 6), default=0),
        sa.Column('voucher_type', sa.String(100), nullable=True, index=True),
        sa.Column('voucher_no', sa.String(255), nullable=True, index=True),
        sa.Column('voucher_detail_no', sa.String(255), nullable=True),
        sa.Column('batch_no', sa.String(255), nullable=True, index=True),
        sa.Column('serial_no', sa.Text(), nullable=True),
        sa.Column('fiscal_year', sa.String(20), nullable=True),
        sa.Column('is_cancelled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    op.create_index('ix_stock_ledger_entries_item_code', 'stock_ledger_entries', ['item_code'])
    op.create_index('ix_stock_ledger_entries_warehouse', 'stock_ledger_entries', ['warehouse'])
    op.create_index('ix_stock_ledger_entries_posting_date', 'stock_ledger_entries', ['posting_date'])
    op.create_index('ix_stock_ledger_entries_voucher_type', 'stock_ledger_entries', ['voucher_type'])
    op.create_index('ix_stock_ledger_entries_voucher_no', 'stock_ledger_entries', ['voucher_no'])
    op.create_index('ix_stock_ledger_entries_batch_no', 'stock_ledger_entries', ['batch_no'])
    # Composite index for common queries
    op.create_index('ix_stock_ledger_entries_item_warehouse', 'stock_ledger_entries', ['item_code', 'warehouse'])


def downgrade() -> None:
    op.drop_index('ix_stock_ledger_entries_item_warehouse', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_batch_no', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_voucher_no', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_voucher_type', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_posting_date', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_warehouse', table_name='stock_ledger_entries')
    op.drop_index('ix_stock_ledger_entries_item_code', table_name='stock_ledger_entries')
    op.drop_table('stock_ledger_entries')

    op.drop_index('ix_stock_entry_details_t_warehouse', table_name='stock_entry_details')
    op.drop_index('ix_stock_entry_details_s_warehouse', table_name='stock_entry_details')
    op.drop_index('ix_stock_entry_details_item_code', table_name='stock_entry_details')
    op.drop_index('ix_stock_entry_details_stock_entry_id', table_name='stock_entry_details')
    op.drop_table('stock_entry_details')

    op.drop_index('ix_stock_entries_to_warehouse', table_name='stock_entries')
    op.drop_index('ix_stock_entries_from_warehouse', table_name='stock_entries')
    op.drop_index('ix_stock_entries_posting_date', table_name='stock_entries')
    op.drop_index('ix_stock_entries_stock_entry_type', table_name='stock_entries')
    op.drop_table('stock_entries')

    op.drop_index('ix_warehouses_warehouse_name', table_name='warehouses')
    op.drop_table('warehouses')

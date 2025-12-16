"""Inventory enhancements: GL accounts, stock receipt/issue, transfers, batch/serial

Revision ID: inv_enhance_001
Revises:
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'inv_enhance_001'
# Chain to latest inventory branch merge
down_revision = '49cb88c33c38'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GL account and inventory fields to items table
    op.add_column('items', sa.Column('stock_account', sa.String(255), nullable=True))
    op.add_column('items', sa.Column('expense_account', sa.String(255), nullable=True))
    op.add_column('items', sa.Column('income_account', sa.String(255), nullable=True))
    op.add_column('items', sa.Column('reorder_level', sa.Numeric(18, 6), server_default='0', nullable=False))
    op.add_column('items', sa.Column('reorder_qty', sa.Numeric(18, 6), server_default='0', nullable=False))
    op.add_column('items', sa.Column('safety_stock', sa.Numeric(18, 6), server_default='0', nullable=False))
    op.add_column('items', sa.Column('has_batch_no', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('items', sa.Column('has_serial_no', sa.Boolean(), server_default='false', nullable=False))

    # Create stock_receipts table
    op.create_table(
        'stock_receipts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('purchase_invoice_id', sa.Integer(), sa.ForeignKey('purchase_invoices.id'), nullable=True, index=True),
        sa.Column('purchase_order', sa.String(255), nullable=True),
        sa.Column('journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id'), nullable=True),
        sa.Column('stock_entry_id', sa.Integer(), sa.ForeignKey('stock_entries.id'), nullable=True),
        sa.Column('posting_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('total_qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('total_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('draft', 'approved', 'posted', 'cancelled', name='stockreceiptstatus'), server_default='draft', nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create stock_receipt_items table
    op.create_table(
        'stock_receipt_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('receipt_id', sa.Integer(), sa.ForeignKey('stock_receipts.id'), nullable=False, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('rate', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('batch_no', sa.String(255), nullable=True),
        sa.Column('serial_no', sa.Text(), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
    )

    # Create stock_issues table
    op.create_table(
        'stock_issues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id'), nullable=True, index=True),
        sa.Column('sales_order', sa.String(255), nullable=True),
        sa.Column('journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id'), nullable=True),
        sa.Column('stock_entry_id', sa.Integer(), sa.ForeignKey('stock_entries.id'), nullable=True),
        sa.Column('posting_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('total_qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('total_cost', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('draft', 'approved', 'posted', 'cancelled', name='stockissuestatus'), server_default='draft', nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create stock_issue_items table
    op.create_table(
        'stock_issue_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('issue_id', sa.Integer(), sa.ForeignKey('stock_issues.id'), nullable=False, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('valuation_rate', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('cost_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('batch_no', sa.String(255), nullable=True),
        sa.Column('serial_no', sa.Text(), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
    )

    # Create transfer_requests table
    op.create_table(
        'transfer_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('from_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('to_warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('request_date', sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('required_date', sa.DateTime(), nullable=True),
        sa.Column('transfer_date', sa.DateTime(), nullable=True),
        sa.Column('total_qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('total_value', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending_approval', 'approved', 'rejected', 'in_transit', 'completed', 'cancelled', name='transferstatus'), server_default='draft', nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('outbound_stock_entry_id', sa.Integer(), sa.ForeignKey('stock_entries.id'), nullable=True),
        sa.Column('inbound_stock_entry_id', sa.Integer(), sa.ForeignKey('stock_entries.id'), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('requested_by_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create transfer_request_items table
    op.create_table(
        'transfer_request_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transfer_id', sa.Integer(), sa.ForeignKey('transfer_requests.id'), nullable=False, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('valuation_rate', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('batch_no', sa.String(255), nullable=True),
        sa.Column('serial_no', sa.Text(), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
    )

    # Create batches table
    op.create_table(
        'batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('batch_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('manufacturing_date', sa.DateTime(), nullable=True),
        sa.Column('expiry_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('batch_qty', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('reference_doctype', sa.String(100), nullable=True),
        sa.Column('reference_name', sa.String(255), nullable=True),
        sa.Column('disabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create serial_numbers table
    op.create_table(
        'serial_numbers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('serial_no', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('warehouse', sa.String(255), nullable=True, index=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('batch_no', sa.String(255), nullable=True, index=True),
        sa.Column('status', sa.Enum('active', 'delivered', 'returned', 'inactive', name='serialstatus'), server_default='active', nullable=False),
        sa.Column('customer', sa.String(255), nullable=True, index=True),
        sa.Column('delivery_document_type', sa.String(100), nullable=True),
        sa.Column('delivery_document_no', sa.String(255), nullable=True),
        sa.Column('delivery_date', sa.DateTime(), nullable=True),
        sa.Column('purchase_document_type', sa.String(100), nullable=True),
        sa.Column('purchase_document_no', sa.String(255), nullable=True),
        sa.Column('purchase_date', sa.DateTime(), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('warranty_expiry_date', sa.DateTime(), nullable=True),
        sa.Column('warranty_period', sa.Integer(), nullable=True),
        sa.Column('amc_expiry_date', sa.DateTime(), nullable=True),
        sa.Column('maintenance_status', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create journal_entry_items table if it doesn't exist (for GL posting)
    op.create_table(
        'journal_entry_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id'), nullable=False, index=True),
        sa.Column('account', sa.String(255), nullable=False, index=True),
        sa.Column('debit', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('credit', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('reference_type', sa.String(100), nullable=True),
        sa.Column('reference_name', sa.String(255), nullable=True),
        sa.Column('party_type', sa.String(100), nullable=True),
        sa.Column('party', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('journal_entry_items')
    op.drop_table('serial_numbers')
    op.drop_table('batches')
    op.drop_table('transfer_request_items')
    op.drop_table('transfer_requests')
    op.drop_table('stock_issue_items')
    op.drop_table('stock_issues')
    op.drop_table('stock_receipt_items')
    op.drop_table('stock_receipts')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS serialstatus')
    op.execute('DROP TYPE IF EXISTS transferstatus')
    op.execute('DROP TYPE IF EXISTS stockissuestatus')
    op.execute('DROP TYPE IF EXISTS stockreceiptstatus')

    # Remove columns from items table
    op.drop_column('items', 'has_serial_no')
    op.drop_column('items', 'has_batch_no')
    op.drop_column('items', 'safety_stock')
    op.drop_column('items', 'reorder_qty')
    op.drop_column('items', 'reorder_level')
    op.drop_column('items', 'income_account')
    op.drop_column('items', 'expense_account')
    op.drop_column('items', 'stock_account')

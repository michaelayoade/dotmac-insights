"""Add order line items tables for sales orders, quotations, and purchase orders.

Revision ID: add_order_line_items
Revises:
Create Date: 2024-12-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_order_line_items'
down_revision = None  # Will be set by Alembic
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sales_order_items table
    op.create_table(
        'sales_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sales_order_id', sa.Integer(), nullable=False),
        # DocumentLineMixin fields
        sa.Column('item_code', sa.String(100), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 6), server_default='1'),
        sa.Column('rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_percentage', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('tax_code_id', sa.Integer(), nullable=True),
        sa.Column('tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('is_tax_inclusive', sa.Boolean(), server_default='false'),
        sa.Column('withholding_tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('withholding_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('base_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('account', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0'),
        # SalesOrderItem specific fields
        sa.Column('stock_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('stock_uom', sa.String(50), nullable=True),
        sa.Column('conversion_factor', sa.Numeric(18, 6), server_default='1'),
        sa.Column('warehouse', sa.String(255), nullable=True),
        sa.Column('delivered_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('delivery_date', sa.Date(), nullable=True),
        sa.Column('price_list_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('billed_amt', sa.Numeric(18, 4), server_default='0'),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tax_code_id'], ['tax_codes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sales_order_items_id', 'sales_order_items', ['id'])
    op.create_index('ix_sales_order_items_sales_order_id', 'sales_order_items', ['sales_order_id'])

    # Create quotation_items table
    op.create_table(
        'quotation_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quotation_id', sa.Integer(), nullable=False),
        # DocumentLineMixin fields
        sa.Column('item_code', sa.String(100), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 6), server_default='1'),
        sa.Column('rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_percentage', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('tax_code_id', sa.Integer(), nullable=True),
        sa.Column('tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('is_tax_inclusive', sa.Boolean(), server_default='false'),
        sa.Column('withholding_tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('withholding_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('base_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('account', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0'),
        # QuotationItem specific fields
        sa.Column('stock_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('stock_uom', sa.String(50), nullable=True),
        sa.Column('conversion_factor', sa.Numeric(18, 6), server_default='1'),
        sa.Column('warehouse', sa.String(255), nullable=True),
        sa.Column('price_list_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('margin_type', sa.String(50), nullable=True),
        sa.Column('margin_rate_or_amount', sa.Numeric(18, 6), server_default='0'),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['quotation_id'], ['quotations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tax_code_id'], ['tax_codes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quotation_items_id', 'quotation_items', ['id'])
    op.create_index('ix_quotation_items_quotation_id', 'quotation_items', ['quotation_id'])

    # Create purchase_orders table
    op.create_table(
        'purchase_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('erpnext_id', sa.String(255), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('supplier_name', sa.String(255), nullable=True),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('order_type', sa.String(100), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('currency', sa.String(10), server_default='NGN'),
        sa.Column('transaction_date', sa.Date(), nullable=True),
        sa.Column('schedule_date', sa.Date(), nullable=True),
        sa.Column('total_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('total', sa.Numeric(18, 4), server_default='0'),
        sa.Column('net_total', sa.Numeric(18, 4), server_default='0'),
        sa.Column('grand_total', sa.Numeric(18, 4), server_default='0'),
        sa.Column('rounded_total', sa.Numeric(18, 4), server_default='0'),
        sa.Column('total_taxes_and_charges', sa.Numeric(18, 4), server_default='0'),
        sa.Column('per_received', sa.Numeric(10, 2), server_default='0'),
        sa.Column('per_billed', sa.Numeric(10, 2), server_default='0'),
        sa.Column('billing_status', sa.String(50), nullable=True),
        sa.Column('receipt_status', sa.String(50), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'to_receive_and_bill', 'to_bill', 'to_receive',
            'completed', 'cancelled', 'closed', 'on_hold',
            name='purchaseorderstatus'
        ), server_default='draft'),
        sa.Column('docstatus', sa.Integer(), server_default='0'),
        sa.Column('buying_price_list', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('project', sa.String(255), nullable=True),
        sa.Column('payment_terms_template', sa.String(255), nullable=True),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_purchase_orders_id', 'purchase_orders', ['id'])
    op.create_index('ix_purchase_orders_erpnext_id', 'purchase_orders', ['erpnext_id'], unique=True)
    op.create_index('ix_purchase_orders_supplier', 'purchase_orders', ['supplier'])
    op.create_index('ix_purchase_orders_transaction_date', 'purchase_orders', ['transaction_date'])
    op.create_index('ix_purchase_orders_status', 'purchase_orders', ['status'])

    # Create purchase_order_items table
    op.create_table(
        'purchase_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        # DocumentLineMixin fields
        sa.Column('item_code', sa.String(100), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 6), server_default='1'),
        sa.Column('rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('uom', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_percentage', sa.Numeric(18, 4), server_default='0'),
        sa.Column('discount_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('tax_code_id', sa.Integer(), nullable=True),
        sa.Column('tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('is_tax_inclusive', sa.Boolean(), server_default='false'),
        sa.Column('withholding_tax_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('withholding_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('base_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_net_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('base_tax_amount', sa.Numeric(18, 4), server_default='0'),
        sa.Column('account', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0'),
        # PurchaseOrderItem specific fields
        sa.Column('stock_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('stock_uom', sa.String(50), nullable=True),
        sa.Column('conversion_factor', sa.Numeric(18, 6), server_default='1'),
        sa.Column('warehouse', sa.String(255), nullable=True),
        sa.Column('received_qty', sa.Numeric(18, 6), server_default='0'),
        sa.Column('expected_delivery_date', sa.Date(), nullable=True),
        sa.Column('price_list_rate', sa.Numeric(18, 6), server_default='0'),
        sa.Column('billed_amt', sa.Numeric(18, 4), server_default='0'),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tax_code_id'], ['tax_codes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_purchase_order_items_id', 'purchase_order_items', ['id'])
    op.create_index('ix_purchase_order_items_purchase_order_id', 'purchase_order_items', ['purchase_order_id'])


def downgrade() -> None:
    op.drop_table('purchase_order_items')
    op.drop_table('purchase_orders')
    op.drop_table('quotation_items')
    op.drop_table('sales_order_items')

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS purchaseorderstatus")

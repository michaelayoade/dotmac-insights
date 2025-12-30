"""add_tax_models

Revision ID: e8f9a1b2c3d4
Revises: ab12cd34ef56
Create Date: 2025-12-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a1b2c3d4'
# Place this after the latest head to avoid branching.
down_revision: Union[str, None] = '7c1e2d2f9b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= TAX CATEGORIES =============
    op.create_table(
        'tax_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('category_name', sa.String(255), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('is_inter_state', sa.Boolean(), default=False),
        sa.Column('is_reverse_charge', sa.Boolean(), default=False),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ============= SALES TAX TEMPLATES =============
    op.create_table(
        'sales_tax_templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('template_name', sa.String(255), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('tax_category', sa.String(255), nullable=True, index=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_sales_tax_templates_tax_category', 'sales_tax_templates', ['tax_category'])

    # Sales Tax Template Details (child table)
    op.create_table(
        'sales_tax_template_details',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('sales_tax_templates.id'), nullable=False, index=True),
        sa.Column('charge_type', sa.String(100), nullable=True),
        sa.Column('account_head', sa.String(255), nullable=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rate', sa.Numeric(18, 6), default=0),
        sa.Column('tax_amount', sa.Numeric(18, 6), default=0),
        sa.Column('row_id', sa.String(50), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('included_in_print_rate', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_sales_tax_template_details_template_id', 'sales_tax_template_details', ['template_id'])
    op.create_index('ix_sales_tax_template_details_account_head', 'sales_tax_template_details', ['account_head'])

    # ============= PURCHASE TAX TEMPLATES =============
    op.create_table(
        'purchase_tax_templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('template_name', sa.String(255), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('tax_category', sa.String(255), nullable=True, index=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_purchase_tax_templates_tax_category', 'purchase_tax_templates', ['tax_category'])

    # Purchase Tax Template Details (child table)
    op.create_table(
        'purchase_tax_template_details',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('purchase_tax_templates.id'), nullable=False, index=True),
        sa.Column('charge_type', sa.String(100), nullable=True),
        sa.Column('account_head', sa.String(255), nullable=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rate', sa.Numeric(18, 6), default=0),
        sa.Column('tax_amount', sa.Numeric(18, 6), default=0),
        sa.Column('row_id', sa.String(50), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        sa.Column('add_deduct_tax', sa.String(20), nullable=True),
        sa.Column('included_in_print_rate', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_purchase_tax_template_details_template_id', 'purchase_tax_template_details', ['template_id'])
    op.create_index('ix_purchase_tax_template_details_account_head', 'purchase_tax_template_details', ['account_head'])

    # ============= ITEM TAX TEMPLATES =============
    op.create_table(
        'item_tax_templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('template_name', sa.String(255), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Item Tax Template Details (child table)
    op.create_table(
        'item_tax_template_details',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('item_tax_templates.id'), nullable=False, index=True),
        sa.Column('tax_type', sa.String(255), nullable=True, index=True),
        sa.Column('tax_rate', sa.Numeric(18, 6), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_item_tax_template_details_template_id', 'item_tax_template_details', ['template_id'])
    op.create_index('ix_item_tax_template_details_tax_type', 'item_tax_template_details', ['tax_type'])

    # ============= TAX WITHHOLDING CATEGORIES =============
    op.create_table(
        'tax_withholding_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('category_name', sa.String(255), nullable=False, unique=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('round_off_tax_amount', sa.Boolean(), default=False),
        sa.Column('consider_party_ledger_amount', sa.Boolean(), default=False),
        sa.Column('account', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ============= TAX RULES =============
    op.create_table(
        'tax_rules',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('rule_name', sa.String(255), nullable=True),
        sa.Column('tax_type', sa.String(50), nullable=True),
        sa.Column('sales_tax_template', sa.String(255), nullable=True),
        sa.Column('purchase_tax_template', sa.String(255), nullable=True),
        sa.Column('tax_category', sa.String(255), nullable=True, index=True),
        sa.Column('customer', sa.String(255), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('customer_group', sa.String(255), nullable=True),
        sa.Column('supplier_group', sa.String(255), nullable=True),
        sa.Column('billing_city', sa.String(100), nullable=True),
        sa.Column('billing_state', sa.String(100), nullable=True),
        sa.Column('billing_country', sa.String(100), nullable=True),
        sa.Column('billing_zipcode', sa.String(50), nullable=True),
        sa.Column('shipping_city', sa.String(100), nullable=True),
        sa.Column('shipping_state', sa.String(100), nullable=True),
        sa.Column('shipping_country', sa.String(100), nullable=True),
        sa.Column('shipping_zipcode', sa.String(50), nullable=True),
        sa.Column('item', sa.String(255), nullable=True),
        sa.Column('item_group', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('priority', sa.Integer(), default=1),
        sa.Column('use_for_shopping_cart', sa.Boolean(), default=False),
        sa.Column('from_date', sa.DateTime(), nullable=True),
        sa.Column('to_date', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_tax_rules_tax_category', 'tax_rules', ['tax_category'])


def downgrade() -> None:
    op.drop_index('ix_tax_rules_tax_category', table_name='tax_rules')
    op.drop_table('tax_rules')
    op.drop_table('tax_withholding_categories')
    op.drop_index('ix_item_tax_template_details_tax_type', table_name='item_tax_template_details')
    op.drop_index('ix_item_tax_template_details_template_id', table_name='item_tax_template_details')
    op.drop_table('item_tax_template_details')
    op.drop_table('item_tax_templates')
    op.drop_index('ix_purchase_tax_template_details_account_head', table_name='purchase_tax_template_details')
    op.drop_index('ix_purchase_tax_template_details_template_id', table_name='purchase_tax_template_details')
    op.drop_table('purchase_tax_template_details')
    op.drop_index('ix_purchase_tax_templates_tax_category', table_name='purchase_tax_templates')
    op.drop_table('purchase_tax_templates')
    op.drop_index('ix_sales_tax_template_details_account_head', table_name='sales_tax_template_details')
    op.drop_index('ix_sales_tax_template_details_template_id', table_name='sales_tax_template_details')
    op.drop_table('sales_tax_template_details')
    op.drop_index('ix_sales_tax_templates_tax_category', table_name='sales_tax_templates')
    op.drop_table('sales_tax_templates')
    op.drop_table('tax_categories')

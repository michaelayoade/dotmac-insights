"""add_erpnext_sales_and_hr_models

Revision ID: 0b207e32b691
Revises: 3df42795f1ea
Create Date: 2025-12-09 10:02:06.581137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b207e32b691'
down_revision: Union[str, None] = '3df42795f1ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= SALES MODELS =============

    # Customer Groups
    op.create_table(
        'customer_groups',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('customer_group_name', sa.String(255), nullable=False, unique=True),
        sa.Column('parent_customer_group', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('default_price_list', sa.String(255), nullable=True),
        sa.Column('default_payment_terms_template', sa.String(255), nullable=True),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Territories
    op.create_table(
        'territories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('territory_name', sa.String(255), nullable=False, unique=True),
        sa.Column('parent_territory', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('territory_manager', sa.String(255), nullable=True),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Sales Persons
    op.create_table(
        'sales_persons',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('sales_person_name', sa.String(255), nullable=False, index=True),
        sa.Column('parent_sales_person', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('employee', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('commission_rate', sa.Numeric(), default=0),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Item Groups
    op.create_table(
        'item_groups',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('item_group_name', sa.String(255), nullable=False, unique=True),
        sa.Column('parent_item_group', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Items (Products/Services)
    op.create_table(
        'items',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('item_code', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=False),
        sa.Column('item_group', sa.String(255), nullable=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_stock_item', sa.Boolean(), default=True),
        sa.Column('is_fixed_asset', sa.Boolean(), default=False),
        sa.Column('is_sales_item', sa.Boolean(), default=True),
        sa.Column('is_purchase_item', sa.Boolean(), default=True),
        sa.Column('stock_uom', sa.String(50), nullable=True),
        sa.Column('default_warehouse', sa.String(255), nullable=True),
        sa.Column('standard_rate', sa.Numeric(), default=0),
        sa.Column('valuation_rate', sa.Numeric(), default=0),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('has_variants', sa.Boolean(), default=False),
        sa.Column('variant_of', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ERPNext Leads
    op.create_table(
        'erpnext_leads',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('lead_name', sa.String(255), nullable=False, index=True),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('email_id', sa.String(255), nullable=True, index=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('mobile_no', sa.String(50), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('lead_owner', sa.String(255), nullable=True),
        sa.Column('territory', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('market_segment', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('lead', 'open', 'replied', 'opportunity', 'quotation', 'lost_quotation', 'interested', 'converted', 'do_not_contact', name='erpnextleadstatus'), default='lead'),
        sa.Column('qualification_status', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('converted', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Quotations
    op.create_table(
        'quotations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('quotation_to', sa.String(50), nullable=True),
        sa.Column('party_name', sa.String(255), nullable=True, index=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('order_type', sa.String(100), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('currency', sa.String(10), default='NGN'),
        sa.Column('transaction_date', sa.Date(), nullable=True, index=True),
        sa.Column('valid_till', sa.Date(), nullable=True),
        sa.Column('total_qty', sa.Numeric(), default=0),
        sa.Column('total', sa.Numeric(), default=0),
        sa.Column('net_total', sa.Numeric(), default=0),
        sa.Column('grand_total', sa.Numeric(), default=0),
        sa.Column('rounded_total', sa.Numeric(), default=0),
        sa.Column('total_taxes_and_charges', sa.Numeric(), default=0),
        sa.Column('status', sa.Enum('draft', 'open', 'replied', 'ordered', 'lost', 'cancelled', 'expired', name='quotationstatus'), default='draft'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('sales_partner', sa.String(255), nullable=True),
        sa.Column('territory', sa.String(255), nullable=True),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('campaign', sa.String(255), nullable=True),
        sa.Column('order_lost_reason', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Sales Orders
    op.create_table(
        'sales_orders',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('customer', sa.String(255), nullable=True, index=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('order_type', sa.String(100), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('currency', sa.String(10), default='NGN'),
        sa.Column('transaction_date', sa.Date(), nullable=True, index=True),
        sa.Column('delivery_date', sa.Date(), nullable=True),
        sa.Column('total_qty', sa.Numeric(), default=0),
        sa.Column('total', sa.Numeric(), default=0),
        sa.Column('net_total', sa.Numeric(), default=0),
        sa.Column('grand_total', sa.Numeric(), default=0),
        sa.Column('rounded_total', sa.Numeric(), default=0),
        sa.Column('total_taxes_and_charges', sa.Numeric(), default=0),
        sa.Column('per_delivered', sa.Numeric(), default=0),
        sa.Column('per_billed', sa.Numeric(), default=0),
        sa.Column('billing_status', sa.String(50), nullable=True),
        sa.Column('delivery_status', sa.String(50), nullable=True),
        sa.Column('status', sa.Enum('draft', 'to_deliver_and_bill', 'to_bill', 'to_deliver', 'completed', 'cancelled', 'closed', 'on_hold', name='salesorderstatus'), default='draft'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('sales_partner', sa.String(255), nullable=True),
        sa.Column('territory', sa.String(255), nullable=True),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('campaign', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ============= HR MODELS =============

    # Departments
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('department_name', sa.String(255), nullable=False, index=True),
        sa.Column('parent_department', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('is_group', sa.Boolean(), default=False),
        sa.Column('lft', sa.Integer(), nullable=True),
        sa.Column('rgt', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Designations
    op.create_table(
        'designations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('designation_name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ERPNext Users
    op.create_table(
        'erpnext_users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('user_type', sa.String(100), nullable=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True, index=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # HD Teams (Helpdesk Teams)
    op.create_table(
        'hd_teams',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('team_name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assignment_rule', sa.String(100), nullable=True),
        sa.Column('ignore_restrictions', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # HD Team Members
    op.create_table(
        'hd_team_members',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('hd_teams.id'), nullable=False, index=True),
        sa.Column('user', sa.String(255), nullable=False, index=True),
        sa.Column('user_name', sa.String(255), nullable=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop HR tables
    op.drop_table('hd_team_members')
    op.drop_table('hd_teams')
    op.drop_table('erpnext_users')
    op.drop_table('designations')
    op.drop_table('departments')

    # Drop Sales tables
    op.drop_table('sales_orders')
    op.drop_table('quotations')
    op.drop_table('erpnext_leads')
    op.drop_table('items')
    op.drop_table('item_groups')
    op.drop_table('sales_persons')
    op.drop_table('territories')
    op.drop_table('customer_groups')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS salesorderstatus")
    op.execute("DROP TYPE IF EXISTS quotationstatus")
    op.execute("DROP TYPE IF EXISTS erpnextleadstatus")

"""add_asset_management_models

Revision ID: g2h3i4j5k6l7
Revises: b1c2d3e4f5g6
Create Date: 2025-12-12 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, None] = 'b1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= ASSET CATEGORIES =============
    op.create_table(
        'asset_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('asset_category_name', sa.String(255), nullable=False),
        sa.Column('enable_cwip_accounting', sa.Boolean(), default=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_asset_categories_erpnext_id', 'asset_categories', ['erpnext_id'], unique=True)
    op.create_index('ix_asset_categories_asset_category_name', 'asset_categories', ['asset_category_name'])

    # Asset Category Finance Books (child table)
    op.create_table(
        'asset_category_finance_books',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_category_id', sa.Integer(), sa.ForeignKey('asset_categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('finance_book', sa.String(255), nullable=True),
        sa.Column('depreciation_method', sa.String(100), nullable=True),
        sa.Column('total_number_of_depreciations', sa.Integer(), default=0),
        sa.Column('frequency_of_depreciation', sa.Integer(), default=12),
        sa.Column('fixed_asset_account', sa.String(255), nullable=True),
        sa.Column('accumulated_depreciation_account', sa.String(255), nullable=True),
        sa.Column('depreciation_expense_account', sa.String(255), nullable=True),
        sa.Column('capital_work_in_progress_account', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_asset_category_finance_books_asset_category_id', 'asset_category_finance_books', ['asset_category_id'])

    # ============= ASSETS =============
    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        # Basic Info
        sa.Column('asset_name', sa.String(255), nullable=False),
        sa.Column('asset_category', sa.String(255), nullable=True),
        sa.Column('item_code', sa.String(255), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        # Company and Location
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('custodian', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        # Purchase Info
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('available_for_use_date', sa.Date(), nullable=True),
        sa.Column('gross_purchase_amount', sa.Numeric(18, 6), default=0),
        sa.Column('purchase_receipt', sa.String(255), nullable=True),
        sa.Column('purchase_invoice', sa.String(255), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        # Asset Value
        sa.Column('asset_quantity', sa.Integer(), default=1),
        sa.Column('opening_accumulated_depreciation', sa.Numeric(18, 6), default=0),
        sa.Column('asset_value', sa.Numeric(18, 6), default=0),
        # Depreciation Settings
        sa.Column('calculate_depreciation', sa.Boolean(), default=True),
        sa.Column('is_existing_asset', sa.Boolean(), default=False),
        sa.Column('is_composite_asset', sa.Boolean(), default=False),
        # Status
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        # Disposal Info
        sa.Column('disposal_date', sa.Date(), nullable=True),
        sa.Column('journal_entry_for_scrap', sa.String(255), nullable=True),
        # Insurance
        sa.Column('insured_value', sa.Numeric(18, 6), default=0),
        sa.Column('insurance_start_date', sa.Date(), nullable=True),
        sa.Column('insurance_end_date', sa.Date(), nullable=True),
        sa.Column('comprehensive_insurance', sa.String(255), nullable=True),
        # Warranty
        sa.Column('warranty_expiry_date', sa.Date(), nullable=True),
        # Maintenance
        sa.Column('maintenance_required', sa.Boolean(), default=False),
        sa.Column('next_depreciation_date', sa.Date(), nullable=True),
        # Description
        sa.Column('asset_owner', sa.String(100), nullable=True),
        sa.Column('asset_owner_company', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        # Serial/Identification
        sa.Column('serial_no', sa.String(255), nullable=True),
        # Sync metadata
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_assets_erpnext_id', 'assets', ['erpnext_id'], unique=True)
    op.create_index('ix_assets_asset_name', 'assets', ['asset_name'])
    op.create_index('ix_assets_asset_category', 'assets', ['asset_category'])
    op.create_index('ix_assets_item_code', 'assets', ['item_code'])
    op.create_index('ix_assets_location', 'assets', ['location'])
    op.create_index('ix_assets_purchase_date', 'assets', ['purchase_date'])
    op.create_index('ix_assets_status', 'assets', ['status'])

    # Asset Finance Books (child table)
    op.create_table(
        'asset_finance_books',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('finance_book', sa.String(255), nullable=True),
        sa.Column('depreciation_method', sa.String(100), nullable=True),
        sa.Column('total_number_of_depreciations', sa.Integer(), default=0),
        sa.Column('frequency_of_depreciation', sa.Integer(), default=12),
        sa.Column('depreciation_start_date', sa.Date(), nullable=True),
        sa.Column('expected_value_after_useful_life', sa.Numeric(18, 6), default=0),
        sa.Column('value_after_depreciation', sa.Numeric(18, 6), default=0),
        sa.Column('daily_depreciation_amount', sa.Numeric(18, 6), default=0),
        sa.Column('rate_of_depreciation', sa.Numeric(10, 6), default=0),
        sa.Column('idx', sa.Integer(), default=0),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
    )
    op.create_index('ix_asset_finance_books_asset_id', 'asset_finance_books', ['asset_id'])
    op.create_index('ix_asset_finance_books_finance_book', 'asset_finance_books', ['finance_book'])

    # Asset Depreciation Schedules (child table)
    op.create_table(
        'asset_depreciation_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('finance_book', sa.String(255), nullable=True),
        sa.Column('schedule_date', sa.Date(), nullable=True),
        sa.Column('depreciation_amount', sa.Numeric(18, 6), default=0),
        sa.Column('accumulated_depreciation_amount', sa.Numeric(18, 6), default=0),
        sa.Column('journal_entry', sa.String(255), nullable=True),
        sa.Column('depreciation_booked', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
    )
    op.create_index('ix_asset_depreciation_schedules_asset_id', 'asset_depreciation_schedules', ['asset_id'])
    op.create_index('ix_asset_depreciation_schedules_finance_book', 'asset_depreciation_schedules', ['finance_book'])
    op.create_index('ix_asset_depreciation_schedules_schedule_date', 'asset_depreciation_schedules', ['schedule_date'])
    op.create_index('ix_asset_depreciation_schedules_journal_entry', 'asset_depreciation_schedules', ['journal_entry'])
    # Composite index for common queries
    op.create_index('ix_asset_depreciation_schedules_asset_finance', 'asset_depreciation_schedules', ['asset_id', 'finance_book'])


def downgrade() -> None:
    # Drop depreciation schedules
    op.drop_index('ix_asset_depreciation_schedules_asset_finance', table_name='asset_depreciation_schedules')
    op.drop_index('ix_asset_depreciation_schedules_journal_entry', table_name='asset_depreciation_schedules')
    op.drop_index('ix_asset_depreciation_schedules_schedule_date', table_name='asset_depreciation_schedules')
    op.drop_index('ix_asset_depreciation_schedules_finance_book', table_name='asset_depreciation_schedules')
    op.drop_index('ix_asset_depreciation_schedules_asset_id', table_name='asset_depreciation_schedules')
    op.drop_table('asset_depreciation_schedules')

    # Drop asset finance books
    op.drop_index('ix_asset_finance_books_finance_book', table_name='asset_finance_books')
    op.drop_index('ix_asset_finance_books_asset_id', table_name='asset_finance_books')
    op.drop_table('asset_finance_books')

    # Drop assets
    op.drop_index('ix_assets_status', table_name='assets')
    op.drop_index('ix_assets_purchase_date', table_name='assets')
    op.drop_index('ix_assets_location', table_name='assets')
    op.drop_index('ix_assets_item_code', table_name='assets')
    op.drop_index('ix_assets_asset_category', table_name='assets')
    op.drop_index('ix_assets_asset_name', table_name='assets')
    op.drop_index('ix_assets_erpnext_id', table_name='assets')
    op.drop_table('assets')

    # Drop asset category finance books
    op.drop_index('ix_asset_category_finance_books_asset_category_id', table_name='asset_category_finance_books')
    op.drop_table('asset_category_finance_books')

    # Drop asset categories
    op.drop_index('ix_asset_categories_asset_category_name', table_name='asset_categories')
    op.drop_index('ix_asset_categories_erpnext_id', table_name='asset_categories')
    op.drop_table('asset_categories')

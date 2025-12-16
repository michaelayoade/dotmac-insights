"""Add asset management tables

Revision ID: asset_mgmt_001
Revises:
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'asset_mgmt_001'
down_revision = None  # Will be updated based on actual head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create asset_categories table
    op.create_table(
        'asset_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('asset_category_name', sa.String(255), nullable=False, index=True),
        sa.Column('enable_cwip_accounting', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create asset_category_finance_books table
    op.create_table(
        'asset_category_finance_books',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_category_id', sa.Integer(), sa.ForeignKey('asset_categories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('finance_book', sa.String(255), nullable=True),
        sa.Column('depreciation_method', sa.String(100), nullable=True),
        sa.Column('total_number_of_depreciations', sa.Integer(), server_default='0', nullable=False),
        sa.Column('frequency_of_depreciation', sa.Integer(), server_default='12', nullable=False),
        sa.Column('fixed_asset_account', sa.String(255), nullable=True),
        sa.Column('accumulated_depreciation_account', sa.String(255), nullable=True),
        sa.Column('depreciation_expense_account', sa.String(255), nullable=True),
        sa.Column('capital_work_in_progress_account', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
    )

    # Create AssetStatus enum
    asset_status = postgresql.ENUM(
        'draft', 'submitted', 'partially_depreciated', 'fully_depreciated',
        'sold', 'scrapped', 'in_maintenance', 'out_of_order',
        name='assetstatus',
        create_type=True
    )
    asset_status.create(op.get_bind(), checkfirst=True)

    # Create assets table
    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        # Basic Info
        sa.Column('asset_name', sa.String(255), nullable=False, index=True),
        sa.Column('asset_category', sa.String(255), nullable=True, index=True),
        sa.Column('item_code', sa.String(255), nullable=True, index=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        # Company and Location
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True, index=True),
        sa.Column('custodian', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('cost_center', sa.String(255), nullable=True),
        # Purchase Info
        sa.Column('purchase_date', sa.Date(), nullable=True, index=True),
        sa.Column('available_for_use_date', sa.Date(), nullable=True),
        sa.Column('gross_purchase_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('purchase_receipt', sa.String(255), nullable=True),
        sa.Column('purchase_invoice', sa.String(255), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        # Asset Value
        sa.Column('asset_quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('opening_accumulated_depreciation', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('asset_value', sa.Numeric(18, 6), server_default='0', nullable=False),
        # Depreciation Settings
        sa.Column('calculate_depreciation', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_existing_asset', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_composite_asset', sa.Boolean(), server_default='false', nullable=False),
        # Status
        sa.Column('status', sa.Enum('draft', 'submitted', 'partially_depreciated', 'fully_depreciated',
                                     'sold', 'scrapped', 'in_maintenance', 'out_of_order',
                                     name='assetstatus', create_type=False),
                  server_default='draft', nullable=False, index=True),
        sa.Column('docstatus', sa.Integer(), server_default='0', nullable=False),
        # Disposal Info
        sa.Column('disposal_date', sa.Date(), nullable=True),
        sa.Column('journal_entry_for_scrap', sa.String(255), nullable=True),
        # Insurance
        sa.Column('insured_value', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('insurance_start_date', sa.Date(), nullable=True),
        sa.Column('insurance_end_date', sa.Date(), nullable=True),
        sa.Column('comprehensive_insurance', sa.String(255), nullable=True),
        # Warranty
        sa.Column('warranty_expiry_date', sa.Date(), nullable=True),
        # Maintenance
        sa.Column('maintenance_required', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('next_depreciation_date', sa.Date(), nullable=True),
        # Description
        sa.Column('asset_owner', sa.String(100), nullable=True),
        sa.Column('asset_owner_company', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        # Serial/Identification
        sa.Column('serial_no', sa.String(255), nullable=True),
        # Sync metadata
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create asset_finance_books table
    op.create_table(
        'asset_finance_books',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('finance_book', sa.String(255), nullable=True, index=True),
        sa.Column('depreciation_method', sa.String(100), nullable=True),
        sa.Column('total_number_of_depreciations', sa.Integer(), server_default='0', nullable=False),
        sa.Column('frequency_of_depreciation', sa.Integer(), server_default='12', nullable=False),
        sa.Column('depreciation_start_date', sa.Date(), nullable=True),
        sa.Column('expected_value_after_useful_life', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('value_after_depreciation', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('daily_depreciation_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('rate_of_depreciation', sa.Numeric(10, 6), server_default='0', nullable=False),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
    )

    # Create asset_depreciation_schedules table
    op.create_table(
        'asset_depreciation_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('finance_book', sa.String(255), nullable=True, index=True),
        sa.Column('schedule_date', sa.Date(), nullable=True, index=True),
        sa.Column('depreciation_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('accumulated_depreciation_amount', sa.Numeric(18, 6), server_default='0', nullable=False),
        sa.Column('journal_entry', sa.String(255), nullable=True, index=True),
        sa.Column('depreciation_booked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('idx', sa.Integer(), server_default='0', nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('asset_depreciation_schedules')
    op.drop_table('asset_finance_books')
    op.drop_table('assets')
    op.drop_table('asset_category_finance_books')
    op.drop_table('asset_categories')

    # Drop enum
    op.execute('DROP TYPE IF EXISTS assetstatus')

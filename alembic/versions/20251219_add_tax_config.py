"""Add generic tax configuration tables

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r4
Create Date: 2025-12-19 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'n9o0p1q2r3s4'
down_revision = 'm8n9o0p1q2r4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create TaxCategoryType enum
    taxcategorytype_enum = postgresql.ENUM(
        'sales_tax', 'withholding', 'income_tax', 'excise', 'customs', 'stamp_duty', 'other',
        name='taxcategorytype',
        create_type=False
    )
    taxcategorytype_enum.create(op.get_bind(), checkfirst=True)

    # Create TaxTransactionType enum
    taxtransactiontype_enum = postgresql.ENUM(
        'output', 'input', 'withholding', 'remittance',
        name='taxtransactiontype',
        create_type=False
    )
    taxtransactiontype_enum.create(op.get_bind(), checkfirst=True)

    # Create TaxFilingFrequency enum
    taxfilingfrequency_enum = postgresql.ENUM(
        'monthly', 'quarterly', 'semi_annual', 'annual',
        name='taxfilingfrequency',
        create_type=False
    )
    taxfilingfrequency_enum.create(op.get_bind(), checkfirst=True)

    # Create TaxTransactionStatus enum
    taxtransactionstatus_enum = postgresql.ENUM(
        'draft', 'confirmed', 'filed', 'paid', 'void',
        name='taxtransactionstatus',
        create_type=False
    )
    taxtransactionstatus_enum.create(op.get_bind(), checkfirst=True)

    # Create tax_regions table
    op.create_table(
        'tax_regions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), nullable=False, unique=True, index=True,
                  comment='ISO 3166-1 alpha-2 country code'),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('tax_authority_name', sa.String(255), nullable=True),
        sa.Column('tax_authority_code', sa.String(50), nullable=True),
        sa.Column('tax_id_label', sa.String(50), nullable=False, server_default='Tax ID'),
        sa.Column('tax_id_format', sa.String(100), nullable=True),
        sa.Column('default_sales_tax_rate', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('default_withholding_rate', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('default_filing_frequency', postgresql.ENUM('monthly', 'quarterly', 'semi_annual', 'annual',
                  name='taxfilingfrequency', create_type=False), nullable=False, server_default='monthly'),
        sa.Column('filing_deadline_day', sa.Integer(), nullable=False, server_default='21'),
        sa.Column('fiscal_year_start_month', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('requires_compliance_addon', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('compliance_addon_code', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # Create taxconf_categories table (renamed to avoid collision with existing tax_categories)
    op.create_table(
        'taxconf_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('region_id', sa.Integer(), sa.ForeignKey('tax_regions.id'), nullable=False, index=True),
        sa.Column('code', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category_type', postgresql.ENUM('sales_tax', 'withholding', 'income_tax', 'excise',
                  'customs', 'stamp_duty', 'other', name='taxcategorytype', create_type=False), nullable=False, index=True),
        sa.Column('default_rate', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('is_recoverable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_inclusive', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('applies_to_purchases', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('applies_to_sales', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('filing_frequency', postgresql.ENUM('monthly', 'quarterly', 'semi_annual', 'annual',
                  name='taxfilingfrequency', create_type=False), nullable=True),
        sa.Column('filing_deadline_day', sa.Integer(), nullable=True),
        sa.Column('output_account', sa.String(255), nullable=True),
        sa.Column('input_account', sa.String(255), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('region_id', 'code', name='uq_taxconf_categories_region_code'),
    )
    op.create_index('ix_taxconf_categories_region', 'taxconf_categories', ['region_id'])

    # Create taxconf_rates table
    op.create_table(
        'taxconf_rates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('taxconf_categories.id'), nullable=False, index=True),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('rate', sa.Numeric(10, 6), nullable=False),
        sa.Column('conditions', postgresql.JSONB(), nullable=True,
                  comment='JSON conditions for rate applicability'),
        sa.Column('min_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('max_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index('ix_taxconf_rates_category_effective', 'taxconf_rates',
                    ['category_id', 'effective_from', 'effective_to'])

    # Create taxconf_transactions table
    op.create_table(
        'taxconf_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('region_id', sa.Integer(), sa.ForeignKey('tax_regions.id'), nullable=False, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('taxconf_categories.id'), nullable=False, index=True),
        sa.Column('reference_number', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('transaction_type', postgresql.ENUM('output', 'input', 'withholding', 'remittance',
                  name='taxtransactiontype', create_type=False), nullable=False, index=True),
        sa.Column('transaction_date', sa.Date(), nullable=False, index=True),
        sa.Column('company', sa.String(255), nullable=False, index=True),
        sa.Column('party_type', sa.String(50), nullable=False),
        sa.Column('party_id', sa.Integer(), nullable=True),
        sa.Column('party_name', sa.String(255), nullable=False),
        sa.Column('party_tax_id', sa.String(50), nullable=True),
        sa.Column('taxable_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('tax_rate', sa.Numeric(10, 6), nullable=False),
        sa.Column('tax_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('exchange_rate', sa.Numeric(12, 6), nullable=False, server_default='1'),
        sa.Column('base_tax_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('filing_period', sa.String(10), nullable=False, index=True),
        sa.Column('status', postgresql.ENUM('draft', 'confirmed', 'filed', 'paid', 'void',
                  name='taxtransactionstatus', create_type=False), nullable=False, server_default='draft', index=True),
        sa.Column('is_exempt', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_zero_rated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('exemption_reason', sa.String(255), nullable=True),
        sa.Column('source_doctype', sa.String(50), nullable=False),
        sa.Column('source_docname', sa.String(255), nullable=False),
        sa.Column('filed_at', sa.DateTime(), nullable=True),
        sa.Column('filed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('filing_reference', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_taxconf_transactions_period', 'taxconf_transactions', ['region_id', 'filing_period'])
    op.create_index('ix_taxconf_transactions_company_period', 'taxconf_transactions', ['company', 'filing_period'])
    op.create_index('ix_taxconf_transactions_source', 'taxconf_transactions', ['source_doctype', 'source_docname'])

    # Create company_tax_settings table
    op.create_table(
        'company_tax_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('region_id', sa.Integer(), sa.ForeignKey('tax_regions.id'), nullable=False, index=True),
        sa.Column('company', sa.String(255), nullable=False, index=True),
        sa.Column('tax_id', sa.String(50), nullable=True),
        sa.Column('vat_registration_number', sa.String(50), nullable=True),
        sa.Column('registration_number', sa.String(50), nullable=True),
        sa.Column('filing_frequency', postgresql.ENUM('monthly', 'quarterly', 'semi_annual', 'annual',
                  name='taxfilingfrequency', create_type=False), nullable=True),
        sa.Column('is_registered', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_withholding_agent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('fiscal_year_start_month', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('company', 'region_id', name='uq_company_tax_settings'),
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table('company_tax_settings')
    op.drop_table('taxconf_transactions')
    op.drop_table('taxconf_rates')
    op.drop_table('taxconf_categories')
    op.drop_table('tax_regions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS taxtransactionstatus")
    op.execute("DROP TYPE IF EXISTS taxfilingfrequency")
    op.execute("DROP TYPE IF EXISTS taxtransactiontype")
    op.execute("DROP TYPE IF EXISTS taxcategorytype")

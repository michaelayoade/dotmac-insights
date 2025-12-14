"""Add Nigerian Tax Administration models

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import date

# revision identifiers, used by Alembic.
revision = 'j5k6l7m8n9o0'
down_revision = ('20241216_hr_support_settings', 'i4j5k6l7m8n9')  # Merge multiple heads
branch_labels = None
depends_on = None

# Default company for single-tenant mode
DEFAULT_COMPANY = 'default'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    def table_exists(name: str) -> bool:
        return inspector.has_table(name)

    def constraint_exists(table: str, constraint: str) -> bool:
        return table_exists(table) and any(c["name"] == constraint for c in inspector.get_unique_constraints(table))

    # Create enums (checkfirst=True handles existing enums)
    nigerian_tax_type = postgresql.ENUM(
        'vat', 'wht', 'cit', 'paye', 'tet', 'edt', 'cgt', 'stamp_duty',
        name='nigeriantaxtype'
    )
    nigerian_tax_type.create(conn, checkfirst=True)

    tax_jurisdiction = postgresql.ENUM('federal', 'state', name='taxjurisdiction')
    tax_jurisdiction.create(conn, checkfirst=True)

    wht_payment_type = postgresql.ENUM(
        'dividend', 'interest', 'rent', 'royalty', 'commission', 'consultancy',
        'technical_service', 'management_fee', 'director_fee', 'contract',
        'supply', 'construction', 'professional_fee', 'hire_of_equipment', 'all_aspects',
        name='whtpaymenttype'
    )
    wht_payment_type.create(conn, checkfirst=True)

    cit_company_size = postgresql.ENUM('small', 'medium', 'large', name='citcompanysize')
    cit_company_size.create(conn, checkfirst=True)

    vat_transaction_type = postgresql.ENUM('output', 'input', name='vattransactiontype')
    vat_transaction_type.create(conn, checkfirst=True)

    einvoice_status = postgresql.ENUM(
        'draft', 'validated', 'submitted', 'accepted', 'rejected', 'cancelled',
        name='einvoicestatus'
    )
    einvoice_status.create(conn, checkfirst=True)

    paye_filing_frequency = postgresql.ENUM(
        'monthly', 'quarterly', 'annual',
        name='payefilingfrequency'
    )
    paye_filing_frequency.create(conn, checkfirst=True)

    # Create sequences for reference number generation (thread-safe under load)
    conn.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS ng_vat_ref_seq START 1"))
    conn.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS ng_wht_ref_seq START 1"))

    # Create ng_tax_settings table
    if not table_exists('ng_tax_settings'):
        op.create_table(
            'ng_tax_settings',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY),
            sa.Column('tin', sa.String(20), nullable=True),
            sa.Column('vat_registration_number', sa.String(50), nullable=True),
            sa.Column('cac_registration_number', sa.String(50), nullable=True),
            sa.Column('state_tin', sa.String(20), nullable=True),
            sa.Column('state_of_residence', sa.String(100), nullable=True),
            sa.Column('default_jurisdiction', postgresql.ENUM('federal', 'state', name='taxjurisdiction', create_type=False), server_default='federal'),
            sa.Column('company_size', postgresql.ENUM('small', 'medium', 'large', name='citcompanysize', create_type=False), server_default='medium'),
            sa.Column('annual_turnover', sa.Numeric(18, 2), server_default='0'),
            sa.Column('vat_registered', sa.Boolean(), server_default='true'),
            sa.Column('vat_rate', sa.Numeric(5, 4), server_default='0.0750'),
            sa.Column('vat_filing_frequency', sa.String(20), server_default='monthly'),
            sa.Column('is_wht_agent', sa.Boolean(), server_default='true'),
            sa.Column('apply_tin_penalty', sa.Boolean(), server_default='true'),
            sa.Column('einvoice_enabled', sa.Boolean(), server_default='false'),
            sa.Column('einvoice_threshold', sa.Numeric(18, 2), server_default='50000'),
            sa.Column('paye_filing_frequency', postgresql.ENUM('monthly', 'quarterly', 'annual', name='payefilingfrequency', create_type=False), server_default='monthly'),
            sa.Column('fiscal_year_start_month', sa.Integer(), server_default='1'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
    if not constraint_exists('ng_tax_settings', 'uq_ng_tax_settings_company'):
        op.create_unique_constraint('uq_ng_tax_settings_company', 'ng_tax_settings', ['company'])

    # Create ng_tax_rates table
    if not table_exists('ng_tax_rates'):
        op.create_table(
            'ng_tax_rates',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tax_type', postgresql.ENUM('vat', 'wht', 'cit', 'paye', 'tet', 'edt', 'cgt', 'stamp_duty', name='nigeriantaxtype', create_type=False), nullable=False, index=True),
            sa.Column('wht_payment_type', postgresql.ENUM(
                'dividend', 'interest', 'rent', 'royalty', 'commission', 'consultancy',
                'technical_service', 'management_fee', 'director_fee', 'contract',
                'supply', 'construction', 'professional_fee', 'hire_of_equipment', 'all_aspects',
                name='whtpaymenttype', create_type=False
            ), nullable=True, index=True),
            sa.Column('rate', sa.Numeric(8, 6), nullable=False),
            sa.Column('rate_name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_corporate', sa.Boolean(), server_default='true'),
            sa.Column('is_individual', sa.Boolean(), server_default='false'),
            sa.Column('min_threshold', sa.Numeric(18, 2), nullable=True),
            sa.Column('max_threshold', sa.Numeric(18, 2), nullable=True),
            sa.Column('effective_from', sa.Date(), nullable=False, index=True),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('jurisdiction', postgresql.ENUM('federal', 'state', name='taxjurisdiction', create_type=False), server_default='federal'),
            sa.Column('is_active', sa.Boolean(), server_default='true', index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    # Create ng_vat_transactions table
    if not table_exists('ng_vat_transactions'):
        op.create_table(
            'ng_vat_transactions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('reference_number', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('transaction_type', postgresql.ENUM('output', 'input', name='vattransactiontype', create_type=False), nullable=False, index=True),
            sa.Column('transaction_date', sa.Date(), nullable=False, index=True),
            sa.Column('party_type', sa.String(20), nullable=False),
            sa.Column('party_id', sa.Integer(), nullable=True, index=True),
            sa.Column('party_name', sa.String(255), nullable=False),
            sa.Column('party_tin', sa.String(20), nullable=True),
            sa.Column('party_vat_number', sa.String(50), nullable=True),
            sa.Column('source_doctype', sa.String(50), nullable=False),
            sa.Column('source_docname', sa.String(255), nullable=False, index=True),
            sa.Column('taxable_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('vat_rate', sa.Numeric(5, 4), server_default='0.0750'),
            sa.Column('vat_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('total_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('currency', sa.String(3), server_default='NGN'),
            sa.Column('exchange_rate', sa.Numeric(18, 6), server_default='1'),
            sa.Column('filing_period', sa.String(10), nullable=False, index=True),
            sa.Column('is_filed', sa.Boolean(), server_default='false', index=True),
            sa.Column('filed_at', sa.DateTime(), nullable=True),
            sa.Column('filing_reference', sa.String(100), nullable=True),
            sa.Column('is_exempt', sa.Boolean(), server_default='false'),
            sa.Column('is_zero_rated', sa.Boolean(), server_default='false'),
            sa.Column('exemption_reason', sa.String(255), nullable=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ng_vat_filing_period_type ON ng_vat_transactions (filing_period, transaction_type)"
    ))

    # Create ng_wht_certificates table first (referenced by ng_wht_transactions)
    if not table_exists('ng_wht_certificates'):
        op.create_table(
            'ng_wht_certificates',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('certificate_number', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('issue_date', sa.Date(), nullable=False, index=True),
            sa.Column('valid_until', sa.Date(), nullable=True),
            sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('suppliers.id'), nullable=True, index=True),
            sa.Column('supplier_name', sa.String(255), nullable=False),
            sa.Column('supplier_tin', sa.String(20), nullable=True),
            sa.Column('supplier_address', sa.Text(), nullable=True),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('total_gross_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('total_wht_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('transaction_count', sa.Integer(), server_default='0'),
            sa.Column('is_issued', sa.Boolean(), server_default='false'),
            sa.Column('issued_at', sa.DateTime(), nullable=True),
            sa.Column('issued_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('is_cancelled', sa.Boolean(), server_default='false'),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancellation_reason', sa.Text(), nullable=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('company_tin', sa.String(20), nullable=True),
            sa.Column('company_address', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )

    # Create ng_wht_transactions table
    if not table_exists('ng_wht_transactions'):
        op.create_table(
            'ng_wht_transactions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('reference_number', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('transaction_date', sa.Date(), nullable=False, index=True),
            sa.Column('payment_type', postgresql.ENUM(
                'dividend', 'interest', 'rent', 'royalty', 'commission', 'consultancy',
                'technical_service', 'management_fee', 'director_fee', 'contract',
                'supply', 'construction', 'professional_fee', 'hire_of_equipment', 'all_aspects',
                name='whtpaymenttype', create_type=False
            ), nullable=False, index=True),
            sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('suppliers.id'), nullable=True, index=True),
            sa.Column('supplier_name', sa.String(255), nullable=False),
            sa.Column('supplier_tin', sa.String(20), nullable=True),
            sa.Column('supplier_is_corporate', sa.Boolean(), server_default='true'),
            sa.Column('has_valid_tin', sa.Boolean(), server_default='true'),
            sa.Column('source_doctype', sa.String(50), nullable=False),
            sa.Column('source_docname', sa.String(255), nullable=False, index=True),
            sa.Column('gross_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('wht_rate', sa.Numeric(5, 4), nullable=False),
            sa.Column('standard_rate', sa.Numeric(5, 4), nullable=False),
            sa.Column('wht_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('net_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('currency', sa.String(3), server_default='NGN'),
            sa.Column('exchange_rate', sa.Numeric(18, 6), server_default='1'),
            sa.Column('jurisdiction', postgresql.ENUM('federal', 'state', name='taxjurisdiction', create_type=False), server_default='federal'),
            sa.Column('remittance_due_date', sa.Date(), nullable=False),
            sa.Column('is_remitted', sa.Boolean(), server_default='false', index=True),
            sa.Column('remitted_at', sa.DateTime(), nullable=True),
            sa.Column('remittance_reference', sa.String(100), nullable=True),
            sa.Column('certificate_id', sa.Integer(), sa.ForeignKey('ng_wht_certificates.id'), nullable=True, index=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ng_wht_date_jurisdiction ON ng_wht_transactions (transaction_date, jurisdiction)"
    ))

    # Create ng_paye_calculations table
    if not table_exists('ng_paye_calculations'):
        op.create_table(
            'ng_paye_calculations',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False, index=True),
            sa.Column('employee_name', sa.String(255), nullable=False),
            sa.Column('employee_tin', sa.String(20), nullable=True),
            sa.Column('payroll_period', sa.String(10), nullable=False, index=True),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('basic_salary', sa.Numeric(18, 2), nullable=False),
            sa.Column('housing_allowance', sa.Numeric(18, 2), server_default='0'),
            sa.Column('transport_allowance', sa.Numeric(18, 2), server_default='0'),
            sa.Column('other_allowances', sa.Numeric(18, 2), server_default='0'),
            sa.Column('bonus', sa.Numeric(18, 2), server_default='0'),
            sa.Column('gross_income', sa.Numeric(18, 2), nullable=False),
            sa.Column('annual_gross_income', sa.Numeric(18, 2), nullable=False),
            sa.Column('cra_fixed', sa.Numeric(18, 2), nullable=False),
            sa.Column('cra_percentage', sa.Numeric(18, 2), nullable=False),
            sa.Column('total_cra', sa.Numeric(18, 2), nullable=False),
            sa.Column('pension_contribution', sa.Numeric(18, 2), server_default='0'),
            sa.Column('nhf_contribution', sa.Numeric(18, 2), server_default='0'),
            sa.Column('nhis_contribution', sa.Numeric(18, 2), server_default='0'),
            sa.Column('life_assurance', sa.Numeric(18, 2), server_default='0'),
            sa.Column('other_reliefs', sa.Numeric(18, 2), server_default='0'),
            sa.Column('total_reliefs', sa.Numeric(18, 2), nullable=False),
            sa.Column('annual_taxable_income', sa.Numeric(18, 2), nullable=False),
            sa.Column('tax_bands_breakdown', postgresql.JSON(), nullable=True),
            sa.Column('annual_tax', sa.Numeric(18, 2), nullable=False),
            sa.Column('monthly_tax', sa.Numeric(18, 2), nullable=False),
            sa.Column('effective_rate', sa.Numeric(8, 6), nullable=False),
            sa.Column('is_filed', sa.Boolean(), server_default='false', index=True),
            sa.Column('filed_at', sa.DateTime(), nullable=True),
            sa.Column('state_of_residence', sa.String(100), nullable=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ng_paye_employee_period ON ng_paye_calculations (employee_id, payroll_period)"
    ))

    # Create ng_cit_assessments table
    if not table_exists('ng_cit_assessments'):
        op.create_table(
            'ng_cit_assessments',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('assessment_number', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('fiscal_year', sa.String(10), nullable=False, index=True),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('company_size', postgresql.ENUM('small', 'medium', 'large', name='citcompanysize', create_type=False), nullable=False),
            sa.Column('gross_turnover', sa.Numeric(18, 2), nullable=False),
            sa.Column('gross_profit', sa.Numeric(18, 2), nullable=False),
            sa.Column('disallowed_expenses', sa.Numeric(18, 2), server_default='0'),
            sa.Column('capital_allowances', sa.Numeric(18, 2), server_default='0'),
            sa.Column('loss_brought_forward', sa.Numeric(18, 2), server_default='0'),
            sa.Column('investment_allowances', sa.Numeric(18, 2), server_default='0'),
            sa.Column('adjusted_profit', sa.Numeric(18, 2), nullable=False),
            sa.Column('assessable_profit', sa.Numeric(18, 2), nullable=False),
            sa.Column('cit_rate', sa.Numeric(5, 4), nullable=False),
            sa.Column('cit_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('tet_rate', sa.Numeric(5, 4), server_default='0.03'),
            sa.Column('tet_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('minimum_tax', sa.Numeric(18, 2), server_default='0'),
            sa.Column('is_minimum_tax_applicable', sa.Boolean(), server_default='false'),
            sa.Column('total_tax_liability', sa.Numeric(18, 2), nullable=False),
            sa.Column('amount_paid', sa.Numeric(18, 2), server_default='0'),
            sa.Column('balance_due', sa.Numeric(18, 2), nullable=False),
            sa.Column('is_self_assessment', sa.Boolean(), server_default='true'),
            sa.Column('is_filed', sa.Boolean(), server_default='false', index=True),
            sa.Column('filed_at', sa.DateTime(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('company_tin', sa.String(20), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )

    # Create ng_einvoices table
    if not table_exists('ng_einvoices'):
        op.create_table(
            'ng_einvoices',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('ubl_version_id', sa.String(10), server_default='2.1'),
            sa.Column('customization_id', sa.String(100), server_default='urn:firs.gov.ng:einvoice:1.0'),
            sa.Column('profile_id', sa.String(100), server_default='urn:firs.gov.ng:profile:bis:billing:3.0'),
            sa.Column('invoice_number', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('uuid', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('issue_date', sa.Date(), nullable=False, index=True),
            sa.Column('issue_time', sa.String(20), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('invoice_type_code', sa.String(10), server_default='380'),
            sa.Column('source_doctype', sa.String(50), nullable=False),
            sa.Column('source_docname', sa.String(255), nullable=False, index=True),
            sa.Column('document_currency_code', sa.String(3), server_default='NGN'),
            sa.Column('tax_currency_code', sa.String(3), server_default='NGN'),
            sa.Column('order_reference', sa.String(100), nullable=True),
            sa.Column('contract_reference', sa.String(100), nullable=True),
            # Supplier fields
            sa.Column('supplier_name', sa.String(255), nullable=False),
            sa.Column('supplier_tin', sa.String(20), nullable=True),
            sa.Column('supplier_vat_number', sa.String(50), nullable=True),
            sa.Column('supplier_registration_name', sa.String(255), nullable=True),
            sa.Column('supplier_street', sa.String(255), nullable=True),
            sa.Column('supplier_building', sa.String(100), nullable=True),
            sa.Column('supplier_city', sa.String(100), nullable=True),
            sa.Column('supplier_postal_code', sa.String(20), nullable=True),
            sa.Column('supplier_state', sa.String(100), nullable=True),
            sa.Column('supplier_country_code', sa.String(2), server_default='NG'),
            sa.Column('supplier_phone', sa.String(50), nullable=True),
            sa.Column('supplier_email', sa.String(255), nullable=True),
            sa.Column('supplier_contact_name', sa.String(255), nullable=True),
            sa.Column('supplier_bank_account', sa.String(50), nullable=True),
            sa.Column('supplier_bank_name', sa.String(255), nullable=True),
            # Customer fields
            sa.Column('customer_name', sa.String(255), nullable=False),
            sa.Column('customer_tin', sa.String(20), nullable=True),
            sa.Column('customer_vat_number', sa.String(50), nullable=True),
            sa.Column('customer_street', sa.String(255), nullable=True),
            sa.Column('customer_city', sa.String(100), nullable=True),
            sa.Column('customer_postal_code', sa.String(20), nullable=True),
            sa.Column('customer_state', sa.String(100), nullable=True),
            sa.Column('customer_country_code', sa.String(2), server_default='NG'),
            sa.Column('customer_phone', sa.String(50), nullable=True),
            sa.Column('customer_email', sa.String(255), nullable=True),
            # Delivery
            sa.Column('delivery_date', sa.Date(), nullable=True),
            sa.Column('delivery_location', sa.Text(), nullable=True),
            # Payment
            sa.Column('payment_means_code', sa.String(10), nullable=True),
            sa.Column('payment_terms', sa.Text(), nullable=True),
            # Totals
            sa.Column('line_extension_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('tax_exclusive_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('tax_inclusive_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('allowance_total_amount', sa.Numeric(18, 2), server_default='0'),
            sa.Column('charge_total_amount', sa.Numeric(18, 2), server_default='0'),
            sa.Column('prepaid_amount', sa.Numeric(18, 2), server_default='0'),
            sa.Column('payable_amount', sa.Numeric(18, 2), nullable=False),
            # Tax
            sa.Column('tax_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('tax_category_code', sa.String(10), server_default='S'),
            sa.Column('tax_rate', sa.Numeric(5, 4), server_default='0.0750'),
            # Status
            sa.Column('status', postgresql.ENUM('draft', 'validated', 'submitted', 'accepted', 'rejected', 'cancelled', name='einvoicestatus', create_type=False), server_default='draft', index=True),
            sa.Column('validation_errors', postgresql.JSON(), nullable=True),
            sa.Column('validated_at', sa.DateTime(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('submission_reference', sa.String(100), nullable=True),
            sa.Column('firs_response', postgresql.JSON(), nullable=True),
            sa.Column('qr_code_data', sa.Text(), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('company', sa.String(255), nullable=True, server_default=DEFAULT_COMPANY, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )

    # Create ng_einvoice_lines table
    if not table_exists('ng_einvoice_lines'):
        op.create_table(
            'ng_einvoice_lines',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('einvoice_id', sa.Integer(), sa.ForeignKey('ng_einvoices.id'), nullable=False, index=True),
            sa.Column('line_id', sa.String(20), nullable=False),
            sa.Column('item_name', sa.String(255), nullable=False),
            sa.Column('item_description', sa.Text(), nullable=True),
            sa.Column('item_code', sa.String(50), nullable=True),
            sa.Column('quantity', sa.Numeric(18, 4), nullable=False),
            sa.Column('unit_code', sa.String(10), server_default='EA'),
            sa.Column('unit_price', sa.Numeric(18, 4), nullable=False),
            sa.Column('line_extension_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('allowance_amount', sa.Numeric(18, 2), server_default='0'),
            sa.Column('charge_amount', sa.Numeric(18, 2), server_default='0'),
            sa.Column('tax_category_code', sa.String(10), server_default='S'),
            sa.Column('tax_rate', sa.Numeric(5, 4), server_default='0.0750'),
            sa.Column('tax_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('total_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('idx', sa.Integer(), server_default='0'),
        )

    # Seed default settings row for single-tenant mode
    conn.execute(sa.text("""
        INSERT INTO ng_tax_settings (company, vat_rate, default_jurisdiction, company_size)
        VALUES (:company, 0.0750, 'federal', 'medium')
        ON CONFLICT (company) DO NOTHING
    """), {"company": DEFAULT_COMPANY})

    # Seed baseline VAT rate
    conn.execute(sa.text("""
        INSERT INTO ng_tax_rates (tax_type, rate, rate_name, description, effective_from, jurisdiction, is_active)
        SELECT 'vat', 0.0750, 'Standard VAT', 'Nigeria standard VAT rate 7.5%', '2020-02-01', 'federal', true
        WHERE NOT EXISTS (
            SELECT 1 FROM ng_tax_rates WHERE tax_type = 'vat' AND rate_name = 'Standard VAT'
        )
    """))

    # Seed WHT rates (Corporate)
    wht_corporate_rates = [
        ('dividend', 0.10, 'WHT on Dividend', 'Withholding tax on dividends'),
        ('interest', 0.10, 'WHT on Interest', 'Withholding tax on interest'),
        ('rent', 0.10, 'WHT on Rent', 'Withholding tax on rent'),
        ('royalty', 0.10, 'WHT on Royalty', 'Withholding tax on royalties'),
        ('commission', 0.10, 'WHT on Commission', 'Withholding tax on commission'),
        ('consultancy', 0.10, 'WHT on Consultancy', 'Withholding tax on consultancy fees'),
        ('technical_service', 0.10, 'WHT on Technical Service', 'Withholding tax on technical services'),
        ('management_fee', 0.10, 'WHT on Management Fee', 'Withholding tax on management fees'),
        ('director_fee', 0.10, 'WHT on Director Fee', 'Withholding tax on director fees'),
        ('contract', 0.05, 'WHT on Contract', 'Withholding tax on contracts'),
        ('supply', 0.05, 'WHT on Supply', 'Withholding tax on supply of goods'),
        ('construction', 0.05, 'WHT on Construction', 'Withholding tax on construction'),
        ('professional_fee', 0.10, 'WHT on Professional Fee', 'Withholding tax on professional fees'),
        ('hire_of_equipment', 0.10, 'WHT on Equipment Hire', 'Withholding tax on equipment hire'),
    ]
    for payment_type, rate, name, desc in wht_corporate_rates:
        conn.execute(sa.text("""
            INSERT INTO ng_tax_rates (tax_type, wht_payment_type, rate, rate_name, description,
                                       is_corporate, is_individual, effective_from, jurisdiction, is_active)
            SELECT 'wht', :payment_type, :rate, :name, :desc, true, false, '2020-01-01', 'federal', true
            WHERE NOT EXISTS (
                SELECT 1 FROM ng_tax_rates WHERE tax_type = 'wht' AND rate_name = :name
            )
        """), {"payment_type": payment_type, "rate": rate, "name": name, "desc": desc})

    # Seed WHT rates (Individual - lower for some categories)
    wht_individual_rates = [
        ('dividend', 0.10, 'WHT on Dividend (Individual)', 'Withholding tax on dividends - individual'),
        ('interest', 0.10, 'WHT on Interest (Individual)', 'Withholding tax on interest - individual'),
        ('rent', 0.10, 'WHT on Rent (Individual)', 'Withholding tax on rent - individual'),
        ('royalty', 0.05, 'WHT on Royalty (Individual)', 'Withholding tax on royalties - individual'),
        ('commission', 0.05, 'WHT on Commission (Individual)', 'Withholding tax on commission - individual'),
        ('consultancy', 0.05, 'WHT on Consultancy (Individual)', 'Withholding tax on consultancy fees - individual'),
        ('contract', 0.025, 'WHT on Contract (Individual)', 'Withholding tax on contracts - individual'),
        ('supply', 0.02, 'WHT on Supply (Individual)', 'Withholding tax on supply of goods - individual'),
    ]
    for payment_type, rate, name, desc in wht_individual_rates:
        conn.execute(sa.text("""
            INSERT INTO ng_tax_rates (tax_type, wht_payment_type, rate, rate_name, description,
                                       is_corporate, is_individual, effective_from, jurisdiction, is_active)
            SELECT 'wht', :payment_type, :rate, :name, :desc, false, true, '2020-01-01', 'federal', true
            WHERE NOT EXISTS (
                SELECT 1 FROM ng_tax_rates WHERE tax_type = 'wht' AND rate_name = :name
            )
        """), {"payment_type": payment_type, "rate": rate, "name": name, "desc": desc})

    # Seed PAYE bands (PITA - current law)
    paye_bands = [
        (0, 300000, 0.07, 'First N300,000'),
        (300000, 600000, 0.11, 'Next N300,000'),
        (600000, 1100000, 0.15, 'Next N500,000'),
        (1100000, 1600000, 0.19, 'Next N500,000'),
        (1600000, 3200000, 0.21, 'Next N1,600,000'),
        (3200000, None, 0.24, 'Above N3,200,000'),
    ]
    for min_t, max_t, rate, name in paye_bands:
        conn.execute(sa.text("""
            INSERT INTO ng_tax_rates (tax_type, rate, rate_name, description,
                                       min_threshold, max_threshold, effective_from, jurisdiction, is_active)
            SELECT 'paye', :rate, :name, 'PAYE progressive band - PITA',
                   :min_t, :max_t, '2011-06-01', 'federal', true
            WHERE NOT EXISTS (
                SELECT 1 FROM ng_tax_rates WHERE tax_type = 'paye' AND rate_name = :name
            )
        """), {"rate": rate, "name": name, "min_t": min_t, "max_t": max_t})

    # Seed CIT rates
    cit_rates = [
        (0, 25000000, 0.00, 'Small Company (0%)', 'CIT for companies with turnover <= N25M'),
        (25000000, 100000000, 0.20, 'Medium Company (20%)', 'CIT for companies with turnover N25M - N100M'),
        (100000000, None, 0.30, 'Large Company (30%)', 'CIT for companies with turnover > N100M'),
    ]
    for min_t, max_t, rate, name, desc in cit_rates:
        conn.execute(sa.text("""
            INSERT INTO ng_tax_rates (tax_type, rate, rate_name, description,
                                       min_threshold, max_threshold, effective_from, jurisdiction, is_active)
            SELECT 'cit', :rate, :name, :desc, :min_t, :max_t, '2020-01-01', 'federal', true
            WHERE NOT EXISTS (
                SELECT 1 FROM ng_tax_rates WHERE tax_type = 'cit' AND rate_name = :name
            )
        """), {"rate": rate, "name": name, "desc": desc, "min_t": min_t, "max_t": max_t})


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('ng_einvoice_lines')
    op.drop_table('ng_einvoices')
    op.drop_table('ng_cit_assessments')
    op.drop_table('ng_paye_calculations')
    op.drop_table('ng_wht_transactions')
    op.drop_table('ng_wht_certificates')
    op.drop_table('ng_vat_transactions')
    op.drop_table('ng_tax_rates')
    op.drop_table('ng_tax_settings')

    # Drop sequences
    op.execute('DROP SEQUENCE IF EXISTS ng_vat_ref_seq')
    op.execute('DROP SEQUENCE IF EXISTS ng_wht_ref_seq')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS payefilingfrequency')
    op.execute('DROP TYPE IF EXISTS einvoicestatus')
    op.execute('DROP TYPE IF EXISTS vattransactiontype')
    op.execute('DROP TYPE IF EXISTS citcompanysize')
    op.execute('DROP TYPE IF EXISTS whtpaymenttype')
    op.execute('DROP TYPE IF EXISTS taxjurisdiction')
    op.execute('DROP TYPE IF EXISTS nigeriantaxtype')

"""Add generic payroll configuration tables

Revision ID: m8n9o0p1q2r4
Revises: l7m8n9o0p1q2
Create Date: 2025-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm8n9o0p1q2r4'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create CalcMethod enum
    calcmethod_enum = postgresql.ENUM(
        'flat', 'percentage', 'progressive',
        name='calcmethod',
        create_type=False
    )
    calcmethod_enum.create(op.get_bind(), checkfirst=True)

    # Create DeductionType enum
    deductiontype_enum = postgresql.ENUM(
        'tax', 'pension', 'insurance', 'levy', 'other',
        name='deductiontype',
        create_type=False
    )
    deductiontype_enum.create(op.get_bind(), checkfirst=True)

    # Create PayrollFrequency enum (skip if exists - may already exist with different case)
    # Note: Existing enum has uppercase values: WEEKLY, BIWEEKLY, MONTHLY, SEMIMONTHLY

    # Create RuleApplicability enum
    ruleapplicability_enum = postgresql.ENUM(
        'employee', 'employer', 'both',
        name='ruleapplicability',
        create_type=False
    )
    ruleapplicability_enum.create(op.get_bind(), checkfirst=True)

    # Create payroll_regions table
    op.create_table(
        'payroll_regions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), nullable=False, unique=True, index=True,
                  comment='ISO 3166-1 alpha-2 country code (e.g., NG, KE, US)'),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('default_pay_frequency', postgresql.ENUM('WEEKLY', 'BIWEEKLY', 'MONTHLY', 'SEMIMONTHLY',
                  name='payrollfrequency', create_type=False), nullable=False, server_default='MONTHLY'),
        sa.Column('fiscal_year_start_month', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('payment_day', sa.Integer(), nullable=False, server_default='28'),
        sa.Column('has_statutory_deductions', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('requires_compliance_addon', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('compliance_addon_code', sa.String(50), nullable=True,
                  comment='Feature flag code for compliance add-on (e.g., NIGERIA_COMPLIANCE)'),
        sa.Column('tax_authority_name', sa.String(255), nullable=True),
        sa.Column('tax_id_label', sa.String(50), nullable=False, server_default='Tax ID'),
        sa.Column('tax_id_format', sa.String(100), nullable=True, comment='Regex pattern for validation'),
        sa.Column('paye_filing_frequency', sa.String(20), nullable=True),
        sa.Column('paye_filing_deadline_day', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # Create deduction_rules table
    op.create_table(
        'deduction_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('region_id', sa.Integer(), sa.ForeignKey('payroll_regions.id'), nullable=False, index=True),
        sa.Column('code', sa.String(50), nullable=False, index=True,
                  comment='Rule code (e.g., PAYE, PENSION_EE, NHF)'),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deduction_type', postgresql.ENUM('tax', 'pension', 'insurance', 'levy', 'other',
                  name='deductiontype', create_type=False), nullable=False, index=True),
        sa.Column('applicability', postgresql.ENUM('employee', 'employer', 'both',
                  name='ruleapplicability', create_type=False), nullable=False, server_default='employee'),
        sa.Column('is_statutory', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('calc_method', postgresql.ENUM('flat', 'percentage', 'progressive',
                  name='calcmethod', create_type=False), nullable=False),
        sa.Column('rate', sa.Numeric(10, 6), nullable=True, comment='For PERCENTAGE method'),
        sa.Column('flat_amount', sa.Numeric(18, 2), nullable=True, comment='For FLAT method'),
        sa.Column('employee_share', sa.Numeric(6, 4), nullable=True,
                  comment='Employee share when applicability=both (0-1)'),
        sa.Column('employer_share', sa.Numeric(6, 4), nullable=True,
                  comment='Employer share when applicability=both (0-1)'),
        sa.Column('base_components', postgresql.JSONB(), nullable=True,
                  comment='Array of component names for PERCENTAGE calculation'),
        sa.Column('min_base', sa.Numeric(18, 2), nullable=True),
        sa.Column('max_base', sa.Numeric(18, 2), nullable=True),
        sa.Column('cap_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('floor_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('employment_types', postgresql.JSONB(), nullable=True,
                  comment='Array of applicable employment types, null means all'),
        sa.Column('min_service_months', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('statutory_code', sa.String(50), nullable=True,
                  comment='Reference to statutory law (e.g., PITA, PFA2014)'),
        sa.Column('filing_frequency', sa.String(20), nullable=True),
        sa.Column('remittance_deadline_days', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.CheckConstraint(
            "(calc_method = 'flat' AND flat_amount IS NOT NULL) OR "
            "(calc_method = 'percentage' AND rate IS NOT NULL) OR "
            "(calc_method = 'progressive')",
            name='ck_deduction_rules_calc_method_values'
        ),
        sa.CheckConstraint(
            "(applicability != 'both') OR "
            "(employee_share IS NOT NULL AND employer_share IS NOT NULL AND "
            "employee_share + employer_share = 1)",
            name='ck_deduction_rules_both_split'
        ),
    )
    op.create_index('ix_deduction_rules_region_code', 'deduction_rules', ['region_id', 'code'])
    op.create_index('ix_deduction_rules_effective', 'deduction_rules', ['region_id', 'effective_from', 'effective_to'])

    # Create tax_bands table
    op.create_table(
        'tax_bands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('deduction_rule_id', sa.Integer(), sa.ForeignKey('deduction_rules.id'), nullable=False, index=True),
        sa.Column('lower_limit', sa.Numeric(18, 2), nullable=False, comment='Lower limit of band (annual)'),
        sa.Column('upper_limit', sa.Numeric(18, 2), nullable=True, comment='Upper limit of band, null for unlimited'),
        sa.Column('rate', sa.Numeric(10, 6), nullable=False, comment='Tax rate for this band (e.g., 0.07 for 7%)'),
        sa.Column('band_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index('ix_tax_bands_rule_order', 'tax_bands', ['deduction_rule_id', 'band_order'])


    # Add region_code to payroll_entries
    op.add_column('payroll_entries', sa.Column('region_code', sa.String(10), nullable=True,
                  comment='ISO 3166-1 alpha-2 region code for statutory calculations'))
    op.create_index('ix_payroll_entries_region_code', 'payroll_entries', ['region_code'])

    # Add region_code to salary_slips
    op.add_column('salary_slips', sa.Column('region_code', sa.String(10), nullable=True,
                  comment='ISO 3166-1 alpha-2 region code for statutory calculations'))
    op.create_index('ix_salary_slips_region_code', 'salary_slips', ['region_code'])


def downgrade() -> None:
    # Drop region_code from existing tables
    op.drop_index('ix_salary_slips_region_code', table_name='salary_slips')
    op.drop_column('salary_slips', 'region_code')
    op.drop_index('ix_payroll_entries_region_code', table_name='payroll_entries')
    op.drop_column('payroll_entries', 'region_code')

    # Drop tables
    op.drop_table('tax_bands')
    op.drop_table('deduction_rules')
    op.drop_table('payroll_regions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS ruleapplicability")
    op.execute("DROP TYPE IF EXISTS payrollfrequency")
    op.execute("DROP TYPE IF EXISTS deductiontype")
    op.execute("DROP TYPE IF EXISTS calcmethod")

"""Add employment type deduction configuration

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2024-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = 'k6l7m8n9o0p1'
down_revision = 'j5k6l7m8n9o0'
branch_labels = None
depends_on = None

DEFAULT_COMPANY = 'default'


def upgrade() -> None:
    conn = op.get_bind()

    # Create EmploymentType enum
    employment_type_enum = postgresql.ENUM(
        'PERMANENT', 'CONTRACT', 'PART_TIME', 'INTERN', 'NYSC',
        'PROBATION', 'CASUAL', 'CONSULTANT', 'EXPATRIATE',
        name='employmenttype'
    )
    employment_type_enum.create(conn, checkfirst=True)

    # Create employment_type_deduction_configs table
    op.create_table(
        'employment_type_deduction_configs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('company', sa.String(255), nullable=True, index=True, server_default=DEFAULT_COMPANY),
        sa.Column('employment_type', postgresql.ENUM(
            'PERMANENT', 'CONTRACT', 'PART_TIME', 'INTERN', 'NYSC',
            'PROBATION', 'CASUAL', 'CONSULTANT', 'EXPATRIATE',
            name='employmenttype', create_type=False
        ), nullable=False, index=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # Statutory deduction eligibility
        sa.Column('paye_applicable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('pension_applicable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('nhf_applicable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('nhis_applicable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('nsitf_applicable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('itf_applicable', sa.Boolean(), nullable=False, server_default='true'),
        # Minimum service period for pension (months)
        sa.Column('pension_min_service_months', sa.Integer(), nullable=False, server_default='0'),
        # ITF headcount
        sa.Column('counts_for_itf_headcount', sa.Boolean(), nullable=False, server_default='true'),
        # Gratuity
        sa.Column('gratuity_eligible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('gratuity_min_service_years', sa.Integer(), nullable=False, server_default='5'),
        # Is this on-payroll?
        sa.Column('is_payroll_employee', sa.Boolean(), nullable=False, server_default='true'),
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=func.now(), onupdate=func.now()),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # Unique constraint
    op.create_unique_constraint(
        'uq_employment_type_config_company_type',
        'employment_type_deduction_configs',
        ['company', 'employment_type']
    )

    # Add employment_type_enum column to employees table (keeping old string column)
    op.add_column(
        'employees',
        sa.Column('employment_type_enum', postgresql.ENUM(
            'PERMANENT', 'CONTRACT', 'PART_TIME', 'INTERN', 'NYSC',
            'PROBATION', 'CASUAL', 'CONSULTANT', 'EXPATRIATE',
            name='employmenttype', create_type=False
        ), nullable=True, index=True)
    )
    op.create_index('ix_employees_employment_type_enum', 'employees', ['employment_type_enum'], if_not_exists=True)

    # Seed default configurations for all employment types
    default_configs = [
        {
            "employment_type": "PERMANENT",
            "display_name": "Permanent Staff",
            "description": "Full-time permanent employees",
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": True,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": True,
            "gratuity_min_service_years": 5,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "CONTRACT",
            "display_name": "Contract Staff",
            "description": "Fixed-term contract employees",
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": False,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 3,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "PART_TIME",
            "display_name": "Part-Time Staff",
            "description": "Part-time employees",
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": False,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 3,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "INTERN",
            "display_name": "Intern / SIWES",
            "description": "Industrial training students",
            "paye_applicable": True,
            "pension_applicable": False,
            "nhf_applicable": False,
            "nhis_applicable": False,
            "nsitf_applicable": False,
            "itf_applicable": False,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": False,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "NYSC",
            "display_name": "NYSC Corps Member",
            "description": "National Youth Service Corps members",
            "paye_applicable": False,
            "pension_applicable": False,
            "nhf_applicable": False,
            "nhis_applicable": False,
            "nsitf_applicable": False,
            "itf_applicable": False,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": False,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "PROBATION",
            "display_name": "Probationary Staff",
            "description": "Employees on probation period",
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": True,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": True,
            "gratuity_min_service_years": 5,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "CASUAL",
            "display_name": "Casual Worker",
            "description": "Daily/casual workers",
            "paye_applicable": True,
            "pension_applicable": False,
            "nhf_applicable": False,
            "nhis_applicable": False,
            "nsitf_applicable": False,
            "itf_applicable": False,
            "pension_min_service_months": 3,
            "counts_for_itf_headcount": False,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "CONSULTANT",
            "display_name": "In-house Consultant",
            "description": "Consultants on company payroll",
            "paye_applicable": True,
            "pension_applicable": False,
            "nhf_applicable": False,
            "nhis_applicable": False,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": False,
            "gratuity_min_service_years": 0,
            "is_payroll_employee": True,
        },
        {
            "employment_type": "EXPATRIATE",
            "display_name": "Expatriate Staff",
            "description": "Foreign/expatriate employees",
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": False,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 0,
            "counts_for_itf_headcount": True,
            "gratuity_eligible": True,
            "gratuity_min_service_years": 5,
            "is_payroll_employee": True,
        },
    ]

    for cfg in default_configs:
        conn.execute(sa.text("""
            INSERT INTO employment_type_deduction_configs (
                company, employment_type, display_name, description,
                paye_applicable, pension_applicable, nhf_applicable, nhis_applicable,
                nsitf_applicable, itf_applicable, pension_min_service_months,
                counts_for_itf_headcount, gratuity_eligible, gratuity_min_service_years,
                is_payroll_employee, is_active
            ) VALUES (
                :company, :employment_type, :display_name, :description,
                :paye_applicable, :pension_applicable, :nhf_applicable, :nhis_applicable,
                :nsitf_applicable, :itf_applicable, :pension_min_service_months,
                :counts_for_itf_headcount, :gratuity_eligible, :gratuity_min_service_years,
                :is_payroll_employee, true
            )
            ON CONFLICT (company, employment_type) DO NOTHING
        """), {"company": DEFAULT_COMPANY, **cfg})

    # Migrate existing employment_type string values to enum
    # Map common ERPNext values to our enum
    type_mappings = [
        ("Full-time", "PERMANENT"),
        ("Permanent", "PERMANENT"),
        ("Part-time", "PART_TIME"),
        ("Part Time", "PART_TIME"),
        ("Contract", "CONTRACT"),
        ("Contractual", "CONTRACT"),
        ("Intern", "INTERN"),
        ("Internship", "INTERN"),
        ("SIWES", "INTERN"),
        ("NYSC", "NYSC"),
        ("Corper", "NYSC"),
        ("Probation", "PROBATION"),
        ("Probationary", "PROBATION"),
        ("Casual", "CASUAL"),
        ("Daily", "CASUAL"),
        ("Consultant", "CONSULTANT"),
        ("Expatriate", "EXPATRIATE"),
        ("Expat", "EXPATRIATE"),
    ]

    for old_value, new_value in type_mappings:
        # Use format string for the enum cast since SQLAlchemy text() gets confused with ::
        conn.execute(sa.text(f"""
            UPDATE employees
            SET employment_type_enum = '{new_value}'::employmenttype
            WHERE LOWER(employment_type) = LOWER(:old_value)
            AND employment_type_enum IS NULL
        """), {"old_value": old_value})

    # Set remaining NULL values to PERMANENT as default (for active employees)
    conn.execute(sa.text("""
        UPDATE employees
        SET employment_type_enum = 'PERMANENT'::employmenttype
        WHERE employment_type_enum IS NULL
        AND status = 'ACTIVE'::employmentstatus
    """))


def downgrade() -> None:
    op.drop_index('ix_employees_employment_type_enum', table_name='employees')
    # Remove column from employees
    op.drop_column('employees', 'employment_type_enum')

    # Drop table
    op.drop_table('employment_type_deduction_configs')

    # Drop enum
    op.execute('DROP TYPE IF EXISTS employmenttype')

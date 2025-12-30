"""Backfill NULL company values to default company.

This migration sets company = DEFAULT_COMPANY for all records where company IS NULL.
Run this before enforcing NOT NULL constraints on company columns.

Revision ID: 20251221_backfill_null_company
Revises: fa02400b5de5
Create Date: 2025-12-21

"""
from typing import Sequence, Union
from alembic import op
import os
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251221_backfill_null_company'
down_revision: Union[str, None] = 'fa02400b5de5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get default company from environment or use fallback
DEFAULT_COMPANY = os.getenv('DEFAULT_COMPANY', 'DotMac Limited')

# Tables organized by priority
# High priority: Financial/Transactional (must be accurate for reporting)
HIGH_PRIORITY_TABLES = [
    'invoices',
    'payments',
    'purchase_invoices',
    'journal_entries',
    'journal_entry_items',
    'gl_entries',
    'credit_notes',
    'debit_notes',
    'sales_orders',
    'quotations',
    'purchase_orders',
    'supplier_payments',
    'gateway_transactions',
    'transfers',
    'bank_transactions',
    'bank_reconciliations',
]

# Medium priority: Operational
MEDIUM_PRIORITY_TABLES = [
    'projects',
    'tasks',
    'tickets',
    'expenses',
    'expense_claims',
    'expense_categories',
    'expense_policies',
    'cash_advances',
    'assets',
    'vehicles',
    'warehouses',
    'stock_entries',
    'stock_entry_details',
    'stock_ledger_entries',
    'landed_cost_vouchers',
    'stock_receipts',
    'stock_issues',
    'virtual_accounts',
    'payment_subscriptions',
    'open_banking_connections',
]

# Lower priority: Configuration/Settings
LOW_PRIORITY_TABLES = [
    'tax_codes',
    'tax_categories',
    'sales_tax_templates',
    'purchase_tax_templates',
    'item_tax_templates',
    'tax_withholding_categories',
    'tax_rules',
    'payment_terms_templates',
    'books_settings',
    'document_number_formats',
    'accounting_controls',
    'exchange_rates',
    'accounts',
    'notifications',
    'document_attachments',
]

# HR Tables
HR_TABLES = [
    'departments',
    'salary_components',
    'salary_structures',
    'salary_structure_earnings',
    'salary_structure_deductions',
    'leave_types',
    'holiday_lists',
    'leave_policies',
    'job_openings',
    'job_applicants',
    'job_offers',
    'appraisals',
    'training_programs',
    'shift_types',
    'shift_assignments',
    'attendances',
    'employee_onboardings',
    'employee_onboarding_activities',
    'employee_separations',
    'employee_separation_activities',
    'employee_promotions',
    'employee_transfers',
]

# Omni/Support Tables
SUPPORT_TABLES = [
    'inbox_routing_rules',
]

# All tables combined
ALL_TABLES = (
    HIGH_PRIORITY_TABLES +
    MEDIUM_PRIORITY_TABLES +
    LOW_PRIORITY_TABLES +
    HR_TABLES +
    SUPPORT_TABLES
)


def upgrade() -> None:
    """Backfill NULL company values to DEFAULT_COMPANY."""
    # Use raw SQL for efficiency and to handle missing tables gracefully
    conn = op.get_bind()

    for table in ALL_TABLES:
        # Check if table exists before updating
        result = conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                )
                """
            ),
            {"table_name": table},
        )
        table_exists = result.scalar()

        if not table_exists:
            print(f"  Skipping {table} (table does not exist)")
            continue

        # Check if table has company column
        result = conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                    AND column_name = 'company'
                )
                """
            ),
            {"table_name": table},
        )
        has_company = result.scalar()

        if not has_company:
            print(f"  Skipping {table} (no company column)")
            continue

        # Count NULL records
        result = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE company IS NULL")
        )
        null_count = result.scalar()

        if null_count == 0:
            print(f"  Skipping {table} (no NULL company values)")
            continue

        # Perform the backfill
        print(f"  Backfilling {table}: {null_count} records")
        conn.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET company = :default_company
                WHERE company IS NULL
                """
            ),
            {"default_company": DEFAULT_COMPANY},
        )
        conn.commit()

    print(f"\nBackfill complete. DEFAULT_COMPANY = '{DEFAULT_COMPANY}'")


def downgrade() -> None:
    """Cannot reliably downgrade - data was legitimately NULL before.

    If you need to reverse this, run:
    UPDATE <table> SET company = NULL WHERE company = '<DEFAULT_COMPANY>';

    But be aware this will affect any records that were legitimately set
    to DEFAULT_COMPANY after the migration.
    """
    pass

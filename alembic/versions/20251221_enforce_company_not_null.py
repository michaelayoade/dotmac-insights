"""Enforce NOT NULL on company columns (Phase 3).

DO NOT RUN THIS MIGRATION until:
1. The backfill migration (20251221_backfill_null_company) has been run
2. You have verified all NULL company values have been backfilled
3. The API layer is updated to always set company on new records

To verify before running:
    SELECT table_name, COUNT(*) as null_count
    FROM (
        SELECT 'invoices' as table_name FROM invoices WHERE company IS NULL
        UNION ALL SELECT 'journal_entries' FROM journal_entries WHERE company IS NULL
        UNION ALL SELECT 'sales_orders' FROM sales_orders WHERE company IS NULL
        -- ... add other tables
    ) sub
    GROUP BY table_name
    HAVING COUNT(*) > 0;

If any rows are returned, run the backfill migration first.

Revision ID: 20251221_enforce_company_not_null
Revises: 20251221_backfill_null_company
Create Date: 2025-12-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import os

# revision identifiers, used by Alembic.
revision: str = '20251221_enforce_company_not_null'
down_revision: Union[str, None] = '20251221_backfill_null_company'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get default company from environment
DEFAULT_COMPANY = os.getenv('DEFAULT_COMPANY', 'DotMac Limited')

# High-priority tables that should have NOT NULL company
# These are core financial/transactional tables
ENFORCE_NOT_NULL_TABLES = [
    'invoices',
    'journal_entries',
    'journal_entry_items',
    'gl_entries',
    'purchase_invoices',
    'sales_orders',
    'quotations',
    'credit_notes',
    'debit_notes',
]


def upgrade() -> None:
    """Add NOT NULL constraint with default value to company columns.

    Uses ALTER COLUMN with server_default to handle existing NULL values.
    """
    conn = op.get_bind()

    for table in ENFORCE_NOT_NULL_TABLES:
        # Check if table exists
        result = conn.execute(
            f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '{table}'
            )
            """
        )
        if not result.scalar():
            print(f"  Skipping {table} (table does not exist)")
            continue

        # Check if column exists
        result = conn.execute(
            f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = '{table}'
                AND column_name = 'company'
            )
            """
        )
        if not result.scalar():
            print(f"  Skipping {table} (no company column)")
            continue

        # Check for remaining NULL values
        result = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE company IS NULL")
        null_count = result.scalar()

        if null_count > 0:
            raise RuntimeError(
                f"Cannot enforce NOT NULL on {table}.company: "
                f"{null_count} NULL values remain. "
                f"Run the backfill migration first."
            )

        # Add NOT NULL constraint with default
        print(f"  Enforcing NOT NULL on {table}.company")
        op.alter_column(
            table,
            'company',
            existing_type=sa.String(255),
            nullable=False,
            server_default=DEFAULT_COMPANY,
        )

    print("\nNOT NULL constraints enforced successfully.")


def downgrade() -> None:
    """Remove NOT NULL constraints from company columns."""
    for table in ENFORCE_NOT_NULL_TABLES:
        try:
            op.alter_column(
                table,
                'company',
                existing_type=sa.String(255),
                nullable=True,
                server_default=None,
            )
        except Exception as e:
            print(f"  Warning: Could not downgrade {table}: {e}")

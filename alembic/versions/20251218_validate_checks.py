"""validate_checks

Revision ID: 20251218_validate_checks
Revises: 20251218_checks_notvalid
Create Date: 2025-12-18

VALIDATES CHECK constraints added in previous migration.
This scans existing data but does NOT block writes.

IMPORTANT: Run schema_prechecks.py BEFORE this migration!
All blocking violations must be fixed first.

Usage:
    1. Run: python scripts/schema_prechecks.py
    2. Fix any blocking violations
    3. Run: alembic upgrade 20251218_validate_checks
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_validate_checks"
down_revision: Union[str, None] = "20251218_checks_notvalid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Validate CHECK constraints (scans data, doesn't block writes)."""

    # Validate journal entries balance check
    op.execute("ALTER TABLE journal_entries VALIDATE CONSTRAINT chk_journal_entry_balanced")

    # Validate payment allocation check
    op.execute("ALTER TABLE payments VALIDATE CONSTRAINT chk_payment_allocation_valid")

    # Validate invoice positive amounts check
    op.execute("ALTER TABLE invoices VALIDATE CONSTRAINT chk_invoice_positive")


def downgrade() -> None:
    """
    Cannot "un-validate" a constraint.
    To revert, drop and re-add as NOT VALID.
    """
    # Drop constraints
    op.execute("ALTER TABLE journal_entries DROP CONSTRAINT IF EXISTS chk_journal_entry_balanced")
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_payment_allocation_valid")
    op.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS chk_invoice_positive")

    # Re-add as NOT VALID
    op.execute("""
        ALTER TABLE journal_entries
        ADD CONSTRAINT chk_journal_entry_balanced
        CHECK (ABS(total_debit - total_credit) < 0.01)
        NOT VALID
    """)
    op.execute("""
        ALTER TABLE payments
        ADD CONSTRAINT chk_payment_allocation_valid
        CHECK (
            (amount < 0 OR (total_allocated + unallocated_amount) <= (amount + 0.01))
            AND total_allocated >= 0
            AND unallocated_amount >= 0
        )
        NOT VALID
    """)
    op.execute("""
        ALTER TABLE invoices
        ADD CONSTRAINT chk_invoice_positive
        CHECK (
            amount >= 0
            AND total_amount >= 0
            AND (balance IS NULL OR balance >= 0)
        )
        NOT VALID
    """)

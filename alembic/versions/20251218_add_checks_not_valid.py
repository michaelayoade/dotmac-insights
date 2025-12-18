"""add_checks_not_valid

Revision ID: 20251218_checks_notvalid
Revises: 20251218_idx_proj_status
Create Date: 2025-12-18

Adds CHECK constraints as NOT VALID (instant, no table scan).
This only enforces the constraint on NEW rows.
Run schema_prechecks.py and fix violations before running VALIDATE.

Constraints added:
- chk_journal_entry_balanced: total_debit ~= total_credit
- chk_payment_allocation_valid: allocations don't exceed amount
- chk_invoice_positive: invoice amounts are positive
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_checks_notvalid"
down_revision: Union[str, None] = "20251218_idx_proj_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraints as NOT VALID (instant, non-blocking)."""

    # Journal entries must be balanced (debit = credit within tolerance)
    op.execute("""
        ALTER TABLE journal_entries
        ADD CONSTRAINT chk_journal_entry_balanced
        CHECK (ABS(total_debit - total_credit) < 0.01)
        NOT VALID
    """)

    # Payment allocations: total_allocated + unallocated must not exceed amount
    op.execute("""
        ALTER TABLE payments
        ADD CONSTRAINT chk_payment_allocation_valid
        CHECK (
            (total_allocated + unallocated_amount) <= (amount + 0.01)
            AND total_allocated >= 0
            AND unallocated_amount >= 0
        )
        NOT VALID
    """)

    # Invoices must have non-negative amounts
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


def downgrade() -> None:
    """Remove CHECK constraints."""
    op.execute("ALTER TABLE journal_entries DROP CONSTRAINT IF EXISTS chk_journal_entry_balanced")
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_payment_allocation_valid")
    op.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS chk_invoice_positive")

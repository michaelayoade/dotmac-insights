"""validate_fks

Revision ID: 20251218_validate_fks
Revises: 20251218_merge_fk_cleanup
Create Date: 2025-12-18

VALIDATES FK constraints added in previous migrations.
This scans existing data to verify FK integrity but does NOT block writes.

IMPORTANT: Run schema_prechecks.py BEFORE this migration!
All FK violations must be fixed (or NULL) first.

Usage:
    1. Run: python scripts/schema_prechecks.py
    2. Fix any blocking violations (supplier_match_rate, bank_account_references)
    3. Run: alembic upgrade 20251218_validate_fks
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_validate_fks"
down_revision: Union[str, None] = "20251218_merge_fk_cleanup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Validate FK constraints (scans data, doesn't block writes)."""

    # Validate supplier FK on purchase_invoices
    op.execute(
        "ALTER TABLE purchase_invoices VALIDATE CONSTRAINT purchase_invoices_supplier_id_fkey"
    )

    # Validate bank_account FK on bank_transactions
    op.execute(
        "ALTER TABLE bank_transactions VALIDATE CONSTRAINT bank_transactions_bank_account_id_fkey"
    )

    # Validate customer FK on erpnext_leads
    op.execute(
        "ALTER TABLE erpnext_leads VALIDATE CONSTRAINT erpnext_leads_customer_id_fkey"
    )


def downgrade() -> None:
    """
    Cannot "un-validate" a constraint.
    To revert, drop and re-add as NOT VALID.
    """
    # Drop FK constraints
    op.execute(
        "ALTER TABLE purchase_invoices DROP CONSTRAINT IF EXISTS purchase_invoices_supplier_id_fkey"
    )
    op.execute(
        "ALTER TABLE bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_bank_account_id_fkey"
    )
    op.execute(
        "ALTER TABLE erpnext_leads DROP CONSTRAINT IF EXISTS erpnext_leads_customer_id_fkey"
    )

    # Re-add as NOT VALID
    op.execute("""
        ALTER TABLE purchase_invoices
        ADD CONSTRAINT purchase_invoices_supplier_id_fkey
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON DELETE SET NULL
        NOT VALID
    """)
    op.execute("""
        ALTER TABLE bank_transactions
        ADD CONSTRAINT bank_transactions_bank_account_id_fkey
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
        ON DELETE SET NULL
        NOT VALID
    """)
    op.execute("""
        ALTER TABLE erpnext_leads
        ADD CONSTRAINT erpnext_leads_customer_id_fkey
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE SET NULL
        NOT VALID
    """)

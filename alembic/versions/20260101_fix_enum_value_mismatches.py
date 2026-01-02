"""Fix enum value mismatches between Python models and database.

Revision ID: fix_enum_values_001
Revises: mikrotik_provisioning_001
Create Date: 2026-01-01

This migration adds missing enum values to align Python models with database:
- ExpenseStatus: add 'rejected'
- InvoiceSource: add 'internal'
- PaymentStatus: add 'approved', 'posted'
- PaymentSource: add 'internal'

Note: CustomerStatus has 'CANCELLED' in DB but not in Python - that's fixed
in the Python model, not here.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'fix_enum_values_001'
down_revision = 'mikrotik_provisioning_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing enum values to fix Python/DB mismatches."""

    # ExpenseStatus - Python has REJECTED but DB doesn't
    # DB has: DRAFT, PENDING, APPROVED, PAID, CANCELLED
    # Python expects: draft, pending, approved, rejected, paid, cancelled
    op.execute("ALTER TYPE expensestatus ADD VALUE IF NOT EXISTS 'rejected'")

    # InvoiceSource - Python has INTERNAL but DB only has SPLYNX, ERPNEXT
    # This allows creating invoices directly in the system
    op.execute("ALTER TYPE invoicesource ADD VALUE IF NOT EXISTS 'internal'")

    # PaymentStatus - Python has APPROVED, POSTED for workflow states
    # DB has: PENDING, COMPLETED, FAILED, REFUNDED (+ lowercase from previous migration)
    # These are needed for payment approval workflows
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'approved'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'posted'")

    # PaymentSource - Python has INTERNAL but DB only has SPLYNX, ERPNEXT
    # This allows creating payments directly in the system
    op.execute("ALTER TYPE paymentsource ADD VALUE IF NOT EXISTS 'internal'")


def downgrade():
    """Cannot remove enum values in PostgreSQL, so this is a no-op.

    To fully revert, you would need to:
    1. Create new enum types without the added values
    2. Migrate all data to use the new types
    3. Drop the old types and rename the new ones

    This is rarely needed and risky, so we leave this as no-op.
    """
    pass

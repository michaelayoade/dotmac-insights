"""Add APPROVED and POSTED to PaymentStatus enum

Revision ID: 20251218_payment_status_enum
Revises: 20251218_hierarchy_checks
Create Date: 2025-12-18

Adds new values to the paymentstatus PostgreSQL enum type to support
the AR payment approval/posting workflow:
- APPROVED: Payment approved for posting
- POSTED: Payment posted to GL

Note: PostgreSQL requires ALTER TYPE to add values to an existing enum.
Ordering is not enforced here to avoid depending on legacy label casing.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_payment_status_enum"
down_revision: Union[str, None] = "20251218_hierarchy_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add APPROVED and POSTED values to paymentstatus enum."""
    # PostgreSQL requires adding enum values one at a time
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'approved'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'posted'")


def downgrade() -> None:
    """
    Cannot remove enum values in PostgreSQL without recreating the type.

    To fully downgrade, you would need to:
    1. Create a new enum without the values
    2. Update all columns to use the new type
    3. Drop the old type

    This is destructive and not recommended. The values will remain
    but won't be used if the code is rolled back.
    """
    # No-op: PostgreSQL doesn't support removing enum values
    pass

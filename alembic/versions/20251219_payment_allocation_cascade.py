"""Add cascade policies to payment_allocations FKs

Revision ID: 20251219_payment_allocation_cascade
Revises: 20251220_merge_heads
Create Date: 2025-12-19

Updates FK actions to enforce cascading deletes:
- payment_allocations.payment_id -> payments.id (CASCADE)
- payment_allocations.supplier_payment_id -> supplier_payments.id (CASCADE)

When a payment is deleted, its allocations should also be deleted to prevent orphans.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251219_payment_allocation_cascade"
down_revision: Union[str, Sequence[str], None] = "20251220_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_if_exists(table: str, column: str) -> None:
    """Drop the FK on (table.column) if present, regardless of its generated name."""
    op.execute(
        f"""
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT tc.constraint_name INTO fk_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.constraint_schema = kcu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = current_schema()
              AND tc.table_name = '{table}'
              AND kcu.column_name = '{column}'
            LIMIT 1;

            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', fk_name);
            END IF;
        END$$;
        """
    )


def upgrade() -> None:
    """Apply cascading delete policies to payment_allocations."""
    # payment_allocations.payment_id -> payments.id ON DELETE CASCADE
    _drop_fk_if_exists("payment_allocations", "payment_id")
    op.execute(
        """
        ALTER TABLE payment_allocations
        ADD CONSTRAINT payment_allocations_payment_id_fkey
        FOREIGN KEY (payment_id) REFERENCES payments(id)
        ON DELETE CASCADE
        """
    )

    # payment_allocations.supplier_payment_id -> supplier_payments.id ON DELETE CASCADE
    _drop_fk_if_exists("payment_allocations", "supplier_payment_id")
    op.execute(
        """
        ALTER TABLE payment_allocations
        ADD CONSTRAINT payment_allocations_supplier_payment_id_fkey
        FOREIGN KEY (supplier_payment_id) REFERENCES supplier_payments(id)
        ON DELETE CASCADE
        """
    )


def downgrade() -> None:
    """Revert to the previous (no action) FK policies."""
    _drop_fk_if_exists("payment_allocations", "supplier_payment_id")
    op.execute(
        """
        ALTER TABLE payment_allocations
        ADD CONSTRAINT payment_allocations_supplier_payment_id_fkey
        FOREIGN KEY (supplier_payment_id) REFERENCES supplier_payments(id)
        """
    )

    _drop_fk_if_exists("payment_allocations", "payment_id")
    op.execute(
        """
        ALTER TABLE payment_allocations
        ADD CONSTRAINT payment_allocations_payment_id_fkey
        FOREIGN KEY (payment_id) REFERENCES payments(id)
        """
    )

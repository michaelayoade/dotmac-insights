"""Add cascade policies for FK cleanup

Revision ID: 20251218_add_cascade_policies
Revises: 20251218_merge_all_heads
Create Date: 2025-12-18

Updates FK actions to enforce cascading deletes/nulls:
- credit_notes.invoice_id -> invoices.id (CASCADE)
- corporate_card_transactions.card_id -> corporate_cards.id (CASCADE)
- payments.invoice_id -> invoices.id (SET NULL) - column already nullable
- payments.customer_id -> customers.id (SET NULL) - column already nullable
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_add_cascade_policies"
down_revision: Union[str, Sequence[str], None] = "20251218_merge_all_heads"
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
    """Apply cascading delete policies."""
    # credit_notes.invoice_id -> invoices.id ON DELETE CASCADE
    _drop_fk_if_exists("credit_notes", "invoice_id")
    op.execute(
        """
        ALTER TABLE credit_notes
        ADD CONSTRAINT credit_notes_invoice_id_fkey
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        ON DELETE CASCADE
        """
    )

    # corporate_card_transactions.card_id -> corporate_cards.id ON DELETE CASCADE
    _drop_fk_if_exists("corporate_card_transactions", "card_id")
    op.execute(
        """
        ALTER TABLE corporate_card_transactions
        ADD CONSTRAINT corporate_card_transactions_card_id_fkey
        FOREIGN KEY (card_id) REFERENCES corporate_cards(id)
        ON DELETE CASCADE
        """
    )

    # payments.invoice_id -> invoices.id ON DELETE SET NULL
    # Column is already nullable (app/models/payment.py:56)
    _drop_fk_if_exists("payments", "invoice_id")
    op.execute(
        """
        ALTER TABLE payments
        ADD CONSTRAINT payments_invoice_id_fkey
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        ON DELETE SET NULL
        """
    )

    # payments.customer_id -> customers.id ON DELETE SET NULL
    # Column is already nullable (app/models/payment.py:55)
    _drop_fk_if_exists("payments", "customer_id")
    op.execute(
        """
        ALTER TABLE payments
        ADD CONSTRAINT payments_customer_id_fkey
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    """Revert to the previous (no action) FK policies."""
    # Restore payments FKs without cascade policies
    _drop_fk_if_exists("payments", "customer_id")
    op.execute(
        """
        ALTER TABLE payments
        ADD CONSTRAINT payments_customer_id_fkey
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        """
    )

    _drop_fk_if_exists("payments", "invoice_id")
    op.execute(
        """
        ALTER TABLE payments
        ADD CONSTRAINT payments_invoice_id_fkey
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        """
    )

    _drop_fk_if_exists("corporate_card_transactions", "card_id")
    op.execute(
        """
        ALTER TABLE corporate_card_transactions
        ADD CONSTRAINT corporate_card_transactions_card_id_fkey
        FOREIGN KEY (card_id) REFERENCES corporate_cards(id)
        """
    )

    _drop_fk_if_exists("credit_notes", "invoice_id")
    op.execute(
        """
        ALTER TABLE credit_notes
        ADD CONSTRAINT credit_notes_invoice_id_fkey
        FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        """
    )

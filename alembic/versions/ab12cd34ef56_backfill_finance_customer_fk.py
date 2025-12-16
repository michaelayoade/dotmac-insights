"""Backfill finance customer FK and enforce non-null.

Revision ID: ab12cd34ef56
Revises: c3d4e5f6a7b8
Create Date: 2025-02-22
"""

from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill customer_id on finance tables and enforce NOT NULL when possible."""
    if context.is_offline_mode():
        # Skip data backfill in offline/--sql mode
        return

    conn = op.get_bind()

    # 1) Backfill invoices by parsing the customer hint embedded in invoice_number.
    #    Splynx invoice numbers end with the customer id (zero-padded).
    conn.execute(
        text(
            """
            UPDATE invoices i
            SET customer_id = c.id
            FROM customers c
            WHERE i.customer_id IS NULL
              AND i.invoice_number IS NOT NULL
              AND c.splynx_id = CAST(right(regexp_replace(i.invoice_number, '\\D', '', 'g'), 6) AS INTEGER)
            """
        )
    )

    # 2) Backfill invoices from payments that already carry a customer link.
    conn.execute(
        text(
            """
            UPDATE invoices i
            SET customer_id = p.customer_id
            FROM payments p
            WHERE i.customer_id IS NULL
              AND p.invoice_id = i.id
              AND p.customer_id IS NOT NULL
            """
        )
    )

    # 3) Propagate invoice customer -> payments.
    conn.execute(
        text(
            """
            UPDATE payments p
            SET customer_id = i.customer_id
            FROM invoices i
            WHERE p.customer_id IS NULL
              AND p.invoice_id = i.id
              AND i.customer_id IS NOT NULL
            """
        )
    )

    # 4) Propagate invoice customer -> credit notes.
    conn.execute(
        text(
            """
            UPDATE credit_notes cn
            SET customer_id = i.customer_id
            FROM invoices i
            WHERE cn.customer_id IS NULL
              AND cn.invoice_id = i.id
              AND i.customer_id IS NOT NULL
            """
        )
    )

    # Verify no null customer_id remain
    counts = {
        "invoices": conn.execute(text("SELECT count(*) FROM invoices WHERE customer_id IS NULL")).scalar() or 0,
        "payments": conn.execute(text("SELECT count(*) FROM payments WHERE customer_id IS NULL")).scalar() or 0,
        "credit_notes": conn.execute(text("SELECT count(*) FROM credit_notes WHERE customer_id IS NULL")).scalar() or 0,
    }
    remaining = {k: v for k, v in counts.items() if v > 0}
    if remaining:
        # Leave columns nullable so the API can continue serving data while upstream sync fills the gaps.
        print(f"[finance-migration] Remaining null customer_id counts: {remaining} (columns left nullable)")
        return

    # Enforce NOT NULL on customer_id columns when everything has been backfilled
    op.alter_column("invoices", "customer_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("payments", "customer_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("credit_notes", "customer_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Allow NULLs again
    op.alter_column("credit_notes", "customer_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("payments", "customer_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("invoices", "customer_id", existing_type=sa.Integer(), nullable=True)

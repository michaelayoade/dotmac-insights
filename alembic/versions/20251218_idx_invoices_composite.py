"""idx_invoices_composite

Revision ID: 20251218_idx_inv_composite
Revises: 20251218_idx_gl_composite
Create Date: 2025-12-18

Adds composite indexes on invoices for common query patterns.
Uses CREATE INDEX CONCURRENTLY to avoid table locks.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_idx_inv_composite"
down_revision: Union[str, None] = "20251218_idx_gl_composite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create composite indexes CONCURRENTLY to avoid table locks."""
    # Must run outside transaction for CONCURRENTLY
    with op.get_context().autocommit_block():
        # Index for customer invoice lookups
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_customer_posting
            ON invoices (customer_id, invoice_date)
        """)
        # Index for status filtering
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_status_posting
            ON invoices (status, invoice_date)
        """)
        # Index for due date queries (aging reports)
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_due_date
            ON invoices (due_date)
            WHERE COALESCE(balance, 0) > 0
        """)


def downgrade() -> None:
    """Drop the indexes."""
    op.execute("DROP INDEX IF EXISTS ix_invoices_customer_posting")
    op.execute("DROP INDEX IF EXISTS ix_invoices_status_posting")
    op.execute("DROP INDEX IF EXISTS ix_invoices_due_date")

"""idx_bank_transactions

Revision ID: 20251218_idx_bank_txn
Revises: 20251218_idx_inv_composite
Create Date: 2025-12-18

Adds indexes on bank_transactions for reconciliation queries.
Uses CREATE INDEX CONCURRENTLY to avoid table locks.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_idx_bank_txn"
down_revision: Union[str, None] = "20251218_idx_inv_composite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes CONCURRENTLY to avoid table locks."""
    # Must run outside transaction for CONCURRENTLY
    with op.get_context().autocommit_block():
        # Index for bank account + date queries
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bank_transactions_account_date
            ON bank_transactions (bank_account, date)
        """)
        # Index for unreconciled/pending transactions (status column)
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bank_transactions_unreconciled
            ON bank_transactions (date)
            WHERE status = 'UNRECONCILED'
        """)


def downgrade() -> None:
    """Drop the indexes."""
    op.execute("DROP INDEX IF EXISTS ix_bank_transactions_account_date")
    op.execute("DROP INDEX IF EXISTS ix_bank_transactions_unreconciled")

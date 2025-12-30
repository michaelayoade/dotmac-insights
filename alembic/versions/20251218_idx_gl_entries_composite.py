"""idx_gl_entries_composite

Revision ID: 20251218_idx_gl_composite
Revises: 20251218_idx_je_posting
Create Date: 2025-12-18

Adds composite index on gl_entries for common query patterns.
Uses CREATE INDEX CONCURRENTLY to avoid table locks.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_idx_gl_composite"
down_revision: Union[str, None] = "20251218_idx_je_posting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create composite index CONCURRENTLY to avoid table locks."""
    # Must run outside transaction for CONCURRENTLY
    with op.get_context().autocommit_block():
        # Index for common GL queries: account + posting_date (string account column)
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_gl_entries_account_posting
            ON gl_entries (account, posting_date)
        """)


def downgrade() -> None:
    """Drop the indexes."""
    op.execute("DROP INDEX IF EXISTS ix_gl_entries_account_posting")

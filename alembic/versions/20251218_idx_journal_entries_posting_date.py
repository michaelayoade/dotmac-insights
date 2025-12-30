"""idx_journal_entries_posting_date

Revision ID: 20251218_idx_je_posting
Revises: 20251218_add_domain_rbac_scopes
Create Date: 2025-12-18

Adds index on journal_entries.posting_date for date-range queries.
Uses CREATE INDEX CONCURRENTLY to avoid table locks.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_idx_je_posting"
down_revision: Union[str, None] = "20251218_add_domain_rbac_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create index CONCURRENTLY to avoid table locks."""
    # Must run outside transaction for CONCURRENTLY
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_journal_entries_posting_date
            ON journal_entries (posting_date)
        """)


def downgrade() -> None:
    """Drop the index."""
    op.execute("DROP INDEX IF EXISTS ix_journal_entries_posting_date")

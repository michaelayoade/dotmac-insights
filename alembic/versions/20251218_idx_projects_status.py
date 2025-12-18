"""idx_projects_status

Revision ID: 20251218_idx_proj_status
Revises: 20251218_idx_bank_txn
Create Date: 2025-12-18

Adds index on projects.status for status filtering queries.
Uses CREATE INDEX CONCURRENTLY to avoid blocking writes.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_idx_proj_status"
down_revision: Union[str, None] = "20251218_idx_bank_txn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create index CONCURRENTLY."""
    op.execute("COMMIT")
    # Index for status filtering
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projects_status
        ON projects (status)
    """)
    # Index for customer projects
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projects_customer
        ON projects (customer_id)
        WHERE customer_id IS NOT NULL
    """)


def downgrade() -> None:
    """Drop the indexes."""
    op.execute("DROP INDEX IF EXISTS ix_projects_status")
    op.execute("DROP INDEX IF EXISTS ix_projects_customer")

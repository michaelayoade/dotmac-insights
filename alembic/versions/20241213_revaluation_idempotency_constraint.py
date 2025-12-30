"""Add unique constraint for revaluation idempotency.

Ensures each account can only be revalued once per fiscal period per base currency.
This enforces at the DB level what fx_service.py checks at the application level.

Revision ID: 20241213_revaluation_idempotency
Revises: i4j5k6l7m8n9, 20241213_add_books_rbac_scopes (merge)
Create Date: 2024-12-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "20241213_revaluation_idempotency"
down_revision: Union[str, Sequence[str], None] = ("i4j5k6l7m8n9", "20241213_add_books_rbac_scopes")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, clean up any duplicate entries (keep the one with highest id)
    # This handles cases where duplicates were created before this constraint
    conn = op.get_bind()

    # Find and delete duplicates, keeping the latest (highest id) entry
    # Using a CTE to identify duplicates
    conn.execute(text("""
        DELETE FROM revaluation_entries
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY fiscal_period_id, account_id, base_currency
                           ORDER BY id DESC
                       ) as rn
                FROM revaluation_entries
            ) sub
            WHERE rn > 1
        )
    """))

    # Now add the unique constraint
    op.create_unique_constraint(
        "uq_revaluation_period_account_currency",
        "revaluation_entries",
        ["fiscal_period_id", "account_id", "base_currency"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_revaluation_period_account_currency",
        "revaluation_entries",
        type_="unique"
    )

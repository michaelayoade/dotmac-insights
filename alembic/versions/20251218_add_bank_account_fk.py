"""add_bank_account_fk

Revision ID: 20251218_add_bank_acct_fk
Revises: 20251218_add_supplier_fk
Create Date: 2025-12-18

Adds bank_account_id FK column to bank_transactions with backfill.
Uses NOT VALID pattern - constraint is added but not validated until separate migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251218_add_bank_acct_fk"
down_revision: Union[str, None] = "20251218_add_supplier_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bank_account_id FK column to bank_transactions with backfill."""
    # Add column
    op.add_column(
        "bank_transactions",
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
    )

    # Backfill from existing bank_account string column
    # Match on bank account name or account_number
    op.execute("""
        UPDATE bank_transactions bt
        SET bank_account_id = ba.id
        FROM bank_accounts ba
        WHERE bt.bank_account_id IS NULL
          AND bt.bank_account IS NOT NULL
          AND bt.bank_account != ''
          AND (bt.bank_account = ba.name OR bt.bank_account = ba.account_number)
    """)

    # Add index CONCURRENTLY
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bank_transactions_bank_account_id
            ON bank_transactions (bank_account_id)
        """)

    # Add FK constraint as NOT VALID (instant, no table scan)
    op.execute("""
        ALTER TABLE bank_transactions
        ADD CONSTRAINT bank_transactions_bank_account_id_fkey
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
        ON DELETE SET NULL
        NOT VALID
    """)


def downgrade() -> None:
    """Remove bank_account_id FK column."""
    op.drop_constraint(
        "bank_transactions_bank_account_id_fkey",
        "bank_transactions",
        type_="foreignkey",
    )
    op.drop_index("ix_bank_transactions_bank_account_id", "bank_transactions")
    op.drop_column("bank_transactions", "bank_account_id")

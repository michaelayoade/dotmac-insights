"""Enforce NOT NULL on journal_entry_items.account_id after backfill.

Revision ID: 20251221_enforce_journal_entry_item_account_fk
Revises: 20251221_backfill_cross_module_fks
Create Date: 2025-12-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251221_enforce_journal_entry_item_account_fk"
down_revision: Union[str, None] = "20251221_backfill_cross_module_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make journal_entry_items.account_id required once fully backfilled."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("journal_entry_items"):
        return
    columns = {col["name"] for col in inspector.get_columns("journal_entry_items")}
    if "account_id" not in columns:
        return

    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM journal_entry_items WHERE account_id IS NULL")
    ).scalar()
    if null_count:
        raise RuntimeError(
            f"journal_entry_items.account_id still NULL for {null_count} rows; "
            "backfill missing account_id values before enforcing NOT NULL."
        )

    op.alter_column("journal_entry_items", "account_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    """Allow NULLs on account_id again."""
    op.alter_column("journal_entry_items", "account_id", existing_type=sa.Integer(), nullable=True)

"""Enforce NOT NULL on suppliers.supplier_group_id after backfill.

Revision ID: 20251222_enforce_supplier_group_not_null
Revises: cc3a9f8e3ad6
Create Date: 2025-12-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251222_enforce_supplier_group_not_null"
down_revision: Union[str, None] = "20251222_backfill_supplier_group_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Require supplier_group_id once fully backfilled."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("suppliers"):
        return

    columns = {col["name"] for col in inspector.get_columns("suppliers")}
    if "supplier_group_id" not in columns:
        return

    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM suppliers WHERE supplier_group_id IS NULL")
    ).scalar()
    if null_count:
        raise RuntimeError(
            f"suppliers.supplier_group_id still NULL for {null_count} rows; "
            "backfill missing supplier_group_id values before enforcing NOT NULL."
        )

    op.alter_column(
        "suppliers",
        "supplier_group_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    """Allow NULLs on supplier_group_id again."""
    op.alter_column(
        "suppliers",
        "supplier_group_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

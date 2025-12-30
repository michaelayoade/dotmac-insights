"""Backfill NULL supplier_group_id values to default group.

Revision ID: 20251222_backfill_supplier_group_defaults
Revises: cc3a9f8e3ad6
Create Date: 2025-12-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251222_backfill_supplier_group_defaults"
down_revision: Union[str, None] = "cc3a9f8e3ad6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill suppliers with NULL supplier_group_id to default group."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("suppliers") or not inspector.has_table("supplier_groups"):
        return

    columns = {col["name"] for col in inspector.get_columns("suppliers")}
    if "supplier_group_id" not in columns:
        return

    group_id = bind.execute(
        sa.text("SELECT id FROM supplier_groups WHERE name = :name"),
        {"name": "All Supplier Groups"},
    ).scalar()

    if group_id is None:
        result = bind.execute(
            sa.text(
                """
                INSERT INTO supplier_groups (name, is_group, created_at, updated_at)
                VALUES (:name, true, NOW(), NOW())
                RETURNING id
                """
            ),
            {"name": "All Supplier Groups"},
        )
        group_id = result.scalar()

    bind.execute(
        sa.text(
            """
            UPDATE suppliers
            SET supplier_group_id = :group_id
            WHERE supplier_group_id IS NULL
            """
        ),
        {"group_id": group_id},
    )


def downgrade() -> None:
    """No-op: do not unset supplier_group_id values."""
    pass

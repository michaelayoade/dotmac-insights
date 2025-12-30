"""Add soft delete columns to supplier payments

Revision ID: 20251220_soft_delete_supplier_payments
Revises: 20251220_soft_delete_finance
Create Date: 2025-12-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251220_soft_delete_supplier_payments"
down_revision: Union[str, None] = "20251220_soft_delete_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add soft delete columns to supplier_payments."""
    inspector = sa.inspect(op.get_bind())
    existing_columns = {col["name"] for col in inspector.get_columns("supplier_payments")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("supplier_payments")}
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("supplier_payments")}

    if "is_deleted" not in existing_columns:
        op.add_column(
            "supplier_payments",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "deleted_at" not in existing_columns:
        op.add_column(
            "supplier_payments",
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
    if "deleted_by_id" not in existing_columns:
        op.add_column(
            "supplier_payments",
            sa.Column("deleted_by_id", sa.Integer(), nullable=True),
        )
    if "ix_supplier_payments_is_deleted" not in existing_indexes:
        op.create_index(
            "ix_supplier_payments_is_deleted",
            "supplier_payments",
            ["is_deleted"],
        )
    if "supplier_payments_deleted_by_id_fkey" not in existing_fks:
        op.create_foreign_key(
            "supplier_payments_deleted_by_id_fkey",
            "supplier_payments",
            "users",
            ["deleted_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Remove soft delete columns from supplier_payments."""
    op.drop_constraint("supplier_payments_deleted_by_id_fkey", "supplier_payments", type_="foreignkey")
    op.drop_index("ix_supplier_payments_is_deleted", "supplier_payments")
    op.drop_column("supplier_payments", "deleted_by_id")
    op.drop_column("supplier_payments", "deleted_at")
    op.drop_column("supplier_payments", "is_deleted")

"""Add soft delete columns to finance tables

Revision ID: 20251220_soft_delete_finance
Revises: 20251218_soft_delete
Create Date: 2025-12-20

Adds soft delete columns to invoices, payments, credit_notes, and quotations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251220_soft_delete_finance"
down_revision: Union[str, None] = "20251218_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_existing_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table_name)}


def _get_existing_indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _get_existing_fks(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def _add_soft_delete_columns(table_name: str) -> None:
    existing_columns = _get_existing_columns(table_name)
    existing_indexes = _get_existing_indexes(table_name)
    existing_fks = _get_existing_fks(table_name)

    if "is_deleted" not in existing_columns:
        op.add_column(
            table_name,
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "deleted_at" not in existing_columns:
        op.add_column(
            table_name,
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
    if "deleted_by_id" not in existing_columns:
        op.add_column(
            table_name,
            sa.Column("deleted_by_id", sa.Integer(), nullable=True),
        )
    index_name = f"ix_{table_name}_is_deleted"
    if index_name not in existing_indexes:
        op.create_index(
            index_name,
            table_name,
            ["is_deleted"],
        )
    fk_name = f"{table_name}_deleted_by_id_fkey"
    if fk_name not in existing_fks:
        op.create_foreign_key(
            fk_name,
            table_name,
            "users",
            ["deleted_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def _drop_soft_delete_columns(table_name: str) -> None:
    op.drop_constraint(f"{table_name}_deleted_by_id_fkey", table_name, type_="foreignkey")
    op.drop_index(f"ix_{table_name}_is_deleted", table_name)
    op.drop_column(table_name, "deleted_by_id")
    op.drop_column(table_name, "deleted_at")
    op.drop_column(table_name, "is_deleted")


def upgrade() -> None:
    """Add soft delete columns to finance tables."""
    _add_soft_delete_columns("invoices")
    _add_soft_delete_columns("payments")
    _add_soft_delete_columns("credit_notes")
    _add_soft_delete_columns("quotations")


def downgrade() -> None:
    """Remove soft delete columns from finance tables."""
    _drop_soft_delete_columns("quotations")
    _drop_soft_delete_columns("credit_notes")
    _drop_soft_delete_columns("payments")
    _drop_soft_delete_columns("invoices")

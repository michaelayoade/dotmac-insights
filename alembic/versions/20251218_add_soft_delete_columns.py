"""add_soft_delete_columns

Revision ID: 20251218_soft_delete
Revises: 20251218_lead_customer_fk
Create Date: 2025-12-18

Adds soft delete columns to customers and employees tables.
Enables soft deletion instead of hard delete for records with dependencies.

Columns added:
- is_deleted: Boolean flag indicating soft deletion
- deleted_at: Timestamp of deletion
- deleted_by_id: FK to users who performed the deletion
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251218_soft_delete"
down_revision: Union[str, None] = "20251218_lead_customer_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add soft delete columns to customers and employees."""
    # Customers table
    op.add_column(
        "customers",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "customers",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("deleted_by_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_customers_is_deleted",
        "customers",
        ["is_deleted"],
    )
    op.create_foreign_key(
        "customers_deleted_by_id_fkey",
        "customers",
        "users",
        ["deleted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Employees table
    op.add_column(
        "employees",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "employees",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("deleted_by_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_employees_is_deleted",
        "employees",
        ["is_deleted"],
    )
    op.create_foreign_key(
        "employees_deleted_by_id_fkey",
        "employees",
        "users",
        ["deleted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove soft delete columns."""
    # Employees
    op.drop_constraint("employees_deleted_by_id_fkey", "employees", type_="foreignkey")
    op.drop_index("ix_employees_is_deleted", "employees")
    op.drop_column("employees", "deleted_by_id")
    op.drop_column("employees", "deleted_at")
    op.drop_column("employees", "is_deleted")

    # Customers
    op.drop_constraint("customers_deleted_by_id_fkey", "customers", type_="foreignkey")
    op.drop_index("ix_customers_is_deleted", "customers")
    op.drop_column("customers", "deleted_by_id")
    op.drop_column("customers", "deleted_at")
    op.drop_column("customers", "is_deleted")

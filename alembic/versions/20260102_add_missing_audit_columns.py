"""Add missing audit columns to high-traffic tables

Revision ID: add_audit_cols_001
Revises: 99b8a398e3dd
Create Date: 2026-01-02

Adds missing created_by_id, updated_by_id, deleted_by_id columns
to ensure all high-traffic tables have complete audit trail.

New columns added:
- bank_transactions: updated_by_id, deleted_by_id
- attendances: deleted_by_id
- invoices: updated_by_id
- customers: created_by_id, updated_by_id
- salary_slips: deleted_by_id
- purchase_invoices: updated_by_id, deleted_by_id
"""
from alembic import op
import sqlalchemy as sa


revision = "add_audit_cols_001"
down_revision = "99b8a398e3dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bank_transactions: add updated_by_id, deleted_by_id
    op.add_column(
        "bank_transactions",
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("deleted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # attendances: add deleted_by_id
    op.add_column(
        "attendances",
        sa.Column("deleted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # invoices: add updated_by_id
    op.add_column(
        "invoices",
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # customers: add created_by_id, updated_by_id
    op.add_column(
        "customers",
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # salary_slips: add deleted_by_id
    op.add_column(
        "salary_slips",
        sa.Column("deleted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # purchase_invoices: add updated_by_id, deleted_by_id
    op.add_column(
        "purchase_invoices",
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("deleted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column("purchase_invoices", "deleted_by_id")
    op.drop_column("purchase_invoices", "updated_by_id")
    op.drop_column("salary_slips", "deleted_by_id")
    op.drop_column("customers", "updated_by_id")
    op.drop_column("customers", "created_by_id")
    op.drop_column("invoices", "updated_by_id")
    op.drop_column("attendances", "deleted_by_id")
    op.drop_column("bank_transactions", "deleted_by_id")
    op.drop_column("bank_transactions", "updated_by_id")

"""add supplier links to payments

Revision ID: 7c1e2d2f9b21
Revises: f5545281ad87
Create Date: 2025-03-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c1e2d2f9b21"
down_revision: Union[str, None] = "f5545281ad87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("purchase_invoice_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_payments_supplier_id"), "payments", ["supplier_id"], unique=False)
    op.create_index(op.f("ix_payments_purchase_invoice_id"), "payments", ["purchase_invoice_id"], unique=False)
    op.create_foreign_key(
        "fk_payments_supplier_id_suppliers",
        "payments",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_payments_purchase_invoice_id_purchase_invoices",
        "payments",
        "purchase_invoices",
        ["purchase_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_purchase_invoice_id_purchase_invoices", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_supplier_id_suppliers", "payments", type_="foreignkey")
    op.drop_index(op.f("ix_payments_purchase_invoice_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_supplier_id"), table_name="payments")
    op.drop_column("payments", "purchase_invoice_id")
    op.drop_column("payments", "supplier_id")

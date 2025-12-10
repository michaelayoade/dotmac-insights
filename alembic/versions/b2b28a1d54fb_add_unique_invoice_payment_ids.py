"""Add unique partial indexes for cross-system IDs on invoices and payments

Revision ID: b2b28a1d54fb
Revises: 8e621ec9f6ad
Create Date: 2026-01-20 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2b28a1d54fb"
down_revision: Union[str, None] = "8e621ec9f6ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Invoices
    op.create_index(
        "uq_invoices_splynx_id_not_null",
        "invoices",
        ["splynx_id"],
        unique=True,
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )
    op.create_index(
        "uq_invoices_erpnext_id_not_null",
        "invoices",
        ["erpnext_id"],
        unique=True,
        postgresql_where=sa.text("erpnext_id IS NOT NULL"),
    )

    # Payments
    op.create_index(
        "uq_payments_splynx_id_not_null",
        "payments",
        ["splynx_id"],
        unique=True,
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payments_erpnext_id_not_null",
        "payments",
        ["erpnext_id"],
        unique=True,
        postgresql_where=sa.text("erpnext_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_erpnext_id_not_null", table_name="payments")
    op.drop_index("uq_payments_splynx_id_not_null", table_name="payments")
    op.drop_index("uq_invoices_erpnext_id_not_null", table_name="invoices")
    op.drop_index("uq_invoices_splynx_id_not_null", table_name="invoices")

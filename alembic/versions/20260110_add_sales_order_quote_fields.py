"""Add sales order and quotation contact fields.

Revision ID: 20260110_add_sales_order_quote_fields
Revises: 20260105_merge_all_heads_v2
Create Date: 2026-01-10 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_add_sales_order_quote_fields"
down_revision: Union[str, Sequence[str], None] = "20260105_merge_all_heads_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("quotation_id", sa.Integer(), nullable=True))
    op.add_column("sales_orders", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("contact_phone", sa.String(length=50), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_address", sa.Text(), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_address", sa.Text(), nullable=True))
    op.create_index("ix_sales_orders_quotation_id", "sales_orders", ["quotation_id"], unique=False)
    op.create_foreign_key(
        "fk_sales_orders_quotation_id",
        "sales_orders",
        "quotations",
        ["quotation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("quotations", sa.Column("customer_account_id", sa.BigInteger(), nullable=True))
    op.add_column("quotations", sa.Column("lead_id", sa.Integer(), nullable=True))
    op.add_column("quotations", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("contact_phone", sa.String(length=50), nullable=True))
    op.add_column("quotations", sa.Column("billing_address", sa.Text(), nullable=True))
    op.add_column("quotations", sa.Column("shipping_address", sa.Text(), nullable=True))
    op.create_index("ix_quotations_customer_account_id", "quotations", ["customer_account_id"], unique=False)
    op.create_index("ix_quotations_lead_id", "quotations", ["lead_id"], unique=False)
    op.create_foreign_key(
        "fk_quotations_customer_account_id",
        "quotations",
        "customer_accounts",
        ["customer_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_quotations_lead_id",
        "quotations",
        "erpnext_leads",
        ["lead_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_quotations_lead_id", "quotations", type_="foreignkey")
    op.drop_constraint("fk_quotations_customer_account_id", "quotations", type_="foreignkey")
    op.drop_index("ix_quotations_lead_id", table_name="quotations")
    op.drop_index("ix_quotations_customer_account_id", table_name="quotations")
    op.drop_column("quotations", "shipping_address")
    op.drop_column("quotations", "billing_address")
    op.drop_column("quotations", "contact_phone")
    op.drop_column("quotations", "contact_email")
    op.drop_column("quotations", "contact_name")
    op.drop_column("quotations", "lead_id")
    op.drop_column("quotations", "customer_account_id")

    op.drop_constraint("fk_sales_orders_quotation_id", "sales_orders", type_="foreignkey")
    op.drop_index("ix_sales_orders_quotation_id", table_name="sales_orders")
    op.drop_column("sales_orders", "shipping_address")
    op.drop_column("sales_orders", "billing_address")
    op.drop_column("sales_orders", "contact_phone")
    op.drop_column("sales_orders", "contact_email")
    op.drop_column("sales_orders", "contact_name")
    op.drop_column("sales_orders", "quotation_id")

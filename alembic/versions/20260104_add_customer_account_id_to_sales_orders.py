"""Add customer_account_id to sales_orders

Revision ID: add_cust_acct_so
Revises: merge_cleaning_automation
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_cust_acct_so"
down_revision: Union[str, None] = "7c9d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("sales_orders")}
    if "customer_account_id" not in columns:
        op.add_column(
            "sales_orders",
            sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
        )

    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("sales_orders") if fk.get("name")}
    if "fk_sales_orders_customer_account" not in fk_names:
        op.create_foreign_key(
            "fk_sales_orders_customer_account",
            "sales_orders",
            "customer_accounts",
            ["customer_account_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("sales_orders") if fk.get("name")}
    if "fk_sales_orders_customer_account" in fk_names:
        op.drop_constraint("fk_sales_orders_customer_account", "sales_orders", type_="foreignkey")

    columns = {col["name"] for col in inspector.get_columns("sales_orders")}
    if "customer_account_id" in columns:
        op.drop_column("sales_orders", "customer_account_id")

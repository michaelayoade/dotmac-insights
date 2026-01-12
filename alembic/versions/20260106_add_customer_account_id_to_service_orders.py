"""Add customer_account_id to service_orders.

Revision ID: y2z3a4b5c6d7
Revises: x1y2z3a4b5c6
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa

revision = "y2z3a4b5c6d7"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = [c["name"] for c in connection.execute(sa.text(
        "SELECT column_name as name FROM information_schema.columns "
        "WHERE table_name = 'service_orders'"
    )).mappings().all()]

    if "customer_account_id" not in columns:
        op.add_column(
            "service_orders",
            sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
        )
        op.create_index(
            "ix_service_orders_customer_account_id",
            "service_orders",
            ["customer_account_id"],
        )
        op.create_foreign_key(
            "fk_service_orders_customer_account_id",
            "service_orders",
            "customer_accounts",
            ["customer_account_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint("fk_service_orders_customer_account_id", "service_orders", type_="foreignkey")
    op.drop_index("ix_service_orders_customer_account_id", table_name="service_orders")
    op.drop_column("service_orders", "customer_account_id")

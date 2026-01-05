"""Add customer_account_id links to invoices and payments.

Revision ID: 20260102_add_customer_account_links
Revises: 20260102_unified_identity
Create Date: 2026-01-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260102_add_customer_account_links"
down_revision = "20260102_unified_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_invoices_customer_account_id",
        "invoices",
        ["customer_account_id"],
    )
    op.create_foreign_key(
        "fk_invoices_customer_account_id",
        "invoices",
        "customer_accounts",
        ["customer_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "payments",
        sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_payments_customer_account_id",
        "payments",
        ["customer_account_id"],
    )
    op.create_foreign_key(
        "fk_payments_customer_account_id",
        "payments",
        "customer_accounts",
        ["customer_account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_customer_account_id", "payments", type_="foreignkey")
    op.drop_index("ix_payments_customer_account_id", table_name="payments")
    op.drop_column("payments", "customer_account_id")

    op.drop_constraint("fk_invoices_customer_account_id", "invoices", type_="foreignkey")
    op.drop_index("ix_invoices_customer_account_id", table_name="invoices")
    op.drop_column("invoices", "customer_account_id")

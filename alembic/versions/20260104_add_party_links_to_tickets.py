"""Add customer_account_id and party_id to tickets.

This migration adds FK columns to link tickets to the unified party model.

Revision ID: 20260104_add_party_links_to_tickets
Revises: 20260105_merge_all_heads_v2
Create Date: 2026-01-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260104_add_party_links_to_tickets"
down_revision = "20260105_merge_all_heads_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add customer_account_id column
    op.add_column(
        "tickets",
        sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_tickets_customer_account_id",
        "tickets",
        ["customer_account_id"],
    )
    op.create_foreign_key(
        "fk_tickets_customer_account_id",
        "tickets",
        "customer_accounts",
        ["customer_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add party_id column
    op.add_column(
        "tickets",
        sa.Column("party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_tickets_party_id",
        "tickets",
        ["party_id"],
    )
    op.create_foreign_key(
        "fk_tickets_party_id",
        "tickets",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tickets_party_id", "tickets", type_="foreignkey")
    op.drop_index("ix_tickets_party_id", table_name="tickets")
    op.drop_column("tickets", "party_id")

    op.drop_constraint("fk_tickets_customer_account_id", "tickets", type_="foreignkey")
    op.drop_index("ix_tickets_customer_account_id", table_name="tickets")
    op.drop_column("tickets", "customer_account_id")

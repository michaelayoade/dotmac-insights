"""Add customer_account_id to conversations.

Revision ID: 20260102_add_conversation_customer_account
Revises: 20260102_backfill_customer_account_links
Create Date: 2026-01-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260102_add_conversation_customer_account"
down_revision = "20260102_backfill_customer_account_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_conversations_customer_account_id",
        "conversations",
        ["customer_account_id"],
    )
    op.create_foreign_key(
        "fk_conversations_customer_account_id",
        "conversations",
        "customer_accounts",
        ["customer_account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_customer_account_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_customer_account_id", table_name="conversations")
    op.drop_column("conversations", "customer_account_id")

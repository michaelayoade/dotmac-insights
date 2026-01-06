"""Add party_id to Splynx administrators and ERPNext leads.

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2025-01-12 09:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "u1v2w3x4y5z6"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "administrators",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_administrators_party_id", "administrators", ["party_id"])

    op.add_column(
        "erpnext_leads",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_erpnext_leads_party_id", "erpnext_leads", ["party_id"])

    connection = op.get_bind()
    has_customer_account_id = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'erpnext_leads' AND column_name = 'customer_account_id'"
        )
    ).first()
    if has_customer_account_id:
        connection.execute(
            sa.text(
                "UPDATE erpnext_leads el "
                "SET party_id = ca.party_id "
                "FROM customer_accounts ca "
                "WHERE el.party_id IS NULL "
                "AND el.customer_account_id = ca.id "
                "AND ca.party_id IS NOT NULL"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_erpnext_leads_party_id", table_name="erpnext_leads")
    op.drop_column("erpnext_leads", "party_id")

    op.drop_index("ix_administrators_party_id", table_name="administrators")
    op.drop_column("administrators", "party_id")

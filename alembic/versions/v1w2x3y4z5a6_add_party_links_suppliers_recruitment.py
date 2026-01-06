"""Add party_id to suppliers and recruitment tables.

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2025-01-12 10:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "v1w2x3y4z5a6"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_suppliers_party_id", "suppliers", ["party_id"])

    op.add_column(
        "job_applicants",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_job_applicants_party_id", "job_applicants", ["party_id"])

    op.add_column(
        "job_offers",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_job_offers_party_id", "job_offers", ["party_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE suppliers s "
            "SET party_id = sa.party_id "
            "FROM supplier_accounts sa "
            "WHERE s.party_id IS NULL "
            "AND sa.supplier_id = s.id "
            "AND sa.party_id IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE job_offers jo "
            "SET party_id = ja.party_id "
            "FROM job_applicants ja "
            "WHERE jo.party_id IS NULL "
            "AND jo.job_applicant_id = ja.id "
            "AND ja.party_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_job_offers_party_id", table_name="job_offers")
    op.drop_column("job_offers", "party_id")

    op.drop_index("ix_job_applicants_party_id", table_name="job_applicants")
    op.drop_column("job_applicants", "party_id")

    op.drop_index("ix_suppliers_party_id", table_name="suppliers")
    op.drop_column("suppliers", "party_id")

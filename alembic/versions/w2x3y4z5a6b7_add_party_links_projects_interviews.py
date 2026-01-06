"""Add party_id to project users and interviews.

Revision ID: w2x3y4z5a6b7
Revises: 86f7fc4f5a6d
Create Date: 2025-01-12 11:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "w2x3y4z5a6b7"
down_revision = "86f7fc4f5a6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_users",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_project_users_party_id", "project_users", ["party_id"])

    op.add_column(
        "interviews",
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_interviews_party_id", "interviews", ["party_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE interviews i "
            "SET party_id = ja.party_id "
            "FROM job_applicants ja "
            "WHERE i.party_id IS NULL "
            "AND i.job_applicant_id = ja.id "
            "AND ja.party_id IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE project_users pu "
            "SET party_id = p.id "
            "FROM parties p "
            "WHERE pu.party_id IS NULL "
            "AND pu.email IS NOT NULL "
            "AND lower(pu.email) = lower(p.primary_email) "
            "AND p.primary_email IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE project_users pu "
            "SET party_id = eu.party_id "
            "FROM erpnext_users eu "
            "WHERE pu.party_id IS NULL "
            "AND eu.party_id IS NOT NULL "
            "AND (pu.user = eu.erpnext_id OR pu.user = eu.email OR pu.erpnext_name = eu.erpnext_id OR pu.erpnext_name = eu.email)"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE project_users pu "
            "SET party_id = e.party_id "
            "FROM erpnext_users eu "
            "JOIN employees e ON e.id = eu.employee_id "
            "WHERE pu.party_id IS NULL "
            "AND e.party_id IS NOT NULL "
            "AND (pu.user = eu.erpnext_id OR pu.user = eu.email OR pu.erpnext_name = eu.erpnext_id OR pu.erpnext_name = eu.email)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_interviews_party_id", table_name="interviews")
    op.drop_column("interviews", "party_id")

    op.drop_index("ix_project_users_party_id", table_name="project_users")
    op.drop_column("project_users", "party_id")

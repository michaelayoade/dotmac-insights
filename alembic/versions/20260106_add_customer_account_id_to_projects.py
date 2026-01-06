"""Add customer_account_id to projects.

Revision ID: x1y2z3a4b5c6
Revises: w2x3y4z5a6b7
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa

revision = "x1y2z3a4b5c6"
down_revision = "20260220_merge_job_applicant_party_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists
    connection = op.get_bind()
    columns = [c["name"] for c in connection.execute(sa.text(
        "SELECT column_name as name FROM information_schema.columns "
        "WHERE table_name = 'projects'"
    )).mappings().all()]

    if "customer_account_id" not in columns:
        op.add_column(
            "projects",
            sa.Column("customer_account_id", sa.BigInteger(), nullable=True),
        )
        op.create_index(
            "ix_projects_customer_account_id",
            "projects",
            ["customer_account_id"],
        )
        op.create_foreign_key(
            "fk_projects_customer_account_id",
            "projects",
            "customer_accounts",
            ["customer_account_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint("fk_projects_customer_account_id", "projects", type_="foreignkey")
    op.drop_index("ix_projects_customer_account_id", table_name="projects")
    op.drop_column("projects", "customer_account_id")

"""Add party_id to job_openings.

Revision ID: z3a4b5c6d7e8
Revises: y2z3a4b5c6d7
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa

revision = "z3a4b5c6d7e8"
down_revision = "20260301_merge_support_automation_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = [c["name"] for c in connection.execute(sa.text(
        "SELECT column_name as name FROM information_schema.columns "
        "WHERE table_name = 'job_openings'"
    )).mappings().all()]

    if "party_id" not in columns:
        op.add_column(
            "job_openings",
            sa.Column("party_id", sa.BigInteger(), nullable=True),
        )
        op.create_index(
            "ix_job_openings_party_id",
            "job_openings",
            ["party_id"],
        )
        op.create_foreign_key(
            "fk_job_openings_party_id",
            "job_openings",
            "parties",
            ["party_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint("fk_job_openings_party_id", "job_openings", type_="foreignkey")
    op.drop_index("ix_job_openings_party_id", table_name="job_openings")
    op.drop_column("job_openings", "party_id")

"""Add party_id to job applicants

Revision ID: 20260220_add_party_id_job_applicants
Revises: 86f7fc4f5a6d
Create Date: 2026-02-20 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260220_add_party_id_job_applicants"
down_revision: Union[str, None] = "86f7fc4f5a6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("job_applicants")}
    if "party_id" not in columns:
        op.add_column("job_applicants", sa.Column("party_id", sa.BigInteger(), nullable=True))
    indexes = {idx["name"] for idx in inspector.get_indexes("job_applicants")}
    if "ix_job_applicants_party_id" not in indexes:
        op.create_index("ix_job_applicants_party_id", "job_applicants", ["party_id"])
    fks = {fk.get("name") for fk in inspector.get_foreign_keys("job_applicants")}
    if "fk_job_applicants_party_id" not in fks:
        op.create_foreign_key(
            "fk_job_applicants_party_id",
            "job_applicants",
            "parties",
            ["party_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    fks = {fk.get("name") for fk in inspector.get_foreign_keys("job_applicants")}
    if "fk_job_applicants_party_id" in fks:
        op.drop_constraint("fk_job_applicants_party_id", "job_applicants", type_="foreignkey")
    indexes = {idx["name"] for idx in inspector.get_indexes("job_applicants")}
    if "ix_job_applicants_party_id" in indexes:
        op.drop_index("ix_job_applicants_party_id", table_name="job_applicants")
    columns = {col["name"] for col in inspector.get_columns("job_applicants")}
    if "party_id" in columns:
        op.drop_column("job_applicants", "party_id")

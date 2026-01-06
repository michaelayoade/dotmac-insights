"""Merge job applicant party heads

Revision ID: 20260220_merge_job_applicant_party_heads
Revises: 20260220_add_party_id_job_applicants, w2x3y4z5a6b7
Create Date: 2026-02-20 10:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260220_merge_job_applicant_party_heads"
down_revision: Union[str, None] = ("20260220_add_party_id_job_applicants", "w2x3y4z5a6b7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

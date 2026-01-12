"""Add is_active to leave_types

Revision ID: 20260301_add_leave_type_is_active
Revises: 20260220_merge_job_applicant_party_heads
Create Date: 2026-03-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260301_add_leave_type_is_active"
down_revision: Union[str, None] = "20260220_merge_job_applicant_party_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active soft-delete flag to leave_types."""
    op.add_column(
        "leave_types",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    """Remove is_active from leave_types."""
    op.drop_column("leave_types", "is_active")

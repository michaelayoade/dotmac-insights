"""Merge support_automation heads

Revision ID: 20260301_merge_support_automation_heads
Revises: y2z3a4b5c6d7, 20260301_add_leave_type_is_active
Create Date: 2026-03-01 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260301_merge_support_automation_heads"
down_revision: Union[str, None] = ("y2z3a4b5c6d7", "20260301_add_leave_type_is_active")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads."""
    pass


def downgrade() -> None:
    """Split heads."""
    pass

"""Merge expense, support, and settings heads

Revision ID: 20250307_merge_all_heads
Revises: 20240920_add_expense_management, 20241213_csat, l7m8n9o0p1q2
Create Date: 2025-03-07
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20250307_merge_all_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20240920_add_expense_management",
    "20241213_csat",
    "l7m8n9o0p1q2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge point only; no schema changes.
    pass


def downgrade() -> None:
    # Merge point only; no schema changes.
    pass

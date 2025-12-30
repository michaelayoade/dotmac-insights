"""Merge HR and notification heads

Revision ID: 20250205_merge_heads
Revises: 20241213_notification_system, 20241213_hr_audit
Create Date: 2025-02-05
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250205_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("20241213_notification_system", "20241213_hr_audit")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge point; no-op.
    pass


def downgrade() -> None:
    # Merge point; no-op.
    pass

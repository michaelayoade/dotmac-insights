"""merge_fk_cleanup

Revision ID: 20251218_merge_fk_cleanup
Revises: 20251217_merge_all_module_heads, 20251218_soft_delete
Create Date: 2025-12-18

Merges FK cleanup migrations with main module heads.
"""
from typing import Sequence, Union


revision: str = "20251218_merge_fk_cleanup"
down_revision: Union[str, Sequence[str]] = (
    "20251217_merge_all_module_heads",
    "20251218_soft_delete",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point - no operations."""
    pass


def downgrade() -> None:
    """Merge point - no operations."""
    pass

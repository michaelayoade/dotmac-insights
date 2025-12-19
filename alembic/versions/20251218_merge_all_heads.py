"""Merge all migration heads

Revision ID: 20251218_merge_all_heads
Revises: 20251218_add_outbound_sync, add_unified_ticket_backlinks, 20251218_validate_fks
Create Date: 2025-12-18

Merges all migration branches into a single head:
- 20251218_add_outbound_sync (outbound sync columns)
- add_unified_ticket_backlinks (unified ticket FK backlinks)
- 20251218_validate_fks (FK validation)
"""
from typing import Sequence, Union


revision: str = "20251218_merge_all_heads"
down_revision: Union[str, Sequence[str]] = (
    "20251218_add_outbound_sync",
    "add_unified_ticket_backlinks",
    "20251218_validate_fks",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point - no operations."""
    pass


def downgrade() -> None:
    """Merge point - no operations."""
    pass

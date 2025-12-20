"""Merge support automation, vehicles, and support RBAC heads.

Revision ID: 20251220_merge_support_heads
Revises: 20241220_add_vehicles, 20251219_payment_allocation_cascade, 20251220_add_support_rbac
Create Date: 2025-12-20
"""
from typing import Sequence, Union


revision: str = "20251220_merge_support_heads"
down_revision: Union[str, Sequence[str]] = (
    "20241220_add_vehicles",
    "20251219_payment_allocation_cascade",
    "20251220_add_support_rbac",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point - no operations."""
    pass


def downgrade() -> None:
    """Merge point - no operations."""
    pass

"""Merge current migration heads

Revision ID: 20251220_merge_heads
Revises: 20251218_payment_status_enum, n9o0p1q2r3s4, n1o2p3q4r5s6, 20251220_soft_delete_supplier_payments
Create Date: 2025-12-20
"""
from typing import Sequence, Union


revision: str = "20251220_merge_heads"
down_revision: Union[str, Sequence[str]] = (
    "20251218_payment_status_enum",
    "n9o0p1q2r3s4",
    "n1o2p3q4r5s6",
    "20251220_soft_delete_supplier_payments",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point - no operations."""
    pass


def downgrade() -> None:
    """Merge point - no operations."""
    pass

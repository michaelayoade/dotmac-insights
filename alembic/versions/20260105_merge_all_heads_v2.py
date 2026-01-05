"""Merge all current heads

Revision ID: 20260105_merge_all_heads_v2
Revises: 20241215_merge_books_payroll, 5bde4be2482f, snmp001_add_monitoring,
8e621ec9f6ad, fcaad815e605, cc3a9f8e3ad6, 20260105_merge_all_heads,
c3d4e5f6a7b8, c32bdad740a3, add_cust_acct_so
Create Date: 2026-01-05 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260105_merge_all_heads_v2'
down_revision: Union[str, Sequence[str], None] = (
    '20241215_merge_books_payroll',
    '5bde4be2482f',
    'snmp001_add_monitoring',
    '8e621ec9f6ad',
    'fcaad815e605',
    'cc3a9f8e3ad6',
    '20260105_merge_all_heads',
    'c3d4e5f6a7b8',
    'c32bdad740a3',
    'add_cust_acct_so',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""Merge all heads after marketing models

Revision ID: 20260105_merge_all_heads
Revises: fix_enum_values_001, 20260101_validate_erp_fks, add_unified_ticket_backlinks,
20241213_csat, n1o2p3q4r5s6, add_order_line_items, 20241213_hr_audit,
20241220_add_vehicles, merge_uc003_perf001, n9o0p1q2r3s4, crm_001,
data_cleanup_001, customer_contact_migration_001, marketing_001, chatwoot_metrics_001
Create Date: 2026-01-05 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260105_merge_all_heads'
down_revision: Union[str, Sequence[str], None] = (
    'fix_enum_values_001',
    '20260101_validate_erp_fks',
    'add_unified_ticket_backlinks',
    '20241213_csat',
    'n1o2p3q4r5s6',
    'add_order_line_items',
    '20241213_hr_audit',
    '20241220_add_vehicles',
    'merge_uc003_perf001',
    'n9o0p1q2r3s4',
    'crm_001',
    'data_cleanup_001',
    'customer_contact_migration_001',
    'marketing_001',
    'chatwoot_metrics_001',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""Merge all module heads into single chain

This migration resolves all diverging heads:
- 20251215_add_customer_address_to_invoices (sync columns)
- asset_mgmt_001 (asset management)
- 20251216_inbox_enhancements (inbox/omni)
- inv_enhance_001 (inventory enhancements)
- 20251217_add_crm_project_kpis (CRM/Projects KPIs, end of unified contact chain)

Revision ID: 20251217_merge_all_module_heads
Revises: 20251215_add_customer_address_to_invoices, asset_mgmt_001, 20251216_inbox_enhancements, inv_enhance_001, 20251217_add_crm_project_kpis
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20251217_merge_all_module_heads'
down_revision = (
    '20251215_add_customer_address_to_invoices',
    'asset_mgmt_001',
    '20251216_inbox_enhancements',
    'inv_enhance_001',
    '20251217_add_crm_project_kpis',
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge point - no schema changes needed."""
    pass


def downgrade() -> None:
    """Merge point - no schema changes needed."""
    pass

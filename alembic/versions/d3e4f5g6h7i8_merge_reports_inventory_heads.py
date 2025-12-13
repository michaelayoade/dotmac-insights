"""merge_reports_inventory_heads

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7, 20240908_customers_audit_writeback
Create Date: 2025-12-12 17:30:00.000000

Merge the reports permission and all audit writeback branches.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5g6h7i8'
down_revision: Union[str, Sequence[str], None] = ('c2d3e4f5g6h7', '20240909_financial_audit_writeback')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no operations needed."""
    pass


def downgrade() -> None:
    """Merge migration - no operations needed."""
    pass

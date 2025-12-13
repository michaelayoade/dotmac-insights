"""merge_audit_reports

Revision ID: h3i4j5k6l7m8
Revises: 20240911_purchase_invoice_audit_writeback, d3e4f5g6h7i8
Create Date: 2025-12-12 17:50:00.000000

Merge the audit writeback and reports branches.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'h3i4j5k6l7m8'
down_revision: Union[str, Sequence[str]] = ('20240911_purchase_invoice_audit_writeback', 'd3e4f5g6h7i8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

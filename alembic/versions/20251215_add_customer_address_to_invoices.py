"""Add customer_address column to invoices for sync.

Revision ID: 20251215_add_customer_address_to_invoices
Revises: 20251215_add_missing_columns_for_sync
Create Date: 2025-12-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251215_add_customer_address_to_invoices"
down_revision: Union[str, None] = "20251215_add_missing_columns_for_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS customer_address TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS customer_address")

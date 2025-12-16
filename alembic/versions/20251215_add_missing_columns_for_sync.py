"""Add missing columns used by sync tasks (customer_tax_id, tags, base_currency).

Revision ID: 20251215_add_missing_columns_for_sync
Revises: 20250307_merge_all_heads
Create Date: 2025-12-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20251215_add_missing_columns_for_sync"
down_revision: Union[str, None] = "20250307_merge_all_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS guards to allow reruns when columns were added manually.
    op.execute(
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS customer_tax_id VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS tags JSONB"
    )
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS base_currency VARCHAR(10) NOT NULL DEFAULT 'NGN'"
    )
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS base_amount NUMERIC(18,4) NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    # Drop only if present to remain symmetric with upgrade guards.
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS base_amount")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS base_currency")
    op.execute("ALTER TABLE tickets DROP COLUMN IF EXISTS tags")
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS customer_tax_id")

"""drop legacy contact indexes

Revision ID: 20178a73eace
Revises: d1dc290281d5
Create Date: 2026-01-02 15:02:34.323020

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20178a73eace'
down_revision: Union[str, None] = 'd1dc290281d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_lead_qualification;")
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_outstanding_balance_positive;")
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_tags_gin;")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unified_contacts_lead_qualification "
        "ON contacts (lead_qualification);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unified_contacts_outstanding_balance_positive "
        "ON contacts (outstanding_balance) WHERE outstanding_balance > 0;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unified_contacts_tags_gin "
        "ON contacts USING gin (tags);"
    )

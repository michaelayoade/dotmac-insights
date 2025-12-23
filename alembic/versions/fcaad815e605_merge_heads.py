"""merge heads

Revision ID: fcaad815e605
Revises: add_order_line_items, 20251221_enforce_company_not_null, 20251221_enforce_journal_entry_item_account_fk
Create Date: 2025-12-21 17:21:50.733479

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcaad815e605'
down_revision: Union[str, None] = ('add_order_line_items', '20251221_enforce_company_not_null', '20251221_enforce_journal_entry_item_account_fk')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

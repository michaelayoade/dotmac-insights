"""merge sales order fields

Revision ID: ef390db26fdd
Revises: t1u2v3w4x5y6, 20260110_add_sales_order_quote_fields
Create Date: 2026-01-06 03:48:46.192446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef390db26fdd'
down_revision: Union[str, None] = ('t1u2v3w4x5y6', '20260110_add_sales_order_quote_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

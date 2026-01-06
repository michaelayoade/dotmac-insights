"""merge heads

Revision ID: 86f7fc4f5a6d
Revises: launcher001_user_prefs, 20260110_add_structured_addresses_sales, v1w2x3y4z5a6
Create Date: 2026-01-06 04:36:03.368334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86f7fc4f5a6d'
down_revision: Union[str, None] = ('launcher001_user_prefs', '20260110_add_structured_addresses_sales', 'v1w2x3y4z5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

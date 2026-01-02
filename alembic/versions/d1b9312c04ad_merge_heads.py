"""merge heads

Revision ID: d1b9312c04ad
Revises: audit_indexes_001, 5fbb4d717a6d
Create Date: 2026-01-02 16:52:16.587127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1b9312c04ad'
down_revision: Union[str, None] = ('audit_indexes_001', '5fbb4d717a6d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

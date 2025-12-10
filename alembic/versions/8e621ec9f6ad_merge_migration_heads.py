"""Merge migration heads

Revision ID: 8e621ec9f6ad
Revises: 68bd5601a1ae, 7a3a6ab2d8df
Create Date: 2025-12-09 14:08:42.169348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e621ec9f6ad'
down_revision: Union[str, None] = ('68bd5601a1ae', '7a3a6ab2d8df')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""merge subscription lifecycle and support automation heads

Revision ID: f804051a528a
Revises: 7f3c2a1b9d0e, 5d97e6ab8475
Create Date: 2026-01-03 10:44:54.270541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f804051a528a'
down_revision: Union[str, None] = ('7f3c2a1b9d0e', '5d97e6ab8475')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

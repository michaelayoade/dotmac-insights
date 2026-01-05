"""merge cleaning ops and support automation heads

Revision ID: 7c9d1e2f3a4b
Revises: 20260103_cleaning_ops, c0ffee123456
Create Date: 2026-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9d1e2f3a4b'
down_revision: Union[str, None] = ('20260103_cleaning_ops', 'c0ffee123456')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""merge inventory branch

Revision ID: 49cb88c33c38
Revises: f1a2b3c4d5e6, ab12cd34ef56
Create Date: 2025-12-12 12:42:39.712211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49cb88c33c38'
down_revision: Union[str, None] = ('f1a2b3c4d5e6', 'ab12cd34ef56')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

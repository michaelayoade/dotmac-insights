"""merge heads

Revision ID: 18f951bfba37
Revises: dc5bb4595c87, 20260112_migrate_field_team_members_party
Create Date: 2026-01-05 07:47:06.876388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18f951bfba37'
down_revision: Union[str, None] = ('dc5bb4595c87', '20260112_migrate_field_team_members_party')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

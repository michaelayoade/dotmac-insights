"""merge tickets audit fks

Revision ID: 92f0d830518f
Revises: d1b9312c04ad, tickets_audit_fks_001
Create Date: 2026-01-02 17:00:52.859277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f0d830518f'
down_revision: Union[str, None] = ('d1b9312c04ad', 'tickets_audit_fks_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

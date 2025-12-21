"""merge heads

Revision ID: fa02400b5de5
Revises: 20251220_seed_support_rbac, 20251221_add_dashboard_indexes
Create Date: 2025-12-21 06:49:44.825082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa02400b5de5'
down_revision: Union[str, None] = ('20251220_seed_support_rbac', '20251221_add_dashboard_indexes')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

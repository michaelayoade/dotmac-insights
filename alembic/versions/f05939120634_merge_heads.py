"""merge heads

Revision ID: f05939120634
Revises: perf_indexes_001, rbac_seed_001
Create Date: 2026-01-01 16:38:23.237652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f05939120634'
down_revision: Union[str, None] = ('perf_indexes_001', 'rbac_seed_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

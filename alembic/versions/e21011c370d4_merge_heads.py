"""merge heads

Revision ID: e21011c370d4
Revises: customer_contact_migration_001, f05939120634
Create Date: 2026-01-01 17:25:40.811181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e21011c370d4'
down_revision: Union[str, None] = ('customer_contact_migration_001', 'f05939120634')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

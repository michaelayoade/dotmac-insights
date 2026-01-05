"""drop legacy customers contacts

Revision ID: 5d97e6ab8475
Revises: f85bf5868197
Create Date: 2026-01-03 00:16:02.858710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d97e6ab8475'
down_revision: Union[str, None] = 'f85bf5868197'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.execute("DROP TABLE IF EXISTS contacts CASCADE;")


def downgrade() -> None:
    raise NotImplementedError("Dropping legacy customers/contacts is irreversible.")

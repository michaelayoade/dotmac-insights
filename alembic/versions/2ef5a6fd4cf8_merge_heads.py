"""merge heads

Revision ID: 2ef5a6fd4cf8
Revises: 20260101_validate_erp_fks, 20260102_backfill_conversation_customer_account
Create Date: 2026-01-02 10:33:46.640259

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ef5a6fd4cf8'
down_revision: Union[str, None] = ('20260101_validate_erp_fks', '20260102_backfill_conversation_customer_account')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

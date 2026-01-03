"""merge heads

Revision ID: f85bf5868197
Revises: 20260102_add_missing_core_tables, supplier_accounts_001, party_integration_002, b3c9e1a7f4b2
Create Date: 2026-01-03 00:15:52.348055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f85bf5868197'
down_revision: Union[str, None] = ('20260102_add_missing_core_tables', 'supplier_accounts_001', 'party_integration_002', 'b3c9e1a7f4b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

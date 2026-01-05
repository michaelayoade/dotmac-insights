"""merge_heads

Revision ID: dc5bb4595c87
Revises: 20260104_add_party_links_to_tickets, 20260106_add_marketing_rbac, 20260111_add_activity_log
Create Date: 2026-01-05 06:48:12.652036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc5bb4595c87'
down_revision: Union[str, None] = ('20260104_add_party_links_to_tickets', '20260106_add_marketing_rbac', '20260111_add_activity_log')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

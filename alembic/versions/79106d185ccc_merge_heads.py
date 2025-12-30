"""merge heads

Revision ID: 79106d185ccc
Revises: 20251224_rename_unified_contact_to_contact, fix_enum_case_001
Create Date: 2025-12-30 09:52:20.664792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79106d185ccc'
down_revision: Union[str, None] = ('20251224_rename_unified_contact_to_contact', 'fix_enum_case_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

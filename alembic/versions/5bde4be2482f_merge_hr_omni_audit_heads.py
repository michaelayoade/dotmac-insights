"""merge_hr_omni_audit_heads

Revision ID: 5bde4be2482f
Revises: 20240914_projects_tickets_audit_writeback, 20240920_add_omni_core, 20241215_hr_module
Create Date: 2025-12-13 07:51:10.237736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bde4be2482f'
down_revision: Union[str, None] = ('20240914_projects_tickets_audit_writeback', '20240920_add_omni_core', '20241215_hr_module')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

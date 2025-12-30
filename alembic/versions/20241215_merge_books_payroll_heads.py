"""Merge books settings and payroll payment heads

Revision ID: 20241215_merge_books_payroll
Revises: 20241213_books_settings_number_formats, 20241214_003
Create Date: 2024-12-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241215_merge_books_payroll'
down_revision: Union[str, Sequence[str], None] = ('20241213_books_settings_number_formats', '20241214_003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

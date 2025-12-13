"""Add geolocation and device fields to Attendance model

Revision ID: 20241214_001
Revises: 20241215_hr_module
Create Date: 2024-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241214_001'
down_revision: Union[str, None] = '20241215_hr_module'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add geolocation and device fields to attendances table
    op.add_column('attendances', sa.Column('check_in_latitude', sa.Float(), nullable=True))
    op.add_column('attendances', sa.Column('check_in_longitude', sa.Float(), nullable=True))
    op.add_column('attendances', sa.Column('check_out_latitude', sa.Float(), nullable=True))
    op.add_column('attendances', sa.Column('check_out_longitude', sa.Float(), nullable=True))
    op.add_column('attendances', sa.Column('device_info', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove geolocation and device fields from attendances table
    op.drop_column('attendances', 'device_info')
    op.drop_column('attendances', 'check_out_longitude')
    op.drop_column('attendances', 'check_out_latitude')
    op.drop_column('attendances', 'check_in_longitude')
    op.drop_column('attendances', 'check_in_latitude')

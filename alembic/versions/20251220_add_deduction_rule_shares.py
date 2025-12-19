"""Add employee/employer share fields for BOTH applicability rules

Revision ID: n1o2p3q4r5s6
Revises: m8n9o0p1q2r4
Create Date: 2025-12-20 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'n1o2p3q4r5s6'
down_revision = 'm8n9o0p1q2r4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: these columns and constraint were already created in 20251219_add_payroll_config.py
    pass


def downgrade() -> None:
    # No-op: corresponding to the no-op upgrade
    pass

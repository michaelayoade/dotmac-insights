"""Add payment tracking and void fields to SalarySlip, expand status enum

Revision ID: 20241214_003
Revises: 20241214_002
Create Date: 2024-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241214_003'
down_revision: Union[str, None] = '20241214_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add payment tracking fields to salary_slips table
    op.add_column('salary_slips', sa.Column('paid_at', sa.DateTime(), nullable=True))
    op.add_column('salary_slips', sa.Column('paid_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('salary_slips', sa.Column('payment_reference', sa.String(255), nullable=True))
    op.add_column('salary_slips', sa.Column('payment_mode', sa.String(100), nullable=True))

    # Add void tracking fields to salary_slips table
    op.add_column('salary_slips', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('salary_slips', sa.Column('voided_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('salary_slips', sa.Column('void_reason', sa.String(500), nullable=True))

    # Note: SalarySlipStatus uses VARCHAR column, not PostgreSQL enum.
    # New status values can be used directly without schema changes.


def downgrade() -> None:
    # Remove void tracking fields from salary_slips table
    op.drop_column('salary_slips', 'void_reason')
    op.drop_column('salary_slips', 'voided_by_id')
    op.drop_column('salary_slips', 'voided_at')

    # Remove payment tracking fields from salary_slips table
    op.drop_column('salary_slips', 'payment_mode')
    op.drop_column('salary_slips', 'payment_reference')
    op.drop_column('salary_slips', 'paid_by_id')
    op.drop_column('salary_slips', 'paid_at')

    # Note: Removing enum values from PostgreSQL is complex and not recommended
    # The new values will remain but won't cause issues

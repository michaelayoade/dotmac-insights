"""add_credit_notes

Revision ID: f064b5d7a2ab
Revises: 92ae185149b7
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f064b5d7a2ab'
down_revision: Union[str, None] = '92ae185149b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'credit_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('splynx_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('credit_number', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'ISSUED', 'APPLIED', 'CANCELLED', name='creditnotestatus'), nullable=True),
        sa.Column('issue_date', sa.DateTime(), nullable=True),
        sa.Column('applied_date', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credit_notes_credit_number'), 'credit_notes', ['credit_number'], unique=False)
    op.create_index(op.f('ix_credit_notes_id'), 'credit_notes', ['id'], unique=False)
    op.create_index(op.f('ix_credit_notes_splynx_id'), 'credit_notes', ['splynx_id'], unique=True)
    op.create_index(op.f('ix_credit_notes_status'), 'credit_notes', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_credit_notes_status'), table_name='credit_notes')
    op.drop_index(op.f('ix_credit_notes_splynx_id'), table_name='credit_notes')
    op.drop_index(op.f('ix_credit_notes_id'), table_name='credit_notes')
    op.drop_index(op.f('ix_credit_notes_credit_number'), table_name='credit_notes')
    op.drop_table('credit_notes')

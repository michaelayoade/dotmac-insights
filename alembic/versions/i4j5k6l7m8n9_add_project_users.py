"""add_project_users

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2025-12-12 17:55:00.000000

Add project_users child table for project team members.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i4j5k6l7m8n9'
down_revision: Union[str, Sequence[str]] = ('h3i4j5k6l7m8', '20240912_purchase_orders_debit_notes_audit')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('project_status', sa.String(100), nullable=True),
        sa.Column('view_attachments', sa.Boolean(), default=True),
        sa.Column('welcome_email_sent', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
    )
    op.create_index('ix_project_users_project_id', 'project_users', ['project_id'])
    op.create_index('ix_project_users_user', 'project_users', ['user'])


def downgrade() -> None:
    op.drop_index('ix_project_users_user', table_name='project_users')
    op.drop_index('ix_project_users_project_id', table_name='project_users')
    op.drop_table('project_users')

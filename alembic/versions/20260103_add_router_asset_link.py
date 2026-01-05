"""add router asset link

Revision ID: 20260103_asset_router
Revises:
Create Date: 2026-01-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260103_asset_router'
down_revision: Union[str, None] = 'f9a3b7c2d5e8'  # After NOC alerting tables
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add asset_id foreign key to routers table
    op.add_column(
        'routers',
        sa.Column('asset_id', sa.Integer(), nullable=True)
    )
    op.create_index(
        'ix_routers_asset_id',
        'routers',
        ['asset_id']
    )
    op.create_foreign_key(
        'fk_routers_asset_id',
        'routers',
        'assets',
        ['asset_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_routers_asset_id', 'routers', type_='foreignkey')
    op.drop_index('ix_routers_asset_id', 'routers')
    op.drop_column('routers', 'asset_id')

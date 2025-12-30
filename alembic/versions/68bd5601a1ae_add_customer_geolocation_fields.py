"""add_customer_geolocation_fields

Revision ID: 68bd5601a1ae
Revises: f5545281ad87
Create Date: 2025-12-09 13:22:36.143124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68bd5601a1ae'
down_revision: Union[str, None] = 'f5545281ad87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new geolocation columns to customers table
    op.add_column('customers', sa.Column('country', sa.String(100), nullable=True, server_default='Nigeria'))
    op.add_column('customers', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('customers', sa.Column('longitude', sa.Float(), nullable=True))

    # Add indexes for city, state (for filtering/grouping)
    op.create_index('ix_customers_city', 'customers', ['city'])
    op.create_index('ix_customers_state', 'customers', ['state'])

    # Add indexes for geolocation (for geo queries)
    op.create_index('ix_customers_latitude', 'customers', ['latitude'])
    op.create_index('ix_customers_longitude', 'customers', ['longitude'])

    # Composite index for geo queries
    op.create_index('ix_customers_lat_lng', 'customers', ['latitude', 'longitude'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_customers_lat_lng', table_name='customers')
    op.drop_index('ix_customers_longitude', table_name='customers')
    op.drop_index('ix_customers_latitude', table_name='customers')
    op.drop_index('ix_customers_state', table_name='customers')
    op.drop_index('ix_customers_city', table_name='customers')

    # Drop columns
    op.drop_column('customers', 'longitude')
    op.drop_column('customers', 'latitude')
    op.drop_column('customers', 'country')

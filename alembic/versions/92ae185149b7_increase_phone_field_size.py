"""increase_phone_field_size

Revision ID: 92ae185149b7
Revises: 200efd647fe2
Create Date: 2025-12-08 21:55:43.901043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92ae185149b7'
down_revision: Union[str, None] = '200efd647fe2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Increase field sizes to accommodate Splynx data with multiple values
    op.alter_column('customers', 'phone',
                    existing_type=sa.String(50),
                    type_=sa.String(255),
                    existing_nullable=True)
    op.alter_column('customers', 'phone_secondary',
                    existing_type=sa.String(50),
                    type_=sa.String(255),
                    existing_nullable=True)
    op.alter_column('customers', 'city',
                    existing_type=sa.String(100),
                    type_=sa.String(255),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('customers', 'phone',
                    existing_type=sa.String(255),
                    type_=sa.String(50),
                    existing_nullable=True)
    op.alter_column('customers', 'phone_secondary',
                    existing_type=sa.String(255),
                    type_=sa.String(50),
                    existing_nullable=True)
    op.alter_column('customers', 'city',
                    existing_type=sa.String(255),
                    type_=sa.String(100),
                    existing_nullable=True)

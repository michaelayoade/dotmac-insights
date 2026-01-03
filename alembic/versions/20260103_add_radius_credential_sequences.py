"""add radius credential sequences

Revision ID: radius_cred_seq_001
Revises: f85bf5868197
Create Date: 2026-01-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'radius_cred_seq_001'
down_revision: Union[str, None] = 'f85bf5868197'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'radius_credential_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sequence_name', sa.String(length=100), nullable=False,
                  comment='Unique sequence identifier (e.g., default, or per-company)'),
        sa.Column('current_value', sa.Integer(), nullable=False, server_default='0',
                  comment='Current counter value'),
        sa.Column('prefix', sa.String(length=50), nullable=False, server_default='USER',
                  comment='Username prefix (e.g., USER for USER0001)'),
        sa.Column('padding_length', sa.Integer(), nullable=False, server_default='4',
                  comment='Zero-padding length (4 = 0001)'),
        sa.Column('company', sa.String(length=50), nullable=True,
                  comment='Company scope for multi-tenant'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_name'),
        sa.CheckConstraint('padding_length >= 1 AND padding_length <= 10'),
        sa.CheckConstraint('current_value >= 0'),
    )
    op.create_index('ix_radius_cred_seq_name', 'radius_credential_sequences', ['sequence_name'])
    op.create_index('ix_radius_cred_seq_company', 'radius_credential_sequences', ['company'])

    # Insert default sequence
    op.execute("""
        INSERT INTO radius_credential_sequences (sequence_name, prefix, padding_length)
        VALUES ('default', 'USER', 4)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('ix_radius_cred_seq_company', table_name='radius_credential_sequences')
    op.drop_index('ix_radius_cred_seq_name', table_name='radius_credential_sequences')
    op.drop_table('radius_credential_sequences')

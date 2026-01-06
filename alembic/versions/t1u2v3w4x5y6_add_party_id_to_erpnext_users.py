"""Add party_id to ERPNext users

Revision ID: t1u2v3w4x5y6
Revises: r7s8t9u0v1w2
Create Date: 2025-01-10 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 't1u2v3w4x5y6'
down_revision = 'r7s8t9u0v1w2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'erpnext_users',
        sa.Column(
            'party_id',
            sa.BigInteger(),
            sa.ForeignKey('parties.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_erpnext_users_party_id', 'erpnext_users', ['party_id'])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE erpnext_users eu "
            "SET party_id = e.party_id "
            "FROM employees e "
            "WHERE eu.party_id IS NULL "
            "AND eu.employee_id = e.id "
            "AND e.party_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index('ix_erpnext_users_party_id', table_name='erpnext_users')
    op.drop_column('erpnext_users', 'party_id')

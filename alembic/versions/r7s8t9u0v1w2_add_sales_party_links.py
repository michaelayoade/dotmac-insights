"""Add party_id to sales persons and sales orders

Revision ID: r7s8t9u0v1w2
Revises: p1q2r3s4t5u6
Create Date: 2025-01-10 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'r7s8t9u0v1w2'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'sales_persons',
        sa.Column(
            'party_id',
            sa.BigInteger(),
            sa.ForeignKey('parties.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_sales_persons_party_id', 'sales_persons', ['party_id'])

    op.add_column(
        'sales_orders',
        sa.Column(
            'party_id',
            sa.BigInteger(),
            sa.ForeignKey('parties.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_sales_orders_party_id', 'sales_orders', ['party_id'])

    connection = op.get_bind()

    connection.execute(
        sa.text(
            "UPDATE sales_persons sp "
            "SET employee_id = e.id "
            "FROM employees e "
            "WHERE sp.employee_id IS NULL "
            "AND sp.employee IS NOT NULL "
            "AND e.erpnext_id = sp.employee"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE sales_persons sp "
            "SET party_id = e.party_id "
            "FROM employees e "
            "WHERE sp.party_id IS NULL "
            "AND sp.employee_id = e.id "
            "AND e.party_id IS NOT NULL"
        )
    )

    connection.execute(
        sa.text(
            "UPDATE sales_orders so "
            "SET party_id = ca.party_id "
            "FROM customer_accounts ca "
            "WHERE so.party_id IS NULL "
            "AND so.customer_account_id = ca.id "
            "AND ca.party_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index('ix_sales_orders_party_id', table_name='sales_orders')
    op.drop_column('sales_orders', 'party_id')

    op.drop_index('ix_sales_persons_party_id', table_name='sales_persons')
    op.drop_column('sales_persons', 'party_id')

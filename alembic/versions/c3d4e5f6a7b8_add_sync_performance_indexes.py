"""Add sync performance indexes for duplicate checking

Revision ID: c3d4e5f6a7b8
Revises: b2b28a1d54fb
Create Date: 2025-12-11

These indexes optimize the duplicate-checking queries used during sync,
particularly the ERPNext invoice soft-match query that was causing timeouts.
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2b28a1d54fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        # Skip index creation in offline/--sql mode
        return

    conn = op.get_bind()

    # Helper to create index if it doesn't exist
    def create_index_if_not_exists(name, table, columns, **kwargs):
        result = conn.execute(sa.text(
            f"SELECT 1 FROM pg_indexes WHERE indexname = '{name}'"
        ))
        if result.fetchone() is None:
            op.create_index(name, table, columns, **kwargs)

    # Composite index for ERPNext invoice duplicate checking (soft match)
    # Query: source=SPLYNX, customer_id=X, total_amount=Y, date(invoice_date)=Z, erpnext_id IS NULL
    # Uses functional index on date(invoice_date) since query uses date() function
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_invoices_erpnext_soft_match'"
    ))
    if result.fetchone() is None:
        conn.execute(sa.text("""
            CREATE INDEX ix_invoices_erpnext_soft_match
            ON invoices (source, customer_id, total_amount, date(invoice_date))
            WHERE erpnext_id IS NULL
        """))

    # Index for invoices without erpnext_id (speeds up NULL checks)
    create_index_if_not_exists(
        'ix_invoices_erpnext_id_null',
        'invoices',
        ['erpnext_id'],
        postgresql_where=sa.text("erpnext_id IS NULL"),
    )

    # Composite index for payment duplicate checking
    create_index_if_not_exists(
        'ix_payments_splynx_lookup',
        'payments',
        ['splynx_id'],
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )

    # Index for customer lookups by erpnext_id
    create_index_if_not_exists(
        'ix_customers_erpnext_id',
        'customers',
        ['erpnext_id'],
        postgresql_where=sa.text("erpnext_id IS NOT NULL"),
    )

    # Composite index for subscription duplicate checking
    create_index_if_not_exists(
        'ix_subscriptions_splynx_lookup',
        'subscriptions',
        ['splynx_id'],
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )

    # Index for ticket duplicate checking
    create_index_if_not_exists(
        'ix_tickets_splynx_lookup',
        'tickets',
        ['splynx_id'],
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )

    # Index for credit notes duplicate checking
    create_index_if_not_exists(
        'ix_credit_notes_splynx_lookup',
        'credit_notes',
        ['splynx_id'],
        postgresql_where=sa.text("splynx_id IS NOT NULL"),
    )


def downgrade() -> None:
    if context.is_offline_mode():
        return

    conn = op.get_bind()

    def drop_index_if_exists(name, table):
        result = conn.execute(sa.text(
            f"SELECT 1 FROM pg_indexes WHERE indexname = '{name}'"
        ))
        if result.fetchone() is not None:
            op.drop_index(name, table_name=table)

    drop_index_if_exists('ix_credit_notes_splynx_lookup', 'credit_notes')
    drop_index_if_exists('ix_tickets_splynx_lookup', 'tickets')
    drop_index_if_exists('ix_subscriptions_splynx_lookup', 'subscriptions')
    drop_index_if_exists('ix_customers_erpnext_id', 'customers')
    drop_index_if_exists('ix_payments_splynx_lookup', 'payments')
    drop_index_if_exists('ix_invoices_erpnext_id_null', 'invoices')
    drop_index_if_exists('ix_invoices_erpnext_soft_match', 'invoices')

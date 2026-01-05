"""Add performance indexes for common query patterns

Revision ID: perf_indexes_001
Revises: e12634e8e3aa
Create Date: 2026-01-01 16:00:00.000000

Indexes added based on performance review:
- invoice.customer_id (common filter)
- invoice.due_date (aging queries)
- invoice.status (list filtering)
- supplier_payment.supplier_id (common filter)
- gl_entry.account (balance calculations)
- customer.email (data quality queries)
- customer.status (list filtering)
- unified_ticket.status + priority (support dashboard)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'perf_indexes_001'
down_revision = 'e12634e8e3aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Invoice indexes for AR aging and filtering
    op.create_index(
        'ix_invoice_customer_id',
        'invoices',
        ['customer_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_invoice_due_date',
        'invoices',
        ['due_date'],
        if_not_exists=True
    )
    op.create_index(
        'ix_invoice_status',
        'invoices',
        ['status'],
        if_not_exists=True
    )
    # Composite index for common AR aging query pattern
    op.create_index(
        'ix_invoice_status_due_date',
        'invoices',
        ['status', 'due_date'],
        if_not_exists=True
    )

    # Supplier payment index for AP queries
    op.create_index(
        'ix_supplier_payment_supplier_id',
        'supplier_payments',
        ['supplier_id'],
        if_not_exists=True
    )

    # GL Entry index for balance calculations
    op.create_index(
        'ix_gl_entry_account',
        'gl_entries',
        ['account'],
        if_not_exists=True
    )
    # Composite index for ledger queries
    op.create_index(
        'ix_gl_entry_posting_date_account',
        'gl_entries',
        ['posting_date', 'account'],
        if_not_exists=True
    )

    # Customer indexes for data quality and filtering
    op.create_index(
        'ix_customer_email',
        'customers',
        ['email'],
        if_not_exists=True
    )
    op.create_index(
        'ix_customer_status',
        'customers',
        ['status'],
        if_not_exists=True
    )

    # Support ticket composite index for dashboard queries
    op.create_index(
        'ix_unified_ticket_status_priority',
        'unified_tickets',
        ['status', 'priority'],
        if_not_exists=True
    )
    op.create_index(
        'ix_unified_ticket_assigned_status',
        'unified_tickets',
        ['assigned_to_id', 'status'],
        if_not_exists=True
    )


def downgrade() -> None:
    # Remove indexes in reverse order
    op.drop_index('ix_unified_ticket_assigned_status', table_name='unified_tickets', if_exists=True)
    op.drop_index('ix_unified_ticket_status_priority', table_name='unified_tickets', if_exists=True)
    op.drop_index('ix_customer_status', table_name='customers', if_exists=True)
    op.drop_index('ix_customer_email', table_name='customers', if_exists=True)
    op.drop_index('ix_gl_entry_posting_date_account', table_name='gl_entries', if_exists=True)
    op.drop_index('ix_gl_entry_account', table_name='gl_entries', if_exists=True)
    op.drop_index('ix_supplier_payment_supplier_id', table_name='supplier_payments', if_exists=True)
    op.drop_index('ix_invoice_status_due_date', table_name='invoices', if_exists=True)
    op.drop_index('ix_invoice_status', table_name='invoices', if_exists=True)
    op.drop_index('ix_invoice_due_date', table_name='invoices', if_exists=True)
    op.drop_index('ix_invoice_customer_id', table_name='invoices', if_exists=True)

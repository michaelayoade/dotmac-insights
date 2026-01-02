"""Add audit column indexes for high-traffic tables

Revision ID: audit_indexes_001
Revises: add_audit_cols_001
Create Date: 2026-01-02

Creates indexes on all audit columns (created_by_id, updated_by_id, deleted_by_id)
for all high-traffic tables.

Tables covered (27 indexes total):
- payments: created_by_id, updated_by_id, deleted_by_id
- bank_transactions: created_by_id, updated_by_id, deleted_by_id
- attendances: created_by_id, updated_by_id, deleted_by_id
- tickets: created_by_id, updated_by_id, deleted_by_id
- invoices: created_by_id, updated_by_id, deleted_by_id
- credit_notes: created_by_id, updated_by_id, deleted_by_id
- customers: created_by_id, updated_by_id, deleted_by_id
- salary_slips: created_by_id, updated_by_id, deleted_by_id
- purchase_invoices: created_by_id, updated_by_id, deleted_by_id
"""
from alembic import op
from sqlalchemy import text


revision = "audit_indexes_001"
down_revision = "add_audit_cols_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # payments (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payments_created_by_id ON payments (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payments_updated_by_id ON payments (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payments_deleted_by_id ON payments (deleted_by_id)"
    ))

    # bank_transactions (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_created_by_id ON bank_transactions (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_updated_by_id ON bank_transactions (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_deleted_by_id ON bank_transactions (deleted_by_id)"
    ))

    # attendances (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_attendances_created_by_id ON attendances (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_attendances_updated_by_id ON attendances (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_attendances_deleted_by_id ON attendances (deleted_by_id)"
    ))

    # tickets (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tickets_created_by_id ON tickets (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tickets_updated_by_id ON tickets (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tickets_deleted_by_id ON tickets (deleted_by_id)"
    ))

    # invoices (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_invoices_created_by_id ON invoices (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_invoices_updated_by_id ON invoices (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_invoices_deleted_by_id ON invoices (deleted_by_id)"
    ))

    # credit_notes (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_credit_notes_created_by_id ON credit_notes (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_credit_notes_updated_by_id ON credit_notes (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_credit_notes_deleted_by_id ON credit_notes (deleted_by_id)"
    ))

    # customers (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_customers_created_by_id ON customers (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_customers_updated_by_id ON customers (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_customers_deleted_by_id ON customers (deleted_by_id)"
    ))

    # salary_slips (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_salary_slips_created_by_id ON salary_slips (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_salary_slips_updated_by_id ON salary_slips (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_salary_slips_deleted_by_id ON salary_slips (deleted_by_id)"
    ))

    # purchase_invoices (3 indexes)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_purchase_invoices_created_by_id ON purchase_invoices (created_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_purchase_invoices_updated_by_id ON purchase_invoices (updated_by_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_purchase_invoices_deleted_by_id ON purchase_invoices (deleted_by_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop all 27 indexes
    tables = [
        "purchase_invoices", "salary_slips", "customers", "credit_notes",
        "invoices", "tickets", "attendances", "bank_transactions", "payments"
    ]
    columns = ["deleted_by_id", "updated_by_id", "created_by_id"]

    for table in tables:
        for col in columns:
            conn.execute(text(f"DROP INDEX IF EXISTS ix_{table}_{col}"))

"""Add performance indexes for common query patterns.

Optimizes:
- GL entry aggregations by account with date/cancelled filters
- Stock ledger queries by item/warehouse
- Invoice aging and dunning queries
- Bank transaction reconciliation
- Approval workflow lookups

Revision ID: 20241213_performance_indexes
Revises: 20241213_revaluation_idempotency
Create Date: 2024-12-13
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "20241213_performance_indexes"
down_revision: Union[str, None] = "20241213_revaluation_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to make migration idempotent
    conn = op.get_bind()

    # ==========================================================================
    # GL ENTRIES - Heavy aggregation workload
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_gl_entries_reporting ON gl_entries (is_cancelled, posting_date, account)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_gl_entries_party_ledger ON gl_entries (party_type, party, posting_date)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_gl_entries_voucher_date ON gl_entries (voucher_type, voucher_no, posting_date)"
    ))

    # ==========================================================================
    # STOCK LEDGER ENTRIES - Inventory valuation queries
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_sle_stock_balance ON stock_ledger_entries (item_code, warehouse, is_cancelled)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_sle_valuation ON stock_ledger_entries (item_code, warehouse, posting_date, id)"
    ))

    # ==========================================================================
    # INVOICES - AR aging and dunning
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_invoices_aging ON invoices (status, due_date)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_invoices_customer_ar ON invoices (customer_id, status)"
    ))

    # ==========================================================================
    # BANK TRANSACTIONS - Reconciliation
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bank_txn_reconciliation ON bank_transactions (bank_account, status, date)"
    ))

    # ==========================================================================
    # APPROVAL WORKFLOW - Pending approvals
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_doc_approvals_pending ON document_approvals (status, current_step, doctype)"
    ))

    # ==========================================================================
    # FISCAL PERIODS - Period lookups
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_fiscal_periods_date_lookup ON fiscal_periods (start_date, end_date, status)"
    ))

    # ==========================================================================
    # EXCHANGE RATES - Rate lookups
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_exchange_rates_latest ON exchange_rates (from_currency, to_currency, rate_date DESC)"
    ))

    # ==========================================================================
    # PURCHASE INVOICES - AP aging
    # ==========================================================================
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_purchase_invoices_aging ON purchase_invoices (status, due_date, is_deleted)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_purchase_invoices_supplier ON purchase_invoices (supplier, status, is_deleted)"
    ))



def downgrade() -> None:
    conn = op.get_bind()
    # Drop all indexes (IF EXISTS for safety)
    conn.execute(text("DROP INDEX IF EXISTS ix_purchase_invoices_supplier"))
    conn.execute(text("DROP INDEX IF EXISTS ix_purchase_invoices_aging"))
    conn.execute(text("DROP INDEX IF EXISTS ix_exchange_rates_latest"))
    conn.execute(text("DROP INDEX IF EXISTS ix_fiscal_periods_date_lookup"))
    conn.execute(text("DROP INDEX IF EXISTS ix_doc_approvals_pending"))
    conn.execute(text("DROP INDEX IF EXISTS ix_bank_txn_reconciliation"))
    conn.execute(text("DROP INDEX IF EXISTS ix_invoices_customer_ar"))
    conn.execute(text("DROP INDEX IF EXISTS ix_invoices_aging"))
    conn.execute(text("DROP INDEX IF EXISTS ix_sle_valuation"))
    conn.execute(text("DROP INDEX IF EXISTS ix_sle_stock_balance"))
    conn.execute(text("DROP INDEX IF EXISTS ix_gl_entries_voucher_date"))
    conn.execute(text("DROP INDEX IF EXISTS ix_gl_entries_party_ledger"))
    conn.execute(text("DROP INDEX IF EXISTS ix_gl_entries_reporting"))

"""Add dashboard and FK indexes for core finance/support tables.

Revision ID: 20251221_add_dashboard_indexes
Revises: 20251220_add_contact_and_expense_indexes
Create Date: 2025-12-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251221_add_dashboard_indexes"
down_revision: Union[str, Sequence[str]] = "20251220_add_contact_and_expense_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes supporting dashboard and high-traffic queries."""
    # Payments: collections & trends
    op.create_index(
        "ix_payments_status_date_currency",
        "payments",
        ["status", "payment_date", "currency"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_payments_status_date",
        "payments",
        ["status", "payment_date"],
        unique=False,
    )

    # Invoices: AR outstanding & aging
    op.create_index(
        "ix_invoices_status_currency",
        "invoices",
        ["status", "currency"],
        unique=False,
    )
    op.create_index(
        "ix_invoices_due_status_currency",
        "invoices",
        ["due_date", "status", "currency"],
        unique=False,
        postgresql_where=sa.text("status IN ('PENDING','OVERDUE','PARTIALLY_PAID')"),
    )

    # Purchase invoices: AP outstanding & overdue
    op.create_index(
        "ix_purchase_invoices_status_date_currency",
        "purchase_invoices",
        ["status", "posting_date", "currency"],
        unique=False,
        postgresql_where=sa.text("outstanding_amount > 0"),
    )
    op.create_index(
        "ix_purchase_invoices_due_status",
        "purchase_invoices",
        ["due_date", "status"],
        unique=False,
        postgresql_where=sa.text("outstanding_amount > 0"),
    )
    op.create_index(
        "ix_purchase_invoices_supplier_outstanding",
        "purchase_invoices",
        ["supplier_name", sa.text("outstanding_amount DESC")],
        unique=False,
    )

    # Subscriptions: MRR by status/currency
    op.create_index(
        "ix_subscriptions_status_currency",
        "subscriptions",
        ["status", "currency"],
        unique=False,
    )

    # GL entries: payment entry lookups & account balances
    op.create_index(
        "ix_gl_entries_voucher_party_cancelled",
        "gl_entries",
        ["voucher_type", "party_type", "is_cancelled", sa.text("posting_date DESC")],
        unique=False,
    )
    op.create_index(
        "ix_gl_entries_account_cancelled_date",
        "gl_entries",
        ["account", "is_cancelled", "posting_date"],
        unique=False,
    )

    # Unified tickets: SLA & category analysis
    op.create_index(
        "ix_unified_tickets_status_resolution_created",
        "unified_tickets",
        ["status", "resolution_by", "created_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('open','in_progress','waiting')"),
    )
    op.create_index(
        "ix_unified_tickets_category_created",
        "unified_tickets",
        ["category", "created_at"],
        unique=False,
    )

    # Accounts: balance sheet grouping
    op.create_index(
        "ix_accounts_root_type_disabled",
        "accounts",
        ["root_type", "disabled"],
        unique=False,
    )

    # Foreign keys: high-traffic tables
    op.create_index("ix_invoices_payment_terms_id", "invoices", ["payment_terms_id"], unique=False)
    op.create_index("ix_invoices_fiscal_period_id", "invoices", ["fiscal_period_id"], unique=False)
    op.create_index("ix_invoices_journal_entry_id", "invoices", ["journal_entry_id"], unique=False)

    op.create_index("ix_payments_bank_account_id", "payments", ["bank_account_id"], unique=False)
    op.create_index("ix_payments_fiscal_period_id", "payments", ["fiscal_period_id"], unique=False)
    op.create_index("ix_payments_journal_entry_id", "payments", ["journal_entry_id"], unique=False)

    op.create_index("ix_purchase_invoices_payment_terms_id", "purchase_invoices", ["payment_terms_id"], unique=False)
    op.create_index("ix_purchase_invoices_fiscal_period_id", "purchase_invoices", ["fiscal_period_id"], unique=False)
    op.create_index("ix_purchase_invoices_journal_entry_id", "purchase_invoices", ["journal_entry_id"], unique=False)

    op.create_index("ix_unified_tickets_merged_into_id", "unified_tickets", ["merged_into_id"], unique=False)


def downgrade() -> None:
    """Drop dashboard and FK indexes."""
    op.drop_index("ix_unified_tickets_merged_into_id", table_name="unified_tickets")

    op.drop_index("ix_purchase_invoices_journal_entry_id", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_fiscal_period_id", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_payment_terms_id", table_name="purchase_invoices")

    op.drop_index("ix_payments_journal_entry_id", table_name="payments")
    op.drop_index("ix_payments_fiscal_period_id", table_name="payments")
    op.drop_index("ix_payments_bank_account_id", table_name="payments")

    op.drop_index("ix_invoices_journal_entry_id", table_name="invoices")
    op.drop_index("ix_invoices_fiscal_period_id", table_name="invoices")
    op.drop_index("ix_invoices_payment_terms_id", table_name="invoices")

    op.drop_index("ix_accounts_root_type_disabled", table_name="accounts")
    op.drop_index("ix_unified_tickets_category_created", table_name="unified_tickets")
    op.drop_index(
        "ix_unified_tickets_status_resolution_created",
        table_name="unified_tickets",
        postgresql_where=sa.text("status IN ('open','in_progress','waiting')"),
    )
    op.drop_index("ix_gl_entries_account_cancelled_date", table_name="gl_entries")
    op.drop_index("ix_gl_entries_voucher_party_cancelled", table_name="gl_entries")
    op.drop_index("ix_subscriptions_status_currency", table_name="subscriptions")
    op.drop_index("ix_purchase_invoices_supplier_outstanding", table_name="purchase_invoices")
    op.drop_index(
        "ix_purchase_invoices_due_status",
        table_name="purchase_invoices",
        postgresql_where=sa.text("outstanding_amount > 0"),
    )
    op.drop_index(
        "ix_purchase_invoices_status_date_currency",
        table_name="purchase_invoices",
        postgresql_where=sa.text("outstanding_amount > 0"),
    )
    op.drop_index(
        "ix_invoices_due_status_currency",
        table_name="invoices",
        postgresql_where=sa.text("status IN ('PENDING','OVERDUE','PARTIALLY_PAID')"),
    )
    op.drop_index("ix_invoices_status_currency", table_name="invoices")
    op.drop_index("ix_payments_status_date", table_name="payments")
    op.drop_index(
        "ix_payments_status_date_currency",
        table_name="payments",
        postgresql_where=sa.text("is_deleted = false"),
    )

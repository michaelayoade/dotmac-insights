"""books_settings_number_formats

Revision ID: 20241213_books_settings_number_formats
Revises: 20250205_merge_heads
Create Date: 2024-12-13

Adds comprehensive books settings infrastructure:
- books_settings: Company-wide accounting configuration
- document_number_formats: Configurable document numbering
- currency_settings: Currency display and rounding configuration
- debit_notes: Debit note document model
- Unique constraints on existing document number fields
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241213_books_settings_number_formats"
# This migration follows the HR/Notification merge head so new accounting settings
# land on the consolidated branch.
down_revision: Union[str, None] = "20250205_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # BOOKS SETTINGS (Company-wide configuration)
    # ==========================================================================
    op.create_table(
        "books_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, unique=True),

        # General Settings
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("currency_precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("quantity_precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("rate_precision", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("exchange_rate_precision", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("rounding_method", sa.String(20), nullable=False, server_default="round_half_up"),

        # Fiscal Year Settings
        sa.Column("fiscal_year_start_month", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fiscal_year_start_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_create_fiscal_years", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("auto_create_fiscal_periods", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Display Format Settings
        sa.Column("date_format", sa.String(20), nullable=False, server_default="DD/MM/YYYY"),
        sa.Column("number_format", sa.String(20), nullable=False, server_default="1,234.56"),
        sa.Column("negative_format", sa.String(20), nullable=False, server_default="minus"),
        sa.Column("currency_symbol_position", sa.String(10), nullable=False, server_default="before"),

        # Posting Controls
        sa.Column("backdating_days_allowed", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("future_posting_days_allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("require_posting_in_open_period", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Document Control
        sa.Column("auto_voucher_numbering", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("allow_duplicate_party_invoice", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Attachment Requirements
        sa.Column("require_attachment_journal_entry", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_attachment_expense", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("require_attachment_payment", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_attachment_invoice", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Approval Requirements
        sa.Column("require_approval_journal_entry", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_approval_expense", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("require_approval_payment", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Default Accounts
        sa.Column("retained_earnings_account", sa.String(255), nullable=True),
        sa.Column("fx_gain_account", sa.String(255), nullable=True),
        sa.Column("fx_loss_account", sa.String(255), nullable=True),
        sa.Column("default_receivable_account", sa.String(255), nullable=True),
        sa.Column("default_payable_account", sa.String(255), nullable=True),
        sa.Column("default_income_account", sa.String(255), nullable=True),
        sa.Column("default_expense_account", sa.String(255), nullable=True),

        # Inventory Settings
        sa.Column("allow_negative_stock", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("default_valuation_method", sa.String(20), nullable=False, server_default="FIFO"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # Add check constraints
    op.execute("""
        ALTER TABLE books_settings
        ADD CONSTRAINT chk_fiscal_year_start_month
        CHECK (fiscal_year_start_month >= 1 AND fiscal_year_start_month <= 12)
    """)
    op.execute("""
        ALTER TABLE books_settings
        ADD CONSTRAINT chk_fiscal_year_start_day
        CHECK (fiscal_year_start_day >= 1 AND fiscal_year_start_day <= 31)
    """)
    op.execute("""
        ALTER TABLE books_settings
        ADD CONSTRAINT chk_currency_precision
        CHECK (currency_precision >= 0 AND currency_precision <= 4)
    """)

    # ==========================================================================
    # DOCUMENT NUMBER FORMATS
    # ==========================================================================
    op.create_table(
        "document_number_formats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_type", sa.String(50), nullable=False, index=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),

        # Format Configuration
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("format_pattern", sa.String(100), nullable=False),
        sa.Column("min_digits", sa.Integer(), nullable=False, server_default="4"),

        # Sequence Management
        sa.Column("starting_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reset_frequency", sa.String(20), nullable=False, server_default="never"),
        sa.Column("last_reset_date", sa.Date(), nullable=True),
        sa.Column("last_reset_period", sa.String(20), nullable=True),

        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # One active format per document type per company
    op.create_unique_constraint(
        "uq_document_number_format_type_company",
        "document_number_formats",
        ["document_type", "company"]
    )
    op.create_index(
        "ix_doc_num_format_active",
        "document_number_formats",
        ["document_type", "is_active"]
    )

    # Add check constraints
    op.execute("""
        ALTER TABLE document_number_formats
        ADD CONSTRAINT chk_min_digits
        CHECK (min_digits >= 1 AND min_digits <= 10)
    """)
    op.execute("""
        ALTER TABLE document_number_formats
        ADD CONSTRAINT chk_starting_number
        CHECK (starting_number >= 0)
    """)

    # ==========================================================================
    # CURRENCY SETTINGS
    # ==========================================================================
    op.create_table(
        "currency_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("currency_code", sa.String(3), nullable=False, unique=True, index=True),
        sa.Column("currency_name", sa.String(100), nullable=False),

        # Display Settings
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("symbol_position", sa.String(10), nullable=False, server_default="before"),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("thousands_separator", sa.String(1), nullable=False, server_default=","),
        sa.Column("decimal_separator", sa.String(1), nullable=False, server_default="."),

        # Rounding
        sa.Column("smallest_unit", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0.01"),
        sa.Column("rounding_method", sa.String(20), nullable=False, server_default="round_half_up"),

        # Status
        sa.Column("is_base_currency", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false(), index=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Add check constraints
    op.execute("""
        ALTER TABLE currency_settings
        ADD CONSTRAINT chk_decimal_places
        CHECK (decimal_places >= 0 AND decimal_places <= 6)
    """)
    op.execute("""
        ALTER TABLE currency_settings
        ADD CONSTRAINT chk_smallest_unit
        CHECK (smallest_unit > 0)
    """)

    # ==========================================================================
    # DEBIT NOTES
    # ==========================================================================
    op.create_table(
        "debit_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("debit_note_number", sa.String(100), nullable=True, unique=True, index=True),
        sa.Column("erpnext_id", sa.String(255), nullable=True, unique=True, index=True),

        # Supplier Reference
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True, index=True),
        sa.Column("supplier_name", sa.String(255), nullable=True),

        # Linked Documents
        sa.Column("purchase_invoice_id", sa.Integer(), sa.ForeignKey("purchase_invoices.id"), nullable=True, index=True),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),

        # Amounts
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("outstanding_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),

        # Dates
        sa.Column("posting_date", sa.Date(), nullable=True, index=True),
        sa.Column("due_date", sa.Date(), nullable=True),

        # Status
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),

        # Details
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # ==========================================================================
    # SEED DEFAULT DATA
    # ==========================================================================

    # Seed default global books settings
    op.execute("""
        INSERT INTO books_settings (company, base_currency, fiscal_year_start_month)
        VALUES (NULL, 'NGN', 1)
        ON CONFLICT DO NOTHING
    """)

    # Seed default document number formats
    op.execute("""
        INSERT INTO document_number_formats (document_type, company, prefix, format_pattern, min_digits, starting_number, current_number, reset_frequency, is_active)
        VALUES
            ('invoice', NULL, 'INV', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('bill', NULL, 'BILL', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('payment', NULL, 'PAY', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('receipt', NULL, 'RCP', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('credit_note', NULL, 'CN', '{PREFIX}-{YYYY}-{####}', 4, 1, 0, 'never', true),
            ('debit_note', NULL, 'DN', '{PREFIX}-{YYYY}-{####}', 4, 1, 0, 'never', true),
            ('journal_entry', NULL, 'JV', '{PREFIX}-{FY}-{#####}', 5, 1, 0, 'never', true),
            ('purchase_order', NULL, 'PO', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('sales_order', NULL, 'SO', '{PREFIX}-{YYYY}{MM}-{####}', 4, 1, 0, 'never', true),
            ('quotation', NULL, 'QTN', '{PREFIX}-{YYYY}-{####}', 4, 1, 0, 'never', true)
        ON CONFLICT DO NOTHING
    """)

    # Seed default currencies
    op.execute("""
        INSERT INTO currency_settings (currency_code, currency_name, symbol, decimal_places, is_base_currency, is_enabled)
        VALUES
            ('NGN', 'Nigerian Naira', '₦', 2, true, true),
            ('USD', 'US Dollar', '$', 2, false, true),
            ('EUR', 'Euro', '€', 2, false, true),
            ('GBP', 'British Pound', '£', 2, false, true),
            ('KES', 'Kenyan Shilling', 'KSh', 2, false, true),
            ('GHS', 'Ghanaian Cedi', 'GH₵', 2, false, true),
            ('ZAR', 'South African Rand', 'R', 2, false, true)
        ON CONFLICT DO NOTHING
    """)

    # ==========================================================================
    # ADD UNIQUE CONSTRAINTS TO EXISTING DOCUMENT NUMBERS
    # Note: These use partial unique indexes to allow NULLs
    # ==========================================================================

    # Invoice number - unique when not null
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_invoice_number
        ON invoices (invoice_number)
        WHERE invoice_number IS NOT NULL
    """)

    # Payment receipt number - unique when not null
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_receipt_number
        ON payments (receipt_number)
        WHERE receipt_number IS NOT NULL
    """)

    # Credit note number - unique when not null
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_notes_credit_number
        ON credit_notes (credit_number)
        WHERE credit_number IS NOT NULL
    """)


def downgrade() -> None:
    # Drop unique indexes on existing tables
    op.execute("DROP INDEX IF EXISTS uq_invoices_invoice_number")
    op.execute("DROP INDEX IF EXISTS uq_payments_receipt_number")
    op.execute("DROP INDEX IF EXISTS uq_credit_notes_credit_number")

    # Drop new tables
    op.drop_table("debit_notes")
    op.drop_table("currency_settings")
    op.drop_table("document_number_formats")
    op.drop_table("books_settings")

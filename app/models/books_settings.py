"""
Books Settings Models

Comprehensive configuration for accounting/books module including:
- Company-wide books settings
- Document number formats with auto-generation
- Currency settings with display formatting
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.document_lines import DebitNoteLine

from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class DocumentType(str, Enum):
    """Document types that require unique numbering."""
    INVOICE = "invoice"
    BILL = "bill"
    PAYMENT = "payment"
    RECEIPT = "receipt"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    JOURNAL_ENTRY = "journal_entry"
    PURCHASE_ORDER = "purchase_order"
    SALES_ORDER = "sales_order"
    QUOTATION = "quotation"
    DELIVERY_NOTE = "delivery_note"
    GOODS_RECEIPT = "goods_receipt"
    EXPENSE_CLAIM = "expense_claim"
    CASH_ADVANCE = "cash_advance"


class ResetFrequency(str, Enum):
    """How often to reset document number sequences."""
    NEVER = "never"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class RoundingMethod(str, Enum):
    """Rounding methods for currency amounts."""
    ROUND_HALF_UP = "round_half_up"      # Standard rounding (0.5 -> 1)
    ROUND_HALF_DOWN = "round_half_down"  # 0.5 -> 0
    ROUND_DOWN = "round_down"            # Always truncate
    ROUND_UP = "round_up"                # Always round up
    BANKERS = "bankers"                  # Round half to even


class NegativeFormat(str, Enum):
    """How to display negative amounts."""
    MINUS = "minus"              # -1,234.56
    PARENTHESES = "parentheses"  # (1,234.56)
    MINUS_AFTER = "minus_after"  # 1,234.56-


class SymbolPosition(str, Enum):
    """Currency symbol position."""
    BEFORE = "before"  # $1,234.56
    AFTER = "after"    # 1,234.56$


class DateFormatType(str, Enum):
    """Date display formats."""
    DD_MM_YYYY = "DD/MM/YYYY"
    MM_DD_YYYY = "MM/DD/YYYY"
    YYYY_MM_DD = "YYYY-MM-DD"
    DD_MMM_YYYY = "DD-MMM-YYYY"  # 13-Dec-2024


class NumberFormatType(str, Enum):
    """Number display formats."""
    COMMA_DOT = "1,234.56"      # US/UK style
    DOT_COMMA = "1.234,56"      # European style
    SPACE_COMMA = "1 234,56"    # French style
    INDIAN = "1,23,456.78"      # Indian numbering


# ============================================================================
# BOOKS SETTINGS MODEL
# ============================================================================

class BooksSettings(Base):
    """
    Company-wide books/accounting settings.

    One record per company (company=null for global defaults).
    """
    __tablename__ = "books_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True,
        comment="Company scope (null = global defaults)"
    )

    # --- General Settings ---
    base_currency: Mapped[str] = mapped_column(
        String(3), default="NGN",
        comment="Primary currency code (ISO 4217)"
    )
    currency_precision: Mapped[int] = mapped_column(
        Integer, default=2,
        comment="Decimal places for currency amounts (0, 2, or 4)"
    )
    quantity_precision: Mapped[int] = mapped_column(
        Integer, default=2,
        comment="Decimal places for quantities"
    )
    rate_precision: Mapped[int] = mapped_column(
        Integer, default=4,
        comment="Decimal places for rates/prices"
    )
    exchange_rate_precision: Mapped[int] = mapped_column(
        Integer, default=6,
        comment="Decimal places for exchange rates"
    )
    rounding_method: Mapped[RoundingMethod] = mapped_column(
        default=RoundingMethod.ROUND_HALF_UP
    )

    # --- Fiscal Year Settings ---
    fiscal_year_start_month: Mapped[int] = mapped_column(
        Integer, default=1,
        comment="Month fiscal year starts (1-12)"
    )
    fiscal_year_start_day: Mapped[int] = mapped_column(
        Integer, default=1,
        comment="Day fiscal year starts (1-31)"
    )
    auto_create_fiscal_years: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Automatically create fiscal years"
    )
    auto_create_fiscal_periods: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Automatically create periods within fiscal year"
    )

    # --- Display Format Settings ---
    date_format: Mapped[DateFormatType] = mapped_column(
        default=DateFormatType.DD_MM_YYYY
    )
    number_format: Mapped[NumberFormatType] = mapped_column(
        default=NumberFormatType.COMMA_DOT
    )
    negative_format: Mapped[NegativeFormat] = mapped_column(
        default=NegativeFormat.MINUS
    )
    currency_symbol_position: Mapped[SymbolPosition] = mapped_column(
        default=SymbolPosition.BEFORE
    )

    # --- Posting Controls ---
    backdating_days_allowed: Mapped[int] = mapped_column(
        Integer, default=7,
        comment="Days allowed to backdate transactions"
    )
    future_posting_days_allowed: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="Days allowed for future-dated transactions"
    )
    require_posting_in_open_period: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Require posting date to be in an open fiscal period"
    )

    # --- Document Control ---
    auto_voucher_numbering: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Automatically generate document numbers"
    )
    allow_duplicate_party_invoice: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Allow duplicate invoice numbers from same party"
    )

    # --- Attachment Requirements ---
    require_attachment_journal_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    require_attachment_expense: Mapped[bool] = mapped_column(Boolean, default=True)
    require_attachment_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    require_attachment_invoice: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Approval Requirements ---
    require_approval_journal_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    require_approval_expense: Mapped[bool] = mapped_column(Boolean, default=True)
    require_approval_payment: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Default Accounts ---
    retained_earnings_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fx_gain_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fx_loss_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_receivable_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_payable_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_income_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Inventory Settings ---
    allow_negative_stock: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Allow stock to go negative"
    )
    default_valuation_method: Mapped[str] = mapped_column(
        String(20), default="FIFO",
        comment="FIFO, LIFO, or AVERAGE"
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("fiscal_year_start_month >= 1 AND fiscal_year_start_month <= 12"),
        CheckConstraint("fiscal_year_start_day >= 1 AND fiscal_year_start_day <= 31"),
        CheckConstraint("currency_precision >= 0 AND currency_precision <= 4"),
        CheckConstraint("quantity_precision >= 0 AND quantity_precision <= 6"),
    )


# ============================================================================
# DOCUMENT NUMBER FORMAT MODEL
# ============================================================================

class DocumentNumberFormat(Base):
    """
    Configurable document numbering formats.

    Supports format tokens:
        {PREFIX}  - Document prefix
        {YYYY}    - 4-digit year
        {YY}      - 2-digit year
        {MM}      - 2-digit month (01-12)
        {DD}      - 2-digit day (01-31)
        {FY}      - Fiscal year (e.g., 2024-25)
        {Q}       - Quarter (1-4)
        {####}    - Sequence number (# count = padding)
        {COMPANY} - Company code
        {BRANCH}  - Branch code

    Examples:
        INV-{YYYY}{MM}-{####}     -> INV-202412-0001
        BILL-{YYYY}-{#####}       -> BILL-2024-00001
        JV-{FY}-{#####}           -> JV-2024-25-00001
    """
    __tablename__ = "document_number_formats"

    id: Mapped[int] = mapped_column(primary_key=True)

    document_type: Mapped[DocumentType] = mapped_column(
        index=True,
        comment="Type of document this format applies to"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
        comment="Company scope (null = global default)"
    )

    # --- Format Configuration ---
    prefix: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Document prefix (e.g., INV, BILL, JV)"
    )
    format_pattern: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Format pattern with tokens (e.g., {PREFIX}-{YYYY}-{####})"
    )
    min_digits: Mapped[int] = mapped_column(
        Integer, default=4,
        comment="Minimum digits for sequence (zero-padded)"
    )

    # --- Sequence Management ---
    starting_number: Mapped[int] = mapped_column(
        Integer, default=1,
        comment="Starting sequence number"
    )
    current_number: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="Current sequence number (last used)"
    )
    reset_frequency: Mapped[ResetFrequency] = mapped_column(
        default=ResetFrequency.NEVER,
        comment="How often to reset the sequence"
    )
    last_reset_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Last date sequence was reset"
    )
    last_reset_period: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Last period key when reset (e.g., 2024, 2024-12)"
    )

    # --- Status ---
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True,
        comment="Whether this format is currently active"
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        # One active format per document type per company
        UniqueConstraint(
            "document_type", "company",
            name="uq_document_number_format_type_company"
        ),
        Index("ix_doc_num_format_active", "document_type", "is_active"),
        CheckConstraint("min_digits >= 1 AND min_digits <= 10"),
        CheckConstraint("starting_number >= 0"),
        CheckConstraint("current_number >= 0"),
    )


# ============================================================================
# CURRENCY SETTINGS MODEL
# ============================================================================

class CurrencySettings(Base):
    """
    Currency configuration with display formatting.

    Stores both ISO currency data and display preferences.
    """
    __tablename__ = "currency_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Currency Identity ---
    currency_code: Mapped[str] = mapped_column(
        String(3), unique=True, nullable=False, index=True,
        comment="ISO 4217 currency code (e.g., NGN, USD)"
    )
    currency_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Full currency name (e.g., Nigerian Naira)"
    )

    # --- Display Settings ---
    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Currency symbol (e.g., ₦, $, €)"
    )
    symbol_position: Mapped[SymbolPosition] = mapped_column(
        default=SymbolPosition.BEFORE
    )
    decimal_places: Mapped[int] = mapped_column(
        Integer, default=2,
        comment="Standard decimal places for this currency"
    )
    thousands_separator: Mapped[str] = mapped_column(
        String(1), default=",",
        comment="Thousands grouping separator"
    )
    decimal_separator: Mapped[str] = mapped_column(
        String(1), default=".",
        comment="Decimal point character"
    )

    # --- Rounding ---
    smallest_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0.01"),
        comment="Smallest currency unit (e.g., 0.01 for cents, 1 for NGN coins)"
    )
    rounding_method: Mapped[RoundingMethod] = mapped_column(
        default=RoundingMethod.ROUND_HALF_UP
    )

    # --- Status ---
    is_base_currency: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True,
        comment="Is this the company's base/home currency"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True,
        comment="Is this currency available for use"
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint("decimal_places >= 0 AND decimal_places <= 6"),
        CheckConstraint("smallest_unit > 0"),
    )

    def format_amount(self, amount: Decimal) -> str:
        """Format an amount according to this currency's settings."""
        # Round to appropriate decimal places
        rounded = round(amount, self.decimal_places)

        # Format number
        if self.decimal_places > 0:
            format_str = f"{{:,.{self.decimal_places}f}}"
        else:
            format_str = "{:,.0f}"

        formatted = format_str.format(abs(rounded))

        # Replace separators if needed
        if self.thousands_separator != "," or self.decimal_separator != ".":
            # Temporarily use placeholders
            formatted = formatted.replace(",", "THOU")
            formatted = formatted.replace(".", "DEC")
            formatted = formatted.replace("THOU", self.thousands_separator)
            formatted = formatted.replace("DEC", self.decimal_separator)

        # Add symbol
        if self.symbol_position == SymbolPosition.BEFORE:
            result = f"{self.symbol}{formatted}"
        else:
            result = f"{formatted}{self.symbol}"

        # Handle negative
        if amount < 0:
            result = f"-{result}"

        return result


# ============================================================================
# DEBIT NOTE MODEL (Missing from current implementation)
# ============================================================================

class DebitNoteStatus(str, Enum):
    """Status for debit notes."""
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class DebitNote(Base):
    """
    Debit Note model for adjustments to supplier accounts.

    Issued when:
    - Goods returned to supplier
    - Overcharge correction
    - Damaged goods claim
    """
    __tablename__ = "debit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Document Number ---
    debit_note_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True,
        comment="Unique debit note number"
    )

    # --- External IDs ---
    erpnext_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )

    # --- Supplier Reference ---
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Linked Documents ---
    purchase_invoice_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("purchase_invoices.id"), nullable=True, index=True,
        comment="Original purchase invoice being adjusted"
    )
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("journal_entries.id"), nullable=True,
        comment="Associated journal entry"
    )

    # --- Amounts ---
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"),
        comment="Total debit note amount"
    )
    outstanding_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"),
        comment="Amount not yet applied"
    )

    # --- FX Fields ---
    base_currency: Mapped[str] = mapped_column(String(3), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("1"),
        comment="Exchange rate to base currency"
    )
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"),
        comment="Total amount in base currency"
    )

    # --- Workflow ---
    workflow_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, comment="0=Draft,1=Submitted,2=Cancelled")
    fiscal_period_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("fiscal_periods.id"), nullable=True
    )

    # --- Dates ---
    posting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # --- Status ---
    status: Mapped[DebitNoteStatus] = mapped_column(
        default=DebitNoteStatus.DRAFT, index=True
    )

    # --- Details ---
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Company ---
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    purchase_invoice = relationship("PurchaseInvoice", foreign_keys=[purchase_invoice_id])
    journal_entry = relationship("JournalEntry", foreign_keys=[journal_entry_id])
    lines: Mapped[List["DebitNoteLine"]] = relationship(
        back_populates="debit_note",
        cascade="all, delete-orphan",
    )

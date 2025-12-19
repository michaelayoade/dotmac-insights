from __future__ import annotations

from sqlalchemy import String, Text, Enum, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.utils.datetime_utils import utc_now
from decimal import Decimal
from typing import Optional, List
import enum
from app.database import Base
from app.models.document_lines import BillLine


# ============= SUPPLIER =============
class Supplier(Base):
    """Suppliers/Vendors from ERPNext."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    supplier_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    default_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    default_bank_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_withholding_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contact info
    supplier_primary_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_primary_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mobile_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Accounting defaults
    default_price_list: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Flags
    is_transporter: Mapped[bool] = mapped_column(default=False)
    is_internal_supplier: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)
    is_frozen: Mapped[bool] = mapped_column(default=False)
    on_hold: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<Supplier {self.supplier_name}>"


# ============= MODE OF PAYMENT =============
class PaymentModeType(enum.Enum):
    CASH = "cash"
    BANK = "bank"
    GENERAL = "general"


class ModeOfPayment(Base):
    """Payment modes from ERPNext (Cash, Bank Transfer, etc.)."""

    __tablename__ = "modes_of_payment"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    mode_of_payment: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[PaymentModeType] = mapped_column(Enum(PaymentModeType), default=PaymentModeType.GENERAL)
    enabled: Mapped[bool] = mapped_column(default=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<ModeOfPayment {self.mode_of_payment}>"


# ============= COST CENTER =============
class CostCenter(Base):
    """Cost centers from ERPNext for departmental accounting."""

    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    cost_center_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_center_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Tree structure (nested set)
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<CostCenter {self.cost_center_name}>"


# ============= FISCAL YEAR =============
class FiscalYear(Base):
    """Fiscal years from ERPNext for accounting periods."""

    __tablename__ = "fiscal_years"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    year: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    year_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    year_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    is_short_year: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)
    auto_created: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<FiscalYear {self.year}>"


# ============= BANK ACCOUNT =============
class BankAccount(Base):
    """Bank accounts from ERPNext."""

    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_account_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    is_company_account: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<BankAccount {self.account_name} - {self.bank}>"


# ============= JOURNAL ENTRY =============
class JournalEntryType(enum.Enum):
    JOURNAL_ENTRY = "journal_entry"
    BANK_ENTRY = "bank_entry"
    CASH_ENTRY = "cash_entry"
    CREDIT_CARD_ENTRY = "credit_card_entry"
    DEBIT_NOTE = "debit_note"
    CREDIT_NOTE = "credit_note"
    CONTRA_ENTRY = "contra_entry"
    EXCISE_ENTRY = "excise_entry"
    WRITE_OFF_ENTRY = "write_off_entry"
    OPENING_ENTRY = "opening_entry"
    DEPRECIATION_ENTRY = "depreciation_entry"
    EXCHANGE_RATE_REVALUATION = "exchange_rate_revaluation"


class JournalEntry(Base):
    """Journal entries from ERPNext for double-entry bookkeeping."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    voucher_type: Mapped[JournalEntryType] = mapped_column(Enum(JournalEntryType), default=JournalEntryType.JOURNAL_ENTRY)
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    total_debit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_credit: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    cheque_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cheque_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    user_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_opening: Mapped[bool] = mapped_column(default=False)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Relationships
    items: Mapped[List["JournalEntryItem"]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<JournalEntry {self.erpnext_id} - {self.total_debit}>"


class JournalEntryItem(Base):
    """Line items for journal entries."""

    __tablename__ = "journal_entry_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False, index=True
    )

    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    reference_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reference_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    party_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    party: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idx: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<JournalEntryItem {self.account} dr={self.debit} cr={self.credit}>"


# ============= PURCHASE INVOICE =============
class PurchaseInvoiceStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAID = "paid"
    UNPAID = "unpaid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    RETURN = "return"


class PurchaseInvoice(Base):
    """Purchase invoices from ERPNext (vendor bills)."""

    __tablename__ = "purchase_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    # Bill number
    bill_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Supplier info (denormalized)
    supplier_tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Amounts (document currency)
    grand_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    outstanding_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX fields (base currency)
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Payment terms
    payment_terms_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_terms_templates.id"), nullable=True
    )

    status: Mapped[PurchaseInvoiceStatus] = mapped_column(Enum(PurchaseInvoiceStatus), default=PurchaseInvoiceStatus.DRAFT, index=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Workflow
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Additional links
    fiscal_period_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fiscal_periods.id"), nullable=True)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Relationships
    lines: Mapped[List[BillLine]] = relationship(
        back_populates="purchase_invoice",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PurchaseInvoice {self.erpnext_id} - {self.supplier_name}>"


# ============= GL ENTRY (General Ledger) =============
class GLEntry(Base):
    """General Ledger entries from ERPNext - the core of double-entry accounting."""

    __tablename__ = "gl_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    party_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    party: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    debit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    debit_in_account_currency: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    credit_in_account_currency: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    voucher_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    voucher_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fiscal_year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    is_cancelled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    def __repr__(self) -> str:
        return f"<GLEntry {self.erpnext_id} - {self.account}>"


# ============= CHART OF ACCOUNTS =============
class AccountType(enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class Account(Base):
    """Chart of accounts from ERPNext."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    root_type: Mapped[Optional[AccountType]] = mapped_column(Enum(AccountType), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_group: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    balance_must_be: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<Account {self.account_name}>"


# ============= BANK TRANSACTION =============
class BankTransactionStatus(enum.Enum):
    PENDING = "pending"
    SETTLED = "settled"
    UNRECONCILED = "unreconciled"
    RECONCILED = "reconciled"
    CANCELLED = "cancelled"


class BankTransaction(Base):
    """Bank transactions from ERPNext - imported bank statement lines or manual entries."""

    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    status: Mapped[BankTransactionStatus] = mapped_column(Enum(BankTransactionStatus), default=BankTransactionStatus.PENDING)
    bank_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Amounts (document currency)
    deposit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    withdrawal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX fields (base currency)
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Payee information
    payee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payee_account: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Statement reference
    statement_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    statement_line_no: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Manual entry flag
    is_manual_entry: Mapped[bool] = mapped_column(default=False)

    # Reconciliation
    allocated_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    unallocated_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Party info (from bank statement)
    party_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    party: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    bank_party_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_party_account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_party_iban: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Workflow
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Relationships - splits for line-level allocation
    splits: Mapped[List["BankTransactionSplit"]] = relationship(back_populates="bank_transaction")
    payments: Mapped[List["BankTransactionPayment"]] = relationship(
        back_populates="bank_transaction",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BankTransaction {self.erpnext_id} - {self.deposit or self.withdrawal}>"


class BankTransactionPayment(Base):
    """Link table for bank transaction allocations to payment entries."""

    __tablename__ = "bank_transaction_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bank_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payment_document: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_entry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0")
    )
    idx: Mapped[int] = mapped_column(default=0)
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return f"<BankTransactionPayment {self.bank_transaction_id} {self.payment_entry}>"


class BankReconciliationStatus(enum.Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BankReconciliation(Base):
    """Bank reconciliation records."""

    __tablename__ = "bank_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    bank_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    from_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    to_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    bank_statement_opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0")
    )
    bank_statement_closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0")
    )
    account_opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_credits: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_debits: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    status: Mapped[BankReconciliationStatus] = mapped_column(
        Enum(BankReconciliationStatus),
        default=BankReconciliationStatus.DRAFT,
        index=True,
    )
    docstatus: Mapped[int] = mapped_column(default=0)

    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<BankReconciliation {self.bank_account} {self.from_date} - {self.to_date}>"

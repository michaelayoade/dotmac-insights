"""Pydantic schemas for accounting module request/response validation."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class RootType(str, Enum):
    """Account root types."""
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class ApprovalMode(str, Enum):
    """Workflow approval modes."""
    ANY = "any"
    ALL = "all"
    SEQUENTIAL = "sequential"


class TaxType(str, Enum):
    """Tax filing types."""
    VAT = "vat"
    WHT = "wht"
    CIT = "cit"
    PAYE = "paye"
    OTHER = "other"


class PeriodStatus(str, Enum):
    """Fiscal period status."""
    OPEN = "open"
    SOFT_CLOSED = "soft_closed"
    HARD_CLOSED = "hard_closed"


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"


class NonCashTransactionType(str, Enum):
    """Types of non-cash transactions for IAS 7 disclosure."""
    LEASE_INCEPTION = "lease_inception"
    DEBT_CONVERSION = "debt_conversion"
    ASSET_EXCHANGE = "asset_exchange"
    BARTER = "barter"
    SHARE_BASED_PAYMENT = "share_based_payment"
    OTHER = "other"


class ClassificationBasis(str, Enum):
    """Income statement classification basis."""
    BY_NATURE = "by_nature"
    BY_FUNCTION = "by_function"


class InterestDividendClassification(str, Enum):
    """IAS 7 classification policy for interest and dividends."""
    OPERATING = "operating"
    INVESTING = "investing"
    FINANCING = "financing"


# =============================================================================
# Validation Schemas
# =============================================================================

class ValidationIssue(BaseModel):
    """A single validation error or warning."""
    code: str = Field(..., description="Error/warning code for programmatic handling")
    message: str = Field(..., description="Human-readable description")
    field: Optional[str] = Field(None, description="Field path that caused the issue")
    expected: Optional[Any] = Field(None, description="Expected value")
    actual: Optional[Any] = Field(None, description="Actual value found")


class ValidationResultSchema(BaseModel):
    """Validation result included in all financial statement responses."""
    is_valid: bool = Field(..., description="True if all validation checks pass")
    errors: List[ValidationIssue] = Field(default_factory=list, description="Blocking validation errors")
    warnings: List[ValidationIssue] = Field(default_factory=list, description="Non-blocking warnings")


# =============================================================================
# FX and Currency Schemas
# =============================================================================

class FXMetadata(BaseModel):
    """FX metadata for financial statements."""
    functional_currency: str = Field("NGN", description="Entity's functional currency")
    presentation_currency: str = Field("NGN", description="Currency used for presentation")
    is_same_currency: bool = Field(True, description="True if functional = presentation")
    average_rate: Optional[float] = Field(1.0, description="Average FX rate for period")
    closing_rate: Optional[float] = Field(1.0, description="Closing FX rate")


# =============================================================================
# EPS Schemas (IAS 33)
# =============================================================================

class DilutiveInstrument(BaseModel):
    """A dilutive financial instrument for EPS calculation."""
    instrument_type: str = Field(..., description="Type of instrument (options, convertibles, etc.)")
    shares_equivalent: int = Field(..., description="Number of shares if converted/exercised")
    dilutive_effect: float = Field(..., description="Effect on diluted EPS")


class EarningsPerShare(BaseModel):
    """Earnings per share data (IAS 33)."""
    basic_eps: Optional[float] = Field(None, description="Basic earnings per share")
    diluted_eps: Optional[float] = Field(None, description="Diluted earnings per share")
    weighted_average_shares_basic: Optional[int] = Field(None, description="Weighted average shares - basic")
    weighted_average_shares_diluted: Optional[int] = Field(None, description="Weighted average shares - diluted")
    dilutive_instruments: List[DilutiveInstrument] = Field(default_factory=list)
    note: Optional[str] = Field(None, description="EPS calculation note or disclaimer")


# =============================================================================
# Tax Reconciliation Schema (IAS 12)
# =============================================================================

class TaxReconciliationItem(BaseModel):
    """A line item in tax reconciliation."""
    description: str
    amount: float
    rate_effect: Optional[float] = None


class TaxReconciliation(BaseModel):
    """Tax expense reconciliation (IAS 12)."""
    profit_before_tax: float = Field(..., description="PBT from income statement")
    statutory_rate: float = Field(..., description="Applicable statutory tax rate")
    tax_at_statutory_rate: float = Field(..., description="PBT * statutory rate")
    reconciling_items: List[TaxReconciliationItem] = Field(default_factory=list)
    effective_tax_expense: float = Field(..., description="Actual tax expense")
    effective_tax_rate: float = Field(..., description="Effective tax rate")


# =============================================================================
# Non-Cash Transaction Schema (IAS 7)
# =============================================================================

class NonCashTransaction(BaseModel):
    """A non-cash transaction for IAS 7 disclosure."""
    transaction_type: NonCashTransactionType
    description: str
    amount: float
    debit_account: Optional[str] = None
    credit_account: Optional[str] = None


# =============================================================================
# Cash Flow Classification Policy (IAS 7)
# =============================================================================

class CashFlowClassificationPolicy(BaseModel):
    """IAS 7 classification policy choices."""
    interest_paid: InterestDividendClassification = Field(
        InterestDividendClassification.OPERATING,
        description="Classification for interest paid"
    )
    interest_received: InterestDividendClassification = Field(
        InterestDividendClassification.OPERATING,
        description="Classification for interest received"
    )
    dividends_paid: InterestDividendClassification = Field(
        InterestDividendClassification.FINANCING,
        description="Classification for dividends paid"
    )
    dividends_received: InterestDividendClassification = Field(
        InterestDividendClassification.OPERATING,
        description="Classification for dividends received"
    )
    taxes_paid: InterestDividendClassification = Field(
        InterestDividendClassification.OPERATING,
        description="Classification for income taxes paid"
    )


# =============================================================================
# OCI Components Schema (IAS 1)
# =============================================================================

class OCIComponent(BaseModel):
    """Other Comprehensive Income component."""
    description: str
    amount: float
    may_be_reclassified: bool = Field(..., description="True if may be reclassified to P&L")
    reclassification_adjustment: Optional[float] = Field(None, description="Amount reclassified this period")


class OtherComprehensiveIncome(BaseModel):
    """Other Comprehensive Income breakdown (IAS 1)."""
    items_may_be_reclassified: List[OCIComponent] = Field(
        default_factory=list,
        description="Items that may be reclassified to P&L (hedges, FX translation)"
    )
    items_not_reclassified: List[OCIComponent] = Field(
        default_factory=list,
        description="Items that will not be reclassified (revaluations, actuarial)"
    )
    total_may_be_reclassified: float = 0.0
    total_not_reclassified: float = 0.0
    total_oci: float = 0.0


# =============================================================================
# Comparative Period Schema
# =============================================================================

class ComparativePeriod(BaseModel):
    """Prior period comparative data."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    as_of_date: Optional[str] = None


# =============================================================================
# Base/Common Schemas
# =============================================================================

class PaginatedResponse(BaseModel):
    """Base schema for paginated responses."""
    total: int
    limit: int
    offset: int


class DateRangeParams(BaseModel):
    """Common date range parameters."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class PeriodInfo(BaseModel):
    """Period information in responses."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# =============================================================================
# Account Schemas
# =============================================================================

class AccountBase(BaseModel):
    """Base account fields."""
    account_name: str = Field(..., min_length=1, max_length=255)
    account_number: Optional[str] = Field(None, max_length=50)
    root_type: RootType
    account_type: Optional[str] = Field(None, max_length=100)
    parent_account: Optional[str] = None
    is_group: bool = False


class AccountCreate(AccountBase):
    """Schema for creating an account."""
    company: Optional[str] = None


class AccountUpdate(BaseModel):
    """Schema for updating an account."""
    account_name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_number: Optional[str] = Field(None, max_length=50)
    account_type: Optional[str] = Field(None, max_length=100)
    disabled: Optional[bool] = None


class AccountResponse(BaseModel):
    """Schema for account in API responses."""
    id: int
    erpnext_id: Optional[str] = None
    name: str
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[str] = None
    account_type: Optional[str] = None
    is_group: bool
    disabled: bool

    class Config:
        from_attributes = True


class AccountListResponse(PaginatedResponse):
    """Schema for paginated account list."""
    accounts: List[AccountResponse]


# =============================================================================
# Journal Entry Schemas
# =============================================================================

class JournalEntryLineCreate(BaseModel):
    """Schema for a journal entry line item."""
    account: str = Field(..., description="Account erpnext_id")
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return Decimal("0")
        return Decimal(str(v))


class JournalEntryCreate(BaseModel):
    """Schema for creating a journal entry."""
    posting_date: date
    voucher_type: str = Field(default="Journal Entry", max_length=100)
    company: str
    user_remark: Optional[str] = Field(None, max_length=500)
    lines: List[JournalEntryLineCreate] = Field(..., min_length=2)

    @field_validator("lines")
    @classmethod
    def validate_balanced(cls, v):
        total_debit = sum(line.debit for line in v)
        total_credit = sum(line.credit for line in v)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Journal entry must be balanced. Debit: {total_debit}, Credit: {total_credit}")
        return v


class JournalEntryUpdate(BaseModel):
    """Schema for updating a journal entry."""
    posting_date: Optional[date] = None
    user_remark: Optional[str] = Field(None, max_length=500)
    lines: Optional[List[JournalEntryLineCreate]] = None

    @field_validator("lines")
    @classmethod
    def validate_balanced(cls, v):
        if v is None:
            return v
        total_debit = sum(line.debit for line in v)
        total_credit = sum(line.credit for line in v)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Journal entry must be balanced. Debit: {total_debit}, Credit: {total_credit}")
        return v


class JournalEntryLineResponse(BaseModel):
    """Schema for journal entry line in responses."""
    id: int
    account: str
    account_name: Optional[str] = None
    debit: float
    credit: float
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None


class JournalEntryResponse(BaseModel):
    """Schema for journal entry in API responses."""
    id: int
    erpnext_id: Optional[str] = None
    voucher_type: str
    posting_date: date
    company: Optional[str] = None
    total_debit: float
    total_credit: float
    user_remark: Optional[str] = None
    docstatus: Optional[int] = None
    lines: Optional[List[JournalEntryLineResponse]] = None

    class Config:
        from_attributes = True


class JournalEntryListResponse(PaginatedResponse):
    """Schema for paginated journal entry list."""
    entries: List[JournalEntryResponse]


# =============================================================================
# Supplier Schemas
# =============================================================================

class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""
    supplier_name: str = Field(..., min_length=1, max_length=255)
    supplier_group: Optional[str] = Field(None, max_length=100)
    supplier_type: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    default_currency: str = Field(default="NGN", max_length=10)
    tax_id: Optional[str] = Field(None, max_length=50)
    email_id: Optional[str] = Field(None, max_length=255)
    mobile_no: Optional[str] = Field(None, max_length=50)


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier."""
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=255)
    supplier_group: Optional[str] = Field(None, max_length=100)
    supplier_type: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    default_currency: Optional[str] = Field(None, max_length=10)
    tax_id: Optional[str] = Field(None, max_length=50)
    email_id: Optional[str] = Field(None, max_length=255)
    mobile_no: Optional[str] = Field(None, max_length=50)
    disabled: Optional[bool] = None


class SupplierResponse(BaseModel):
    """Schema for supplier in API responses."""
    id: int
    erpnext_id: Optional[str] = None
    supplier_name: str
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    tax_id: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    disabled: bool = False

    class Config:
        from_attributes = True


class SupplierListResponse(PaginatedResponse):
    """Schema for paginated supplier list."""
    suppliers: List[SupplierResponse]


# =============================================================================
# GL Entry Schemas
# =============================================================================

class GLEntryResponse(BaseModel):
    """Schema for GL entry in API responses."""
    id: int
    erpnext_id: Optional[str] = None
    posting_date: Optional[date] = None
    account: Optional[str] = None
    account_name: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0
    party_type: Optional[str] = None
    party: Optional[str] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    remarks: Optional[str] = None
    is_cancelled: bool = False

    class Config:
        from_attributes = True


class GLEntryListResponse(PaginatedResponse):
    """Schema for paginated GL entry list."""
    entries: List[GLEntryResponse]


# =============================================================================
# Workflow Schemas
# =============================================================================

class WorkflowStepCreate(BaseModel):
    """Schema for creating a workflow step."""
    step_order: int = Field(..., ge=1)
    step_name: str = Field(..., min_length=1, max_length=100)
    role_required: Optional[str] = Field(None, max_length=100)
    user_id: Optional[int] = None
    approval_mode: ApprovalMode = ApprovalMode.ANY
    amount_threshold_min: Optional[Decimal] = Field(None, ge=0)
    amount_threshold_max: Optional[Decimal] = Field(None, ge=0)
    can_reject: bool = True
    escalation_timeout_hours: Optional[int] = Field(None, ge=1)
    escalation_role: Optional[str] = None
    escalation_user_id: Optional[int] = None


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""
    name: str = Field(..., min_length=1, max_length=100)
    doctype: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class WorkflowStepResponse(BaseModel):
    """Schema for workflow step in responses."""
    id: int
    step_order: int
    step_name: str
    role_required: Optional[str] = None
    user_id: Optional[int] = None
    approval_mode: str
    amount_threshold_min: Optional[float] = None
    amount_threshold_max: Optional[float] = None
    can_reject: bool


class WorkflowResponse(BaseModel):
    """Schema for workflow in API responses."""
    id: int
    name: str
    doctype: str
    is_active: bool
    steps: Optional[List[WorkflowStepResponse]] = None

    class Config:
        from_attributes = True


# =============================================================================
# Fiscal Period Schemas
# =============================================================================

class FiscalPeriodCreate(BaseModel):
    """Schema for creating a fiscal period."""
    name: str = Field(..., min_length=1, max_length=100)
    fiscal_year_id: int
    period_start: date
    period_end: date
    status: PeriodStatus = PeriodStatus.OPEN


class FiscalPeriodResponse(BaseModel):
    """Schema for fiscal period in responses."""
    id: int
    name: str
    fiscal_year_id: int
    fiscal_year_name: Optional[str] = None
    period_start: date
    period_end: date
    status: str
    closing_journal_entry_id: Optional[int] = None
    closed_by_id: Optional[int] = None
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Tax Filing Schemas
# =============================================================================

class TaxFilingPeriodCreate(BaseModel):
    """Schema for creating a tax filing period."""
    tax_type: TaxType
    period_name: str = Field(..., min_length=1, max_length=100)
    period_start: date
    period_end: date
    due_date: date
    tax_base: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("tax_base", "tax_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return Decimal("0")
        return Decimal(str(v))


class TaxPaymentCreate(BaseModel):
    """Schema for recording a tax payment."""
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_reference: Optional[str] = Field(None, max_length=100)
    payment_method: Optional[str] = Field(None, max_length=50)
    bank_account: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class TaxFilingPeriodResponse(BaseModel):
    """Schema for tax filing period in responses."""
    id: int
    tax_type: str
    period_name: str
    period_start: date
    period_end: date
    due_date: date
    tax_base: float
    tax_amount: float
    amount_paid: float = 0.0
    status: str
    filed_date: Optional[date] = None

    class Config:
        from_attributes = True


# =============================================================================
# Bank Reconciliation Schemas
# =============================================================================

class BankReconciliationStartRequest(BaseModel):
    """Schema for starting bank reconciliation."""
    statement_date: date
    opening_balance: Decimal
    closing_balance: Decimal

    @field_validator("opening_balance", "closing_balance", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class BankTransactionMatchRequest(BaseModel):
    """Schema for matching bank transaction to GL."""
    bank_transaction_id: int
    gl_entry_ids: List[int] = Field(..., min_length=1)


class BankStatementImportResponse(BaseModel):
    """Schema for bank statement import result."""
    imported: int
    skipped: int
    errors: List[str] = []


# =============================================================================
# Dashboard/Report Schemas
# =============================================================================

class DashboardSummary(BaseModel):
    """Dashboard summary section."""
    total_assets: float
    total_liabilities: float
    total_equity: float
    net_worth: float


class DashboardPerformance(BaseModel):
    """Dashboard performance section."""
    total_income: float
    total_expenses: float
    net_profit: float
    profit_margin: float


class DashboardReceivablesPayables(BaseModel):
    """Dashboard AR/AP section."""
    total_receivable: float
    total_payable: float
    net_position: float


class DashboardActivity(BaseModel):
    """Dashboard activity section."""
    gl_entries_count: int
    bank_transactions_count: int


class DashboardResponse(BaseModel):
    """Schema for accounting dashboard response."""
    period: PeriodInfo
    summary: DashboardSummary
    performance: DashboardPerformance
    receivables_payables: DashboardReceivablesPayables
    bank_balances: List[Dict[str, Any]]
    activity: DashboardActivity


# =============================================================================
# Write-off/Waiver Schemas
# =============================================================================

class InvoiceWriteOffRequest(BaseModel):
    """Schema for invoice write-off request."""
    amount: Optional[Decimal] = Field(None, gt=0, description="Amount to write off. Defaults to full balance.")
    reason: str = Field(..., min_length=1, max_length=500)
    write_off_account: Optional[str] = Field(None, description="Account to post write-off. Uses default if not specified.")

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class InvoiceWaiverRequest(BaseModel):
    """Schema for invoice waiver request."""
    waive_amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("waive_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


# =============================================================================
# Credit Management Schemas
# =============================================================================

class CreditLimitUpdate(BaseModel):
    """Schema for updating customer credit limit."""
    credit_limit: Decimal = Field(..., ge=0)
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("credit_limit", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class CreditHoldUpdate(BaseModel):
    """Schema for updating customer credit hold status."""
    on_hold: bool
    reason: Optional[str] = Field(None, max_length=500)


class CustomerCreditStatusResponse(BaseModel):
    """Schema for customer credit status response."""
    customer_id: int
    customer_name: str
    credit_limit: float
    current_balance: float
    available_credit: float
    on_hold: bool
    overdue_amount: float
    oldest_overdue_days: Optional[int] = None


# =============================================================================
# Dunning Schemas
# =============================================================================

class DunningSendRequest(BaseModel):
    """Schema for sending dunning notice."""
    invoice_ids: List[int] = Field(..., min_length=1)
    dunning_level: Optional[int] = Field(None, ge=1, le=5)
    custom_message: Optional[str] = Field(None, max_length=2000)


class DunningHistoryResponse(BaseModel):
    """Schema for dunning history entry."""
    id: int
    invoice_id: int
    level: int
    sent_at: datetime
    sent_by_id: Optional[int] = None
    message: Optional[str] = None
    response: Optional[str] = None

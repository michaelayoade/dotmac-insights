"""Pydantic schemas for Expense Management APIs."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.expense_management import (
    FundingMethod,
    ExpenseClaimStatus,
    CashAdvanceStatus,
    CorporateCardStatus,
    CardTransactionStatus,
    StatementStatus,
)


class ExpenseCategoryCreate(BaseModel):
    code: str
    name: str
    expense_account: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_group: bool = False
    payable_account: Optional[str] = None
    category_type: Optional[str] = None
    default_tax_code_id: Optional[int] = None
    is_tax_deductible: bool = True
    requires_receipt: bool = True
    company: Optional[str] = None


class ExpenseCategoryRead(ExpenseCategoryCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ExpensePolicyCreate(BaseModel):
    policy_name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    applies_to_all: bool = True
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    employment_type: Optional[str] = None
    grade_level: Optional[str] = None
    max_single_expense: Optional[Decimal] = None
    max_daily_limit: Optional[Decimal] = None
    max_monthly_limit: Optional[Decimal] = None
    max_claim_amount: Optional[Decimal] = None
    currency: str = "NGN"
    receipt_required: bool = True
    receipt_threshold: Optional[Decimal] = None
    auto_approve_below: Optional[Decimal] = None
    requires_pre_approval: bool = False
    allow_out_of_pocket: bool = True
    allow_cash_advance: bool = False
    allow_corporate_card: bool = False
    allow_per_diem: bool = False
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: bool = True
    priority: int = 0
    company: Optional[str] = None

    @field_validator(
        "max_single_expense",
        "max_daily_limit",
        "max_monthly_limit",
        "max_claim_amount",
        "auto_approve_below",
        "receipt_threshold",
    )
    @classmethod
    def validate_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Amount values must be positive")
        return v


class ExpensePolicyRead(ExpensePolicyCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ExpenseClaimLineCreate(BaseModel):
    category_id: int
    expense_date: date
    description: str
    claimed_amount: Decimal = Field(gt=0)
    currency: str = "NGN"
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    is_tax_inclusive: bool = False
    is_tax_reclaimable: bool = False
    withholding_tax_rate: Decimal = Decimal("0")
    withholding_tax_amount: Decimal = Decimal("0")
    conversion_rate: Decimal = Decimal("1")
    rate_source: Optional[str] = None
    rate_date: Optional[date] = None
    funding_method: FundingMethod = FundingMethod.OUT_OF_POCKET
    merchant_name: Optional[str] = None
    invoice_number: Optional[str] = None
    cost_center: Optional[str] = None
    project_id: Optional[int] = None
    has_receipt: bool = False
    receipt_missing_reason: Optional[str] = None

    @field_validator("conversion_rate")
    @classmethod
    def validate_conversion_rate(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("conversion_rate must be greater than zero")
        return v


class ExpenseClaimCreate(BaseModel):
    title: str
    employee_id: int
    claim_date: date
    description: Optional[str] = None
    currency: str = "NGN"
    base_currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    project_id: Optional[int] = None
    cost_center: Optional[str] = None
    cash_advance_id: Optional[int] = None
    company: Optional[str] = None
    lines: List[ExpenseClaimLineCreate]

    @field_validator("conversion_rate")
    @classmethod
    def validate_claim_conversion_rate(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("conversion_rate must be greater than zero")
        return v


class ExpenseClaimLineRead(BaseModel):
    id: int
    category_id: int
    expense_date: date
    description: str
    claimed_amount: Decimal
    sanctioned_amount: Decimal
    currency: str
    funding_method: FundingMethod
    has_receipt: bool
    tax_amount: Decimal
    conversion_rate: Decimal
    base_claimed_amount: Decimal
    model_config = ConfigDict(from_attributes=True)


class ExpenseClaimRead(BaseModel):
    id: int
    claim_number: Optional[str] = None
    title: str
    employee_id: int
    claim_date: date
    status: ExpenseClaimStatus
    total_claimed_amount: Decimal
    total_taxes: Decimal
    currency: str
    base_currency: str
    conversion_rate: Decimal
    lines: List[ExpenseClaimLineRead]
    model_config = ConfigDict(from_attributes=True)


# ---------------- Cash Advances ----------------


class CashAdvanceCreate(BaseModel):
    employee_id: int
    purpose: str
    request_date: date
    required_by_date: Optional[date] = None
    project_id: Optional[int] = None
    trip_start_date: Optional[date] = None
    trip_end_date: Optional[date] = None
    destination: Optional[str] = None
    requested_amount: Decimal = Field(gt=0)
    currency: str = "NGN"
    base_currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    company: Optional[str] = None

    @field_validator("conversion_rate")
    @classmethod
    def validate_conversion_rate(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("conversion_rate must be greater than zero")
        return v


class CashAdvanceRead(BaseModel):
    id: int
    advance_number: Optional[str]
    employee_id: int
    purpose: str
    request_date: date
    required_by_date: Optional[date] = None
    project_id: Optional[int] = None
    trip_start_date: Optional[date] = None
    trip_end_date: Optional[date] = None
    destination: Optional[str] = None
    requested_amount: Decimal
    approved_amount: Decimal
    disbursed_amount: Decimal
    settled_amount: Decimal
    outstanding_amount: Decimal
    refund_amount: Decimal
    currency: str
    base_currency: str
    conversion_rate: Decimal
    status: CashAdvanceStatus
    company: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CashAdvanceDisburse(BaseModel):
    amount: Decimal = Field(gt=0)
    mode_of_payment: Optional[str] = None
    payment_reference: Optional[str] = None
    bank_account_id: Optional[int] = None


class CashAdvanceSettle(BaseModel):
    amount: Decimal = Field(ge=0)
    refund_amount: Optional[Decimal] = Field(default=Decimal("0"), ge=0)


# ---------------- Corporate Cards ----------------


class CorporateCardCreate(BaseModel):
    card_number_last4: str = Field(min_length=4, max_length=4)
    card_name: str
    card_type: Optional[str] = None
    bank_name: Optional[str] = None
    card_provider: Optional[str] = None
    employee_id: int
    credit_limit: Decimal = Decimal("0")
    single_transaction_limit: Optional[Decimal] = None
    daily_limit: Optional[Decimal] = None
    monthly_limit: Optional[Decimal] = None
    currency: str = "NGN"
    issue_date: date
    expiry_date: Optional[date] = None
    liability_account: Optional[str] = None
    bank_account_id: Optional[int] = None
    company: Optional[str] = None

    @field_validator("credit_limit", "single_transaction_limit", "daily_limit", "monthly_limit")
    @classmethod
    def validate_positive_limits(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Limit values must be non-negative")
        return v


class CorporateCardUpdate(BaseModel):
    card_name: Optional[str] = None
    card_type: Optional[str] = None
    bank_name: Optional[str] = None
    card_provider: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    single_transaction_limit: Optional[Decimal] = None
    daily_limit: Optional[Decimal] = None
    monthly_limit: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    liability_account: Optional[str] = None
    bank_account_id: Optional[int] = None
    status: Optional[CorporateCardStatus] = None

    @field_validator("credit_limit", "single_transaction_limit", "daily_limit", "monthly_limit")
    @classmethod
    def validate_positive_limits(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Limit values must be non-negative")
        return v


class CorporateCardRead(BaseModel):
    id: int
    card_number_last4: str
    card_name: str
    card_type: Optional[str] = None
    bank_name: Optional[str] = None
    card_provider: Optional[str] = None
    employee_id: int
    credit_limit: Decimal
    single_transaction_limit: Optional[Decimal] = None
    daily_limit: Optional[Decimal] = None
    monthly_limit: Optional[Decimal] = None
    currency: str
    status: CorporateCardStatus
    issue_date: date
    expiry_date: Optional[date] = None
    liability_account: Optional[str] = None
    bank_account_id: Optional[int] = None
    company: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ---------------- Corporate Card Transactions ----------------


class CorporateCardTransactionCreate(BaseModel):
    card_id: int
    statement_id: Optional[int] = None
    transaction_date: date
    posting_date: Optional[date] = None
    merchant_name: Optional[str] = None
    merchant_category_code: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal
    currency: str = "NGN"
    original_amount: Optional[Decimal] = None
    original_currency: Optional[str] = None
    conversion_rate: Decimal = Decimal("1")
    transaction_reference: Optional[str] = None
    authorization_code: Optional[str] = None

    @field_validator("conversion_rate")
    @classmethod
    def validate_conversion_rate(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("conversion_rate must be greater than zero")
        return v


class CorporateCardTransactionUpdate(BaseModel):
    status: Optional[CardTransactionStatus] = None
    expense_claim_line_id: Optional[int] = None
    match_confidence: Optional[Decimal] = None
    dispute_reason: Optional[str] = None
    resolution_notes: Optional[str] = None


class CorporateCardTransactionRead(BaseModel):
    id: int
    card_id: int
    statement_id: Optional[int] = None
    transaction_date: date
    posting_date: Optional[date] = None
    merchant_name: Optional[str] = None
    merchant_category_code: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal
    currency: str
    original_amount: Optional[Decimal] = None
    original_currency: Optional[str] = None
    conversion_rate: Decimal
    transaction_reference: Optional[str] = None
    authorization_code: Optional[str] = None
    status: CardTransactionStatus
    expense_claim_line_id: Optional[int] = None
    match_confidence: Optional[Decimal] = None
    disputed_at: Optional[date] = None
    dispute_reason: Optional[str] = None
    resolution_notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TransactionMatchPayload(BaseModel):
    expense_claim_line_id: int
    confidence: Optional[Decimal] = None


class TransactionDisputePayload(BaseModel):
    reason: str


# ---------------- Corporate Card Statements ----------------


class CorporateCardStatementCreate(BaseModel):
    card_id: int
    period_start: date
    period_end: date
    statement_date: Optional[date] = None
    import_source: Optional[str] = None
    original_filename: Optional[str] = None


class CorporateCardStatementRead(BaseModel):
    id: int
    card_id: int
    period_start: date
    period_end: date
    statement_date: Optional[date] = None
    import_date: date
    import_source: Optional[str] = None
    original_filename: Optional[str] = None
    status: StatementStatus
    total_amount: Decimal
    transaction_count: int
    matched_amount: Decimal
    matched_count: int
    unmatched_count: int
    reconciled_at: Optional[date] = None
    reconciled_by_id: Optional[int] = None
    closed_at: Optional[date] = None
    closed_by_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class StatementImportPayload(BaseModel):
    card_id: int
    period_start: date
    period_end: date
    statement_date: Optional[date] = None
    import_source: str = "manual"
    original_filename: Optional[str] = None
    transactions: List[CorporateCardTransactionCreate]

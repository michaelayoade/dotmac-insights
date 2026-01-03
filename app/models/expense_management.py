"""
Expense Management Models.

Handles expense claims, cash advances, corporate cards, per-diem rates,
and expense policies with approval workflow integration.
"""
from __future__ import annotations

from sqlalchemy import (
    String, Text, ForeignKey, Enum, Index, Numeric, Date, JSON, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.hr import Department, Designation
    from app.models.accounting import BankAccount
    from app.models.tax import TaxCode
    from app.models.project import Project


# =============================================================================
# ENUMS
# =============================================================================

class ExpenseClaimStatus(enum.Enum):
    """Status lifecycle for expense claims."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"  # Sent back for edits by approver
    RECALLED = "recalled"  # Withdrawn by submitter before approval
    POSTED = "posted"
    PAID = "paid"
    REVERSED = "reversed"  # Posted but later reversed via reversal JE
    CANCELLED = "cancelled"


class FundingMethod(enum.Enum):
    """How the expense was/will be funded."""
    OUT_OF_POCKET = "out_of_pocket"      # Employee paid, needs reimbursement
    CASH_ADVANCE = "cash_advance"        # Pre-funded via cash advance
    CORPORATE_CARD = "corporate_card"    # Company credit card
    PER_DIEM = "per_diem"                # Fixed daily allowance


class CashAdvanceStatus(enum.Enum):
    """Status for cash advance requests."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISBURSED = "disbursed"
    PARTIALLY_SETTLED = "partially_settled"
    FULLY_SETTLED = "fully_settled"
    CANCELLED = "cancelled"
    WRITTEN_OFF = "written_off"


class LineStatus(enum.Enum):
    """Status for individual expense lines (line-level approval)."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ADJUSTED = "adjusted"


class CorporateCardStatus(enum.Enum):
    """Corporate card status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class CardTransactionStatus(enum.Enum):
    """Corporate card transaction status for reconciliation."""
    IMPORTED = "imported"
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    DISPUTED = "disputed"
    EXCLUDED = "excluded"
    PERSONAL = "personal"


class StatementStatus(enum.Enum):
    """Corporate card statement status."""
    OPEN = "open"
    RECONCILED = "reconciled"
    CLOSED = "closed"


# =============================================================================
# EXPENSE CATEGORY
# =============================================================================

class ExpenseCategory(Base):
    """
    Hierarchical expense categories with GL account mapping.
    Supports both system-defined and custom categories.
    """
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identification
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("expense_categories.id"), nullable=True, index=True
    )
    is_group: Mapped[bool] = mapped_column(default=False)

    # GL Account Mapping
    expense_account: Mapped[str] = mapped_column(String(255), nullable=False)  # Default debit account
    payable_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Override AP account

    # Category type (for system categories)
    category_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Values: travel, meals, transport, accommodation, supplies, subscriptions,
    #         professional_development, client_entertainment, other

    # Tax handling
    default_tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id"), nullable=True
    )
    is_tax_deductible: Mapped[bool] = mapped_column(default=True)

    # Flags
    is_system: Mapped[bool] = mapped_column(default=False)  # System categories cannot be deleted
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    requires_receipt: Mapped[bool] = mapped_column(default=True)

    # Company scope (null = all companies)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    parent: Mapped[Optional["ExpenseCategory"]] = relationship(
        "ExpenseCategory", remote_side=[id], backref="children"
    )
    policies: Mapped[List["ExpensePolicy"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<ExpenseCategory {self.code}: {self.name}>"


# =============================================================================
# EXPENSE POLICY
# =============================================================================

class ExpensePolicy(Base):
    """
    Policy rules per expense category.
    Defines limits, receipt requirements, and approval thresholds.
    """
    __tablename__ = "expense_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Policy identification
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Category link (null = applies to all categories)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("expense_categories.id"), nullable=True, index=True
    )

    # Scope - which employees this applies to
    applies_to_all: Mapped[bool] = mapped_column(default=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    designation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("designations.id"), nullable=True
    )
    employment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    grade_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Limits
    max_single_expense: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_daily_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_monthly_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_claim_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Receipt requirements
    receipt_required: Mapped[bool] = mapped_column(default=True)
    receipt_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    # Receipt required if amount >= threshold (null = always required if receipt_required=True)

    # Approval settings
    auto_approve_below: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    requires_pre_approval: Mapped[bool] = mapped_column(default=False)

    # Allowed funding methods (gated by implementation phase)
    allow_out_of_pocket: Mapped[bool] = mapped_column(default=True)
    allow_cash_advance: Mapped[bool] = mapped_column(default=False)  # Unlocked in Phase 5
    allow_corporate_card: Mapped[bool] = mapped_column(default=False)  # Unlocked in Phase 8
    allow_per_diem: Mapped[bool] = mapped_column(default=False)  # Unlocked in Phase 8

    # Validity
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Priority (higher = more specific, used in policy resolution)
    priority: Mapped[int] = mapped_column(default=0)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    category: Mapped[Optional["ExpenseCategory"]] = relationship(back_populates="policies")

    def __repr__(self) -> str:
        return f"<ExpensePolicy {self.policy_name}>"


# =============================================================================
# EXPENSE CLAIM (HEADER)
# =============================================================================

class ExpenseClaim(Base):
    """
    Main expense claim document (header).
    Contains one or more expense claim lines.
    Integrates with approval workflow and GL posting.
    """
    __tablename__ = "expense_claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Document identification (assigned on submit, not draft)
    claim_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Employee
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )

    # Project/Cost Center allocation
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    claim_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    posting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expense_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expense_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Amounts (document currency)
    total_claimed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_sanctioned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_advance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_reimbursable: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_taxes: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX fields (base currency)
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_total_claimed: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_total_sanctioned: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Funding method breakdown
    out_of_pocket_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    corporate_card_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    cash_advance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    per_diem_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Cash Advance linkage
    cash_advance_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cash_advances.id"), nullable=True
    )

    # Status
    status: Mapped[ExpenseClaimStatus] = mapped_column(
        Enum(ExpenseClaimStatus), default=ExpenseClaimStatus.DRAFT, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)  # 0=Draft, 1=Submitted, 2=Cancelled
    workflow_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Approval tracking (denormalized for quick access)
    approval_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    return_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Payment tracking
    payment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Values: unpaid, partially_paid, paid
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    payment_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # GL Posting (for idempotency)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    posted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    fiscal_period_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fiscal_periods.id"), nullable=True
    )

    # Reversal tracking
    reversed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reversed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reversal_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reversal_journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )

    # Accounting
    payable_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mode_of_payment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="expense_claims")
    lines: Mapped[List["ExpenseClaimLine"]] = relationship(
        back_populates="expense_claim",
        cascade="all, delete-orphan",
        order_by="ExpenseClaimLine.idx"
    )
    cash_advance: Mapped[Optional["CashAdvance"]] = relationship(
        back_populates="expense_claims",
        foreign_keys=[cash_advance_id]
    )

    __table_args__ = (
        Index("ix_expense_claims_employee_date", "employee_id", "claim_date"),
        Index("ix_expense_claims_status_date", "status", "claim_date"),
    )

    def __repr__(self) -> str:
        return f"<ExpenseClaim {self.claim_number or f'DRAFT-{self.id}'}>"


# =============================================================================
# EXPENSE CLAIM LINE
# =============================================================================

class ExpenseClaimLine(Base):
    """
    Individual expense line items within a claim.
    Links to category and includes detailed expense information.
    """
    __tablename__ = "expense_claim_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    expense_claim_id: Mapped[int] = mapped_column(
        ForeignKey("expense_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Category
    category_id: Mapped[int] = mapped_column(
        ForeignKey("expense_categories.id"), nullable=False, index=True
    )

    # Expense details
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Vendor/Merchant info
    merchant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    merchant_tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Amounts
    claimed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sanctioned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Tax/VAT
    tax_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tax_codes.id"), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    is_tax_inclusive: Mapped[bool] = mapped_column(default=False)
    is_tax_reclaimable: Mapped[bool] = mapped_column(default=False)  # For VAT recovery

    # Withholding tax
    withholding_tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    withholding_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Base currency
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_claimed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_sanctioned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    rate_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # manual, api, policy
    rate_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Funding method for this line
    funding_method: Mapped[FundingMethod] = mapped_column(
        Enum(FundingMethod), default=FundingMethod.OUT_OF_POCKET
    )

    # Corporate card transaction link
    corporate_card_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("corporate_card_transactions.id"), nullable=True
    )

    # Accounting
    expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Project allocation
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)

    # Receipt/Attachment
    has_receipt: Mapped[bool] = mapped_column(default=False)
    receipt_missing_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Mileage (for travel expenses)
    distance_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    mileage_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    # Per-diem fields
    is_per_diem: Mapped[bool] = mapped_column(default=False)
    per_diem_rate_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("per_diem_rates.id"), nullable=True
    )
    per_diem_days: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Line status (for line-level approval/rejection)
    line_status: Mapped[LineStatus] = mapped_column(
        Enum(LineStatus), default=LineStatus.PENDING
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    adjustment_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    expense_claim: Mapped["ExpenseClaim"] = relationship(back_populates="lines")
    category: Mapped["ExpenseCategory"] = relationship()

    __table_args__ = (
        Index("ix_expense_claim_lines_date", "expense_date"),
    )

    def __repr__(self) -> str:
        return f"<ExpenseClaimLine {self.description[:30]}... @ {self.claimed_amount}>"


# =============================================================================
# CASH ADVANCE
# =============================================================================

class CashAdvance(Base):
    """
    Cash advance requests for pre-funding expenses.
    Links to expense claims for settlement.
    """
    __tablename__ = "cash_advances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Document identification (assigned on submit)
    advance_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )

    # Employee
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )

    # Request details
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trip/Project link (optional)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    trip_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    trip_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Amounts
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    disbursed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    settled_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # FX
    base_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))
    base_requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Status
    status: Mapped[CashAdvanceStatus] = mapped_column(
        Enum(CashAdvanceStatus), default=CashAdvanceStatus.DRAFT, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)

    # Dates
    request_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    required_by_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    disbursed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    settlement_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Approval
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Disbursement
    mode_of_payment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=True
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disbursed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # GL posting
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    advance_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Default: Employee Advances account

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="cash_advances")
    expense_claims: Mapped[List["ExpenseClaim"]] = relationship(
        back_populates="cash_advance",
        foreign_keys="ExpenseClaim.cash_advance_id"
    )

    def __repr__(self) -> str:
        return f"<CashAdvance {self.advance_number or f'DRAFT-{self.id}'}>"


# =============================================================================
# PER DIEM RATE
# =============================================================================

class PerDiemRate(Base):
    """
    Location-based daily allowance rates.
    Supports different rates for different locations and employee grades.
    """
    __tablename__ = "per_diem_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identification
    rate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Location
    country: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., "tier1" (major cities), "tier2" (other urban), "tier3" (rural)

    # Rates
    full_day_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    half_day_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    overnight_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Component breakdown (optional)
    meals_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    lodging_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    incidentals_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Employee level rates (different rates by designation/grade)
    designation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("designations.id"), nullable=True
    )
    grade_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # GL Account
    expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Validity
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_per_diem_rates_location", "country", "city"),
    )

    def __repr__(self) -> str:
        return f"<PerDiemRate {self.rate_name}: {self.country}/{self.city}>"


# =============================================================================
# MILEAGE RATE
# =============================================================================

class MileageRate(Base):
    """
    Mileage reimbursement rates per kilometer.
    """
    __tablename__ = "mileage_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rate details
    rate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g., "car", "motorcycle", "bicycle"

    rate_per_km: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Tiered rates (optional)
    first_tier_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    first_tier_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    # GL Account
    expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Validity
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<MileageRate {self.vehicle_type}: {self.rate_per_km}/km>"


# =============================================================================
# CORPORATE CARD
# =============================================================================

class CorporateCard(Base):
    """
    Corporate card assignment and management.
    """
    __tablename__ = "corporate_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Card details (only store last 4 digits for security)
    card_number_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    card_name: Mapped[str] = mapped_column(String(255), nullable=False)
    card_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., "credit", "debit", "prepaid"

    # Bank/Provider
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    card_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g., "visa", "mastercard", "verve"

    # Assignment
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )

    # Limits
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    single_transaction_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    daily_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    monthly_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Status
    status: Mapped[CorporateCardStatus] = mapped_column(
        Enum(CorporateCardStatus), default=CorporateCardStatus.ACTIVE, index=True
    )

    # Dates
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # GL Account
    liability_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Default: Corporate Card Payable

    # Bank account for statement import
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=True
    )

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="corporate_cards")
    transactions: Mapped[List["CorporateCardTransaction"]] = relationship(back_populates="card")
    statements: Mapped[List["CorporateCardStatement"]] = relationship(back_populates="card")

    def __repr__(self) -> str:
        return f"<CorporateCard ****{self.card_number_last4}>"


# =============================================================================
# CORPORATE CARD TRANSACTION
# =============================================================================

class CorporateCardTransaction(Base):
    """
    Corporate card transaction records (from statement import or manual entry).
    """
    __tablename__ = "corporate_card_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Card link
    card_id: Mapped[int] = mapped_column(
        ForeignKey("corporate_cards.id"), nullable=False, index=True
    )

    # Statement link
    statement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("corporate_card_statements.id"), nullable=True, index=True
    )

    # Transaction details
    transaction_date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    merchant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    merchant_category_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # If foreign currency transaction
    original_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    original_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal("1"))

    # Reference
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    authorization_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Reconciliation status
    status: Mapped[CardTransactionStatus] = mapped_column(
        Enum(CardTransactionStatus), default=CardTransactionStatus.IMPORTED, index=True
    )

    # Expense claim link
    expense_claim_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("expense_claim_lines.id"), nullable=True
    )
    match_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Dispute handling
    disputed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    dispute_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Import deduplication (hash of card_id, transaction_date, amount, reference)
    import_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    imported_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    card: Mapped["CorporateCard"] = relationship(back_populates="transactions")

    def __repr__(self) -> str:
        return f"<CorporateCardTransaction {self.merchant_name}: {self.amount}>"


# =============================================================================
# CORPORATE CARD STATEMENT
# =============================================================================

class CorporateCardStatement(Base):
    """
    Corporate card statement period tracking for reconciliation.
    """
    __tablename__ = "corporate_card_statements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Card link
    card_id: Mapped[int] = mapped_column(
        ForeignKey("corporate_cards.id"), nullable=False, index=True
    )

    # Period
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    statement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Import details
    import_date: Mapped[datetime] = mapped_column(nullable=False)
    import_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g., "csv_upload", "api_sync", "manual"
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[StatementStatus] = mapped_column(
        Enum(StatementStatus), default=StatementStatus.OPEN, index=True
    )

    # Totals
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    transaction_count: Mapped[int] = mapped_column(default=0)
    matched_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    matched_count: Mapped[int] = mapped_column(default=0)
    unmatched_count: Mapped[int] = mapped_column(default=0)

    # Reconciliation
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reconciled_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    card: Mapped["CorporateCard"] = relationship(back_populates="statements")
    transactions: Mapped[List["CorporateCardTransaction"]] = relationship(
        foreign_keys="CorporateCardTransaction.statement_id"
    )

    __table_args__ = (
        Index("ix_corp_card_statements_card_period", "card_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return f"<CorporateCardStatement {self.period_start} - {self.period_end}>"

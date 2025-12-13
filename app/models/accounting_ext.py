"""
Extended Accounting Models for Books Module

Provides models for:
- Fiscal Period management and closing
- Approval workflows with multi-step chains
- Immutable audit logging
- Exchange rates and revaluation
- Accounting controls
"""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.accounting import FiscalYear, Account, JournalEntry


# =============================================================================
# ENUMS
# =============================================================================

class FiscalPeriodStatus(enum.Enum):
    """Status of a fiscal period for posting control."""
    OPEN = "open"                    # Normal posting allowed
    SOFT_CLOSED = "soft_closed"      # Closed but can be reopened
    HARD_CLOSED = "hard_closed"      # Permanently closed, no changes


class FiscalPeriodType(enum.Enum):
    """Type of fiscal period."""
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ApprovalStatus(enum.Enum):
    """Document approval status."""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    CANCELLED = "cancelled"


class ApprovalMode(enum.Enum):
    """How multiple approvers at a step should work."""
    ANY = "any"          # Any one approver can approve
    ALL = "all"          # All approvers must approve
    SEQUENTIAL = "sequential"  # Must approve in order


class AuditAction(enum.Enum):
    """Types of audit log actions."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    POST = "post"
    CANCEL = "cancel"
    CLOSE = "close"
    REOPEN = "reopen"
    EXPORT = "export"


class ExchangeRateSource(enum.Enum):
    """Source of exchange rate."""
    MANUAL = "manual"
    API = "api"
    IMPORT = "import"


# =============================================================================
# FISCAL PERIOD
# =============================================================================

class FiscalPeriod(Base):
    """Fiscal period for period-based closing and posting control."""

    __tablename__ = "fiscal_periods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to fiscal year
    fiscal_year_id: Mapped[int] = mapped_column(
        ForeignKey("fiscal_years.id"), nullable=False, index=True
    )

    # Period identification
    period_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "2024-01", "2024-Q1"
    period_type: Mapped[FiscalPeriodType] = mapped_column(
        Enum(FiscalPeriodType), nullable=False
    )

    # Date range
    start_date: Mapped[date] = mapped_column(nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(nullable=False, index=True)

    # Status
    status: Mapped[FiscalPeriodStatus] = mapped_column(
        Enum(FiscalPeriodStatus), default=FiscalPeriodStatus.OPEN, index=True
    )

    # Close tracking
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Reopen tracking
    reopened_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reopened_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Closing entry reference
    closing_journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "period_name", name="uq_fiscal_period_name"),
        Index("ix_fiscal_periods_dates", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<FiscalPeriod {self.period_name} ({self.status.value})>"


# =============================================================================
# APPROVAL WORKFLOW
# =============================================================================

class ApprovalWorkflow(Base):
    """Workflow definition for document approvals."""

    __tablename__ = "approval_workflows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Document type this workflow applies to
    doctype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g., "journal_entry", "expense", "payment", "purchase_invoice"

    # Settings
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    is_mandatory: Mapped[bool] = mapped_column(default=False)  # All docs of this type must use this workflow

    # Escalation settings
    escalation_enabled: Mapped[bool] = mapped_column(default=False)
    escalation_hours: Mapped[Optional[int]] = mapped_column(nullable=True)  # Hours before escalation

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    steps: Mapped[List["ApprovalStep"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="ApprovalStep.step_order"
    )

    def __repr__(self) -> str:
        return f"<ApprovalWorkflow {self.workflow_name} for {self.doctype}>"


class ApprovalStep(Base):
    """Individual step in an approval workflow."""

    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Step ordering
    step_order: Mapped[int] = mapped_column(nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Approval requirements
    role_required: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Role name
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # Specific user

    # Approval mode for this step
    approval_mode: Mapped[ApprovalMode] = mapped_column(
        Enum(ApprovalMode), default=ApprovalMode.ANY
    )

    # Amount thresholds (optional)
    amount_threshold_min: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    amount_threshold_max: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Auto-approve settings
    auto_approve_below: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Escalation override
    escalation_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    escalation_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Can reject at this step?
    can_reject: Mapped[bool] = mapped_column(default=True)

    # Relationships
    workflow: Mapped["ApprovalWorkflow"] = relationship(back_populates="steps")

    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_workflow_step_order"),
    )

    def __repr__(self) -> str:
        return f"<ApprovalStep {self.step_order}: {self.step_name}>"


class DocumentApproval(Base):
    """Tracks approval state for a specific document."""

    __tablename__ = "document_approvals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Document reference
    doctype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # Workflow reference
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("approval_workflows.id"), nullable=False, index=True
    )
    current_step: Mapped[int] = mapped_column(default=0)  # 0 = not yet submitted

    # Status
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.DRAFT, index=True
    )

    # Amount for threshold checks
    amount: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Submission tracking
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    submitted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Current step approval tracking
    step_approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    step_approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    step_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Final approval
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Rejection
    rejected_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rejected_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Posted (after approval)
    posted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    posted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Escalation tracking
    escalated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    escalation_count: Mapped[int] = mapped_column(default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    approval_history: Mapped[List["ApprovalHistory"]] = relationship(
        back_populates="document_approval", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("doctype", "document_id", name="uq_document_approval"),
        Index("ix_document_approvals_status", "status", "doctype"),
    )

    def __repr__(self) -> str:
        return f"<DocumentApproval {self.doctype}:{self.document_id} ({self.status.value})>"


class ApprovalHistory(Base):
    """History of approval actions on a document."""

    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_approval_id: Mapped[int] = mapped_column(
        ForeignKey("document_approvals.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Action details
    step_order: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approve, reject, escalate, etc.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    action_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    document_approval: Mapped["DocumentApproval"] = relationship(back_populates="approval_history")

    def __repr__(self) -> str:
        return f"<ApprovalHistory step={self.step_order} action={self.action}>"


# =============================================================================
# AUDIT LOG
# =============================================================================

class AuditLog(Base):
    """Immutable audit log for all accounting operations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Document reference
    doctype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(nullable=False, index=True)
    document_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Human-readable ref

    # Action
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False, index=True)

    # User info (denormalized for immutability)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Change tracking
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Additional context
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp (immutable)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_logs_doctype_docid", "doctype", "document_id"),
        Index("ix_audit_logs_timestamp_action", "timestamp", "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.doctype}:{self.document_id} {self.action.value} at {self.timestamp}>"


# =============================================================================
# EXCHANGE RATE
# =============================================================================

class ExchangeRate(Base):
    """Exchange rate history for multi-currency support."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Currency pair
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)

    # Rate and date
    rate_date: Mapped[date] = mapped_column(nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(nullable=False)

    # Source
    source: Mapped[ExchangeRateSource] = mapped_column(
        Enum(ExchangeRateSource), default=ExchangeRateSource.MANUAL
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "rate_date", name="uq_exchange_rate"),
        Index("ix_exchange_rates_pair_date", "from_currency", "to_currency", "rate_date"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.from_currency}/{self.to_currency} = {self.rate} on {self.rate_date}>"


class RevaluationEntry(Base):
    """FX revaluation entries for period-end adjustments."""

    __tablename__ = "revaluation_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Period reference
    fiscal_period_id: Mapped[int] = mapped_column(
        ForeignKey("fiscal_periods.id"), nullable=False, index=True
    )

    # Account being revalued
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Original values
    original_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(nullable=False)

    # Revalued values
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate_used: Mapped[Decimal] = mapped_column(nullable=False)
    revalued_amount: Mapped[Decimal] = mapped_column(nullable=False)

    # Gain/loss
    gain_loss_amount: Mapped[Decimal] = mapped_column(nullable=False)
    is_realized: Mapped[bool] = mapped_column(default=False)

    # Generated journal entry
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_revaluation_period_account", "fiscal_period_id", "account_id"),
        UniqueConstraint(
            "fiscal_period_id", "account_id", "base_currency",
            name="uq_revaluation_period_account_currency"
        ),
    )

    def __repr__(self) -> str:
        return f"<RevaluationEntry account={self.account_name} gain_loss={self.gain_loss_amount}>"


# =============================================================================
# ACCOUNTING CONTROL
# =============================================================================

class AccountingControl(Base):
    """Accounting control settings (singleton per company or global)."""

    __tablename__ = "accounting_controls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Company scope (null = global defaults)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    # Base currency
    base_currency: Mapped[str] = mapped_column(String(3), default="NGN")

    # Posting controls
    backdating_days_allowed: Mapped[int] = mapped_column(default=7)
    future_posting_days_allowed: Mapped[int] = mapped_column(default=0)

    # Voucher numbering
    auto_voucher_numbering: Mapped[bool] = mapped_column(default=True)
    voucher_prefix_format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g., "JV-{YYYY}-{MM}-{####}"

    # Attachment requirements
    require_attachment_journal_entry: Mapped[bool] = mapped_column(default=False)
    require_attachment_expense: Mapped[bool] = mapped_column(default=True)
    require_attachment_payment: Mapped[bool] = mapped_column(default=False)
    require_attachment_invoice: Mapped[bool] = mapped_column(default=False)

    # Approval settings
    require_approval_journal_entry: Mapped[bool] = mapped_column(default=False)
    require_approval_expense: Mapped[bool] = mapped_column(default=True)
    require_approval_payment: Mapped[bool] = mapped_column(default=False)

    # Period settings
    auto_create_fiscal_periods: Mapped[bool] = mapped_column(default=True)
    default_period_type: Mapped[FiscalPeriodType] = mapped_column(
        Enum(FiscalPeriodType), default=FiscalPeriodType.MONTH
    )

    # Retained earnings account
    retained_earnings_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Gain/loss accounts for FX
    fx_gain_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fx_loss_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<AccountingControl company={self.company or 'GLOBAL'}>"


# =============================================================================
# VOUCHER SEQUENCE
# =============================================================================

class VoucherSequence(Base):
    """Tracks voucher numbering sequences."""

    __tablename__ = "voucher_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Sequence identification
    prefix: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "JV-2024-12"
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Current sequence
    current_number: Mapped[int] = mapped_column(default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("prefix", "company", name="uq_voucher_sequence"),
    )

    def __repr__(self) -> str:
        return f"<VoucherSequence {self.prefix}: {self.current_number}>"

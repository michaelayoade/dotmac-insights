"""Type definitions for expense services.

These dataclasses define the contract for expense operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

__all__ = [
    # Enums
    "ClaimStatus",
    "FundingMethod",
    # Expense claim types
    "ExpenseClaimFilters",
    "ExpenseLineData",
    "ExpenseClaimCreateData",
    "ExpenseClaimUpdateData",
    # Cash advance types
    "CashAdvanceFilters",
    "CashAdvanceCreateData",
    # Expense report types
    "ExpenseReportFilters",
    "ExpenseSummaryResult",
]


# =============================================================================
# Enums
# =============================================================================

class ClaimStatus(str, Enum):
    """Expense claim status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    REVERSED = "reversed"


class FundingMethod(str, Enum):
    """How an expense was funded."""
    OUT_OF_POCKET = "out_of_pocket"
    CORPORATE_CARD = "corporate_card"
    CASH_ADVANCE = "cash_advance"
    PER_DIEM = "per_diem"


# =============================================================================
# Expense Claim Types
# =============================================================================

@dataclass
class ExpenseClaimFilters:
    """Filters for listing expense claims."""

    search: Optional[str] = None
    status: Optional[ClaimStatus] = None
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    project_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    funding_method: Optional[FundingMethod] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    company: Optional[str] = None
    sort_by: str = "claim_date"
    sort_dir: str = "desc"


@dataclass
class ExpenseLineData:
    """Data for an expense line item."""

    category_id: int
    expense_date: date
    claimed_amount: Decimal
    description: Optional[str] = None
    expense_account: Optional[str] = None
    funding_method: str = "out_of_pocket"
    merchant: Optional[str] = None
    location: Optional[str] = None
    # Tax
    tax_amount: Decimal = Decimal("0")
    tax_code: Optional[str] = None
    is_tax_reclaimable: bool = False
    # Cost tracking
    cost_center: Optional[str] = None
    project_id: Optional[int] = None
    # Receipt
    receipt_required: bool = True
    receipt_attached: bool = False
    receipt_url: Optional[str] = None


@dataclass
class ExpenseClaimCreateData:
    """Data for creating an expense claim."""

    employee_id: int
    title: str
    claim_date: date
    lines: List[ExpenseLineData] = field(default_factory=list)
    description: Optional[str] = None
    currency: str = "NGN"
    base_currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    project_id: Optional[int] = None
    cost_center: Optional[str] = None
    cash_advance_id: Optional[int] = None
    company: Optional[str] = None


@dataclass
class ExpenseClaimUpdateData:
    """Data for updating an expense claim (draft only)."""

    title: Optional[str] = None
    description: Optional[str] = None
    claim_date: Optional[date] = None
    project_id: Optional[int] = None
    cost_center: Optional[str] = None


# =============================================================================
# Cash Advance Types
# =============================================================================

@dataclass
class CashAdvanceFilters:
    """Filters for listing cash advances."""

    search: Optional[str] = None
    status: Optional[str] = None
    employee_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    has_balance: Optional[bool] = None
    sort_by: str = "advance_date"
    sort_dir: str = "desc"


@dataclass
class CashAdvanceCreateData:
    """Data for creating a cash advance request."""

    employee_id: int
    purpose: str
    advance_amount: Decimal
    currency: str = "NGN"
    advance_date: Optional[date] = None
    expected_expense_date: Optional[date] = None
    remarks: Optional[str] = None
    project_id: Optional[int] = None
    cost_center: Optional[str] = None


# =============================================================================
# Expense Report Types
# =============================================================================

@dataclass
class ExpenseReportFilters:
    """Filters for expense reports."""

    from_date: date
    to_date: date
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    project_id: Optional[int] = None
    category_id: Optional[int] = None
    funding_method: Optional[FundingMethod] = None
    company: Optional[str] = None
    group_by: str = "category"  # category, employee, department, project, month


@dataclass
class ExpenseSummaryResult:
    """Result of expense summary query."""

    total_claimed: Decimal
    total_approved: Decimal
    total_paid: Decimal
    total_pending: Decimal
    claim_count: int
    by_category: dict
    by_funding_method: dict
    by_status: dict
    from_date: date
    to_date: date

"""Type definitions for tax service.

These dataclasses define the contract for tax filing and payment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

__all__ = [
    # Tax Filing types
    "TaxCodeFilters",
    "TaxCodeCreateData",
    "TaxCodeUpdateData",
    "TaxFilingFilters",
    "TaxFilingCreateData",
    "TaxFilingUpdateData",
    "TaxPaymentCreateData",
    "TaxDashboardSummary",
]


@dataclass
class TaxFilingFilters:
    """Filters for listing tax filing periods."""

    tax_type: Optional[str] = None
    status: Optional[str] = None
    year: Optional[int] = None


@dataclass
class TaxCodeFilters:
    """Filters for listing tax codes."""

    query: Optional[str] = None
    tax_type: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class TaxCodeCreateData:
    """Data for creating a tax code."""

    code: str
    name: str
    rate: Decimal
    tax_type: str
    is_tax_inclusive: bool = False
    rounding_method: str = "round"
    rounding_precision: int = 2
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    country: Optional[str] = None
    account_head: Optional[str] = None
    cost_center: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    company: Optional[str] = None


@dataclass
class TaxCodeUpdateData:
    """Data for updating a tax code (all fields optional)."""

    name: Optional[str] = None
    rate: Optional[Decimal] = None
    tax_type: Optional[str] = None
    is_tax_inclusive: Optional[bool] = None
    rounding_method: Optional[str] = None
    rounding_precision: Optional[int] = None
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    country: Optional[str] = None
    account_head: Optional[str] = None
    cost_center: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    company: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class TaxFilingCreateData:
    """Data for creating a tax filing period."""

    tax_type: str
    period_name: str
    period_start: date
    period_end: date
    due_date: date
    tax_base: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")


@dataclass
class TaxFilingUpdateData:
    """Data for updating a tax filing period (all fields optional)."""

    period_name: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    due_date: Optional[date] = None
    tax_base: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None


@dataclass
class TaxPaymentCreateData:
    """Data for recording a tax payment."""

    payment_date: date
    amount: Decimal
    payment_reference: Optional[str] = None
    payment_method: Optional[str] = None
    bank_account: Optional[str] = None


@dataclass
class TaxTypeSummary:
    """Summary for a single tax type."""

    open_periods: int
    total_outstanding: float
    overdue_count: int


@dataclass
class TaxDashboardSummary:
    """Tax dashboard summary."""

    as_of_date: date
    summary_by_type: dict
    total_outstanding: float
    total_overdue_count: int
    upcoming_due: List[dict] = field(default_factory=list)
    overdue: List[dict] = field(default_factory=list)

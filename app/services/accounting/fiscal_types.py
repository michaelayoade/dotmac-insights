"""Type definitions for fiscal service.

These dataclasses define the contract for fiscal year and cost center operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

__all__ = [
    # Fiscal Year types
    "FiscalYearFilters",
    "FiscalYearCreateData",
    "FiscalYearUpdateData",
    # Fiscal Period types
    "FiscalPeriodFilters",
    # Cost Center types
    "CostCenterFilters",
    "CostCenterCreateData",
    "CostCenterUpdateData",
    "CostCenterExpenseBreakdown",
]


# ============= FISCAL YEAR TYPES =============

@dataclass
class FiscalYearFilters:
    """Filters for listing fiscal years."""

    include_disabled: bool = False


@dataclass
class FiscalYearCreateData:
    """Data for creating a fiscal year."""

    year: str
    year_start_date: Optional[date] = None
    year_end_date: Optional[date] = None
    is_short_year: bool = False
    disabled: bool = False
    auto_created: bool = False


@dataclass
class FiscalYearUpdateData:
    """Data for updating a fiscal year (all fields optional)."""

    year: Optional[str] = None
    year_start_date: Optional[date] = None
    year_end_date: Optional[date] = None
    is_short_year: Optional[bool] = None
    disabled: Optional[bool] = None
    auto_created: Optional[bool] = None


# ============= FISCAL PERIOD TYPES =============

@dataclass
class FiscalPeriodFilters:
    """Filters for listing fiscal periods."""

    year: Optional[str] = None
    status: Optional[str] = None


# ============= COST CENTER TYPES =============

@dataclass
class CostCenterFilters:
    """Filters for listing cost centers."""

    include_disabled: bool = False
    company: Optional[str] = None


@dataclass
class CostCenterCreateData:
    """Data for creating a cost center."""

    cost_center_name: str
    cost_center_number: Optional[str] = None
    parent_cost_center: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    disabled: bool = False
    lft: Optional[int] = None
    rgt: Optional[int] = None


@dataclass
class CostCenterUpdateData:
    """Data for updating a cost center (all fields optional)."""

    cost_center_name: Optional[str] = None
    cost_center_number: Optional[str] = None
    parent_cost_center: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


@dataclass
class ExpenseByAccount:
    """Expense breakdown by account."""

    account: str
    account_name: str
    amount: float


@dataclass
class CostCenterExpenseBreakdown:
    """Cost center with expense breakdown."""

    id: int
    erpnext_id: Optional[str]
    name: str
    number: Optional[str]
    parent: Optional[str]
    company: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    total_expenses: float
    breakdown: List[ExpenseByAccount] = field(default_factory=list)

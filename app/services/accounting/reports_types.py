"""Type definitions for financial reports service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

__all__ = [
    "TrialBalanceParams",
    "FinancialRatiosParams",
    "BalanceSheetParams",
    "IncomeStatementParams",
    "CashFlowParams",
]


@dataclass
class TrialBalanceParams:
    """Parameters for trial balance report."""

    as_of_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    cost_center: Optional[str] = None
    drill: bool = False


@dataclass
class FinancialRatiosParams:
    """Parameters for financial ratios report."""

    as_of_date: Optional[date] = None
    fiscal_year: Optional[str] = None


@dataclass
class BalanceSheetParams:
    """Parameters for balance sheet report."""

    as_of_date: Optional[date] = None


@dataclass
class IncomeStatementParams:
    """Parameters for income statement report."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class CashFlowParams:
    """Parameters for cash flow report."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = 50

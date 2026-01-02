"""Type definitions for financial reports service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

__all__ = [
    "TrialBalanceParams",
    "FinancialRatiosParams",
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

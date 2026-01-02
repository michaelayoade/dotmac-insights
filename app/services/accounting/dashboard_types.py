"""Type definitions for dashboard service.

These dataclasses define the contract for dashboard operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

__all__ = [
    "DashboardFilters",
    "DatePeriod",
    "BalanceSummary",
    "PerformanceSummary",
    "ReceivablesPayablesSummary",
    "BankBalance",
    "ActivityCounts",
    "DashboardData",
    "DashboardBundleFilters",
    "DashboardBundle",
]


@dataclass
class DashboardFilters:
    """Filters for dashboard."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class DatePeriod:
    """Date range for a report period."""

    start_date: date
    end_date: date


@dataclass
class BalanceSummary:
    """Balance sheet summary."""

    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    net_worth: Decimal


@dataclass
class PerformanceSummary:
    """Income/expense performance summary."""

    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    profit_margin: Decimal


@dataclass
class ReceivablesPayablesSummary:
    """AR/AP summary."""

    total_receivable: Decimal
    total_payable: Decimal
    net_position: Decimal


@dataclass
class BankBalance:
    """Bank account balance."""

    account: str
    balance: Decimal


@dataclass
class ActivityCounts:
    """Activity counts for a period."""

    gl_entries_count: int
    bank_transactions_count: int


@dataclass
class DashboardData:
    """Full dashboard data."""

    period: DatePeriod
    summary: BalanceSummary
    performance: PerformanceSummary
    receivables_payables: ReceivablesPayablesSummary
    bank_balances: List[BankBalance]
    activity: ActivityCounts

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-compatible dict."""
        return {
            "period": {
                "start_date": self.period.start_date.isoformat(),
                "end_date": self.period.end_date.isoformat(),
            },
            "summary": {
                "total_assets": float(self.summary.total_assets),
                "total_liabilities": float(self.summary.total_liabilities),
                "total_equity": float(self.summary.total_equity),
                "net_worth": float(self.summary.net_worth),
            },
            "performance": {
                "total_income": float(self.performance.total_income),
                "total_expenses": float(self.performance.total_expenses),
                "net_profit": float(self.performance.net_profit),
                "profit_margin": float(self.performance.profit_margin),
            },
            "receivables_payables": {
                "total_receivable": float(self.receivables_payables.total_receivable),
                "total_payable": float(self.receivables_payables.total_payable),
                "net_position": float(self.receivables_payables.net_position),
            },
            "bank_balances": [
                {"account": bb.account, "balance": float(bb.balance)}
                for bb in self.bank_balances
            ],
            "activity": {
                "gl_entries_count": self.activity.gl_entries_count,
                "bank_transactions_count": self.activity.bank_transactions_count,
            },
        }


@dataclass
class DashboardBundleFilters:
    """Filters for dashboard bundle."""

    currency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    as_of_date: Optional[date] = None
    top_n: int = 5


@dataclass
class DashboardBundle:
    """Bundled dashboard data with all reports."""

    currency: Optional[str]
    dashboard: Dict[str, Any]
    balance_sheet: Dict[str, Any]
    income_statement: Dict[str, Any]
    cash_flow: Dict[str, Any]
    receivables_outstanding: Dict[str, Any]
    payables_outstanding: Dict[str, Any]
    bank_accounts: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-compatible dict."""
        return {
            "currency": self.currency,
            "dashboard": self.dashboard,
            "balance_sheet": self.balance_sheet,
            "income_statement": self.income_statement,
            "cash_flow": self.cash_flow,
            "receivables_outstanding": self.receivables_outstanding,
            "payables_outstanding": self.payables_outstanding,
            "bank_accounts": self.bank_accounts,
        }

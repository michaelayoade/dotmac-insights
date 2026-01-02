"""Financial reports service.

This module contains business logic for generating financial reports:
- Trial Balance
- Financial Ratios
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, AccountType, GLEntry
from app.services.errors import NotFoundError, ValidationError

from app.api.accounting.helpers import (
    get_accounts_by_erpnext_id,
    get_effective_root_type,
    is_cogs_account,
    is_finance_cost_account,
)

from .reports_types import TrialBalanceParams, FinancialRatiosParams

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ReportsService"]


class ReportsService:
    """Service for generating financial reports."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def _get_fiscal_year_dates(self, fiscal_year: Optional[str] = None) -> Tuple[date, date]:
        """Get fiscal year dates."""
        from app.models.accounting import FiscalYear

        if fiscal_year:
            fy = self.db.query(FiscalYear).filter(FiscalYear.year == fiscal_year).first()
            if not fy:
                raise NotFoundError(f"Fiscal year {fiscal_year} not found")
            if fy.year_start_date is None or fy.year_end_date is None:
                raise ValidationError(f"Fiscal year {fiscal_year} is missing start or end date")
            return fy.year_start_date, fy.year_end_date

        today = date.today()
        return date(today.year, 1, 1), date(today.year, 12, 31)

    def get_trial_balance(self, params: TrialBalanceParams) -> Dict[str, Any]:
        """Get trial balance report.

        Shows debit and credit totals for each account.
        """
        end_date = params.as_of_date or date.today()

        start_date = None
        if params.fiscal_year:
            start_date, _ = self._get_fiscal_year_dates(params.fiscal_year)

        query = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= end_date,
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)

        if params.cost_center:
            query = query.filter(GLEntry.cost_center == params.cost_center)

        query = query.group_by(GLEntry.account)
        results = query.all()

        accounts: Dict[str, Account] = get_accounts_by_erpnext_id(self.db)

        trial_balance = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for row in results:
            acc = accounts.get(row.account)
            debit = row.total_debit or Decimal("0")
            credit = row.total_credit or Decimal("0")
            balance = debit - credit

            entry = {
                "account": row.account,
                "account_name": acc.account_name if acc else row.account,
                "root_type": acc.root_type.value if acc and acc.root_type else None,
                "debit": float(debit),
                "credit": float(credit),
                "balance": float(balance),
                "balance_type": "Dr" if balance >= 0 else "Cr",
            }
            if params.drill and acc:
                entry["account_id"] = acc.id
                entry["drill_url"] = f"/api/accounting/accounts/{acc.id}/ledger"
            trial_balance.append(entry)

            total_debit += debit
            total_credit += credit

        trial_balance.sort(key=lambda x: x["account_name"])

        return {
            "as_of_date": end_date.isoformat(),
            "fiscal_year": params.fiscal_year,
            "total_debit": float(total_debit),
            "total_credit": float(total_credit),
            "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
            "difference": float(abs(total_debit - total_credit)),
            "accounts": trial_balance,
        }

    def get_financial_ratios(self, params: FinancialRatiosParams) -> Dict[str, Any]:
        """Get financial ratios.

        Calculates liquidity, solvency, efficiency, and profitability ratios.
        """
        end_date = params.as_of_date or date.today()

        if params.fiscal_year:
            period_start, period_end = self._get_fiscal_year_dates(params.fiscal_year)
        else:
            period_start = date(end_date.year, 1, 1)
            period_end = end_date

        accounts: Dict[str, Account] = get_accounts_by_erpnext_id(self.db)

        # Balance sheet balances
        balances = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= end_date,
        ).group_by(GLEntry.account).all()

        balance_map = {r.account: float(r.balance or 0) for r in balances if r.account}

        # P&L period data
        period_data = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= period_start,
            GLEntry.posting_date <= period_end,
        ).group_by(GLEntry.account).all()

        period_map = {
            r.account: {"debit": float(r.debit or 0), "credit": float(r.credit or 0)}
            for r in period_data if r.account
        }

        # Balance sheet components
        current_asset_types = {"Bank", "Cash", "Receivable", "Stock", "Current Asset"}
        current_assets = sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type in current_asset_types
        )

        cash = sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type in {"Bank", "Cash"}
        )

        ar = sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type == "Receivable"
        )

        inventory = sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type == "Stock"
        )

        current_liabilities = abs(sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type in {"Payable", "Current Liability", "Tax Liability"}
        ))

        ap = abs(sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if acc.account_type == "Payable"
        ))

        total_assets = sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if get_effective_root_type(acc) == AccountType.ASSET
        )

        total_liabilities = abs(sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if get_effective_root_type(acc) == AccountType.LIABILITY
        ))

        total_equity = abs(sum(
            balance_map.get(acc_id, 0)
            for acc_id, acc in accounts.items()
            if get_effective_root_type(acc) == AccountType.EQUITY
        ))

        # P&L components
        revenue = sum(
            period_map.get(acc_id, {"credit": 0, "debit": 0})["credit"] -
            period_map.get(acc_id, {"credit": 0, "debit": 0})["debit"]
            for acc_id, acc in accounts.items()
            if acc.root_type == AccountType.INCOME
        )

        cogs = sum(
            period_map.get(acc_id, {"debit": 0, "credit": 0})["debit"] -
            period_map.get(acc_id, {"debit": 0, "credit": 0})["credit"]
            for acc_id, acc in accounts.items()
            if acc.root_type == AccountType.EXPENSE and is_cogs_account(acc)
        )

        operating_expenses = sum(
            period_map.get(acc_id, {"debit": 0, "credit": 0})["debit"] -
            period_map.get(acc_id, {"debit": 0, "credit": 0})["credit"]
            for acc_id, acc in accounts.items()
            if acc.root_type == AccountType.EXPENSE and not is_cogs_account(acc)
        )

        interest_expense = sum(
            period_map.get(acc_id, {"debit": 0, "credit": 0})["debit"] -
            period_map.get(acc_id, {"debit": 0, "credit": 0})["credit"]
            for acc_id, acc in accounts.items()
            if is_finance_cost_account(acc)
        )

        gross_profit = revenue - cogs
        operating_income = gross_profit - operating_expenses
        net_income = revenue - cogs - operating_expenses

        def safe_div(a: float, b: float) -> Optional[float]:
            return round(a / b, 4) if b != 0 else None

        return {
            "as_of_date": end_date.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "liquidity": {
                "current_ratio": safe_div(current_assets, current_liabilities),
                "quick_ratio": safe_div(current_assets - inventory, current_liabilities),
                "cash_ratio": safe_div(cash, current_liabilities),
            },
            "solvency": {
                "debt_to_equity": safe_div(total_liabilities, total_equity),
                "debt_to_assets": safe_div(total_liabilities, total_assets),
                "interest_coverage": safe_div(operating_income, interest_expense),
            },
            "efficiency": {
                "ar_turnover": safe_div(revenue, ar) if ar > 0 else None,
                "ar_days": safe_div(ar * 365, revenue) if revenue > 0 else None,
                "ap_turnover": safe_div(cogs, ap) if ap > 0 else None,
                "ap_days": safe_div(ap * 365, cogs) if cogs > 0 else None,
                "inventory_turnover": safe_div(cogs, inventory) if inventory > 0 else None,
                "inventory_days": safe_div(inventory * 365, cogs) if cogs > 0 else None,
                "asset_turnover": safe_div(revenue, total_assets),
            },
            "profitability": {
                "return_on_assets": safe_div(net_income, total_assets),
                "return_on_equity": safe_div(net_income, total_equity),
                "gross_margin": safe_div(gross_profit * 100, revenue),
                "operating_margin": safe_div(operating_income * 100, revenue),
                "net_margin": safe_div(net_income * 100, revenue),
            },
            "components": {
                "current_assets": current_assets,
                "current_liabilities": current_liabilities,
                "total_assets": total_assets,
                "total_liabilities": total_liabilities,
                "total_equity": total_equity,
                "cash": cash,
                "ar": ar,
                "ap": ap,
                "inventory": inventory,
                "revenue": revenue,
                "cogs": cogs,
                "gross_profit": gross_profit,
                "operating_income": operating_income,
                "net_income": net_income,
                "interest_expense": interest_expense,
            },
        }

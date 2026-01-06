"""Financial reports service.

This module contains business logic for generating financial reports:
- Trial Balance
- Financial Ratios
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import Account, AccountType, GLEntry
from app.services.errors import NotFoundError, ValidationError

from .account_utils import (
    get_accounts_by_erpnext_id,
    get_effective_root_type,
    is_cogs_account,
    is_finance_cost_account,
)

from .reports_types import (
    TrialBalanceParams,
    FinancialRatiosParams,
    BalanceSheetParams,
    IncomeStatementParams,
    CashFlowParams,
)

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

    def get_trial_balance_view(self, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get trial balance data for server-rendered views."""
        if not as_of_date:
            as_of_date = datetime.utcnow()

        accounts_data = []

        accounts = self.db.query(Account).filter(
            Account.is_group == False,
        ).order_by(Account.root_type, Account.account_number, Account.account_name).all()

        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for account in accounts:
            debit_sum = self.db.query(func.sum(GLEntry.debit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date <= as_of_date,
            ).scalar() or Decimal("0")

            credit_sum = self.db.query(func.sum(GLEntry.credit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date <= as_of_date,
            ).scalar() or Decimal("0")

            balance = debit_sum - credit_sum

            if balance == 0 and debit_sum == 0 and credit_sum == 0:
                continue

            debit_balance = Decimal("0")
            credit_balance = Decimal("0")

            if account.root_type and account.root_type.value in ["asset", "expense"]:
                if balance >= 0:
                    debit_balance = balance
                else:
                    credit_balance = abs(balance)
            else:
                if balance <= 0:
                    credit_balance = abs(balance)
                else:
                    debit_balance = balance

            accounts_data.append({
                "account": account,
                "debit": debit_balance,
                "credit": credit_balance,
            })

            total_debit += debit_balance
            total_credit += credit_balance

        return {
            "accounts": accounts_data,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
            "as_of_date": as_of_date,
        }

    def get_balance_sheet(self, params: BalanceSheetParams) -> Dict[str, Any]:
        """Get balance sheet data for server-rendered views."""
        as_of_date = params.as_of_date or datetime.utcnow()

        def get_section_data(root_type: AccountType) -> list:
            accounts = self.db.query(Account).filter(
                Account.is_group == False,
                Account.root_type == root_type,
            ).order_by(Account.account_number, Account.account_name).all()

            result = []
            for account in accounts:
                debit_sum = self.db.query(func.sum(GLEntry.debit)).filter(
                    GLEntry.account == account.account_name,
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date <= as_of_date,
                ).scalar() or Decimal("0")

                credit_sum = self.db.query(func.sum(GLEntry.credit)).filter(
                    GLEntry.account == account.account_name,
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date <= as_of_date,
                ).scalar() or Decimal("0")

                balance = debit_sum - credit_sum
                if root_type in [AccountType.LIABILITY, AccountType.EQUITY]:
                    balance = -balance

                if balance != 0:
                    result.append({
                        "account": account,
                        "balance": balance,
                    })

            return result

        assets = get_section_data(AccountType.ASSET)
        liabilities = get_section_data(AccountType.LIABILITY)
        equity = get_section_data(AccountType.EQUITY)

        income_sum = self.db.query(
            func.sum(GLEntry.credit) - func.sum(GLEntry.debit)
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of_date,
            GLEntry.account.in_(
                self.db.query(Account.account_name).filter(
                    Account.root_type == AccountType.INCOME
                )
            ),
        ).scalar() or Decimal("0")

        expense_sum = self.db.query(
            func.sum(GLEntry.debit) - func.sum(GLEntry.credit)
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of_date,
            GLEntry.account.in_(
                self.db.query(Account.account_name).filter(
                    Account.root_type == AccountType.EXPENSE
                )
            ),
        ).scalar() or Decimal("0")

        net_income = income_sum - expense_sum

        total_assets = sum(a["balance"] for a in assets)
        total_liabilities = sum(l["balance"] for l in liabilities)
        total_equity = sum(e["balance"] for e in equity) + net_income

        return {
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < Decimal("0.01"),
            "as_of_date": as_of_date,
        }

    def get_income_statement(self, params: IncomeStatementParams) -> Dict[str, Any]:
        """Get income statement data for server-rendered views."""
        now = datetime.utcnow()
        end_date = params.end_date or now
        start_date = params.start_date or now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )

        def get_section_data(root_type: AccountType) -> list:
            accounts = self.db.query(Account).filter(
                Account.is_group == False,
                Account.root_type == root_type,
            ).order_by(Account.account_number, Account.account_name).all()

            result = []
            for account in accounts:
                debit_sum = self.db.query(func.sum(GLEntry.debit)).filter(
                    GLEntry.account == account.account_name,
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date >= start_date,
                    GLEntry.posting_date <= end_date,
                ).scalar() or Decimal("0")

                credit_sum = self.db.query(func.sum(GLEntry.credit)).filter(
                    GLEntry.account == account.account_name,
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date >= start_date,
                    GLEntry.posting_date <= end_date,
                ).scalar() or Decimal("0")

                if root_type == AccountType.INCOME:
                    balance = credit_sum - debit_sum
                else:
                    balance = debit_sum - credit_sum

                if balance != 0:
                    result.append({
                        "account": account,
                        "balance": balance,
                    })

            return result

        income = get_section_data(AccountType.INCOME)
        expenses = get_section_data(AccountType.EXPENSE)

        total_income = sum(i["balance"] for i in income)
        total_expenses = sum(e["balance"] for e in expenses)
        net_income = total_income - total_expenses

        return {
            "income": income,
            "expenses": expenses,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_income": net_income,
            "start_date": start_date,
            "end_date": end_date,
        }

    def get_cash_flow(self, params: CashFlowParams) -> Dict[str, Any]:
        """Get cash flow data for server-rendered views."""
        now = datetime.utcnow()
        end_date = params.end_date or now
        start_date = params.start_date or now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )

        cash_accounts = self.db.query(Account).filter(
            Account.is_group == False,
            Account.root_type == AccountType.ASSET,
            or_(
                Account.account_type.ilike("%cash%"),
                Account.account_type.ilike("%bank%"),
                Account.account_name.ilike("%cash%"),
                Account.account_name.ilike("%bank%"),
            )
        ).all()

        cash_account_names = [a.account_name for a in cash_accounts]

        opening_debit = self.db.query(func.sum(GLEntry.debit)).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date < start_date,
        ).scalar() or Decimal("0")

        opening_credit = self.db.query(func.sum(GLEntry.credit)).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date < start_date,
        ).scalar() or Decimal("0")

        opening_balance = opening_debit - opening_credit

        period_debit = self.db.query(func.sum(GLEntry.debit)).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= start_date,
            GLEntry.posting_date <= end_date,
        ).scalar() or Decimal("0")

        period_credit = self.db.query(func.sum(GLEntry.credit)).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= start_date,
            GLEntry.posting_date <= end_date,
        ).scalar() or Decimal("0")

        net_cash_flow = period_debit - period_credit
        closing_balance = opening_balance + net_cash_flow

        cash_transactions = self.db.query(GLEntry).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= start_date,
            GLEntry.posting_date <= end_date,
        ).order_by(GLEntry.posting_date.desc()).limit(params.limit).all()

        return {
            "cash_accounts": cash_accounts,
            "opening_balance": opening_balance,
            "cash_inflows": period_debit,
            "cash_outflows": period_credit,
            "net_cash_flow": net_cash_flow,
            "closing_balance": closing_balance,
            "transactions": cash_transactions,
            "start_date": start_date,
            "end_date": end_date,
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

    def get_financial_ratios_view(self, params: FinancialRatiosParams) -> Dict[str, Any]:
        """Get enriched financial ratios for server-rendered views."""
        raw_data = self.get_financial_ratios(params)

        def ratio_status(value: Optional[float], good_min: float, good_max: float,
                         warning_min: float, warning_max: float) -> str:
            if value is None:
                return "info"
            if good_min <= value <= good_max:
                return "good"
            if warning_min <= value <= warning_max:
                return "warning"
            return "critical"

        c = raw_data["components"]
        liq = raw_data["liquidity"]
        solv = raw_data["solvency"]
        eff = raw_data["efficiency"]
        prof = raw_data["profitability"]

        ar_days = 365 / eff["ar_turnover"] if eff["ar_turnover"] else 0
        ap_days = 365 / eff["ap_turnover"] if eff["ap_turnover"] else 0
        inventory_days = 365 / eff["inventory_turnover"] if eff["inventory_turnover"] else 0
        working_capital = c["current_assets"] - c["current_liabilities"]
        shareholders_equity = c["total_equity"] + c["net_income"]

        period_start = date.fromisoformat(raw_data["period_start"])
        period_end = date.fromisoformat(raw_data["period_end"])
        days_in_period = (period_end - period_start).days + 1

        return {
            "as_of_date": raw_data["as_of_date"],
            "period": {
                "start_date": raw_data["period_start"],
                "end_date": raw_data["period_end"],
                "days": days_in_period,
            },
            "liquidity_ratios": {
                "current_ratio": {
                    "value": round(liq["current_ratio"] or 0, 2),
                    "interpretation": "Current Assets / Current Liabilities",
                    "status": ratio_status(liq["current_ratio"], 1.5, 3.0, 1.0, 4.0),
                    "benchmark": "1.5 - 2.0 is healthy",
                },
                "quick_ratio": {
                    "value": round(liq["quick_ratio"] or 0, 2),
                    "interpretation": "(Current Assets - Inventory) / Current Liabilities",
                    "status": ratio_status(liq["quick_ratio"], 1.0, 2.0, 0.5, 3.0),
                    "benchmark": "1.0+ is healthy",
                },
                "cash_ratio": {
                    "value": round(liq["cash_ratio"] or 0, 2),
                    "interpretation": "Cash / Current Liabilities",
                    "status": ratio_status(liq["cash_ratio"], 0.2, 1.0, 0.1, 2.0),
                    "benchmark": "0.2 - 0.5 is typical",
                },
                "working_capital": {
                    "value": round(working_capital, 2),
                    "interpretation": "Current Assets - Current Liabilities",
                    "status": "good" if working_capital > 0 else "critical",
                },
            },
            "solvency_ratios": {
                "debt_to_equity": {
                    "value": round(solv["debt_to_equity"] or 0, 2),
                    "interpretation": "Total Liabilities / Shareholders' Equity",
                    "status": ratio_status(solv["debt_to_equity"], 0.0, 1.5, 0.0, 2.5),
                    "benchmark": "< 1.5 is conservative",
                },
                "debt_to_assets": {
                    "value": round(solv["debt_to_assets"] or 0, 2),
                    "interpretation": "Total Liabilities / Total Assets",
                    "status": ratio_status(solv["debt_to_assets"], 0.0, 0.5, 0.0, 0.7),
                    "benchmark": "< 0.5 is conservative",
                },
                "equity_ratio": {
                    "value": round(1 - (solv["debt_to_assets"] or 0), 2),
                    "interpretation": "Shareholders' Equity / Total Assets",
                    "status": ratio_status(1 - (solv["debt_to_assets"] or 0), 0.4, 1.0, 0.2, 1.0),
                    "benchmark": "> 0.5 is strong",
                },
            },
            "efficiency_ratios": {
                "receivables_turnover": {
                    "value": round(eff["ar_turnover"] or 0, 2),
                    "days": round(ar_days, 0),
                    "interpretation": "Revenue / Accounts Receivable",
                    "status": ratio_status(ar_days, 0, 45, 0, 90),
                    "benchmark": "30-45 days is typical",
                },
                "payables_turnover": {
                    "value": round(eff["ap_turnover"] or 0, 2),
                    "days": round(ap_days, 0),
                    "interpretation": "COGS / Accounts Payable",
                    "status": "info",
                    "benchmark": "30-60 days is typical",
                },
                "inventory_turnover": {
                    "value": round(eff["inventory_turnover"] or 0, 2),
                    "days": round(inventory_days, 0),
                    "interpretation": "COGS / Average Inventory",
                    "status": ratio_status(eff["inventory_turnover"] or 0, 4, 20, 2, 30),
                    "benchmark": "4-6x per year is typical",
                },
                "asset_turnover": {
                    "value": round(eff["asset_turnover"] or 0, 2),
                    "interpretation": "Revenue / Total Assets",
                    "status": ratio_status(eff["asset_turnover"] or 0, 0.5, 3.0, 0.2, 5.0),
                    "benchmark": "Varies by industry",
                },
                "cash_conversion_cycle": {
                    "value": round(ar_days + inventory_days - ap_days, 0),
                    "interpretation": "AR Days + Inventory Days - AP Days",
                    "status": "info",
                    "benchmark": "Lower is better",
                },
            },
            "profitability_ratios": {
                "gross_margin": {
                    "value": round(prof["gross_margin"] or 0, 2),
                    "interpretation": "Gross Profit / Revenue x 100",
                    "status": ratio_status(prof["gross_margin"] or 0, 20, 80, 10, 90),
                    "benchmark": "Varies by industry",
                },
                "operating_margin": {
                    "value": round(prof["operating_margin"] or 0, 2),
                    "interpretation": "Operating Income / Revenue x 100",
                    "status": ratio_status(prof["operating_margin"] or 0, 10, 40, 5, 50),
                    "benchmark": "10-20% is healthy",
                },
                "net_margin": {
                    "value": round(prof["net_margin"] or 0, 2),
                    "interpretation": "Net Income / Revenue x 100",
                    "status": ratio_status(prof["net_margin"] or 0, 5, 30, 0, 50),
                    "benchmark": "5-15% is typical",
                },
                "return_on_assets": {
                    "value": round(prof["return_on_assets"] or 0, 2),
                    "interpretation": "Net Income / Total Assets x 100",
                    "status": ratio_status(prof["return_on_assets"] or 0, 5, 20, 0, 30),
                    "benchmark": "5-10% is good",
                },
                "return_on_equity": {
                    "value": round(prof["return_on_equity"] or 0, 2),
                    "interpretation": "Net Income / Shareholders' Equity x 100",
                    "status": ratio_status(prof["return_on_equity"] or 0, 10, 30, 5, 50),
                    "benchmark": "15-20% is excellent",
                },
            },
            "components": {
                "current_assets": round(c["current_assets"], 2),
                "current_liabilities": round(c["current_liabilities"], 2),
                "total_assets": round(c["total_assets"], 2),
                "total_liabilities": round(c["total_liabilities"], 2),
                "shareholders_equity": round(shareholders_equity, 2),
                "revenue": round(c["revenue"], 2),
                "cogs": round(c["cogs"], 2),
                "gross_profit": round(c["gross_profit"], 2),
                "operating_income": round(c["operating_income"], 2),
                "net_income": round(c["net_income"], 2),
                "cash": round(c["cash"], 2),
                "receivables": round(c["ar"], 2),
                "inventory": round(c["inventory"], 2),
                "payables": round(c["ap"], 2),
            },
        }

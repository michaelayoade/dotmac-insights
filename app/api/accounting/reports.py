"""Financial reports: Trial Balance, Balance Sheet, Income Statement, Cash Flow."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    GLEntry,
)

from .helpers import (
    parse_date,
    get_fiscal_year_dates,
    get_effective_root_type,
    LIABILITY_ACCOUNT_TYPES,
    ASSET_ACCOUNT_TYPES,
)

router = APIRouter()


# =============================================================================
# TRIAL BALANCE
# =============================================================================

@router.get("/trial-balance", dependencies=[Depends(Require("accounting:read"))])
def get_trial_balance(
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    drill: bool = Query(False, description="Include account_id for drill-through to GL details"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get trial balance report.

    Shows debit and credit totals for each account. The trial balance
    should be balanced (total debits = total credits).

    Args:
        as_of_date: Report as of this date (default: today)
        fiscal_year: Filter by fiscal year
        cost_center: Filter by cost center
        drill: If true, include account_id refs for drill-through to GL

    Returns:
        Trial balance with account details and totals
    """
    end_date = parse_date(as_of_date, "as_of_date") or date.today()

    # Get fiscal year start if specified
    start_date = None
    if fiscal_year:
        start_date, _ = get_fiscal_year_dates(db, fiscal_year)

    # Build GL query
    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("total_debit"),
        func.sum(GLEntry.credit).label("total_credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= end_date,
    )

    if start_date:
        query = query.filter(GLEntry.posting_date >= start_date)

    if cost_center:
        query = query.filter(GLEntry.cost_center == cost_center)

    query = query.group_by(GLEntry.account)
    results = query.all()

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

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
        if drill and acc:
            entry["account_id"] = acc.id
            entry["drill_url"] = f"/api/accounting/accounts/{acc.id}/ledger"
        trial_balance.append(entry)

        total_debit += debit
        total_credit += credit

    # Sort by account name
    trial_balance.sort(key=lambda x: x["account_name"])

    return {
        "as_of_date": end_date.isoformat(),
        "fiscal_year": fiscal_year,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
        "difference": float(abs(total_debit - total_credit)),
        "accounts": trial_balance,
    }


# =============================================================================
# BALANCE SHEET
# =============================================================================

@router.get("/balance-sheet", dependencies=[Depends(Require("accounting:read"))])
def get_balance_sheet(
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    common_size: bool = Query(False, description="Show values as percentage of total assets"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get balance sheet report.

    Assets = Liabilities + Equity

    Automatically corrects common ERPNext account misclassifications
    (e.g., Payable accounts incorrectly classified as Asset root_type).

    Args:
        as_of_date: Report as of this date (default: today)
        comparative_date: Optional date for comparison
        common_size: Show each line as percentage of total assets

    Returns:
        Balance sheet with assets, liabilities, equity sections
    """
    end_date = parse_date(as_of_date, "as_of_date") or date.today()
    comp_date = parse_date(comparative_date, "comparative_date")

    def get_balances(cutoff_date: date) -> Dict[str, Decimal]:
        """Get account balances as of a date."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff_date,
        ).group_by(GLEntry.account).all()

        return {r.account: r.balance or Decimal("0") for r in results}

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    current_balances = get_balances(end_date)
    comparative_balances = get_balances(comp_date) if comp_date else {}

    # Track reclassified accounts for warnings
    reclassified = []

    def build_section(root_type: AccountType, negate: bool = False) -> Dict:
        """Build a section of the balance sheet."""
        section_accounts = []
        total = Decimal("0")
        comp_total = Decimal("0")

        for acc_id, acc in accounts.items():
            effective_type = get_effective_root_type(acc)
            if effective_type != root_type:
                continue

            # Track if account was reclassified
            if acc.root_type != effective_type:
                reclassified.append({
                    "account": acc.account_name,
                    "original_root_type": acc.root_type.value if acc.root_type else None,
                    "effective_root_type": effective_type.value if effective_type else None,
                    "account_type": acc.account_type,
                })

            balance = current_balances.get(acc_id, Decimal("0"))
            comp_balance = comparative_balances.get(acc_id, Decimal("0"))

            if negate:
                balance = -balance
                comp_balance = -comp_balance

            if balance != 0 or comp_balance != 0:
                section_accounts.append({
                    "account": acc.account_name,
                    "account_type": acc.account_type,
                    "balance": float(balance),
                    "comparative_balance": float(comp_balance) if comp_date else None,
                    "change": float(balance - comp_balance) if comp_date else None,
                })
                total += balance
                comp_total += comp_balance

        section_accounts.sort(key=lambda x: x["account"])

        return {
            "accounts": section_accounts,
            "total": float(total),
            "comparative_total": float(comp_total) if comp_date else None,
            "change": float(total - comp_total) if comp_date else None,
        }

    assets = build_section(AccountType.ASSET)
    liabilities = build_section(AccountType.LIABILITY, negate=True)
    equity = build_section(AccountType.EQUITY, negate=True)

    # Calculate retained earnings (Income - Expense for all time)
    income_total = sum(
        -current_balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.INCOME
    )
    expense_total = sum(
        current_balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EXPENSE
    )
    retained_earnings = income_total - expense_total

    total_liab_equity = liabilities["total"] + equity["total"] + float(retained_earnings)
    difference = abs(Decimal(str(assets["total"])) - Decimal(str(total_liab_equity)))

    # Add common-size percentages if requested
    total_assets_val = assets["total"]
    if common_size and total_assets_val != 0:
        for acc in assets["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        for acc in liabilities["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        for acc in equity["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        assets["pct_of_total"] = 100.0
        liabilities["pct_of_total"] = round(liabilities["total"] / total_assets_val * 100, 2)
        equity["pct_of_total"] = round(equity["total"] / total_assets_val * 100, 2)

    result = {
        "as_of_date": end_date.isoformat(),
        "comparative_date": comp_date.isoformat() if comp_date else None,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "retained_earnings": float(retained_earnings),
        "total_assets": assets["total"],
        "total_liabilities_equity": total_liab_equity,
        "difference": float(difference),
        "is_balanced": difference < Decimal("1"),
        "reclassified_accounts": reclassified if reclassified else None,
    }

    if common_size:
        result["common_size_base"] = "total_assets"
        result["retained_earnings_pct"] = round(float(retained_earnings) / total_assets_val * 100, 2) if total_assets_val else 0

    return result


# =============================================================================
# INCOME STATEMENT (P&L)
# =============================================================================

@router.get("/income-statement", dependencies=[Depends(Require("accounting:read"))])
def get_income_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    compare_start: Optional[str] = Query(None, description="Prior period start date for comparison"),
    compare_end: Optional[str] = Query(None, description="Prior period end date for comparison"),
    show_ytd: bool = Query(False, description="Include year-to-date column"),
    common_size: bool = Query(False, description="Show values as percentage of total revenue"),
    basis: str = Query("accrual", description="Accounting basis: 'accrual' (default) or 'cash'"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get income statement (profit & loss) report.

    Shows revenue, expenses, and net income for a period with optional
    comparative analysis and common-size percentages.

    Args:
        start_date: Period start (default: fiscal year start)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates
        cost_center: Filter by cost center
        compare_start: Prior period start date for comparison
        compare_end: Prior period end date for comparison
        show_ytd: Include year-to-date column
        common_size: Show each line as percentage of total revenue
        basis: Accounting basis - 'accrual' includes all transactions,
               'cash' includes only payment-related transactions

    Returns:
        Income statement with income, expenses, and profit metrics
    """
    if basis not in ("accrual", "cash"):
        raise HTTPException(status_code=400, detail="basis must be 'accrual' or 'cash'")

    # Cash basis voucher types
    cash_voucher_types = [
        "Payment Entry",
        "Bank Entry",
        "Cash Entry",
        "payment_entry",
        "bank_entry",
        "cash_entry",
    ]

    # Determine date range
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = parse_date(end_date, "end_date") or date.today()
        period_start = parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Comparative period
    comp_start = parse_date(compare_start, "compare_start")
    comp_end = parse_date(compare_end, "compare_end")
    has_comparison = comp_start is not None and comp_end is not None

    # YTD dates
    ytd_start = date(period_end.year, 1, 1)

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    def get_period_data(p_start: date, p_end: date, cc: Optional[str] = None) -> Dict[str, tuple]:
        """Get account totals for a period."""
        query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        )
        if cc:
            query = query.filter(GLEntry.cost_center == cc)
        if basis == "cash":
            query = query.filter(GLEntry.voucher_type.in_(cash_voucher_types))
        query = query.group_by(GLEntry.account)
        results = query.all()

        data = {}
        for row in results:
            acc = accounts.get(row.account)
            if not acc:
                continue
            if acc.root_type == AccountType.INCOME:
                amount = (row.credit or Decimal("0")) - (row.debit or Decimal("0"))
            elif acc.root_type == AccountType.EXPENSE:
                amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
            else:
                continue
            data[row.account] = (amount, acc)
        return data

    # Get data for all periods
    current_data = get_period_data(period_start, period_end, cost_center)
    comp_data = get_period_data(comp_start, comp_end, cost_center) if has_comparison else {}
    ytd_data = get_period_data(ytd_start, period_end, cost_center) if show_ytd and ytd_start != period_start else {}

    def build_section(root_type: AccountType) -> Dict:
        """Build income or expense section."""
        section_accounts = []
        total = Decimal("0")
        comp_total = Decimal("0")
        ytd_total = Decimal("0")

        all_acc_ids = set(current_data.keys()) | set(comp_data.keys()) | set(ytd_data.keys())

        for acc_id in all_acc_ids:
            acc = accounts.get(acc_id)
            if not acc or acc.root_type != root_type:
                continue

            amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
            comp_amount = comp_data.get(acc_id, (Decimal("0"), acc))[0] if has_comparison else None
            ytd_amount = ytd_data.get(acc_id, (Decimal("0"), acc))[0] if show_ytd and ytd_data else None

            if amount != 0 or (comp_amount and comp_amount != 0) or (ytd_amount and ytd_amount != 0):
                entry = {
                    "account": acc.account_name,
                    "account_type": acc.account_type,
                    "amount": float(amount),
                }
                if has_comparison:
                    entry["prior_amount"] = float(comp_amount) if comp_amount else 0
                    entry["variance"] = float(amount - (comp_amount or Decimal("0")))
                    if comp_amount and comp_amount != 0:
                        entry["variance_pct"] = round(float((amount - comp_amount) / abs(comp_amount) * 100), 2)
                if show_ytd and ytd_data:
                    entry["ytd_amount"] = float(ytd_amount) if ytd_amount else 0

                section_accounts.append(entry)
                total += amount
                if has_comparison and comp_amount:
                    comp_total += comp_amount
                if show_ytd and ytd_amount:
                    ytd_total += ytd_amount

        section_accounts.sort(key=lambda x: -abs(x["amount"]))

        result = {
            "accounts": section_accounts,
            "total": float(total),
        }
        if has_comparison:
            result["prior_total"] = float(comp_total)
            result["variance"] = float(total - comp_total)
            if comp_total != 0:
                result["variance_pct"] = round(float((total - comp_total) / abs(comp_total) * 100), 2)
        if show_ytd and ytd_data:
            result["ytd_total"] = float(ytd_total)

        return result

    income = build_section(AccountType.INCOME)
    expenses = build_section(AccountType.EXPENSE)

    gross_profit = income["total"]
    net_income = income["total"] - expenses["total"]

    # Add common-size percentages
    if common_size and gross_profit != 0:
        for acc in income["accounts"]:
            acc["pct_of_revenue"] = round(acc["amount"] / gross_profit * 100, 2)
        for acc in expenses["accounts"]:
            acc["pct_of_revenue"] = round(acc["amount"] / gross_profit * 100, 2)
        income["pct_of_revenue"] = 100.0
        expenses["pct_of_revenue"] = round(expenses["total"] / gross_profit * 100, 2)

    result = {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "basis": basis,
        "income": income,
        "expenses": expenses,
        "gross_profit": gross_profit,
        "net_income": net_income,
        "profit_margin": round(net_income / gross_profit * 100, 2) if gross_profit else 0,
    }

    if has_comparison:
        result["comparison_period"] = {
            "start_date": comp_start.isoformat(),
            "end_date": comp_end.isoformat(),
        }
        comp_gross = income.get("prior_total", 0)
        comp_net = comp_gross - expenses.get("prior_total", 0)
        result["prior_gross_profit"] = comp_gross
        result["prior_net_income"] = comp_net
        result["net_income_variance"] = net_income - comp_net
        if comp_net != 0:
            result["net_income_variance_pct"] = round((net_income - comp_net) / abs(comp_net) * 100, 2)

    if show_ytd and ytd_data:
        result["ytd_period"] = {
            "start_date": ytd_start.isoformat(),
            "end_date": period_end.isoformat(),
        }
        ytd_gross = income.get("ytd_total", 0)
        ytd_net = ytd_gross - expenses.get("ytd_total", 0)
        result["ytd_gross_profit"] = ytd_gross
        result["ytd_net_income"] = ytd_net

    if common_size:
        result["common_size_base"] = "total_revenue"

    return result


# =============================================================================
# CASH FLOW
# =============================================================================

@router.get("/cash-flow", dependencies=[Depends(Require("accounting:read"))])
def get_cash_flow(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cash flow statement.

    Shows cash inflows and outflows from operating, investing,
    and financing activities.

    Args:
        start_date: Period start (default: Jan 1 of current year)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates

    Returns:
        Cash flow statement with activity breakdown
    """
    # Determine date range
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = parse_date(end_date, "end_date") or date.today()
        period_start = parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Get bank/cash accounts
    cash_accounts = db.query(Account).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        Account.disabled == False,
    ).all()
    cash_account_names = [acc.erpnext_id for acc in cash_accounts]

    def get_cash_balance(as_of: date) -> Decimal:
        """Get total cash balance as of a date."""
        result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
        ).scalar()
        return result or Decimal("0")

    opening_cash = get_cash_balance(period_start - timedelta(days=1)) if period_start else Decimal("0")
    closing_cash = get_cash_balance(period_end)

    # Bank transactions for the period
    bank_txns = db.query(BankTransaction).filter(
        BankTransaction.date >= period_start,
        BankTransaction.date <= period_end,
    ).all()

    deposits = sum(t.deposit for t in bank_txns)
    withdrawals = sum(t.withdrawal for t in bank_txns)

    # Journal entries affecting cash accounts
    cash_entries = db.query(
        GLEntry.voucher_type,
        func.sum(GLEntry.debit).label("inflow"),
        func.sum(GLEntry.credit).label("outflow"),
    ).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.voucher_type).all()

    by_voucher_type = {
        row.voucher_type: {
            "inflow": float(row.inflow or 0),
            "outflow": float(row.outflow or 0),
            "net": float((row.inflow or 0) - (row.outflow or 0)),
        }
        for row in cash_entries
    }

    # Categorize by activity type (simplified)
    operating = Decimal("0")
    investing = Decimal("0")
    financing = Decimal("0")

    for vtype, flows in by_voucher_type.items():
        net = Decimal(str(flows["net"]))
        if vtype in ["Sales Invoice", "Payment Entry", "Journal Entry"]:
            operating += net
        elif vtype in ["Purchase Invoice", "Asset"]:
            investing += net
        else:
            financing += net

    net_change = closing_cash - opening_cash

    return {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "opening_cash": float(opening_cash),
        "closing_cash": float(closing_cash),
        "net_change": float(net_change),
        "operating_activities": float(operating),
        "investing_activities": float(investing),
        "financing_activities": float(financing),
        "bank_deposits": float(deposits),
        "bank_withdrawals": float(withdrawals),
        "by_voucher_type": by_voucher_type,
    }

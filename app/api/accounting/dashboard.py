"""Dashboard endpoint for accounting overview."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    GLEntry,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
)
from app.models.invoice import Invoice, InvoiceStatus

from .helpers import parse_date, get_effective_root_type

router = APIRouter()


@router.get("/dashboard", dependencies=[Depends(Require("accounting:read"))])
def get_accounting_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounting dashboard overview.

    Shows key financial metrics at a glance including:
    - Balance sheet summary (assets, liabilities, equity)
    - Performance metrics (income, expenses, profit)
    - AR/AP summary
    - Bank balances
    - Activity counts

    Args:
        start_date: Period start date (defaults to Jan 1 of current year)
        end_date: Period end date (defaults to today)
        db: Database session

    Returns:
        Dashboard data with all key metrics
    """
    end_dt = parse_date(end_date, "end_date") or date.today()
    start_dt = parse_date(start_date, "start_date") or date(end_dt.year, 1, 1)

    # Get account balances (cumulative to end_dt)
    balances = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= end_dt,
    ).group_by(GLEntry.account).all()

    balance_map = {r.account: float(r.balance or 0) for r in balances}

    # Get accounts with their types
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Calculate totals by effective root type (handles ERPNext misclassifications)
    total_assets = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.ASSET
    )
    total_liabilities = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.LIABILITY
    )
    total_equity = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EQUITY
    )

    # Period income/expenses (within date range)
    period_entries = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= start_dt,
        GLEntry.posting_date <= end_dt,
    ).group_by(GLEntry.account).all()

    period_map = {
        r.account: {"debit": float(r.debit or 0), "credit": float(r.credit or 0)}
        for r in period_entries
    }

    total_income = sum(
        period_map.get(acc_id, {}).get("credit", 0) - period_map.get(acc_id, {}).get("debit", 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.INCOME
    )
    total_expenses = sum(
        period_map.get(acc_id, {}).get("debit", 0) - period_map.get(acc_id, {}).get("credit", 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EXPENSE
    )

    # AR/AP summaries
    total_receivable = db.query(func.sum(Invoice.balance)).filter(
        Invoice.balance > 0,
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED]),
    ).scalar() or Decimal("0")

    total_payable = db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.notin_([PurchaseInvoiceStatus.CANCELLED]),
    ).scalar() or Decimal("0")

    # Bank balances
    bank_accounts_data = []
    for acc_id, acc in accounts.items():
        if acc.account_type == "Bank":
            balance = balance_map.get(acc_id, 0)
            if balance != 0:
                bank_accounts_data.append({
                    "account": acc.account_name,
                    "balance": balance,
                })

    # Recent transactions count
    recent_gl_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.posting_date >= start_dt,
        GLEntry.posting_date <= end_dt,
        GLEntry.is_cancelled == False,
    ).scalar() or 0

    recent_bank_txn_count = db.query(func.count(BankTransaction.id)).filter(
        BankTransaction.date >= start_dt,
        BankTransaction.date <= end_dt,
    ).scalar() or 0

    return {
        "period": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
        },
        "summary": {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "net_worth": total_assets - total_liabilities,
        },
        "performance": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses,
            "profit_margin": round((total_income - total_expenses) / total_income * 100, 2) if total_income else 0,
        },
        "receivables_payables": {
            "total_receivable": float(total_receivable),
            "total_payable": float(total_payable),
            "net_position": float(total_receivable - total_payable),
        },
        "bank_balances": sorted(bank_accounts_data, key=lambda x: x["balance"], reverse=True),
        "activity": {
            "gl_entries_count": recent_gl_count,
            "bank_transactions_count": recent_bank_txn_count,
        },
    }

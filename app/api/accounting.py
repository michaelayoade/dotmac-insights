"""Accounting API endpoints for financial statements and reports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, and_, or_
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.models.customer import Customer
from app.models.accounting import (
    Account,
    AccountType,
    GLEntry,
    JournalEntry,
    JournalEntryType,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    CostCenter,
    FiscalYear,
    Supplier,
    ModeOfPayment,
)
from app.models.invoice import Invoice, InvoiceStatus, DunningHistory, DunningLevel

router = APIRouter(prefix="/accounting", tags=["accounting"])


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        # Handle ISO format with time
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")


def _resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, raise 400."""
    if requested:
        return requested
    currencies = [row[0] for row in db.query(func.distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    if len(set(currencies)) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple currencies detected; please provide the 'currency' query parameter to avoid mixed-currency aggregates.",
        )
    return currencies[0]


def _get_fiscal_year_dates(db: Session, fiscal_year: Optional[str] = None) -> tuple[date, date]:
    """Get start and end dates for a fiscal year."""
    if fiscal_year:
        fy = db.query(FiscalYear).filter(FiscalYear.year == fiscal_year).first()
        if not fy:
            raise HTTPException(status_code=404, detail=f"Fiscal year {fiscal_year} not found")
        return fy.year_start_date, fy.year_end_date

    # Default to current year
    today = date.today()
    return date(today.year, 1, 1), date(today.year, 12, 31)


# ============= DASHBOARD =============

@router.get("/dashboard", dependencies=[Depends(Require("accounting:read"))])
async def get_accounting_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounting dashboard overview.

    Shows key financial metrics at a glance.
    """
    end_dt = _parse_date(end_date, "end_date") or date.today()
    start_dt = _parse_date(start_date, "start_date") or date(end_dt.year, 1, 1)

    # Get account balances
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

    # Calculate totals by root type
    total_assets = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.root_type == AccountType.ASSET
    )
    total_liabilities = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.root_type == AccountType.LIABILITY
    )
    total_equity = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.root_type == AccountType.EQUITY
    )

    # Period income/expenses
    period_entries = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= start_dt,
        GLEntry.posting_date <= end_dt,
    ).group_by(GLEntry.account).all()

    period_map = {r.account: {"debit": float(r.debit or 0), "credit": float(r.credit or 0)} for r in period_entries}

    total_income = sum(
        period_map.get(acc_id, {}).get("credit", 0) - period_map.get(acc_id, {}).get("debit", 0)
        for acc_id, acc in accounts.items()
        if acc.root_type == AccountType.INCOME
    )
    total_expenses = sum(
        period_map.get(acc_id, {}).get("debit", 0) - period_map.get(acc_id, {}).get("credit", 0)
        for acc_id, acc in accounts.items()
        if acc.root_type == AccountType.EXPENSE
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


# ============= CHART OF ACCOUNTS =============

@router.get("/accounts", dependencies=[Depends(Require("accounting:read"))])
async def list_accounts(
    root_type: Optional[str] = None,
    account_type: Optional[str] = None,
    is_group: Optional[bool] = None,
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all accounts with filtering and pagination.

    Args:
        root_type: Filter by root type (asset, liability, equity, income, expense)
        account_type: Filter by account type (Bank, Cash, Receivable, Payable, etc.)
        is_group: Filter group vs leaf accounts
        include_disabled: Include disabled accounts
        search: Search by account name
    """
    query = db.query(Account)

    if root_type:
        try:
            root_type_enum = AccountType(root_type.lower())
            query = query.filter(Account.root_type == root_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {root_type}")

    if account_type:
        query = query.filter(Account.account_type == account_type)

    if is_group is not None:
        query = query.filter(Account.is_group == is_group)

    if not include_disabled:
        query = query.filter(Account.disabled == False)

    if search:
        query = query.filter(Account.account_name.ilike(f"%{search}%"))

    total = query.count()
    accounts = query.order_by(Account.account_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "accounts": [
            {
                "id": acc.id,
                "erpnext_id": acc.erpnext_id,
                "name": acc.account_name,
                "account_number": acc.account_number,
                "parent_account": acc.parent_account,
                "root_type": acc.root_type.value if acc.root_type else None,
                "account_type": acc.account_type,
                "is_group": acc.is_group,
                "disabled": acc.disabled,
            }
            for acc in accounts
        ],
    }


# ============= TAX PAYABLE / RECEIVABLE =============

def _tax_account_filter():
    """Filter to select tax-related accounts."""
    return or_(
        Account.account_type == "Tax",
        Account.account_name.ilike("%tax%"),
    )


def _gl_ar_ap_balances(db: Session, as_of: date) -> Dict[str, float]:
    """Return GL balances for AR/AP control accounts (credits minus debits for liabilities, debits minus credits for assets)."""
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    entries = (
        db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        )
        .filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
            GLEntry.account.isnot(None),
        )
        .group_by(GLEntry.account)
        .all()
    )

    ar_total = 0.0
    ap_total = 0.0
    for row in entries:
        acc = accounts.get(row.account)
        debit = float(row.debit or 0)
        credit = float(row.credit or 0)
        # Heuristic: account_type or root_type classification
        if acc and (acc.account_type == "Receivable" or acc.root_type == AccountType.ASSET):
            ar_total += (debit - credit)
        if acc and (acc.account_type == "Payable" or acc.root_type == AccountType.LIABILITY):
            ap_total += (credit - debit)
    return {"ar": ar_total, "ap": ap_total}


@router.get("/tax-payable", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_payable(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,  # kept for parity; GL entries are single-currency in this model
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate tax payable from GL (credits minus debits) for tax accounts."""
    start_dt = _parse_date(start_date, "start_date") if start_date else None
    end_dt = _parse_date(end_date, "end_date") if end_date else None

    query = (
        db.query(
            GLEntry.account.label("account"),
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
            Account.account_name.label("account_name"),
        )
        .outerjoin(Account, Account.erpnext_id == GLEntry.account)
        .filter(_tax_account_filter())
    )

    if start_dt:
        query = query.filter(GLEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    rows = query.group_by(GLEntry.account, Account.account_name).all()

    by_account = []
    total_payable = 0.0
    for row in rows:
        debit = float(row.debit or 0)
        credit = float(row.credit or 0)
        amount = credit - debit  # credit balance -> payable
        if amount <= 0:
            continue
        total_payable += amount
        by_account.append(
            {
                "account": row.account,
                "account_name": row.account_name or row.account,
                "amount": amount,
            }
        )

    return {
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "currency": currency,
        "total_payable": total_payable,
        "by_account": sorted(by_account, key=lambda x: x["amount"], reverse=True),
    }


@router.get("/tax-receivable", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_receivable(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate tax receivable from GL (debits minus credits) for tax accounts."""
    start_dt = _parse_date(start_date, "start_date") if start_date else None
    end_dt = _parse_date(end_date, "end_date") if end_date else None

    query = (
        db.query(
            GLEntry.account.label("account"),
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
            Account.account_name.label("account_name"),
        )
        .outerjoin(Account, Account.erpnext_id == GLEntry.account)
        .filter(_tax_account_filter())
    )

    if start_dt:
        query = query.filter(GLEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    rows = query.group_by(GLEntry.account, Account.account_name).all()

    by_account = []
    total_receivable = 0.0
    for row in rows:
        debit = float(row.debit or 0)
        credit = float(row.credit or 0)
        amount = debit - credit  # debit balance -> receivable
        if amount <= 0:
            continue
        total_receivable += amount
        by_account.append(
            {
                "account": row.account,
                "account_name": row.account_name or row.account,
                "amount": amount,
            }
        )

    return {
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "currency": currency,
        "total_receivable": total_receivable,
        "by_account": sorted(by_account, key=lambda x: x["amount"], reverse=True),
    }


# ============= OUTSTANDING (AR / AP) =============

@router.get("/receivables-outstanding", dependencies=[Depends(Require("accounting:read"))])
async def get_receivables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Outstanding customer receivables with optional top customers."""
    as_of = date.today()
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)

    inv_query = db.query(
        func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
        func.count(Invoice.id).label("count"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    if currency:
        inv_query = inv_query.filter(Invoice.currency == currency)
    inv_totals = inv_query.first()

    inv_by_customer_query = (
        db.query(
            Invoice.customer_id,
            Customer.name.label("customer_name"),
            func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
        )
        .outerjoin(Customer, Customer.id == Invoice.customer_id)
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
    )
    if currency:
        inv_by_customer_query = inv_by_customer_query.filter(Invoice.currency == currency)
    inv_by_customer = (
        inv_by_customer_query.group_by(Invoice.customer_id, Customer.name)
        .order_by(func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).desc())
        .limit(top)
        .all()
    )

    return {
        "as_of_date": as_of.isoformat(),
        "currency": currency,
        "total_outstanding": float(inv_totals.outstanding or 0),
        "count": int(inv_totals.count or 0),
        "top_customers": [
            {
                "customer_id": row.customer_id,
                "customer_name": row.customer_name or (f"Customer {row.customer_id}" if row.customer_id else "Unassigned"),
                "outstanding": float(row.outstanding or 0),
            }
            for row in inv_by_customer
        ],
    }


@router.get("/payables-outstanding", dependencies=[Depends(Require("accounting:read"))])
async def get_payables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Outstanding vendor payables with optional top suppliers."""
    as_of = date.today()
    currency = _resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    ap_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        func.count(PurchaseInvoice.id).label("count"),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )
    if currency:
        ap_query = ap_query.filter(PurchaseInvoice.currency == currency)
    ap_totals = ap_query.first()

    ap_by_supplier_query = (
        db.query(
            PurchaseInvoice.supplier.label("supplier"),
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        )
        .filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ]),
        )
    )
    if currency:
        ap_by_supplier_query = ap_by_supplier_query.filter(PurchaseInvoice.currency == currency)
    ap_by_supplier = (
        ap_by_supplier_query.group_by(PurchaseInvoice.supplier)
        .order_by(func.sum(PurchaseInvoice.outstanding_amount).desc())
        .limit(top)
        .all()
    )

    return {
        "as_of_date": as_of.isoformat(),
        "currency": currency,
        "total_outstanding": float(ap_totals.outstanding or 0),
        "count": int(ap_totals.count or 0),
        "top_suppliers": [
            {
                "supplier": row.supplier or "Unassigned",
                "outstanding": float(row.outstanding or 0),
            }
            for row in ap_by_supplier
        ],
    }


# ============= RECONCILIATION: GL vs Subledger AR/AP =============

@router.get("/reconciliation/ar-ap", dependencies=[Depends(Require("accounting:read"))])
async def reconcile_ar_ap(
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compare GL AR/AP balances with subledger receivables/payables."""
    as_of = _parse_date(as_of_date, "as_of_date") if as_of_date else date.today()

    # Subledger receivables
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    inv_query = db.query(
        func.sum(Invoice.total_amount - (Invoice.amount_paid or 0)).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    if currency:
        inv_query = inv_query.filter(Invoice.currency == currency)
    inv_total = float(inv_query.scalar() or 0)

    # Subledger payables
    ap_currency = _resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)
    ap_query = db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )
    if ap_currency:
        ap_query = ap_query.filter(PurchaseInvoice.currency == ap_currency)
    ap_total = float(ap_query.scalar() or 0)

    # GL balances
    gl_balances = _gl_ar_ap_balances(db, as_of)
    gl_ar = gl_balances["ar"]
    gl_ap = gl_balances["ap"]

    return {
        "as_of_date": as_of.isoformat(),
        "currency": currency or ap_currency,
        "gl": {
            "receivables": gl_ar,
            "payables": gl_ap,
        },
        "subledger": {
            "receivables": inv_total,
            "payables": ap_total,
        },
        "delta": {
            "receivables": gl_ar - inv_total,
            "payables": gl_ap - ap_total,
        },
    }
@router.get("/accounts/{account_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_account_detail(
    account_id: int,
    include_ledger: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed account information with optional transaction ledger.

    Args:
        account_id: Account ID
        include_ledger: Include recent GL entries for this account
        start_date: Filter ledger from date
        end_date: Filter ledger to date
        limit: Max ledger entries to return
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Calculate current balance
    balance_result = db.query(
        func.sum(GLEntry.debit).label("total_debit"),
        func.sum(GLEntry.credit).label("total_credit"),
    ).filter(
        GLEntry.account == account.erpnext_id,
        GLEntry.is_cancelled == False,
    ).first()

    total_debit = balance_result.total_debit or Decimal("0")
    total_credit = balance_result.total_credit or Decimal("0")
    balance = total_debit - total_credit

    # Determine normal balance type
    if account.root_type in [AccountType.ASSET, AccountType.EXPENSE]:
        normal_balance = "debit"
    else:
        normal_balance = "credit"

    result = {
        "id": account.id,
        "erpnext_id": account.erpnext_id,
        "name": account.account_name,
        "account_number": account.account_number,
        "parent_account": account.parent_account,
        "root_type": account.root_type.value if account.root_type else None,
        "account_type": account.account_type,
        "is_group": account.is_group,
        "disabled": account.disabled,
        "normal_balance": normal_balance,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "balance": float(balance),
        "balance_type": "Dr" if balance >= 0 else "Cr",
    }

    if include_ledger:
        ledger_query = db.query(GLEntry).filter(
            GLEntry.account == account.erpnext_id,
            GLEntry.is_cancelled == False,
        )

        if start_date:
            ledger_query = ledger_query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))
        if end_date:
            ledger_query = ledger_query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

        entries = ledger_query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc()).limit(limit).all()

        result["ledger"] = [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "party_type": e.party_type,
                "party": e.party,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
            }
            for e in entries
        ]
        result["ledger_count"] = len(entries)

    return result


@router.get("/accounts/{account_id}/ledger", dependencies=[Depends(Require("accounting:read"))])
async def get_account_ledger(
    account_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ledger (GL entries) for a specific account with running balance.

    Args:
        account_id: Account ID
        start_date: Filter from date
        end_date: Filter to date
        party_type: Filter by party type
        party: Filter by party name
        voucher_type: Filter by voucher type
        limit: Max entries per page
        offset: Pagination offset
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Base query
    query = db.query(GLEntry).filter(
        GLEntry.account == account.erpnext_id,
        GLEntry.is_cancelled == False,
    )

    # Calculate opening balance (before start_date)
    opening_balance = Decimal("0")
    start_dt = _parse_date(start_date, "start_date")
    end_dt = _parse_date(end_date, "end_date")

    if start_dt:
        opening_result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account == account.erpnext_id,
            GLEntry.is_cancelled == False,
            GLEntry.posting_date < start_dt,
        ).scalar()
        opening_balance = opening_result or Decimal("0")
        query = query.filter(GLEntry.posting_date >= start_dt)

    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)
    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))
    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    total = query.count()
    entries = query.order_by(GLEntry.posting_date.asc(), GLEntry.id.asc()).offset(offset).limit(limit).all()

    # Calculate running balance
    ledger = []
    running_balance = opening_balance
    for e in entries:
        running_balance += e.debit - e.credit
        ledger.append({
            "id": e.id,
            "posting_date": e.posting_date.isoformat() if e.posting_date else None,
            "party_type": e.party_type,
            "party": e.party,
            "debit": float(e.debit),
            "credit": float(e.credit),
            "balance": float(running_balance),
            "voucher_type": e.voucher_type,
            "voucher_no": e.voucher_no,
            "cost_center": e.cost_center,
        })

    return {
        "account": {
            "id": account.id,
            "name": account.account_name,
            "root_type": account.root_type.value if account.root_type else None,
        },
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "opening_balance": float(opening_balance),
        "closing_balance": float(running_balance) if ledger else float(opening_balance),
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": ledger,
    }


@router.get("/chart-of-accounts", dependencies=[Depends(Require("accounting:read"))])
async def get_chart_of_accounts(
    root_type: Optional[str] = None,
    include_disabled: bool = False,
    include_balances: bool = True,
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get chart of accounts as hierarchical tree with balances.

    Args:
        root_type: Filter by root type (asset, liability, equity, income, expense)
        include_disabled: Include disabled accounts
        include_balances: Include account balances from GL entries (default: True)
        as_of_date: Calculate balances as of this date (default: today)
    """
    query = db.query(Account)

    if root_type:
        try:
            root_type_enum = AccountType(root_type.lower())
            query = query.filter(Account.root_type == root_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {root_type}")

    if not include_disabled:
        query = query.filter(Account.disabled == False)

    accounts = query.order_by(Account.account_name).all()

    # Calculate balances from GL entries if requested
    account_balances = {}
    if include_balances:
        cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
        balance_query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff,
        ).group_by(GLEntry.account)

        for row in balance_query.all():
            debit = row.total_debit or Decimal("0")
            credit = row.total_credit or Decimal("0")
            account_balances[row.account] = float(debit - credit)

    # Build tree structure
    def build_tree(accounts: List[Account], parent: Optional[str] = None) -> List[Dict]:
        tree = []
        for acc in accounts:
            if acc.parent_account == parent:
                balance = account_balances.get(acc.erpnext_id, 0.0)
                node = {
                    "id": acc.id,
                    "name": acc.account_name,
                    "account_number": acc.account_number,
                    "root_type": acc.root_type.value if acc.root_type else None,
                    "account_type": acc.account_type,
                    "is_group": acc.is_group,
                    "disabled": acc.disabled,
                    "balance": balance,
                    "children": build_tree(accounts, acc.erpnext_id) if acc.is_group else [],
                }
                tree.append(node)
        return tree

    # Also return flat list for easier processing
    flat_list = [
        {
            "id": acc.id,
            "erpnext_id": acc.erpnext_id,
            "name": acc.account_name,
            "account_number": acc.account_number,
            "parent_account": acc.parent_account,
            "root_type": acc.root_type.value if acc.root_type else None,
            "account_type": acc.account_type,
            "is_group": acc.is_group,
            "disabled": acc.disabled,
            "balance": account_balances.get(acc.erpnext_id, 0.0),
        }
        for acc in accounts
    ]

    # Group by root type
    by_root_type = {}
    for acc in accounts:
        rt = acc.root_type.value if acc.root_type else "unknown"
        if rt not in by_root_type:
            by_root_type[rt] = []
        by_root_type[rt].append(acc.account_name)

    return {
        "total": len(accounts),
        "by_root_type": {k: len(v) for k, v in by_root_type.items()},
        "accounts": flat_list,
        "tree": build_tree(accounts, None),
    }


# ============= TRIAL BALANCE =============

@router.get("/trial-balance", dependencies=[Depends(Require("accounting:read"))])
async def get_trial_balance(
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    drill: bool = Query(False, description="Include account_id for drill-through to GL details"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get trial balance report (optional fiscal year/cost center).

    Shows debit and credit totals for each account.

    Args:
        as_of_date: Report as of this date (default: today)
        fiscal_year: Filter by fiscal year
        cost_center: Filter by cost center
        drill: If true, include account_id refs for drill-through to GL
    """
    end_date = _parse_date(as_of_date, "as_of_date") or date.today()


    # Get fiscal year start if specified
    start_date = None
    if fiscal_year:
        start_date, _ = _get_fiscal_year_dates(db, fiscal_year)

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


# ============= BALANCE SHEET =============

# Account types that indicate liability regardless of root_type
LIABILITY_ACCOUNT_TYPES = {"Payable", "Current Liability"}
# Account types that indicate asset regardless of root_type
ASSET_ACCOUNT_TYPES = {"Receivable", "Bank", "Cash", "Fixed Asset", "Stock", "Current Asset"}


def _get_effective_root_type(acc) -> Optional[AccountType]:
    """Determine effective root type, correcting common ERPNext misclassifications.

    Some accounts in ERPNext have wrong root_type (e.g., Payable accounts classified as Asset).
    This function uses account_type to correct obvious misclassifications.
    """
    # If account_type indicates liability but root_type says asset, treat as liability
    if acc.account_type in LIABILITY_ACCOUNT_TYPES and acc.root_type == AccountType.ASSET:
        return AccountType.LIABILITY
    # If account_type indicates asset but root_type says liability, treat as asset
    if acc.account_type in ASSET_ACCOUNT_TYPES and acc.root_type == AccountType.LIABILITY:
        return AccountType.ASSET
    return acc.root_type


@router.get("/balance-sheet", dependencies=[Depends(Require("accounting:read"))])
async def get_balance_sheet(
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    common_size: bool = Query(False, description="Show values as percentage of total assets"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get balance sheet report with optional comparative date and common-size analysis.

    Assets = Liabilities + Equity

    Note: Automatically corrects common ERPNext account misclassifications
    (e.g., Payable accounts incorrectly classified as Asset root_type).

    Args:
        as_of_date: Report as of this date (default: today)
        comparative_date: Optional date for comparison
        common_size: Show each line as percentage of total assets
    """
    end_date = _parse_date(as_of_date, "as_of_date") or date.today()
    comp_date = _parse_date(comparative_date, "comparative_date")

    def get_balances(cutoff_date: date) -> Dict[str, Decimal]:
        """Get account balances as of a date."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff_date,
        )
        results = results.group_by(GLEntry.account).all()

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
            effective_type = _get_effective_root_type(acc)
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
        if _get_effective_root_type(acc) == AccountType.INCOME
    )
    expense_total = sum(
        current_balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if _get_effective_root_type(acc) == AccountType.EXPENSE
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


# ============= INCOME STATEMENT (P&L) =============

@router.get("/income-statement", dependencies=[Depends(Require("accounting:read"))])
async def get_income_statement(
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
        basis: Accounting basis - 'accrual' includes all transactions when incurred,
               'cash' includes only paid transactions (linked to payment vouchers)
    """
    if basis not in ("accrual", "cash"):
        raise HTTPException(status_code=400, detail="basis must be 'accrual' or 'cash'")

    # Cash basis voucher types (only these are included in cash basis reporting)
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
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Comparative period
    comp_start = _parse_date(compare_start, "compare_start")
    comp_end = _parse_date(compare_end, "compare_end")
    has_comparison = comp_start is not None and comp_end is not None

    # YTD dates (start of year to period end)
    ytd_start = date(period_end.year, 1, 1)

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    def get_period_data(p_start: date, p_end: date, cc: Optional[str] = None) -> Dict[str, Decimal]:
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
        # Cash basis: only include payment-related voucher types
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
        """Build income or expense section with optional comparison and YTD."""
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

    # Add common-size percentages if requested
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


# ============= GENERAL LEDGER =============

@router.get("/general-ledger", dependencies=[Depends(Require("accounting:read"))])
async def get_general_ledger(
    account: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    currency: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get general ledger transactions (single-currency, filterable/paginated).

    Args:
        account: Filter by account
        start_date: Filter from date
        end_date: Filter to date
        party_type: Filter by party type (Customer, Supplier)
        party: Filter by party name
        voucher_type: Filter by voucher type
        currency: Require single currency if dataset has more than one
        limit: Max records to return
        offset: Pagination offset
    """
    query = db.query(GLEntry).filter(GLEntry.is_cancelled == False)

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)

    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))

    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    total = query.count()
    entries = query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "account": e.account,
                "party_type": e.party_type,
                "party": e.party,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
                "fiscal_year": e.fiscal_year,
            }
            for e in entries
        ],
    }


# ============= ACCOUNTS PAYABLE =============

@router.get("/accounts-payable", dependencies=[Depends(Require("accounting:read"))])
async def get_accounts_payable(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts payable aging report.

    Shows outstanding purchase invoices by age bucket.
    """
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    currency = _resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )

    if supplier:
        query = query.filter(PurchaseInvoice.supplier.ilike(f"%{supplier}%"))

    if currency:
        query = query.filter(PurchaseInvoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else cutoff)
        days_overdue = (cutoff - due).days if cutoff > due else 0

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += inv.outstanding_amount
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.erpnext_id,
            "supplier": inv.supplier_name or inv.supplier,
            "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "grand_total": float(inv.grand_total),
            "outstanding": float(inv.outstanding_amount),
            "days_overdue": days_overdue,
        })

    # Convert totals to float
    for bucket in buckets.values():
        bucket["total"] = float(bucket["total"])

    total_payable = sum(b["total"] for b in buckets.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_payable": total_payable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets,
    }


# Alias for payables-aging
@router.get("/payables-aging", dependencies=[Depends(Require("accounting:read"))])
async def get_payables_aging(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for /accounts-payable - AP aging report."""
    return await get_accounts_payable(as_of_date, supplier, currency, db)


# ============= ACCOUNTS RECEIVABLE =============

@router.get("/accounts-receivable", dependencies=[Depends(Require("accounting:read"))])
async def get_accounts_receivable(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts receivable aging report (single-currency).

    Shows outstanding customer invoices by age bucket.
    """
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)

    query = db.query(Invoice).options(
        joinedload(Invoice.customer)
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
    )

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if currency:
        query = query.filter(Invoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else inv.invoice_date.date()
        days_overdue = (cutoff - due).days if cutoff > due else 0
        outstanding = inv.total_amount - inv.amount_paid

        if outstanding <= 0:
            continue

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += outstanding
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.invoice_number,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer.name if inv.customer else None,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "total_amount": float(inv.total_amount),
            "amount_paid": float(inv.amount_paid),
            "outstanding": float(outstanding),
            "days_overdue": days_overdue,
        })

    # Convert totals to float
    for bucket in buckets.values():
        bucket["total"] = float(bucket["total"])

    total_receivable = sum(b["total"] for b in buckets.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_receivable": total_receivable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets,
    }


# Alias for receivables-aging
@router.get("/receivables-aging", dependencies=[Depends(Require("accounting:read"))])
async def get_receivables_aging(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for /accounts-receivable - AR aging report."""
    return await get_accounts_receivable(as_of_date, customer_id, currency, db)


# ============= CASH FLOW =============

@router.get("/cash-flow", dependencies=[Depends(Require("accounting:read"))])
async def get_cash_flow(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cash flow statement.

    Shows cash inflows and outflows from operating, investing, and financing activities.
    """
    # Determine date range
    if fiscal_year:
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Get bank/cash accounts
    cash_accounts = db.query(Account).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        Account.disabled == False,
    ).all()
    cash_account_names = [acc.erpnext_id for acc in cash_accounts]

    # Get opening and closing cash balances
    def get_cash_balance(as_of: date) -> Decimal:
        result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
        )
        result = result.scalar()
        return result or Decimal("0")

    opening_cash = get_cash_balance(period_start - timedelta(days=1)) if period_start else Decimal("0")
    closing_cash = get_cash_balance(period_end)

    # Get cash movements by category
    # This is a simplified version - proper cash flow requires account classification

    # Bank transactions for the period
    bank_txns_query = db.query(BankTransaction).filter(
        BankTransaction.date >= period_start,
        BankTransaction.date <= period_end,
    )
    bank_txns = bank_txns_query.all()

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
    )
    cash_entries = cash_entries.group_by(GLEntry.voucher_type).all()

    by_voucher_type = {
        row.voucher_type: {
            "inflow": float(row.inflow or 0),
            "outflow": float(row.outflow or 0),
            "net": float((row.inflow or 0) - (row.outflow or 0)),
        }
        for row in cash_entries
    }

    # Categorize (simplified)
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


# ============= JOURNAL ENTRIES =============

@router.get("/journal-entries", dependencies=[Depends(Require("accounting:read"))])
async def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get journal entries list."""
    query = db.query(JournalEntry)

    if start_date:
        query = query.filter(JournalEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(JournalEntry.posting_date <= _parse_date(end_date, "end_date"))

    if voucher_type:
        try:
            vtype = JournalEntryType(voucher_type.lower())
            query = query.filter(JournalEntry.voucher_type == vtype)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "voucher_type": e.voucher_type.value if e.voucher_type else None,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "company": e.company,
                "total_debit": float(e.total_debit),
                "total_credit": float(e.total_credit),
                "user_remark": e.user_remark,
                "is_opening": e.is_opening,
            }
            for e in entries
        ],
    }


# ============= SUPPLIERS =============

@router.get("/suppliers", dependencies=[Depends(Require("accounting:read"))])
async def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get suppliers list."""
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if search:
        query = query.filter(Supplier.supplier_name.ilike(f"%{search}%"))

    if supplier_group:
        query = query.filter(Supplier.supplier_group == supplier_group)

    total = query.count()
    suppliers = query.order_by(Supplier.supplier_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "suppliers": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "name": s.supplier_name,
                "group": s.supplier_group,
                "type": s.supplier_type,
                "country": s.country,
                "currency": s.default_currency,
                "email": s.email_id,
                "mobile": s.mobile_no,
            }
            for s in suppliers
        ],
    }


# ============= BANK ACCOUNTS =============

@router.get("/bank-accounts", dependencies=[Depends(Require("accounting:read"))])
async def get_bank_accounts(
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get bank accounts list with current balances.

    Args:
        as_of_date: Calculate balances as of this date (default: today)
    """
    accounts = db.query(BankAccount).filter(BankAccount.disabled == False).all()

    # Calculate balances from GL entries for each bank's GL account
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    gl_accounts = [acc.account for acc in accounts if acc.account]

    account_balances = {}
    if gl_accounts:
        balance_query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff,
            GLEntry.account.in_(gl_accounts),
        ).group_by(GLEntry.account)

        for row in balance_query.all():
            debit = row.total_debit or Decimal("0")
            credit = row.total_credit or Decimal("0")
            account_balances[row.account] = float(debit - credit)

    total_balance = sum(account_balances.values())

    return {
        "total": len(accounts),
        "total_balance": total_balance,
        "as_of_date": cutoff.isoformat(),
        "accounts": [
            {
                "id": acc.id,
                "erpnext_id": acc.erpnext_id,
                "name": acc.account_name,
                "bank": acc.bank,
                "account_no": acc.bank_account_no,
                "gl_account": acc.account,
                "company": acc.company,
                "currency": acc.currency,
                "is_default": acc.is_default,
                "balance": account_balances.get(acc.account, 0.0),
            }
            for acc in accounts
        ],
    }


# ============= FISCAL YEARS =============

@router.get("/fiscal-years", dependencies=[Depends(Require("accounting:read"))])
async def get_fiscal_years(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get fiscal years list."""
    years = db.query(FiscalYear).filter(FiscalYear.disabled == False).order_by(FiscalYear.year.desc()).all()

    return {
        "total": len(years),
        "fiscal_years": [
            {
                "id": fy.id,
                "year": fy.year,
                "start_date": fy.year_start_date.isoformat() if fy.year_start_date else None,
                "end_date": fy.year_end_date.isoformat() if fy.year_end_date else None,
                "is_short_year": fy.is_short_year,
            }
            for fy in years
        ],
    }


# ============= COST CENTERS =============

@router.get("/cost-centers", dependencies=[Depends(Require("accounting:read"))])
async def get_cost_centers(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost centers list."""
    centers = db.query(CostCenter).filter(CostCenter.disabled == False).all()

    return {
        "total": len(centers),
        "cost_centers": [
            {
                "id": cc.id,
                "erpnext_id": cc.erpnext_id,
                "name": cc.cost_center_name,
                "number": cc.cost_center_number,
                "parent": cc.parent_cost_center,
                "company": cc.company,
                "is_group": cc.is_group,
            }
            for cc in centers
        ],
    }


@router.get("/cost-centers/{cost_center_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_cost_center_detail(
    cost_center_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost center detail with expense breakdown."""
    cc = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost center not found")

    # Get expenses by account for this cost center
    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.cost_center == cc.erpnext_id,
        GLEntry.is_cancelled == False,
    )

    start_dt = _parse_date(start_date, "start_date")
    end_dt = _parse_date(end_date, "end_date")

    if start_dt:
        query = query.filter(GLEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    results = query.group_by(GLEntry.account).all()

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}
    breakdown = []
    total = Decimal("0")

    for row in results:
        acc = accounts.get(row.account)
        amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
        if acc and acc.root_type == AccountType.EXPENSE:
            breakdown.append({
                "account": row.account,
                "account_name": acc.account_name if acc else row.account,
                "amount": float(amount),
            })
            total += amount

    breakdown.sort(key=lambda x: -abs(x["amount"]))

    return {
        "id": cc.id,
        "erpnext_id": cc.erpnext_id,
        "name": cc.cost_center_name,
        "number": cc.cost_center_number,
        "parent": cc.parent_cost_center,
        "company": cc.company,
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "total_expenses": float(total),
        "breakdown": breakdown,
    }


# ============= JOURNAL ENTRY DETAIL =============

@router.get("/journal-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_journal_entry_detail(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get journal entry detail with all line items (GL entries)."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    # Get related GL entries (line items)
    gl_entries = db.query(GLEntry).filter(
        GLEntry.voucher_no == entry.erpnext_id,
        GLEntry.voucher_type == "Journal Entry",
    ).order_by(GLEntry.id).all()

    accounts = [
        {
            "id": acc.id,
            "account": acc.account,
            "account_type": acc.account_type,
            "party_type": acc.party_type,
            "party": acc.party,
            "debit": float(acc.debit or 0),
            "credit": float(acc.credit or 0),
            "debit_in_account_currency": float(acc.debit_in_account_currency or 0),
            "credit_in_account_currency": float(acc.credit_in_account_currency or 0),
            "exchange_rate": float(acc.exchange_rate or 1),
            "reference_type": acc.reference_type,
            "reference_name": acc.reference_name,
            "reference_due_date": acc.reference_due_date.isoformat() if acc.reference_due_date else None,
            "cost_center": acc.cost_center,
            "project": acc.project,
            "bank_account": acc.bank_account,
            "cheque_no": acc.cheque_no,
            "cheque_date": acc.cheque_date.isoformat() if acc.cheque_date else None,
            "user_remark": acc.user_remark,
            "idx": acc.idx,
        }
        for acc in getattr(entry, "accounts", [])
    ]

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "voucher_type": entry.voucher_type.value if entry.voucher_type else None,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "company": entry.company,
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "is_balanced": abs(entry.total_debit - entry.total_credit) < Decimal("0.01"),
        "user_remark": entry.user_remark,
        "is_opening": entry.is_opening,
        "line_items": [
            {
                "id": gl.id,
                "account": gl.account,
                "party_type": gl.party_type,
                "party": gl.party,
                "debit": float(gl.debit),
                "credit": float(gl.credit),
                "cost_center": gl.cost_center,
            }
            for gl in gl_entries
        ],
        "line_count": len(gl_entries),
        "accounts": accounts,
    }


# ============= GL ENTRIES LIST =============

@router.get("/gl-entries", dependencies=[Depends(Require("accounting:read"))])
async def list_gl_entries(
    account: Optional[str] = None,
    voucher_type: Optional[str] = None,
    voucher_no: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_cancelled: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default="posting_date", description="posting_date,account,debit,credit"),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List GL entries with filtering."""
    query = db.query(GLEntry)

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    if voucher_no:
        query = query.filter(GLEntry.voucher_no.ilike(f"%{voucher_no}%"))

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)

    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))

    if start_date:
        start_dt = _parse_date(start_date, "start_date")
        if start_dt:
            query = query.filter(GLEntry.posting_date >= start_dt)

    if end_date:
        end_dt = _parse_date(end_date, "end_date")
        if end_dt:
            query = query.filter(GLEntry.posting_date <= end_dt)

    if is_cancelled is not None:
        query = query.filter(GLEntry.is_cancelled == is_cancelled)

    if search:
        query = query.filter(
            or_(
                GLEntry.account.ilike(f"%{search}%"),
                GLEntry.voucher_no.ilike(f"%{search}%"),
                GLEntry.party.ilike(f"%{search}%"),
            )
        )

    total = query.count()

    # Sorting
    sort_column = getattr(GLEntry, sort_by, GLEntry.posting_date)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    entries = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "account": e.account,
                "party_type": e.party_type,
                "party": e.party,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
                "is_cancelled": e.is_cancelled,
            }
            for e in entries
        ],
    }


# ============= BANK TRANSACTIONS =============

@router.get("/bank-transactions", dependencies=[Depends(Require("accounting:read"))])
async def list_bank_transactions(
    bank_account: Optional[str] = None,
    status: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    unallocated_only: bool = False,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default="date", description="date,deposit,withdrawal,unallocated_amount"),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List bank transactions with filtering."""
    query = db.query(BankTransaction)

    if bank_account:
        query = query.filter(BankTransaction.bank_account.ilike(f"%{bank_account}%"))

    if status:
        try:
            status_enum = BankTransactionStatus(status.lower())
            query = query.filter(BankTransaction.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if transaction_type:
        query = query.filter(BankTransaction.transaction_type == transaction_type)

    if start_date:
        start_dt = _parse_date(start_date, "start_date")
        if start_dt:
            query = query.filter(BankTransaction.date >= start_dt)

    if end_date:
        end_dt = _parse_date(end_date, "end_date")
        if end_dt:
            query = query.filter(BankTransaction.date <= end_dt)

    if min_amount:
        query = query.filter(
            or_(
                BankTransaction.deposit >= min_amount,
                BankTransaction.withdrawal >= min_amount,
            )
        )

    if max_amount:
        query = query.filter(
            and_(
                or_(BankTransaction.deposit <= max_amount, BankTransaction.deposit == 0),
                or_(BankTransaction.withdrawal <= max_amount, BankTransaction.withdrawal == 0),
            )
        )

    if unallocated_only:
        query = query.filter(BankTransaction.unallocated_amount > 0)

    if search:
        query = query.filter(
            or_(
                BankTransaction.description.ilike(f"%{search}%"),
                BankTransaction.reference_number.ilike(f"%{search}%"),
                BankTransaction.bank_party_name.ilike(f"%{search}%"),
            )
        )

    total = query.count()

    # Sorting
    sort_column = getattr(BankTransaction, sort_by, BankTransaction.date)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    transactions = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "date": t.date.isoformat() if t.date else None,
                "bank_account": t.bank_account,
                "deposit": float(t.deposit) if t.deposit else 0,
                "withdrawal": float(t.withdrawal) if t.withdrawal else 0,
                "currency": t.currency,
                "description": t.description,
                "reference_number": t.reference_number,
                "transaction_type": t.transaction_type,
                "status": t.status.value if t.status else None,
                "allocated_amount": float(t.allocated_amount) if t.allocated_amount else 0,
                "unallocated_amount": float(t.unallocated_amount) if t.unallocated_amount else 0,
                "party": t.party,
                "party_type": t.party_type,
            }
            for t in transactions
        ],
    }


@router.get("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_bank_transaction_detail(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get bank transaction detail."""
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    return {
        "id": txn.id,
        "erpnext_id": txn.erpnext_id,
        "date": txn.date.isoformat() if txn.date else None,
        "bank_account": txn.bank_account,
        "deposit": float(txn.deposit) if txn.deposit else 0,
        "withdrawal": float(txn.withdrawal) if txn.withdrawal else 0,
        "currency": txn.currency,
        "description": txn.description,
        "reference_number": txn.reference_number,
        "transaction_id": txn.transaction_id,
        "transaction_type": txn.transaction_type,
        "status": txn.status.value if txn.status else None,
        "allocation": {
            "allocated_amount": float(txn.allocated_amount) if txn.allocated_amount else 0,
            "unallocated_amount": float(txn.unallocated_amount) if txn.unallocated_amount else 0,
        },
        "party": {
            "party_type": txn.party_type,
            "party": txn.party,
            "bank_party_name": txn.bank_party_name,
            "bank_party_account_number": txn.bank_party_account_number,
            "bank_party_iban": txn.bank_party_iban,
        },
        "docstatus": txn.docstatus,
    }


# ============= GL ENTRY DETAIL =============

@router.get("/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_gl_entry_detail(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get single GL entry detail."""
    entry = db.query(GLEntry).filter(GLEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="GL entry not found")

    # Get account details
    account = db.query(Account).filter(Account.erpnext_id == entry.account).first()

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "account": entry.account,
        "account_name": account.account_name if account else None,
        "root_type": account.root_type.value if account and account.root_type else None,
        "party_type": entry.party_type,
        "party": entry.party,
        "debit": float(entry.debit),
        "credit": float(entry.credit),
        "voucher_type": entry.voucher_type,
        "voucher_no": entry.voucher_no,
        "cost_center": entry.cost_center,
        "fiscal_year": entry.fiscal_year,
        "is_cancelled": entry.is_cancelled,
        "company": entry.company,
    }


# ============= FINANCIAL RATIOS =============

@router.get("/financial-ratios", dependencies=[Depends(Require("accounting:read"))])
async def get_financial_ratios(
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate key financial ratios.

    Returns liquidity, solvency, and profitability ratios.
    """
    end_date = _parse_date(as_of_date, "as_of_date") or date.today()
    year_start = date(end_date.year, 1, 1)

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Get balances as of date
    balance_results = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= end_date,
    ).group_by(GLEntry.account).all()

    balances = {r.account: r.balance or Decimal("0") for r in balance_results}

    # Get period activity (for income/expense)
    period_results = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= year_start,
        GLEntry.posting_date <= end_date,
    ).group_by(GLEntry.account).all()

    period_activity = {r.account: {"debit": r.debit or Decimal("0"), "credit": r.credit or Decimal("0")} for r in period_results}

    # Classify accounts
    current_assets = Decimal("0")
    cash_and_equivalents = Decimal("0")
    inventory = Decimal("0")
    receivables = Decimal("0")
    total_assets = Decimal("0")
    current_liabilities = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    revenue = Decimal("0")
    cogs = Decimal("0")
    total_expenses = Decimal("0")

    for acc_id, balance in balances.items():
        acc = accounts.get(acc_id)
        if not acc:
            continue

        eff_type = _get_effective_root_type(acc)
        acc_type = acc.account_type or ""

        if eff_type == AccountType.ASSET:
            total_assets += balance
            if acc_type in ["Bank", "Cash"]:
                current_assets += balance
                cash_and_equivalents += balance
            elif acc_type == "Receivable":
                current_assets += balance
                receivables += balance
            elif acc_type == "Stock":
                current_assets += balance
                inventory += balance
            elif acc_type == "Current Asset":
                current_assets += balance

        elif eff_type == AccountType.LIABILITY:
            total_liabilities += -balance
            if acc_type in ["Payable", "Current Liability"]:
                current_liabilities += -balance

        elif eff_type == AccountType.EQUITY:
            total_equity += -balance

    # Calculate income and expenses for the period
    for acc_id, activity in period_activity.items():
        acc = accounts.get(acc_id)
        if not acc:
            continue

        if acc.root_type == AccountType.INCOME:
            revenue += activity["credit"] - activity["debit"]
        elif acc.root_type == AccountType.EXPENSE:
            amount = activity["debit"] - activity["credit"]
            total_expenses += amount
            if acc.account_type == "Cost of Goods Sold":
                cogs += amount

    # Calculate ratios (with safe division)
    def safe_div(a: Decimal, b: Decimal) -> Optional[float]:
        if b == 0:
            return None
        return round(float(a / b), 4)

    net_income = revenue - total_expenses
    gross_profit = revenue - cogs
    working_capital = current_assets - current_liabilities

    return {
        "as_of_date": end_date.isoformat(),
        "period_start": year_start.isoformat(),
        "components": {
            "current_assets": float(current_assets),
            "cash_and_equivalents": float(cash_and_equivalents),
            "receivables": float(receivables),
            "inventory": float(inventory),
            "total_assets": float(total_assets),
            "current_liabilities": float(current_liabilities),
            "total_liabilities": float(total_liabilities),
            "total_equity": float(total_equity),
            "revenue": float(revenue),
            "cogs": float(cogs),
            "gross_profit": float(gross_profit),
            "total_expenses": float(total_expenses),
            "net_income": float(net_income),
            "working_capital": float(working_capital),
        },
        "liquidity_ratios": {
            "current_ratio": safe_div(current_assets, current_liabilities),
            "quick_ratio": safe_div(current_assets - inventory, current_liabilities),
            "cash_ratio": safe_div(cash_and_equivalents, current_liabilities),
            "working_capital": float(working_capital),
        },
        "solvency_ratios": {
            "debt_to_equity": safe_div(total_liabilities, total_equity) if total_equity else None,
            "debt_to_assets": safe_div(total_liabilities, total_assets) if total_assets else None,
            "equity_ratio": safe_div(total_equity, total_assets) if total_assets else None,
        },
        "profitability_ratios": {
            "gross_profit_margin": safe_div(gross_profit * 100, revenue),
            "net_profit_margin": safe_div(net_income * 100, revenue),
            "return_on_assets": safe_div(net_income * 100, total_assets),
            "return_on_equity": safe_div(net_income * 100, total_equity) if total_equity else None,
        },
        "activity_ratios": {
            "receivables_turnover": safe_div(revenue, receivables) if receivables else None,
            "asset_turnover": safe_div(revenue, total_assets) if total_assets else None,
        },
    }


# ============= STATEMENT OF CHANGES IN EQUITY =============

@router.get("/equity-statement", dependencies=[Depends(Require("accounting:read"))])
async def get_equity_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get statement of changes in equity.

    Shows movements in equity accounts (capital, retained earnings, reserves).
    """
    if fiscal_year:
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Get opening equity balances (before period)
    opening_results = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date < period_start,
    ).group_by(GLEntry.account).all()

    opening_balances = {r.account: r.balance or Decimal("0") for r in opening_results}

    # Get movements during period
    period_results = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.account).all()

    period_activity = {r.account: {"debit": r.debit or Decimal("0"), "credit": r.credit or Decimal("0")} for r in period_results}

    # Build equity statement
    equity_accounts = []
    opening_total = Decimal("0")
    closing_total = Decimal("0")
    net_income = Decimal("0")

    for acc_id, acc in accounts.items():
        if acc.root_type == AccountType.EQUITY:
            opening = -(opening_balances.get(acc_id, Decimal("0")))
            activity = period_activity.get(acc_id, {"debit": Decimal("0"), "credit": Decimal("0")})
            change = activity["credit"] - activity["debit"]
            closing = opening + change

            equity_accounts.append({
                "account": acc.account_name,
                "account_type": acc.account_type,
                "opening_balance": float(opening),
                "additions": float(activity["credit"]),
                "deductions": float(activity["debit"]),
                "net_change": float(change),
                "closing_balance": float(closing),
            })

            opening_total += opening
            closing_total += closing

        elif acc.root_type == AccountType.INCOME:
            activity = period_activity.get(acc_id, {"debit": Decimal("0"), "credit": Decimal("0")})
            net_income += activity["credit"] - activity["debit"]

        elif acc.root_type == AccountType.EXPENSE:
            activity = period_activity.get(acc_id, {"debit": Decimal("0"), "credit": Decimal("0")})
            net_income -= activity["debit"] - activity["credit"]

    # Add retained earnings movement
    equity_accounts.append({
        "account": "Retained Earnings (Current Period)",
        "account_type": "Retained Earnings",
        "opening_balance": 0,
        "additions": float(net_income) if net_income > 0 else 0,
        "deductions": float(-net_income) if net_income < 0 else 0,
        "net_change": float(net_income),
        "closing_balance": float(net_income),
    })

    equity_accounts.sort(key=lambda x: x["account"])

    return {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "opening_equity": float(opening_total),
        "net_income": float(net_income),
        "closing_equity": float(closing_total + net_income),
        "accounts": equity_accounts,
    }


# ============= COMPARATIVE INCOME STATEMENT =============

@router.get("/income-statement/comparative", dependencies=[Depends(Require("accounting:read"))])
async def get_comparative_income_statement(
    periods: int = Query(default=3, le=12, description="Number of periods to compare"),
    interval: str = Query(default="month", description="Period interval: month or quarter"),
    end_date: Optional[str] = None,
    cost_center: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comparative income statement across multiple periods.

    Args:
        periods: Number of periods to compare
        interval: month or quarter
        end_date: End date for comparison
        cost_center: Filter by cost center
    """
    end_dt = _parse_date(end_date, "end_date") or date.today()

    # Generate period ranges
    period_ranges = []
    if interval == "quarter":
        # Calculate quarters
        current_q = (end_dt.month - 1) // 3
        current_year = end_dt.year
        for i in range(periods):
            q = current_q - i
            y = current_year
            while q < 0:
                q += 4
                y -= 1
            q_start = date(y, q * 3 + 1, 1)
            if q == 3:
                q_end = date(y, 12, 31)
            else:
                q_end = date(y, (q + 1) * 3 + 1, 1) - timedelta(days=1)
            period_ranges.append((q_start, min(q_end, end_dt), f"Q{q+1} {y}"))
    else:
        # Calculate months
        for i in range(periods):
            m = end_dt.month - i
            y = end_dt.year
            while m <= 0:
                m += 12
                y -= 1
            m_start = date(y, m, 1)
            if m == 12:
                m_end = date(y, 12, 31)
            else:
                m_end = date(y, m + 1, 1) - timedelta(days=1)
            period_ranges.append((m_start, min(m_end, end_dt), f"{m_start.strftime('%b %Y')}"))

    period_ranges.reverse()  # Oldest to newest

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Get data for each period
    period_data = []
    for p_start, p_end, label in period_ranges:
        query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        )

        if cost_center:
            query = query.filter(GLEntry.cost_center == cost_center)

        results = query.group_by(GLEntry.account).all()

        income_total = Decimal("0")
        expense_total = Decimal("0")
        income_accounts = []
        expense_accounts = []

        for row in results:
            acc = accounts.get(row.account)
            if not acc:
                continue

            if acc.root_type == AccountType.INCOME:
                amount = (row.credit or Decimal("0")) - (row.debit or Decimal("0"))
                income_total += amount
                income_accounts.append({"account": acc.account_name, "amount": float(amount)})
            elif acc.root_type == AccountType.EXPENSE:
                amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
                expense_total += amount
                expense_accounts.append({"account": acc.account_name, "amount": float(amount)})

        period_data.append({
            "label": label,
            "start_date": p_start.isoformat(),
            "end_date": p_end.isoformat(),
            "income": float(income_total),
            "expenses": float(expense_total),
            "net_income": float(income_total - expense_total),
            "income_accounts": sorted(income_accounts, key=lambda x: -x["amount"])[:10],
            "expense_accounts": sorted(expense_accounts, key=lambda x: -x["amount"])[:10],
        })

    # Calculate trends
    if len(period_data) >= 2:
        first_net = period_data[0]["net_income"]
        last_net = period_data[-1]["net_income"]
        growth = ((last_net - first_net) / abs(first_net) * 100) if first_net != 0 else None
    else:
        growth = None

    return {
        "interval": interval,
        "periods": periods,
        "growth_rate": round(growth, 2) if growth is not None else None,
        "data": period_data,
        "totals": {
            "total_income": sum(p["income"] for p in period_data),
            "total_expenses": sum(p["expenses"] for p in period_data),
            "total_net_income": sum(p["net_income"] for p in period_data),
            "average_income": sum(p["income"] for p in period_data) / len(period_data) if period_data else 0,
            "average_expenses": sum(p["expenses"] for p in period_data) / len(period_data) if period_data else 0,
            "average_net_income": sum(p["net_income"] for p in period_data) / len(period_data) if period_data else 0,
        },
    }


# ============= PERIOD SUMMARY =============

@router.get("/period-summary", dependencies=[Depends(Require("accounting:read"))])
async def get_period_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive period summary with key metrics.

    Combines income statement, balance sheet highlights, and activity metrics.
    """
    if fiscal_year:
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Get period activity
    period_query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
        func.count(GLEntry.id).label("count"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.account)

    period_results = period_query.all()

    # Calculate metrics
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    transaction_count = 0

    expense_breakdown = []
    income_breakdown = []

    for row in period_results:
        acc = accounts.get(row.account)
        total_debits += row.debit or Decimal("0")
        total_credits += row.credit or Decimal("0")
        transaction_count += row.count

        if not acc:
            continue

        if acc.root_type == AccountType.INCOME:
            amount = (row.credit or Decimal("0")) - (row.debit or Decimal("0"))
            total_revenue += amount
            income_breakdown.append({"account": acc.account_name, "amount": float(amount)})
        elif acc.root_type == AccountType.EXPENSE:
            amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
            total_expenses += amount
            expense_breakdown.append({"account": acc.account_name, "amount": float(amount)})

    # Get ending balances for key accounts
    balance_query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.account)

    balances = {r.account: r.balance or Decimal("0") for r in balance_query.all()}

    # Calculate cash position
    cash_balance = sum(
        balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if acc.account_type in ["Bank", "Cash"]
    )

    # Calculate receivables
    receivables = sum(
        balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if acc.account_type == "Receivable"
    )

    # Calculate payables
    payables = sum(
        -balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if acc.account_type == "Payable"
    )

    net_income = total_revenue - total_expenses
    days_in_period = (period_end - period_start).days + 1

    return {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
            "days": days_in_period,
        },
        "income_statement": {
            "revenue": float(total_revenue),
            "expenses": float(total_expenses),
            "net_income": float(net_income),
            "profit_margin": round(float(net_income / total_revenue * 100), 2) if total_revenue else 0,
        },
        "balance_highlights": {
            "cash_position": float(cash_balance),
            "accounts_receivable": float(receivables),
            "accounts_payable": float(payables),
            "net_working_capital": float(cash_balance + receivables - payables),
        },
        "activity": {
            "total_debits": float(total_debits),
            "total_credits": float(total_credits),
            "transaction_count": transaction_count,
            "daily_average_revenue": round(float(total_revenue / days_in_period), 2) if days_in_period else 0,
            "daily_average_expenses": round(float(total_expenses / days_in_period), 2) if days_in_period else 0,
        },
        "top_income_sources": sorted(income_breakdown, key=lambda x: -x["amount"])[:5],
        "top_expenses": sorted(expense_breakdown, key=lambda x: -x["amount"])[:5],
    }


# ============= ACCOUNT TYPE SUMMARY =============

@router.get("/account-types", dependencies=[Depends(Require("accounting:read"))])
async def get_account_types(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get summary of account types and their usage."""
    accounts = db.query(Account).filter(Account.disabled == False).all()

    # Group by account type
    by_type = {}
    by_root_type = {}

    for acc in accounts:
        # By account_type
        atype = acc.account_type or "Unspecified"
        if atype not in by_type:
            by_type[atype] = {"count": 0, "examples": []}
        by_type[atype]["count"] += 1
        if len(by_type[atype]["examples"]) < 3:
            by_type[atype]["examples"].append(acc.account_name)

        # By root_type
        rtype = acc.root_type.value if acc.root_type else "unknown"
        if rtype not in by_root_type:
            by_root_type[rtype] = 0
        by_root_type[rtype] += 1

    return {
        "total_accounts": len(accounts),
        "by_root_type": by_root_type,
        "by_account_type": [
            {"type": k, "count": v["count"], "examples": v["examples"]}
            for k, v in sorted(by_type.items(), key=lambda x: -x[1]["count"])
        ],
    }


# ============= MODES OF PAYMENT =============

@router.get("/modes-of-payment", dependencies=[Depends(Require("accounting:read"))])
async def get_modes_of_payment(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get payment modes list."""
    modes = db.query(ModeOfPayment).filter(ModeOfPayment.enabled == True).all()

    return {
        "total": len(modes),
        "modes": [
            {
                "id": m.id,
                "erpnext_id": m.erpnext_id,
                "name": m.mode_of_payment,
                "type": m.type.value if m.type else None,
            }
            for m in modes
        ],
    }


# ============= TAX CATEGORIES =============

@router.get("/tax-categories", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_categories(
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax categories list."""
    from app.models.tax import TaxCategory

    query = db.query(TaxCategory)
    if not include_disabled:
        query = query.filter(TaxCategory.disabled == False)

    categories = query.order_by(TaxCategory.category_name).all()

    return {
        "total": len(categories),
        "categories": [
            {
                "id": cat.id,
                "erpnext_id": cat.erpnext_id,
                "name": cat.category_name,
                "title": cat.title,
                "is_inter_state": cat.is_inter_state,
                "is_reverse_charge": cat.is_reverse_charge,
                "disabled": cat.disabled,
            }
            for cat in categories
        ],
    }


# ============= SALES TAX TEMPLATES =============

@router.get("/sales-tax-templates", dependencies=[Depends(Require("accounting:read"))])
async def get_sales_tax_templates(
    company: Optional[str] = None,
    tax_category: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get sales tax templates list."""
    from app.models.tax import SalesTaxTemplate

    query = db.query(SalesTaxTemplate)
    if company:
        query = query.filter(SalesTaxTemplate.company == company)
    if tax_category:
        query = query.filter(SalesTaxTemplate.tax_category == tax_category)
    if not include_disabled:
        query = query.filter(SalesTaxTemplate.disabled == False)

    templates = query.order_by(SalesTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "tax_category": t.tax_category,
                "is_default": t.is_default,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/sales-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_sales_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get sales tax template with all tax line details."""
    from app.models.tax import SalesTaxTemplate, SalesTaxTemplateDetail

    template = db.query(SalesTaxTemplate).filter(SalesTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Sales tax template not found")

    details = db.query(SalesTaxTemplateDetail).filter(
        SalesTaxTemplateDetail.template_id == template_id
    ).order_by(SalesTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "tax_category": template.tax_category,
        "is_default": template.is_default,
        "disabled": template.disabled,
        "taxes": [
            {
                "charge_type": d.charge_type,
                "account_head": d.account_head,
                "description": d.description,
                "rate": float(d.rate),
                "tax_amount": float(d.tax_amount),
                "cost_center": d.cost_center,
                "included_in_print_rate": d.included_in_print_rate,
            }
            for d in details
        ],
    }


# ============= PURCHASE TAX TEMPLATES =============

@router.get("/purchase-tax-templates", dependencies=[Depends(Require("accounting:read"))])
async def get_purchase_tax_templates(
    company: Optional[str] = None,
    tax_category: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase tax templates list."""
    from app.models.tax import PurchaseTaxTemplate

    query = db.query(PurchaseTaxTemplate)
    if company:
        query = query.filter(PurchaseTaxTemplate.company == company)
    if tax_category:
        query = query.filter(PurchaseTaxTemplate.tax_category == tax_category)
    if not include_disabled:
        query = query.filter(PurchaseTaxTemplate.disabled == False)

    templates = query.order_by(PurchaseTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "tax_category": t.tax_category,
                "is_default": t.is_default,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/purchase-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_purchase_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get purchase tax template with all tax line details."""
    from app.models.tax import PurchaseTaxTemplate, PurchaseTaxTemplateDetail

    template = db.query(PurchaseTaxTemplate).filter(PurchaseTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Purchase tax template not found")

    details = db.query(PurchaseTaxTemplateDetail).filter(
        PurchaseTaxTemplateDetail.template_id == template_id
    ).order_by(PurchaseTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "tax_category": template.tax_category,
        "is_default": template.is_default,
        "disabled": template.disabled,
        "taxes": [
            {
                "charge_type": d.charge_type,
                "account_head": d.account_head,
                "description": d.description,
                "rate": float(d.rate),
                "tax_amount": float(d.tax_amount),
                "cost_center": d.cost_center,
                "add_deduct_tax": d.add_deduct_tax,
                "included_in_print_rate": d.included_in_print_rate,
            }
            for d in details
        ],
    }


# ============= ITEM TAX TEMPLATES =============

@router.get("/item-tax-templates", dependencies=[Depends(Require("accounting:read"))])
async def get_item_tax_templates(
    company: Optional[str] = None,
    include_disabled: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get item tax templates list."""
    from app.models.tax import ItemTaxTemplate

    query = db.query(ItemTaxTemplate)
    if company:
        query = query.filter(ItemTaxTemplate.company == company)
    if not include_disabled:
        query = query.filter(ItemTaxTemplate.disabled == False)

    templates = query.order_by(ItemTaxTemplate.template_name).all()

    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "name": t.template_name,
                "title": t.title,
                "company": t.company,
                "disabled": t.disabled,
            }
            for t in templates
        ],
    }


@router.get("/item-tax-templates/{template_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_item_tax_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get item tax template with all tax rate details."""
    from app.models.tax import ItemTaxTemplate, ItemTaxTemplateDetail

    template = db.query(ItemTaxTemplate).filter(ItemTaxTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Item tax template not found")

    details = db.query(ItemTaxTemplateDetail).filter(
        ItemTaxTemplateDetail.template_id == template_id
    ).order_by(ItemTaxTemplateDetail.idx).all()

    return {
        "id": template.id,
        "erpnext_id": template.erpnext_id,
        "name": template.template_name,
        "title": template.title,
        "company": template.company,
        "disabled": template.disabled,
        "taxes": [
            {
                "tax_type": d.tax_type,
                "tax_rate": float(d.tax_rate),
            }
            for d in details
        ],
    }


# ============= TAX WITHHOLDING CATEGORIES =============

@router.get("/tax-withholding-categories", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_withholding_categories(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax withholding categories list."""
    from app.models.tax import TaxWithholdingCategory

    categories = db.query(TaxWithholdingCategory).order_by(TaxWithholdingCategory.category_name).all()

    return {
        "total": len(categories),
        "categories": [
            {
                "id": cat.id,
                "erpnext_id": cat.erpnext_id,
                "name": cat.category_name,
                "company": cat.company,
                "account": cat.account,
                "round_off_tax_amount": cat.round_off_tax_amount,
                "consider_party_ledger_amount": cat.consider_party_ledger_amount,
            }
            for cat in categories
        ],
    }


# ============= TAX RULES =============

@router.get("/tax-rules", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_rules(
    tax_type: Optional[str] = None,
    tax_category: Optional[str] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax rules list."""
    from app.models.tax import TaxRule

    query = db.query(TaxRule)
    if tax_type:
        query = query.filter(TaxRule.tax_type == tax_type)
    if tax_category:
        query = query.filter(TaxRule.tax_category == tax_category)
    if company:
        query = query.filter(TaxRule.company == company)

    rules = query.order_by(TaxRule.priority.desc()).all()

    return {
        "total": len(rules),
        "rules": [
            {
                "id": r.id,
                "erpnext_id": r.erpnext_id,
                "name": r.rule_name,
                "tax_type": r.tax_type,
                "sales_tax_template": r.sales_tax_template,
                "purchase_tax_template": r.purchase_tax_template,
                "tax_category": r.tax_category,
                "customer": r.customer,
                "supplier": r.supplier,
                "customer_group": r.customer_group,
                "supplier_group": r.supplier_group,
                "billing_country": r.billing_country,
                "billing_state": r.billing_state,
                "shipping_country": r.shipping_country,
                "shipping_state": r.shipping_state,
                "item": r.item,
                "item_group": r.item_group,
                "company": r.company,
                "priority": r.priority,
                "from_date": r.from_date.isoformat() if r.from_date else None,
                "to_date": r.to_date.isoformat() if r.to_date else None,
            }
            for r in rules
        ],
    }


# =============================================================================
# BOOKS MODULE: FISCAL PERIODS
# =============================================================================

@router.get("/fiscal-periods", dependencies=[Depends(Require("books:read"))])
async def list_fiscal_periods(
    fiscal_year: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List fiscal periods with optional filtering."""
    from app.models.accounting_ext import FiscalPeriod, FiscalPeriodStatus

    query = db.query(FiscalPeriod).join(FiscalYear, FiscalPeriod.fiscal_year_id == FiscalYear.id)

    if fiscal_year:
        query = query.filter(FiscalYear.year == fiscal_year)
    if status:
        try:
            status_enum = FiscalPeriodStatus(status)
            query = query.filter(FiscalPeriod.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    periods = query.order_by(FiscalPeriod.start_date.desc()).all()

    return {
        "total": len(periods),
        "periods": [
            {
                "id": p.id,
                "fiscal_year_id": p.fiscal_year_id,
                "period_name": p.period_name,
                "period_type": p.period_type.value,
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
                "status": p.status.value,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
                "closed_by_id": p.closed_by_id,
                "has_closing_entry": p.closing_journal_entry_id is not None,
            }
            for p in periods
        ],
    }


@router.get("/fiscal-periods/{period_id}", dependencies=[Depends(Require("books:read"))])
async def get_fiscal_period(
    period_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get fiscal period detail with summary."""
    from app.services.period_manager import PeriodManager, PeriodNotFoundError

    manager = PeriodManager(db)
    try:
        return manager.get_period_summary(period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fiscal-periods", dependencies=[Depends(Require("books:admin"))])
async def create_fiscal_periods(
    fiscal_year_id: int = Query(..., description="ID of the fiscal year"),
    period_type: str = Query("month", description="Period type: month or quarter"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Auto-create fiscal periods for a fiscal year."""
    from app.models.accounting_ext import FiscalPeriodType
    from app.services.period_manager import PeriodManager, PeriodError

    try:
        ptype = FiscalPeriodType(period_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid period type: {period_type}")

    manager = PeriodManager(db)
    try:
        periods = manager.create_fiscal_periods_for_year(
            fiscal_year_id=fiscal_year_id,
            period_type=ptype,
            user_id=user.id,
        )
        db.commit()
        return {
            "message": f"Created {len(periods)} periods",
            "count": len(periods),
            "periods": [
                {
                    "id": p.id,
                    "period_name": p.period_name,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat(),
                }
                for p in periods
            ],
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/fiscal-periods/{period_id}/close", dependencies=[Depends(Require("books:close"))])
async def close_fiscal_period(
    period_id: int,
    soft_close: bool = Query(True, description="Soft close (can be reopened) vs hard close"),
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Close a fiscal period."""
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        period = manager.close_period(
            period_id=period_id,
            user_id=user.id,
            soft_close=soft_close,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": f"Period {period.period_name} {'soft' if soft_close else 'hard'}-closed",
            "period_id": period.id,
            "period_name": period.period_name,
            "status": period.status.value,
            "closed_at": period.closed_at.isoformat() if period.closed_at else None,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/fiscal-periods/{period_id}/reopen", dependencies=[Depends(Require("books:close"))])
async def reopen_fiscal_period(
    period_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Reopen a soft-closed fiscal period."""
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        period = manager.reopen_period(
            period_id=period_id,
            user_id=user.id,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": f"Period {period.period_name} reopened",
            "period_id": period.id,
            "period_name": period.period_name,
            "status": period.status.value,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fiscal-periods/{period_id}/closing-entries", dependencies=[Depends(Require("books:close"))])
async def generate_closing_entries(
    period_id: int,
    retained_earnings_account: Optional[str] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """Generate closing journal entries for a fiscal period."""
    from app.services.period_manager import PeriodManager, PeriodError

    manager = PeriodManager(db)
    try:
        je = manager.generate_closing_entries(
            period_id=period_id,
            user_id=user.id,
            retained_earnings_account=retained_earnings_account,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": "Closing entries generated",
            "journal_entry_id": je.id,
            "total_debit": str(je.total_debit),
            "total_credit": str(je.total_credit),
            "posting_date": je.posting_date.isoformat() if je.posting_date else None,
        }
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BOOKS MODULE: APPROVAL WORKFLOWS
# =============================================================================

@router.get("/workflows", dependencies=[Depends(Require("books:read"))])
async def list_approval_workflows(
    doctype: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List approval workflows."""
    from app.models.accounting_ext import ApprovalWorkflow

    query = db.query(ApprovalWorkflow)
    if doctype:
        query = query.filter(ApprovalWorkflow.doctype == doctype)
    if active_only:
        query = query.filter(ApprovalWorkflow.is_active == True)

    workflows = query.order_by(ApprovalWorkflow.doctype, ApprovalWorkflow.workflow_name).all()

    return {
        "total": len(workflows),
        "workflows": [
            {
                "id": w.id,
                "workflow_name": w.workflow_name,
                "doctype": w.doctype,
                "description": w.description,
                "is_active": w.is_active,
                "is_mandatory": w.is_mandatory,
                "escalation_enabled": w.escalation_enabled,
                "escalation_hours": w.escalation_hours,
            }
            for w in workflows
        ],
    }


@router.get("/workflows/{workflow_id}", dependencies=[Depends(Require("books:read"))])
async def get_workflow_detail(
    workflow_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get workflow detail with all steps."""
    from app.models.accounting_ext import ApprovalWorkflow, ApprovalStep

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps = db.query(ApprovalStep).filter(
        ApprovalStep.workflow_id == workflow_id
    ).order_by(ApprovalStep.step_order).all()

    return {
        "id": workflow.id,
        "workflow_name": workflow.workflow_name,
        "doctype": workflow.doctype,
        "description": workflow.description,
        "is_active": workflow.is_active,
        "is_mandatory": workflow.is_mandatory,
        "escalation_enabled": workflow.escalation_enabled,
        "escalation_hours": workflow.escalation_hours,
        "steps": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "step_name": s.step_name,
                "role_required": s.role_required,
                "user_id": s.user_id,
                "approval_mode": s.approval_mode.value,
                "amount_threshold_min": str(s.amount_threshold_min) if s.amount_threshold_min else None,
                "amount_threshold_max": str(s.amount_threshold_max) if s.amount_threshold_max else None,
                "auto_approve_below": str(s.auto_approve_below) if s.auto_approve_below else None,
                "can_reject": s.can_reject,
            }
            for s in steps
        ],
    }


@router.post("/workflows", dependencies=[Depends(Require("books:admin"))])
async def create_workflow(
    workflow_name: str = Query(...),
    doctype: str = Query(...),
    description: Optional[str] = None,
    is_mandatory: bool = False,
    escalation_enabled: bool = False,
    escalation_hours: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new approval workflow."""
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    workflow = engine.create_workflow(
        workflow_name=workflow_name,
        doctype=doctype,
        user_id=user.id,
        description=description,
        is_mandatory=is_mandatory,
        escalation_enabled=escalation_enabled,
        escalation_hours=escalation_hours,
    )
    db.commit()

    return {
        "message": "Workflow created",
        "id": workflow.id,
        "workflow_name": workflow.workflow_name,
        "doctype": workflow.doctype,
    }


@router.post("/workflows/{workflow_id}/steps", dependencies=[Depends(Require("books:admin"))])
async def add_workflow_step(
    workflow_id: int,
    step_order: int = Query(...),
    step_name: str = Query(...),
    role_required: Optional[str] = None,
    user_id: Optional[int] = None,
    approval_mode: str = "any",
    amount_threshold_min: Optional[float] = None,
    amount_threshold_max: Optional[float] = None,
    auto_approve_below: Optional[float] = None,
    can_reject: bool = True,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a step to a workflow."""
    from app.models.accounting_ext import ApprovalWorkflow, ApprovalMode
    from app.services.approval_engine import ApprovalEngine

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        mode = ApprovalMode(approval_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid approval mode: {approval_mode}")

    # Prevent duplicate step_order
    from app.models.accounting_ext import ApprovalStep

    dup_step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.workflow_id == workflow_id, ApprovalStep.step_order == step_order)
        .first()
    )
    if dup_step:
        raise HTTPException(status_code=400, detail=f"Step order {step_order} already exists in this workflow")

    # Prevent overlapping amount thresholds within the same workflow
    if amount_threshold_min is not None or amount_threshold_max is not None:
        existing_steps = db.query(ApprovalStep).filter(ApprovalStep.workflow_id == workflow_id).all()
        new_min = Decimal(str(amount_threshold_min)) if amount_threshold_min is not None else None
        new_max = Decimal(str(amount_threshold_max)) if amount_threshold_max is not None else None

        for s in existing_steps:
            s_min = s.amount_threshold_min
            s_max = s.amount_threshold_max
            # Overlap if ranges intersect (treat None as unbounded)
            if (
                (new_min is None or s_max is None or new_min <= s_max)
                and (new_max is None or s_min is None or new_max >= s_min)
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Amount range overlaps with existing step '{s.step_name}' (min={s_min}, max={s_max})",
                )

    engine = ApprovalEngine(db)
    step = engine.add_workflow_step(
        workflow_id=workflow_id,
        step_order=step_order,
        step_name=step_name,
        role_required=role_required,
        user_id=user_id,
        approval_mode=mode,
        amount_threshold_min=Decimal(str(amount_threshold_min)) if amount_threshold_min else None,
        amount_threshold_max=Decimal(str(amount_threshold_max)) if amount_threshold_max else None,
        auto_approve_below=Decimal(str(auto_approve_below)) if auto_approve_below else None,
        can_reject=can_reject,
    )
    db.commit()

    return {
        "message": "Step added",
        "step_id": step.id,
        "step_order": step.step_order,
        "step_name": step.step_name,
    }


@router.patch("/workflows/{workflow_id}", dependencies=[Depends(Require("books:admin"))])
async def update_workflow(
    workflow_id: int,
    workflow_name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_mandatory: Optional[bool] = None,
    escalation_enabled: Optional[bool] = None,
    escalation_hours: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update a workflow."""
    from app.services.approval_engine import ApprovalEngine, WorkflowNotFoundError

    updates = {}
    if workflow_name is not None:
        updates["workflow_name"] = workflow_name
    if description is not None:
        updates["description"] = description
    if is_active is not None:
        updates["is_active"] = is_active
    if is_mandatory is not None:
        updates["is_mandatory"] = is_mandatory
    if escalation_enabled is not None:
        updates["escalation_enabled"] = escalation_enabled
    if escalation_hours is not None:
        updates["escalation_hours"] = escalation_hours

    engine = ApprovalEngine(db)
    try:
        workflow = engine.update_workflow(workflow_id, user.id, **updates)
        db.commit()
        return {
            "message": "Workflow updated",
            "id": workflow.id,
            "workflow_name": workflow.workflow_name,
            "is_active": workflow.is_active,
        }
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/workflows/{workflow_id}", dependencies=[Depends(Require("books:admin"))])
async def deactivate_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Deactivate a workflow (soft delete)."""
    from app.services.approval_engine import ApprovalEngine, WorkflowNotFoundError

    engine = ApprovalEngine(db)
    try:
        workflow = engine.deactivate_workflow(workflow_id, user.id)
        db.commit()
        return {
            "message": "Workflow deactivated",
            "id": workflow.id,
            "workflow_name": workflow.workflow_name,
        }
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# BOOKS MODULE: PENDING APPROVALS
# =============================================================================

@router.get("/approvals/pending", dependencies=[Depends(Require("books:approve"))])
async def get_pending_approvals(
    doctype: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Get documents pending approval for the current user."""
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    pending = engine.get_pending_approvals(user.id, doctype)

    return {
        "total": len(pending),
        "pending": pending,
    }


@router.get("/approvals/{doctype}/{document_id}", dependencies=[Depends(Require("books:read"))])
async def get_approval_status(
    doctype: str,
    document_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get approval status for a specific document."""
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    status = engine.get_approval_status(doctype, document_id)

    if not status:
        raise HTTPException(status_code=404, detail="No approval record found")

    return status


# =============================================================================
# BOOKS MODULE: DOCUMENT ACTIONS (Submit/Approve/Reject/Post)
# =============================================================================

@router.post("/journal-entries/{je_id}/submit", dependencies=[Depends(Require("books:write"))])
async def submit_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Submit a journal entry for approval."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    engine = ApprovalEngine(db)
    try:
        approval = engine.submit_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            amount=je.total_debit,
            document_name=je.erpnext_id,
        )
        db.commit()
        return {
            "message": "Journal entry submitted for approval",
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/approve", dependencies=[Depends(Require("books:approve"))])
async def approve_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Approve a journal entry at the current step."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.approve_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": "Journal entry approved",
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/reject", dependencies=[Depends(Require("books:approve"))])
async def reject_journal_entry(
    je_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Reject a journal entry."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.reject_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            reason=reason,
        )
        db.commit()
        return {
            "message": "Journal entry rejected",
            "approval_id": approval.id,
            "status": approval.status.value,
            "rejection_reason": approval.rejection_reason,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Post an approved journal entry to the GL."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.post_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            remarks=remarks,
        )

        # Update JE docstatus to posted
        je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
        if je:
            je.docstatus = 1  # Posted

        db.commit()
        return {
            "message": "Journal entry posted",
            "approval_id": approval.id,
            "status": approval.status.value,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BOOKS MODULE: JOURNAL ENTRY CRUD
# =============================================================================

from pydantic import BaseModel


class JournalEntryAccountCreate(BaseModel):
    """Schema for creating a journal entry account line."""
    account: str
    debit: float = 0
    credit: float = 0
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None
    user_remark: Optional[str] = None


class JournalEntryCreate(BaseModel):
    """Schema for creating a journal entry."""
    voucher_type: str = "journal_entry"
    posting_date: str
    user_remark: Optional[str] = None
    company: Optional[str] = None
    accounts: List[JournalEntryAccountCreate] = []


@router.post("/journal-entries", dependencies=[Depends(Require("books:write"))])
async def create_journal_entry(
    je_data: JournalEntryCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new journal entry."""
    from app.models.accounting import JournalEntryAccount
    from app.services.je_validator import JEValidator, ValidationError
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        voucher_type_enum = JournalEntryType(je_data.voucher_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid voucher type: {je_data.voucher_type}")

    posting_dt = _parse_date(je_data.posting_date, "posting_date")

    # Create JE
    je = JournalEntry(
        voucher_type=voucher_type_enum,
        posting_date=posting_dt,
        user_remark=je_data.user_remark,
        company=je_data.company,
        total_debit=Decimal("0"),
        total_credit=Decimal("0"),
        docstatus=0,  # Draft
    )

    # Parse account lines
    je_accounts = []
    for acc_data in je_data.accounts:
        je_acc = JournalEntryAccount(
            account=acc_data.account,
            debit=Decimal(str(acc_data.debit)),
            credit=Decimal(str(acc_data.credit)),
            party_type=acc_data.party_type,
            party=acc_data.party,
            cost_center=acc_data.cost_center,
            user_remark=acc_data.user_remark,
        )
        je_accounts.append(je_acc)

    # Validate
    validator = JEValidator(db)
    try:
        validator.validate_or_raise(je, je_accounts)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"errors": e.errors})

    # Calculate totals
    je.total_debit = sum(a.debit for a in je_accounts)
    je.total_credit = sum(a.credit for a in je_accounts)

    db.add(je)
    db.flush()

    # Add account lines
    for idx, acc in enumerate(je_accounts, 1):
        acc.journal_entry_id = je.id
        acc.idx = idx
        db.add(acc)

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        new_values=serialize_for_audit(je),
    )

    db.commit()

    return {
        "message": "Journal entry created",
        "id": je.id,
        "total_debit": str(je.total_debit),
        "total_credit": str(je.total_credit),
        "docstatus": je.docstatus,
    }


@router.patch("/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))])
async def update_journal_entry(
    je_id: int,
    posting_date: Optional[str] = None,
    user_remark: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a draft journal entry."""
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if je.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only update draft entries")

    old_values = serialize_for_audit(je)

    if posting_date:
        je.posting_date = _parse_date(posting_date, "posting_date")
    if user_remark is not None:
        je.user_remark = user_remark

    je.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        old_values=old_values,
        new_values=serialize_for_audit(je),
    )

    db.commit()

    return {
        "message": "Journal entry updated",
        "id": je.id,
    }


@router.delete("/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))])
async def delete_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Delete a draft journal entry."""
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if je.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only delete draft entries")

    old_values = serialize_for_audit(je)

    # Audit log before delete
    audit = AuditLogger(db)
    audit.log_delete(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        old_values=old_values,
    )

    db.delete(je)
    db.commit()

    return {"message": "Journal entry deleted"}


# =============================================================================
# BOOKS MODULE: ACCOUNTING CONTROLS
# =============================================================================

@router.get("/controls", dependencies=[Depends(Require("books:read"))])
async def get_accounting_controls(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounting control settings."""
    from app.models.accounting_ext import AccountingControl

    controls = db.query(AccountingControl).filter(
        AccountingControl.company.is_(None)
    ).first()

    if not controls:
        return {"message": "No controls configured", "controls": None}

    return {
        "controls": {
            "id": controls.id,
            "base_currency": controls.base_currency,
            "backdating_days_allowed": controls.backdating_days_allowed,
            "future_posting_days_allowed": controls.future_posting_days_allowed,
            "auto_voucher_numbering": controls.auto_voucher_numbering,
            "voucher_prefix_format": controls.voucher_prefix_format,
            "require_attachment_journal_entry": controls.require_attachment_journal_entry,
            "require_attachment_expense": controls.require_attachment_expense,
            "require_attachment_payment": controls.require_attachment_payment,
            "require_attachment_invoice": controls.require_attachment_invoice,
            "require_approval_journal_entry": controls.require_approval_journal_entry,
            "require_approval_expense": controls.require_approval_expense,
            "require_approval_payment": controls.require_approval_payment,
            "auto_create_fiscal_periods": controls.auto_create_fiscal_periods,
            "default_period_type": controls.default_period_type,
            "retained_earnings_account": controls.retained_earnings_account,
            "fx_gain_account": controls.fx_gain_account,
            "fx_loss_account": controls.fx_loss_account,
        }
    }


@router.patch("/controls", dependencies=[Depends(Require("books:admin"))])
async def update_accounting_controls(
    backdating_days_allowed: Optional[int] = None,
    future_posting_days_allowed: Optional[int] = None,
    auto_voucher_numbering: Optional[bool] = None,
    require_attachment_journal_entry: Optional[bool] = None,
    require_attachment_expense: Optional[bool] = None,
    require_approval_journal_entry: Optional[bool] = None,
    require_approval_expense: Optional[bool] = None,
    retained_earnings_account: Optional[str] = None,
    fx_gain_account: Optional[str] = None,
    fx_loss_account: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update accounting control settings."""
    from app.models.accounting_ext import AccountingControl
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    controls = db.query(AccountingControl).filter(
        AccountingControl.company.is_(None)
    ).first()

    if not controls:
        controls = AccountingControl()
        db.add(controls)
        old_values = {}
    else:
        old_values = serialize_for_audit(controls)

    # Apply updates
    if backdating_days_allowed is not None:
        controls.backdating_days_allowed = backdating_days_allowed
    if future_posting_days_allowed is not None:
        controls.future_posting_days_allowed = future_posting_days_allowed
    if auto_voucher_numbering is not None:
        controls.auto_voucher_numbering = auto_voucher_numbering
    if require_attachment_journal_entry is not None:
        controls.require_attachment_journal_entry = require_attachment_journal_entry
    if require_attachment_expense is not None:
        controls.require_attachment_expense = require_attachment_expense
    if require_approval_journal_entry is not None:
        controls.require_approval_journal_entry = require_approval_journal_entry
    if require_approval_expense is not None:
        controls.require_approval_expense = require_approval_expense
    if retained_earnings_account is not None:
        controls.retained_earnings_account = retained_earnings_account
    if fx_gain_account is not None:
        controls.fx_gain_account = fx_gain_account
    if fx_loss_account is not None:
        controls.fx_loss_account = fx_loss_account

    controls.updated_at = datetime.utcnow()
    controls.updated_by_id = user.id

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="accounting_control",
        document_id=controls.id,
        user_id=user.id,
        old_values=old_values,
        new_values=serialize_for_audit(controls),
    )

    db.commit()

    return {"message": "Controls updated"}


# =============================================================================
# BOOKS MODULE: AUDIT LOG
# =============================================================================

@router.get("/audit-log", dependencies=[Depends(Require("books:read"))])
async def list_audit_logs(
    doctype: Optional[str] = None,
    document_id: Optional[int] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Query audit logs."""
    from app.models.accounting_ext import AuditLog, AuditAction

    query = db.query(AuditLog)

    if doctype:
        query = query.filter(AuditLog.doctype == doctype)
    if document_id:
        query = query.filter(AuditLog.document_id == document_id)
    if action:
        try:
            action_enum = AuditAction(action)
            query = query.filter(AuditLog.action == action_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if start_date:
        query = query.filter(AuditLog.timestamp >= _parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(AuditLog.timestamp <= _parse_date(end_date, "end_date"))

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "doctype": log.doctype,
                "document_id": log.document_id,
                "document_name": log.document_name,
                "action": log.action.value,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "user_name": log.user_name,
                "changed_fields": log.changed_fields,
                "remarks": log.remarks,
            }
            for log in logs
        ],
    }


@router.get("/audit-log/{doctype}/{document_id}", dependencies=[Depends(Require("books:read"))])
async def get_document_audit_history(
    doctype: str,
    document_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get full audit history for a specific document."""
    from app.services.audit_logger import AuditLogger

    audit = AuditLogger(db)
    history = audit.get_document_history(doctype, document_id)

    return {
        "doctype": doctype,
        "document_id": document_id,
        "total": len(history),
        "history": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action.value,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "user_name": log.user_name,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "changed_fields": log.changed_fields,
                "remarks": log.remarks,
            }
            for log in history
        ],
    }


# =============================================================================
# BOOKS MODULE: ACCOUNT CRUD
# =============================================================================

@router.post("/accounts", dependencies=[Depends(Require("books:admin"))])
async def create_account(
    account_name: str = Query(...),
    root_type: str = Query(..., description="Asset, Liability, Equity, Income, or Expense"),
    account_number: Optional[str] = None,
    account_type: Optional[str] = None,
    parent_account: Optional[str] = None,
    is_group: bool = False,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new account in the chart of accounts."""
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        root_type_enum = AccountType(root_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid root type: {root_type}. Must be Asset, Liability, Equity, Income, or Expense"
        )

    account_data = {
        "account_name": account_name,
        "root_type": root_type_enum,
        "account_number": account_number,
        "account_type": account_type,
        "parent_account": parent_account,
        "is_group": is_group,
        "company": company,
    }

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_create(account_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    account = Account(
        account_name=account_name,
        root_type=root_type_enum,
        account_number=account_number,
        account_type=account_type,
        parent_account=parent_account,
        is_group=is_group,
        company=company,
        disabled=False,
    )
    db.add(account)
    db.flush()

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account_name,
        new_values=serialize_for_audit(account),
    )

    db.commit()

    return {
        "message": "Account created",
        "id": account.id,
        "account_name": account.account_name,
        "account_number": account.account_number,
        "root_type": account.root_type.value if account.root_type else None,
    }


@router.patch("/accounts/{account_id}", dependencies=[Depends(Require("books:admin"))])
async def update_account(
    account_id: int,
    account_name: Optional[str] = None,
    account_number: Optional[str] = None,
    account_type: Optional[str] = None,
    disabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update an account."""
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = {}
    if account_name is not None:
        updates["account_name"] = account_name
    if account_number is not None:
        updates["account_number"] = account_number
    if account_type is not None:
        updates["account_type"] = account_type
    if disabled is not None:
        updates["disabled"] = disabled

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_update(account, updates)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    old_values = serialize_for_audit(account)

    # Apply updates
    for field, value in updates.items():
        setattr(account, field, value)
    account.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account.account_name,
        old_values=old_values,
        new_values=serialize_for_audit(account),
    )

    db.commit()

    return {
        "message": "Account updated",
        "id": account.id,
        "account_name": account.account_name,
    }


@router.delete("/accounts/{account_id}", dependencies=[Depends(Require("books:admin"))])
async def disable_account(
    account_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Disable an account (soft delete)."""
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_disable(account)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    old_values = serialize_for_audit(account)
    account.disabled = True
    account.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account.account_name,
        old_values=old_values,
        new_values=serialize_for_audit(account),
        remarks="Account disabled",
    )

    db.commit()

    return {
        "message": "Account disabled",
        "id": account.id,
        "account_name": account.account_name,
    }


# =============================================================================
# BOOKS MODULE: SUPPLIER CRUD
# =============================================================================

@router.post("/suppliers", dependencies=[Depends(Require("books:write"))])
async def create_supplier(
    supplier_name: str = Query(...),
    supplier_group: Optional[str] = None,
    supplier_type: Optional[str] = None,
    country: Optional[str] = None,
    default_currency: str = "NGN",
    tax_id: Optional[str] = None,
    email_id: Optional[str] = None,
    mobile_no: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new supplier."""
    from app.services.je_validator import SupplierValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    supplier_data = {"supplier_name": supplier_name}

    validator = SupplierValidator(db)
    is_valid, errors = validator.validate_create(supplier_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    supplier = Supplier(
        supplier_name=supplier_name,
        supplier_group=supplier_group,
        supplier_type=supplier_type,
        country=country,
        default_currency=default_currency,
        tax_id=tax_id,
        email_id=email_id,
        mobile_no=mobile_no,
        disabled=False,
    )
    db.add(supplier)
    db.flush()

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="supplier",
        document_id=supplier.id,
        user_id=user.id,
        document_name=supplier_name,
        new_values=serialize_for_audit(supplier),
    )

    db.commit()

    return {
        "message": "Supplier created",
        "id": supplier.id,
        "supplier_name": supplier.supplier_name,
    }


@router.patch("/suppliers/{supplier_id}", dependencies=[Depends(Require("books:write"))])
async def update_supplier(
    supplier_id: int,
    supplier_name: Optional[str] = None,
    supplier_group: Optional[str] = None,
    supplier_type: Optional[str] = None,
    country: Optional[str] = None,
    default_currency: Optional[str] = None,
    tax_id: Optional[str] = None,
    email_id: Optional[str] = None,
    mobile_no: Optional[str] = None,
    disabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a supplier."""
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    old_values = serialize_for_audit(supplier)

    # Apply updates
    if supplier_name is not None:
        supplier.supplier_name = supplier_name
    if supplier_group is not None:
        supplier.supplier_group = supplier_group
    if supplier_type is not None:
        supplier.supplier_type = supplier_type
    if country is not None:
        supplier.country = country
    if default_currency is not None:
        supplier.default_currency = default_currency
    if tax_id is not None:
        supplier.tax_id = tax_id
    if email_id is not None:
        supplier.email_id = email_id
    if mobile_no is not None:
        supplier.mobile_no = mobile_no
    if disabled is not None:
        supplier.disabled = disabled

    supplier.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="supplier",
        document_id=supplier.id,
        user_id=user.id,
        document_name=supplier.supplier_name,
        old_values=old_values,
        new_values=serialize_for_audit(supplier),
    )

    db.commit()

    return {
        "message": "Supplier updated",
        "id": supplier.id,
        "supplier_name": supplier.supplier_name,
    }


@router.delete("/suppliers/{supplier_id}", dependencies=[Depends(Require("books:write"))])
async def disable_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Disable a supplier (soft delete)."""
    from app.services.je_validator import SupplierValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    validator = SupplierValidator(db)
    is_valid, errors = validator.validate_disable(supplier_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    old_values = serialize_for_audit(supplier)
    supplier.disabled = True
    supplier.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="supplier",
        document_id=supplier.id,
        user_id=user.id,
        document_name=supplier.supplier_name,
        old_values=old_values,
        new_values=serialize_for_audit(supplier),
        remarks="Supplier disabled",
    )

    db.commit()

    return {
        "message": "Supplier disabled",
        "id": supplier.id,
        "supplier_name": supplier.supplier_name,
    }


# =============================================================================
# BOOKS MODULE: EXCHANGE RATES
# =============================================================================

@router.get("/exchange-rates", dependencies=[Depends(Require("books:read"))])
async def list_exchange_rates(
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List exchange rates."""
    from app.models.accounting_ext import ExchangeRate

    query = db.query(ExchangeRate)

    if from_currency:
        query = query.filter(ExchangeRate.from_currency == from_currency.upper())
    if to_currency:
        query = query.filter(ExchangeRate.to_currency == to_currency.upper())
    if start_date:
        query = query.filter(ExchangeRate.rate_date >= _parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(ExchangeRate.rate_date <= _parse_date(end_date, "end_date"))

    rates = query.order_by(ExchangeRate.rate_date.desc()).limit(limit).all()

    return {
        "total": len(rates),
        "rates": [
            {
                "id": r.id,
                "from_currency": r.from_currency,
                "to_currency": r.to_currency,
                "rate_date": r.rate_date.isoformat(),
                "rate": str(r.rate),
                "source": r.source.value,
            }
            for r in rates
        ],
    }


@router.get("/exchange-rates/latest", dependencies=[Depends(Require("books:read"))])
async def get_latest_exchange_rates(
    base_currency: str = "NGN",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get latest exchange rate for each currency pair."""
    from app.models.accounting_ext import ExchangeRate
    from sqlalchemy import distinct

    # Get distinct currency pairs
    pairs = db.query(
        ExchangeRate.from_currency,
        ExchangeRate.to_currency
    ).filter(
        or_(
            ExchangeRate.from_currency == base_currency.upper(),
            ExchangeRate.to_currency == base_currency.upper(),
        )
    ).distinct().all()

    latest = []
    for from_curr, to_curr in pairs:
        rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_curr,
            ExchangeRate.to_currency == to_curr,
        ).order_by(ExchangeRate.rate_date.desc()).first()

        if rate:
            latest.append({
                "from_currency": rate.from_currency,
                "to_currency": rate.to_currency,
                "rate": str(rate.rate),
                "rate_date": rate.rate_date.isoformat(),
            })

    return {
        "base_currency": base_currency.upper(),
        "rates": latest,
    }


@router.post("/exchange-rates", dependencies=[Depends(Require("books:admin"))])
async def create_exchange_rate(
    from_currency: str = Query(...),
    to_currency: str = Query(...),
    rate_date: str = Query(...),
    rate: float = Query(..., gt=0),
    source: str = "manual",
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Add a new exchange rate."""
    from app.models.accounting_ext import ExchangeRate, ExchangeRateSource
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        source_enum = ExchangeRateSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    rate_dt = _parse_date(rate_date, "rate_date")

    # Check if rate already exists for this date
    existing = db.query(ExchangeRate).filter(
        ExchangeRate.from_currency == from_currency.upper(),
        ExchangeRate.to_currency == to_currency.upper(),
        ExchangeRate.rate_date == rate_dt,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Exchange rate already exists for {from_currency}/{to_currency} on {rate_date}"
        )

    fx_rate = ExchangeRate(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        rate_date=rate_dt,
        rate=Decimal(str(rate)),
        source=source_enum,
        created_by_id=user.id,
    )
    db.add(fx_rate)
    db.flush()

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="exchange_rate",
        document_id=fx_rate.id,
        user_id=user.id,
        document_name=f"{from_currency}/{to_currency}",
        new_values=serialize_for_audit(fx_rate),
    )

    db.commit()

    return {
        "message": "Exchange rate created",
        "id": fx_rate.id,
        "from_currency": fx_rate.from_currency,
        "to_currency": fx_rate.to_currency,
        "rate": str(fx_rate.rate),
        "rate_date": fx_rate.rate_date.isoformat(),
    }


# =============================================================================
# FX REVALUATION
# =============================================================================


@router.post("/revaluation/preview", dependencies=[Depends(Require("books:close"))])
async def preview_revaluation(
    period_id: int = Query(..., description="Fiscal period ID to preview revaluation for"),
    base_currency: str = Query("NGN", description="Base/functional currency"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Preview FX revaluation for a fiscal period without posting.

    Returns unrealized gains/losses on foreign currency balances as of
    the period end date, calculated using current exchange rates.
    """
    from app.services.fx_service import FXService, FXError

    fx_service = FXService(db)

    try:
        preview = fx_service.preview_revaluation(period_id, base_currency)
        return preview
    except FXError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revaluation/apply", dependencies=[Depends(Require("books:close"))])
async def apply_revaluation(
    period_id: int = Query(..., description="Fiscal period ID to apply revaluation for"),
    base_currency: str = Query("NGN", description="Base/functional currency"),
    fx_gain_account: Optional[str] = Query(None, description="Account for FX gains (uses default if not provided)"),
    fx_loss_account: Optional[str] = Query(None, description="Account for FX losses (uses default if not provided)"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:close")),
) -> Dict[str, Any]:
    """
    Apply FX revaluation by posting adjustment journal entries.

    Creates a journal entry to record unrealized gains/losses on foreign
    currency balances. Each affected account is adjusted and offset against
    the FX gain/loss accounts.
    """
    from app.services.fx_service import FXService, FXError

    fx_service = FXService(db)

    try:
        je = fx_service.apply_revaluation(
            period_id=period_id,
            user_id=user.id,
            base_currency=base_currency,
            fx_gain_account=fx_gain_account,
            fx_loss_account=fx_loss_account,
        )
        db.commit()

        return {
            "message": "FX revaluation applied",
            "journal_entry_id": je.id,
            "posting_date": je.posting_date.isoformat(),
            "total_debit": str(je.total_debit),
            "total_credit": str(je.total_credit),
        }
    except FXError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/revaluation/history", dependencies=[Depends(Require("books:read"))])
async def get_revaluation_history(
    period_id: Optional[int] = Query(None, description="Filter by fiscal period ID"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get history of FX revaluations.

    Returns a list of past revaluations grouped by journal entry,
    showing total gains/losses and affected account counts.
    """
    from app.services.fx_service import FXService

    fx_service = FXService(db)
    history = fx_service.get_revaluation_history(period_id=period_id, limit=limit)

    return {
        "count": len(history),
        "revaluations": history,
    }


# =============================================================================
# REPORT EXPORTS
# =============================================================================


@router.get("/trial-balance/export", dependencies=[Depends(Require("books:read"))])
async def export_trial_balance(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export trial balance report to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_trial_balance(
        as_of_date=as_of_date,
        fiscal_year=fiscal_year,
        cost_center=cost_center,
        drill=False,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="trial_balance",
        document_id=0,
        user_id=user.id,
        document_name=f"Trial Balance {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "trial_balance")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=trial_balance.csv"},
            )
        else:
            content = export_service.export_pdf(data, "trial_balance")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=trial_balance.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/balance-sheet/export", dependencies=[Depends(Require("books:read"))])
async def export_balance_sheet(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export balance sheet report to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_balance_sheet(
        as_of_date=as_of_date,
        comparative_date=comparative_date,
        common_size=False,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="balance_sheet",
        document_id=0,
        user_id=user.id,
        document_name=f"Balance Sheet {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "balance_sheet")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=balance_sheet.csv"},
            )
        else:
            content = export_service.export_pdf(data, "balance_sheet")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=balance_sheet.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/income-statement/export", dependencies=[Depends(Require("books:read"))])
async def export_income_statement(
    format: str = Query("csv", description="Export format: csv or pdf"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    basis: str = Query("accrual", description="Accounting basis: accrual or cash"),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export income statement report to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_income_statement(
        start_date=start_date,
        end_date=end_date,
        fiscal_year=fiscal_year,
        cost_center=cost_center,
        compare_start=None,
        compare_end=None,
        show_ytd=False,
        common_size=False,
        basis=basis,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="income_statement",
        document_id=0,
        user_id=user.id,
        document_name=f"Income Statement {start_date or ''} to {end_date or 'today'}",
        remarks=f"Exported as {format.upper()}, basis: {basis}",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "income_statement")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=income_statement.csv"},
            )
        else:
            content = export_service.export_pdf(data, "income_statement")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=income_statement.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/general-ledger/export", dependencies=[Depends(Require("books:read"))])
async def export_general_ledger(
    format: str = Query("csv", description="Export format: csv or pdf"),
    account: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=1000, le=10000),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export general ledger to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_general_ledger(
        account=account,
        start_date=start_date,
        end_date=end_date,
        party_type=party_type,
        party=party,
        voucher_type=voucher_type,
        limit=limit,
        offset=0,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="general_ledger",
        document_id=0,
        user_id=user.id,
        document_name=f"General Ledger {start_date or ''} to {end_date or ''}",
        remarks=f"Exported as {format.upper()}, {data.get('total', 0)} records",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "general_ledger")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=general_ledger.csv"},
            )
        else:
            content = export_service.export_pdf(data, "general_ledger")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=general_ledger.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/receivables-aging/export", dependencies=[Depends(Require("books:read"))])
async def export_receivables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export receivables aging report to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_receivables_aging(as_of_date=as_of_date, db=db)

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="receivables_aging",
        document_id=0,
        user_id=user.id,
        document_name=f"Receivables Aging {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "receivables_aging")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=receivables_aging.csv"},
            )
        else:
            content = export_service.export_pdf(data, "receivables_aging")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=receivables_aging.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payables-aging/export", dependencies=[Depends(Require("books:read"))])
async def export_payables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export payables aging report to CSV or PDF."""
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = await get_payables_aging(as_of_date=as_of_date, db=db)

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="payables_aging",
        document_id=0,
        user_id=user.id,
        document_name=f"Payables Aging {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        if format == "csv":
            content = export_service.export_csv(data, "payables_aging")
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=payables_aging.csv"},
            )
        else:
            content = export_service.export_pdf(data, "payables_aging")
            return StreamingResponse(
                iter([content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=payables_aging.pdf"},
            )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BANK RECONCILIATION
# =============================================================================


@router.get("/bank-accounts/{bank_account_id}/reconciliation-status", dependencies=[Depends(Require("accounting:read"))])
async def get_bank_reconciliation_status(
    bank_account_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get current reconciliation status for a bank account."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        return service.get_reconciliation_status(bank_account_id)
    except ReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bank-accounts/{bank_account_id}/reconciliation/start", dependencies=[Depends(Require("books:write"))])
async def start_bank_reconciliation(
    bank_account_id: int,
    from_date: str = Query(..., description="Statement start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="Statement end date (YYYY-MM-DD)"),
    statement_opening_balance: float = Query(..., description="Opening balance from bank statement"),
    statement_closing_balance: float = Query(..., description="Closing balance from bank statement"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Start a new bank reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        reconciliation = service.start_reconciliation(
            bank_account_id=bank_account_id,
            from_date=_parse_date(from_date, "from_date"),
            to_date=_parse_date(to_date, "to_date"),
            statement_opening_balance=Decimal(str(statement_opening_balance)),
            statement_closing_balance=Decimal(str(statement_closing_balance)),
            user_id=user.id,
        )
        db.commit()

        return {
            "message": "Reconciliation started",
            "reconciliation_id": reconciliation.id,
            "bank_account": reconciliation.bank_account,
            "from_date": reconciliation.from_date.isoformat(),
            "to_date": reconciliation.to_date.isoformat(),
            "statement_opening": float(reconciliation.bank_statement_opening_balance),
            "statement_closing": float(reconciliation.bank_statement_closing_balance),
            "gl_opening": float(reconciliation.account_opening_balance),
        }
    except ReconciliationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bank-reconciliations/{reconciliation_id}/outstanding", dependencies=[Depends(Require("accounting:read"))])
async def get_reconciliation_outstanding(
    reconciliation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get outstanding (unmatched) items for a reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        return service.get_outstanding_items(reconciliation_id)
    except ReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bank-reconciliations/{reconciliation_id}/match", dependencies=[Depends(Require("books:write"))])
async def match_bank_transaction(
    reconciliation_id: int,
    bank_transaction_id: int = Query(..., description="Bank transaction ID to match"),
    gl_entry_ids: str = Query(..., description="Comma-separated GL entry IDs to match"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Match a bank transaction to GL entries."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        entry_ids = [int(x.strip()) for x in gl_entry_ids.split(",")]
        result = service.match_transaction(
            bank_transaction_id=bank_transaction_id,
            gl_entry_ids=entry_ids,
            user_id=user.id,
        )
        db.commit()
        return result
    except (ReconciliationError, ValueError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bank-reconciliations/{reconciliation_id}/auto-match", dependencies=[Depends(Require("books:write"))])
async def auto_match_transactions(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Automatically match bank transactions to GL entries based on amount."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        result = service.auto_match(reconciliation_id, user.id)
        db.commit()
        return result
    except ReconciliationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bank-reconciliations/{reconciliation_id}/complete", dependencies=[Depends(Require("books:write"))])
async def complete_bank_reconciliation(
    reconciliation_id: int,
    adjustment_account: Optional[str] = Query(None, description="Account for difference adjustment"),
    adjustment_remarks: Optional[str] = Query(None, description="Remarks for adjustment"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Complete the bank reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        result = service.complete_reconciliation(
            reconciliation_id=reconciliation_id,
            user_id=user.id,
            adjustment_account=adjustment_account,
            adjustment_remarks=adjustment_remarks,
        )
        db.commit()
        return result
    except ReconciliationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bank-accounts/{bank_account_id}/import-statement", dependencies=[Depends(Require("books:write"))])
async def import_bank_statement(
    bank_account_id: int,
    file: UploadFile = File(...),
    date_format: str = Query("%Y-%m-%d", description="Date format in CSV (e.g., %Y-%m-%d, %d/%m/%Y)"),
    has_header: bool = Query(True, description="Whether CSV has header row"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Import bank statement from CSV file."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    csv_content = content.decode("utf-8")

    service = BankReconciliationService(db)

    try:
        result = service.import_statement_csv(
            bank_account_id=bank_account_id,
            csv_content=csv_content,
            user_id=user.id,
            date_format=date_format,
            has_header=has_header,
        )
        db.commit()
        return result
    except ReconciliationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# TAX FILING MANAGEMENT
# =============================================================================


@router.get("/tax/filing-periods", dependencies=[Depends(Require("accounting:read"))])
async def list_tax_filing_periods(
    tax_type: Optional[str] = Query(None, description="Filter by tax type (vat, wht, cit, paye)"),
    status: Optional[str] = Query(None, description="Filter by status (open, filed, paid, closed)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tax filing periods with optional filters."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    query = db.query(TaxFilingPeriod)

    if tax_type:
        try:
            tax_type_enum = TaxFilingType(tax_type.lower())
            query = query.filter(TaxFilingPeriod.tax_type == tax_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tax type: {tax_type}")

    if status:
        try:
            status_enum = TaxFilingStatus(status.lower())
            query = query.filter(TaxFilingPeriod.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if year:
        query = query.filter(func.extract('year', TaxFilingPeriod.period_start) == year)

    total = query.count()
    periods = query.order_by(TaxFilingPeriod.due_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "periods": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "period_start": p.period_start.isoformat(),
                "period_end": p.period_end.isoformat(),
                "due_date": p.due_date.isoformat(),
                "status": p.status.value,
                "tax_base": float(p.tax_base),
                "tax_amount": float(p.tax_amount),
                "amount_paid": float(p.amount_paid),
                "outstanding": float(p.outstanding_amount),
                "is_overdue": p.is_overdue,
            }
            for p in periods
        ],
    }


@router.post("/tax/filing-periods", dependencies=[Depends(Require("books:admin"))])
async def create_tax_filing_period(
    tax_type: str = Query(..., description="Tax type: vat, wht, cit, paye, other"),
    period_name: str = Query(..., description="Period name (e.g., 2024-Q1, 2024-01)"),
    period_start: str = Query(..., description="Period start date (YYYY-MM-DD)"),
    period_end: str = Query(..., description="Period end date (YYYY-MM-DD)"),
    due_date: str = Query(..., description="Filing due date (YYYY-MM-DD)"),
    tax_base: float = Query(0, description="Tax base amount"),
    tax_amount: float = Query(0, description="Tax amount due"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new tax filing period."""
    from app.models.tax import TaxFilingPeriod, TaxFilingType
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        tax_type_enum = TaxFilingType(tax_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tax type: {tax_type}")

    period = TaxFilingPeriod(
        tax_type=tax_type_enum,
        period_name=period_name,
        period_start=_parse_date(period_start, "period_start"),
        period_end=_parse_date(period_end, "period_end"),
        due_date=_parse_date(due_date, "due_date"),
        tax_base=Decimal(str(tax_base)),
        tax_amount=Decimal(str(tax_amount)),
        created_by_id=user.id,
    )
    db.add(period)
    db.flush()

    audit = AuditLogger(db)
    audit.log_create(
        doctype="tax_filing_period",
        document_id=period.id,
        user_id=user.id,
        document_name=f"{tax_type} {period_name}",
        new_values=serialize_for_audit(period),
    )
    db.commit()

    return {
        "message": "Tax filing period created",
        "id": period.id,
        "tax_type": period.tax_type.value,
        "period_name": period.period_name,
        "due_date": period.due_date.isoformat(),
    }


@router.get("/tax/filing-periods/{period_id}", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_filing_period(
    period_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax filing period details with payments."""
    from app.models.tax import TaxFilingPeriod, TaxPayment

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    payments = db.query(TaxPayment).filter(
        TaxPayment.filing_period_id == period_id
    ).order_by(TaxPayment.payment_date.desc()).all()

    return {
        "id": period.id,
        "tax_type": period.tax_type.value,
        "period_name": period.period_name,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "due_date": period.due_date.isoformat(),
        "status": period.status.value,
        "tax_base": float(period.tax_base),
        "tax_amount": float(period.tax_amount),
        "amount_paid": float(period.amount_paid),
        "outstanding": float(period.outstanding_amount),
        "is_overdue": period.is_overdue,
        "filed_at": period.filed_at.isoformat() if period.filed_at else None,
        "filing_reference": period.filing_reference,
        "payments": [
            {
                "id": p.id,
                "payment_date": p.payment_date.isoformat(),
                "amount": float(p.amount),
                "payment_reference": p.payment_reference,
                "payment_method": p.payment_method,
            }
            for p in payments
        ],
    }


@router.post("/tax/filing-periods/{period_id}/file", dependencies=[Depends(Require("books:write"))])
async def file_tax_period(
    period_id: int,
    filing_reference: Optional[str] = Query(None, description="Filing reference number"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Mark a tax filing period as filed."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus
    from app.services.audit_logger import AuditLogger

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    if period.status != TaxFilingStatus.OPEN:
        raise HTTPException(status_code=400, detail=f"Period is already {period.status.value}")

    old_status = period.status.value
    period.status = TaxFilingStatus.FILED
    period.filed_at = datetime.utcnow()
    period.filed_by_id = user.id
    period.filing_reference = filing_reference

    audit = AuditLogger(db)
    audit.log(
        doctype="tax_filing_period",
        document_id=period.id,
        action="file",
        user_id=user.id,
        document_name=f"{period.tax_type.value} {period.period_name}",
        old_values={"status": old_status},
        new_values={"status": "filed", "filing_reference": filing_reference},
    )
    db.commit()

    return {
        "message": "Tax period marked as filed",
        "id": period.id,
        "status": period.status.value,
        "filed_at": period.filed_at.isoformat(),
    }


@router.post("/tax/filing-periods/{period_id}/pay", dependencies=[Depends(Require("books:write"))])
async def record_tax_payment(
    period_id: int,
    payment_date: str = Query(..., description="Payment date (YYYY-MM-DD)"),
    amount: float = Query(..., gt=0, description="Payment amount"),
    payment_reference: Optional[str] = Query(None, description="Payment reference"),
    payment_method: Optional[str] = Query(None, description="Payment method"),
    bank_account: Optional[str] = Query(None, description="Bank account used"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Record a tax payment for a filing period."""
    from app.models.tax import TaxFilingPeriod, TaxPayment, TaxFilingStatus
    from app.services.audit_logger import AuditLogger

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    payment = TaxPayment(
        filing_period_id=period_id,
        payment_date=_parse_date(payment_date, "payment_date"),
        amount=Decimal(str(amount)),
        payment_reference=payment_reference,
        payment_method=payment_method,
        bank_account=bank_account,
        created_by_id=user.id,
    )
    db.add(payment)

    # Update period totals
    period.amount_paid += Decimal(str(amount))
    if period.amount_paid >= period.tax_amount:
        period.status = TaxFilingStatus.PAID

    audit = AuditLogger(db)
    audit.log(
        doctype="tax_payment",
        document_id=payment.id,
        action="create",
        user_id=user.id,
        document_name=f"{period.tax_type.value} {period.period_name}",
        new_values={"amount": amount, "payment_reference": payment_reference},
        remarks=f"Payment for {period.period_name}",
    )
    db.commit()

    return {
        "message": "Tax payment recorded",
        "payment_id": payment.id,
        "amount": float(payment.amount),
        "period_status": period.status.value,
        "outstanding": float(period.outstanding_amount),
    }


@router.get("/tax/dashboard", dependencies=[Depends(Require("accounting:read"))])
async def get_tax_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get tax obligations dashboard summary."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    today = date.today()

    # Get summary by tax type
    summary_by_type = {}
    for tax_type in TaxFilingType:
        open_periods = db.query(TaxFilingPeriod).filter(
            and_(
                TaxFilingPeriod.tax_type == tax_type,
                TaxFilingPeriod.status.in_([TaxFilingStatus.OPEN, TaxFilingStatus.FILED]),
            )
        ).all()

        total_outstanding = sum(p.outstanding_amount for p in open_periods)
        overdue_count = sum(1 for p in open_periods if p.is_overdue)

        if open_periods or total_outstanding > 0:
            summary_by_type[tax_type.value] = {
                "open_periods": len(open_periods),
                "total_outstanding": float(total_outstanding),
                "overdue_count": overdue_count,
            }

    # Get upcoming due dates
    upcoming = db.query(TaxFilingPeriod).filter(
        and_(
            TaxFilingPeriod.status == TaxFilingStatus.OPEN,
            TaxFilingPeriod.due_date >= today,
        )
    ).order_by(TaxFilingPeriod.due_date).limit(5).all()

    # Get overdue filings
    overdue = db.query(TaxFilingPeriod).filter(
        and_(
            TaxFilingPeriod.status == TaxFilingStatus.OPEN,
            TaxFilingPeriod.due_date < today,
        )
    ).order_by(TaxFilingPeriod.due_date).all()

    return {
        "as_of_date": today.isoformat(),
        "summary_by_type": summary_by_type,
        "total_outstanding": sum(s["total_outstanding"] for s in summary_by_type.values()),
        "total_overdue_count": sum(s["overdue_count"] for s in summary_by_type.values()),
        "upcoming_due": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "outstanding": float(p.outstanding_amount),
            }
            for p in upcoming
        ],
        "overdue": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "days_overdue": (today - p.due_date).days,
                "outstanding": float(p.outstanding_amount),
            }
            for p in overdue
        ],
    }


# ============= CUSTOMER CREDIT MANAGEMENT =============

@router.get("/customers/{customer_id}/credit-status", dependencies=[Depends(Require("books:read"))])
async def get_customer_credit_status(
    customer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer credit limit, usage, and hold status."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Calculate credit used (unpaid invoices)
    unpaid_invoices = db.query(Invoice).filter(
        and_(
            Invoice.customer_id == customer_id,
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            Invoice.is_deleted == False,
        )
    ).all()

    credit_used = sum(float(inv.balance or inv.total_amount - inv.amount_paid) for inv in unpaid_invoices)
    credit_limit = float(customer.credit_limit) if customer.credit_limit else None
    credit_available = (credit_limit - credit_used) if credit_limit else None

    # Count overdue invoices
    overdue_invoices = [inv for inv in unpaid_invoices if inv.is_overdue]
    overdue_amount = sum(float(inv.balance or inv.total_amount - inv.amount_paid) for inv in overdue_invoices)

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "credit_limit": credit_limit,
        "credit_used": credit_used,
        "credit_available": credit_available,
        "credit_hold": customer.credit_hold,
        "credit_hold_reason": customer.credit_hold_reason,
        "credit_hold_date": customer.credit_hold_date.isoformat() if customer.credit_hold_date else None,
        "unpaid_invoice_count": len(unpaid_invoices),
        "overdue_invoice_count": len(overdue_invoices),
        "overdue_amount": overdue_amount,
        "utilization_percent": round((credit_used / credit_limit) * 100, 2) if credit_limit and credit_limit > 0 else None,
    }


@router.patch("/customers/{customer_id}/credit-limit", dependencies=[Depends(Require("books:admin"))])
async def update_customer_credit_limit(
    customer_id: int,
    credit_limit: Optional[Decimal] = Query(None, description="New credit limit (null to remove)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Set or update customer credit limit."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    old_limit = customer.credit_limit
    customer.credit_limit = credit_limit
    customer.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "old_credit_limit": float(old_limit) if old_limit else None,
        "new_credit_limit": float(credit_limit) if credit_limit else None,
    }


@router.patch("/customers/{customer_id}/credit-hold", dependencies=[Depends(Require("books:admin"))])
async def toggle_customer_credit_hold(
    customer_id: int,
    on_hold: bool = Query(..., description="Set credit hold on or off"),
    reason: Optional[str] = Query(None, description="Reason for credit hold"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Toggle customer credit hold status."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.credit_hold = on_hold
    customer.credit_hold_reason = reason if on_hold else None
    customer.credit_hold_date = datetime.now(timezone.utc) if on_hold else None
    customer.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "credit_hold": customer.credit_hold,
        "credit_hold_reason": customer.credit_hold_reason,
        "credit_hold_date": customer.credit_hold_date.isoformat() if customer.credit_hold_date else None,
    }


# ============= INVOICE WRITE-OFF AND WAIVER =============

@router.post("/invoices/{invoice_id}/write-off", dependencies=[Depends(Require("books:admin"))])
async def write_off_invoice(
    invoice_id: int,
    amount: Optional[Decimal] = Query(None, description="Amount to write off (null for full balance)"),
    reason: str = Query(..., description="Reason for write-off"),
    create_journal_entry: bool = Query(True, description="Create JE for write-off"),
    bad_debt_account: Optional[str] = Query(None, description="Bad debt expense account (account_number or account_name)"),
    company: Optional[str] = Query(None, description="Company for the write-off (falls back to invoice company if present)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Write off an invoice or portion of it."""
    invoice = db.query(Invoice).filter(
        and_(Invoice.id == invoice_id, Invoice.is_deleted == False)
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]:
        raise HTTPException(status_code=400, detail=f"Cannot write off invoice with status {invoice.status.value}")

    outstanding = float(invoice.balance or (invoice.total_amount - invoice.amount_paid))
    write_off_amount = float(amount) if amount else outstanding

    if write_off_amount > outstanding:
        raise HTTPException(status_code=400, detail=f"Write-off amount ({write_off_amount}) exceeds outstanding balance ({outstanding})")

    # Create journal entry if requested
    je_id = None
    if create_journal_entry:
        from app.services.je_validator import JEValidator, ValidationError
        from app.services.audit_logger import AuditLogger, serialize_for_audit

        # Resolve company
        target_company = company or invoice.company
        if not target_company:
            raise HTTPException(status_code=400, detail="Company is required for write-off")

        # Resolve AR account for company
        ar_account = (
            db.query(Account)
            .filter(
                Account.account_type == AccountType.RECEIVABLE,
                Account.company == target_company,
            )
            .first()
        )
        if not ar_account:
            raise HTTPException(status_code=400, detail="Receivable account not found for company")

        # Resolve bad debt account
        bad_debt_acct = None
        if bad_debt_account:
            bad_debt_acct = (
                db.query(Account)
                .filter(
                    or_(Account.account_number == bad_debt_account, Account.account_name == bad_debt_account),
                    Account.company == target_company,
                )
                .first()
            )
        if not bad_debt_acct:
            bad_debt_acct = (
                db.query(Account)
                .filter(
                    Account.company == target_company,
                    or_(
                        Account.account_name.ilike("%bad debt%"),
                        Account.account_name.ilike("%write-off%"),
                    ),
                )
                .first()
            )
        if not bad_debt_acct:
            raise HTTPException(status_code=400, detail="Bad debt account not found")

        posting_dt = date.today()

        # Build JE accounts
        je_accounts = [
            # Debit bad debt expense
            {
                "account": bad_debt_acct.account_number or bad_debt_acct.account_name,
                "debit": Decimal(str(write_off_amount)),
                "credit": Decimal("0"),
                "party_type": None,
                "party": None,
            },
            # Credit AR
            {
                "account": ar_account.account_number or ar_account.account_name,
                "debit": Decimal("0"),
                "credit": Decimal(str(write_off_amount)),
                "party_type": "Customer",
                "party": invoice.customer.name if invoice.customer else None,
            },
        ]

        # Validate JE
        validator = JEValidator(db)
        try:
            validator.validate_or_raise(
                JournalEntry(
                    voucher_type=JournalEntryType.JOURNAL_ENTRY,
                    posting_date=posting_dt,
                    company=target_company,
                    user_remark=reason,
                ),
                [
                    JournalEntryAccount(
                        account=line["account"],
                        debit=line["debit"],
                        credit=line["credit"],
                        party_type=line["party_type"],
                        party=line["party"],
                    )
                    for line in je_accounts
                ],
            )
        except ValidationError as e:
            raise HTTPException(status_code=400, detail={"errors": e.errors})

        # Create JE
        je = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=posting_dt,
            company=target_company,
            title=f"Write-off Invoice {invoice.invoice_number}",
            user_remark=reason,
            total_debit=Decimal(str(write_off_amount)),
            total_credit=Decimal(str(write_off_amount)),
            docstatus=1,
        )
        db.add(je)
        db.flush()

        # Add JE accounts
        for idx, line in enumerate(je_accounts, 1):
            db.add(
                JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=line["account"],
                    debit=line["debit"],
                    credit=line["credit"],
                    party_type=line["party_type"],
                    party=line["party"],
                    idx=idx,
                )
            )

        # Add GL entries
        db.add(
            GLEntry(
                posting_date=posting_dt,
                account=bad_debt_acct.account_number or bad_debt_acct.account_name,
                debit=Decimal(str(write_off_amount)),
                credit=Decimal("0"),
                voucher_type="Journal Entry",
                voucher_no=str(je.id),
                journal_entry_id=je.id,
            )
        )
        db.add(
            GLEntry(
                posting_date=posting_dt,
                account=ar_account.account_number or ar_account.account_name,
                debit=Decimal("0"),
                credit=Decimal(str(write_off_amount)),
                voucher_type="Journal Entry",
                voucher_no=str(je.id),
                party_type="Customer",
                party=invoice.customer.name if invoice.customer else None,
                journal_entry_id=je.id,
            )
        )

        # Audit log
        audit = AuditLogger(db)
        audit.log_create(
            doctype="journal_entry",
            document_id=je.id,
            user_id=None,
            new_values=serialize_for_audit(je),
            remarks=f"Write-off Invoice {invoice.invoice_number}",
        )

        je_id = je.id

    # Update invoice
    invoice.written_off_amount = Decimal(str(write_off_amount))
    invoice.written_off_at = datetime.now(timezone.utc)
    invoice.write_off_reason = reason
    invoice.write_off_journal_entry_id = je_id

    # Update status if fully written off
    if write_off_amount >= outstanding:
        invoice.status = InvoiceStatus.WRITTEN_OFF
        invoice.balance = Decimal("0")
    else:
        invoice.balance = Decimal(str(outstanding - write_off_amount))

    db.commit()

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "written_off_amount": write_off_amount,
        "remaining_balance": float(invoice.balance) if invoice.balance else 0,
        "status": invoice.status.value,
        "reason": reason,
        "journal_entry_id": je_id,
    }


@router.post("/invoices/{invoice_id}/waive", dependencies=[Depends(Require("books:write"))])
async def waive_invoice_amount(
    invoice_id: int,
    amount: Decimal = Query(..., description="Amount to waive"),
    reason: str = Query(..., description="Reason for waiver"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Waive a portion of an invoice (discount/adjustment without write-off)."""
    invoice = db.query(Invoice).filter(
        and_(Invoice.id == invoice_id, Invoice.is_deleted == False)
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]:
        raise HTTPException(status_code=400, detail=f"Cannot waive amount on invoice with status {invoice.status.value}")

    outstanding = float(invoice.balance or (invoice.total_amount - invoice.amount_paid))
    waive_amount = float(amount)

    if waive_amount > outstanding:
        raise HTTPException(status_code=400, detail=f"Waive amount ({waive_amount}) exceeds outstanding balance ({outstanding})")

    # Block waiver without accounting entry
    raise HTTPException(
        status_code=400,
        detail="Waiver without accounting entry is not supported. Use a credit note or write-off with JE.",
    )

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "waived_amount": waive_amount,
        "total_waived": float(invoice.waived_amount),
        "remaining_balance": float(invoice.balance) if invoice.balance else 0,
        "status": invoice.status.value,
        "reason": reason,
    }


# ============= DUNNING =============

@router.get("/invoices/{invoice_id}/dunning-history", dependencies=[Depends(Require("books:read"))])
async def get_invoice_dunning_history(
    invoice_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get dunning/collection history for an invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    history = db.query(DunningHistory).filter(
        DunningHistory.invoice_id == invoice_id
    ).order_by(DunningHistory.sent_at.desc()).all()

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "current_dunning_level": invoice.dunning_level,
        "last_dunning_date": invoice.last_dunning_date.isoformat() if invoice.last_dunning_date else None,
        "history": [
            {
                "id": h.id,
                "dunning_level": h.dunning_level.value,
                "subject": h.subject,
                "message": h.message[:200] + "..." if h.message and len(h.message) > 200 else h.message,
                "delivery_method": h.delivery_method,
                "recipient_email": h.recipient_email,
                "sent_at": h.sent_at.isoformat(),
                "is_auto_sent": h.is_auto_sent,
                "amount_due": float(h.amount_due),
                "days_overdue": h.days_overdue,
                "opened_at": h.opened_at.isoformat() if h.opened_at else None,
                "responded_at": h.responded_at.isoformat() if h.responded_at else None,
            }
            for h in history
        ],
    }


@router.post("/dunning/send", dependencies=[Depends(Require("books:write"))])
async def send_dunning_notices(
    invoice_ids: List[int] = Query(None, description="Specific invoice IDs (null for all overdue)"),
    dunning_level: str = Query("reminder", description="Level: reminder, warning, final_notice, collection"),
    delivery_method: str = Query("email", description="email, sms, or letter"),
    custom_message: Optional[str] = Query(None, description="Custom message to include"),
    auto_escalate: bool = Query(False, description="Auto-escalate to next level if already dunned at this level"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send dunning notices to customers with overdue invoices."""
    # Validate dunning level
    try:
        level = DunningLevel(dunning_level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid dunning level: {dunning_level}")

    level_order = {
        DunningLevel.REMINDER: 1,
        DunningLevel.WARNING: 2,
        DunningLevel.FINAL_NOTICE: 3,
        DunningLevel.COLLECTION: 4,
    }

    # Get invoices to dun
    query = db.query(Invoice).filter(
        and_(
            Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.is_deleted == False,
        )
    )

    if invoice_ids:
        query = query.filter(Invoice.id.in_(invoice_ids))
    else:
        # Only get overdue invoices
        query = query.filter(Invoice.due_date < date.today())

    invoices = query.all()

    results = {
        "sent": [],
        "skipped": [],
        "errors": [],
    }

    for invoice in invoices:
        try:
            # Skip customers on credit hold
            if invoice.customer and invoice.customer.credit_hold:
                results["skipped"].append(
                    {
                        "invoice_id": invoice.id,
                        "reason": "Customer on credit hold",
                    }
                )
                continue

            # Determine effective level
            effective_level = level
            if auto_escalate and invoice.dunning_level >= level_order.get(level, 1):
                # Escalate to next level
                current_order = invoice.dunning_level
                if current_order < 4:
                    for lvl, order in level_order.items():
                        if order == current_order + 1:
                            effective_level = lvl
                            break

            # Check if already dunned at this level recently (within 7 days)
            recent_dunning = db.query(DunningHistory).filter(
                and_(
                    DunningHistory.invoice_id == invoice.id,
                    DunningHistory.dunning_level == effective_level,
                    DunningHistory.sent_at > datetime.now(timezone.utc) - timedelta(days=7),
                )
            ).first()

            if recent_dunning and not auto_escalate:
                results["skipped"].append({
                    "invoice_id": invoice.id,
                    "reason": f"Already dunned at {effective_level.value} within 7 days",
                })
                continue

            # Get customer email
            customer = invoice.customer
            recipient_email = customer.billing_email or customer.email if customer else None
            recipient_phone = customer.phone if customer else None

            if delivery_method == "email" and not recipient_email:
                results["skipped"].append({
                    "invoice_id": invoice.id,
                    "reason": "No email address available",
                })
                continue

            # Calculate amounts
            outstanding = float(invoice.balance or (invoice.total_amount - invoice.amount_paid))
            days_overdue = invoice.days_overdue

            # Create dunning record
            subject_templates = {
                DunningLevel.REMINDER: f"Payment Reminder - Invoice {invoice.invoice_number}",
                DunningLevel.WARNING: f"Payment Warning - Invoice {invoice.invoice_number} Overdue",
                DunningLevel.FINAL_NOTICE: f"FINAL NOTICE - Invoice {invoice.invoice_number}",
                DunningLevel.COLLECTION: f"Collection Notice - Invoice {invoice.invoice_number}",
            }

            dunning = DunningHistory(
                invoice_id=invoice.id,
                customer_id=customer.id if customer else 0,
                dunning_level=effective_level,
                subject=subject_templates.get(effective_level, "Payment Notice"),
                message=custom_message,
                delivery_method=delivery_method,
                recipient_email=recipient_email,
                recipient_phone=recipient_phone,
                amount_due=Decimal(str(outstanding)),
                days_overdue=days_overdue,
                is_auto_sent=False,
            )
            db.add(dunning)

            # Update invoice dunning tracking
            invoice.last_dunning_date = datetime.now(timezone.utc)
            invoice.dunning_level = level_order.get(effective_level, 1)

            results["sent"].append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_name": customer.name if customer else "Unknown",
                "dunning_level": effective_level.value,
                "delivery_method": delivery_method,
                "recipient": recipient_email or recipient_phone,
                "amount_due": outstanding,
                "days_overdue": days_overdue,
            })

        except Exception as e:
            results["errors"].append({
                "invoice_id": invoice.id,
                "error": str(e),
            })

    db.commit()

    return {
        "summary": {
            "total_processed": len(invoices),
            "sent_count": len(results["sent"]),
            "skipped_count": len(results["skipped"]),
            "error_count": len(results["errors"]),
        },
        "sent": results["sent"],
        "skipped": results["skipped"],
        "errors": results["errors"],
    }


@router.get("/dunning/queue", dependencies=[Depends(Require("books:read"))])
async def get_dunning_queue(
    min_days_overdue: int = Query(1, description="Minimum days overdue"),
    max_days_overdue: Optional[int] = Query(None, description="Maximum days overdue"),
    min_amount: Optional[Decimal] = Query(None, description="Minimum amount due"),
    dunning_level: Optional[int] = Query(None, description="Filter by current dunning level (0-4)"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get queue of invoices ready for dunning."""
    today = date.today()
    cutoff_date = today - timedelta(days=min_days_overdue)

    query = db.query(Invoice).filter(
        and_(
            Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.is_deleted == False,
            Invoice.due_date < cutoff_date,
        )
    )

    if max_days_overdue:
        max_cutoff = today - timedelta(days=max_days_overdue)
        query = query.filter(Invoice.due_date >= max_cutoff)

    if dunning_level is not None:
        query = query.filter(Invoice.dunning_level == dunning_level)

    # Get total count
    total = query.count()

    # Get paginated results
    invoices = query.order_by(Invoice.due_date.asc()).offset(offset).limit(limit).all()

    # Filter by amount if specified
    items = []
    for inv in invoices:
        outstanding = float(inv.balance or (inv.total_amount - inv.amount_paid))
        if min_amount and outstanding < float(min_amount):
            continue

        items.append({
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer.name if inv.customer else "Unknown",
            "customer_email": inv.customer.billing_email or inv.customer.email if inv.customer else None,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "days_overdue": inv.days_overdue,
            "amount_due": outstanding,
            "currency": inv.currency,
            "current_dunning_level": inv.dunning_level,
            "last_dunning_date": inv.last_dunning_date.isoformat() if inv.last_dunning_date else None,
        })

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/receivables-aging-enhanced", dependencies=[Depends(Require("accounting:read"))])
async def get_enhanced_receivables_aging(
    as_of_date: Optional[str] = None,
    include_expected_date: bool = Query(False, description="Include expected payment dates"),
    include_notes: bool = Query(False, description="Include payment notes"),
    include_dunning: bool = Query(True, description="Include dunning status"),
    group_by: str = Query("customer", description="Group by: customer, invoice, or aging_bucket"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Enhanced receivables aging report with additional AR operations data."""
    as_of = _parse_date(as_of_date, "as_of_date") or date.today()

    # Get unpaid invoices
    query = db.query(Invoice).options(joinedload(Invoice.customer)).filter(
        and_(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            Invoice.is_deleted == False,
            Invoice.invoice_date <= as_of,
        )
    )

    if currency:
        query = query.filter(Invoice.currency == currency)

    invoices = query.all()

    # Define aging buckets
    buckets = {
        "current": {"min": 0, "max": 0, "total": Decimal("0"), "count": 0, "items": []},
        "1_30": {"min": 1, "max": 30, "total": Decimal("0"), "count": 0, "items": []},
        "31_60": {"min": 31, "max": 60, "total": Decimal("0"), "count": 0, "items": []},
        "61_90": {"min": 61, "max": 90, "total": Decimal("0"), "count": 0, "items": []},
        "over_90": {"min": 91, "max": 999999, "total": Decimal("0"), "count": 0, "items": []},
    }

    by_customer = {}
    grand_total = Decimal("0")

    for inv in invoices:
        outstanding = inv.balance or (inv.total_amount - inv.amount_paid)
        if outstanding <= 0:
            continue

        # Calculate days overdue
        if inv.due_date:
            days = (as_of - inv.due_date.date() if hasattr(inv.due_date, 'date') else as_of - inv.due_date).days
        else:
            days = 0

        # Determine bucket
        if days <= 0:
            bucket_key = "current"
        elif days <= 30:
            bucket_key = "1_30"
        elif days <= 60:
            bucket_key = "31_60"
        elif days <= 90:
            bucket_key = "61_90"
        else:
            bucket_key = "over_90"

        item = {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer.name if inv.customer else "Unknown",
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "days_overdue": max(0, days),
            "amount_due": float(outstanding),
            "currency": inv.currency,
        }

        if include_dunning:
            item["dunning_level"] = inv.dunning_level
            item["last_dunning_date"] = inv.last_dunning_date.isoformat() if inv.last_dunning_date else None

        if include_notes:
            item["write_off_reason"] = inv.write_off_reason
            item["waiver_reason"] = inv.waiver_reason

        buckets[bucket_key]["total"] += outstanding
        buckets[bucket_key]["count"] += 1
        buckets[bucket_key]["items"].append(item)

        # Group by customer
        customer_id = inv.customer_id or 0
        if customer_id not in by_customer:
            by_customer[customer_id] = {
                "customer_id": customer_id,
                "customer_name": inv.customer.name if inv.customer else "Unknown",
                "credit_limit": float(inv.customer.credit_limit) if inv.customer and inv.customer.credit_limit else None,
                "credit_hold": inv.customer.credit_hold if inv.customer else False,
                "total_outstanding": Decimal("0"),
                "invoices": [],
                "buckets": {k: Decimal("0") for k in buckets.keys()},
            }
        by_customer[customer_id]["total_outstanding"] += outstanding
        by_customer[customer_id]["buckets"][bucket_key] += outstanding
        by_customer[customer_id]["invoices"].append(item)

        grand_total += outstanding

    # Format response based on group_by
    if group_by == "aging_bucket":
        result_data = {
            k: {
                "range": f"{v['min']}-{v['max']} days" if k != "over_90" else "90+ days",
                "total": float(v["total"]),
                "count": v["count"],
                "percent_of_total": round(float(v["total"]) / float(grand_total) * 100, 2) if grand_total > 0 else 0,
                "items": v["items"][:50],  # Limit items per bucket
            }
            for k, v in buckets.items()
        }
    elif group_by == "customer":
        result_data = [
            {
                **{k: v for k, v in cust.items() if k != "buckets"},
                "total_outstanding": float(cust["total_outstanding"]),
                "aging": {k: float(v) for k, v in cust["buckets"].items()},
            }
            for cust in sorted(by_customer.values(), key=lambda x: x["total_outstanding"], reverse=True)
        ]
    else:  # invoice
        all_items = []
        for bucket in buckets.values():
            all_items.extend(bucket["items"])
        result_data = sorted(all_items, key=lambda x: x["days_overdue"], reverse=True)

    return {
        "as_of_date": as_of.isoformat(),
        "group_by": group_by,
        "summary": {
            "grand_total": float(grand_total),
            "total_invoices": sum(b["count"] for b in buckets.values()),
            "buckets": {
                k: {
                    "total": float(v["total"]),
                    "count": v["count"],
                    "percent": round(float(v["total"]) / float(grand_total) * 100, 2) if grand_total > 0 else 0,
                }
                for k, v in buckets.items()
            },
        },
        "data": result_data,
    }

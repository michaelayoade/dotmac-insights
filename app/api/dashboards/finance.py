"""
Finance Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.api.dashboards.common import resolve_currency_or_raise, parse_date_param

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription
from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier, GLEntry, Account, AccountType, BankAccount, FiscalYear
from app.models.customer import Customer
from app.models.expense_management import ExpenseClaim, ExpenseClaimStatus, CashAdvance, CashAdvanceStatus

router = APIRouter(tags=["dashboards"])

# =============================================================================
# ACCOUNTING DASHBOARD - Consolidated (11 calls → 1)
# =============================================================================

@router.get("/accounting", dependencies=[Depends(Require("accounting:read"))])
@cached("dashboard-accounting", ttl=CACHE_TTL["short"])
async def get_accounting_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Accounting Dashboard endpoint.

    Combines data from:
    - Main dashboard (assets, liabilities, equity, net income)
    - Balance sheet
    - Income statement
    - Suppliers count
    - Bank accounts
    - General ledger count
    - Receivables
    - Fiscal years
    - Receivables outstanding (top 5)
    - Payables outstanding (top 5)
    - Cash flow
    """
    now = datetime.now(timezone.utc)
    today = date.today()
    currency = currency or "NGN"

    # Get current fiscal year
    fiscal_year = db.query(FiscalYear).filter(
        FiscalYear.year_start_date <= today,
        FiscalYear.year_end_date >= today,
    ).first()

    fy_start = (
        fiscal_year.year_start_date if fiscal_year and fiscal_year.year_start_date else date(today.year, 1, 1)
    )
    fy_end = (
        fiscal_year.year_end_date if fiscal_year and fiscal_year.year_end_date else date(today.year, 12, 31)
    )

    # =========== BALANCE SHEET SUMMARY ===========
    # Assets
    asset_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.ASSET,
        Account.disabled == False,
    ).all()
    asset_ids = [a[0] for a in asset_accounts]

    total_assets = 0.0
    if asset_ids:
        assets_sum = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(asset_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_assets = float(assets_sum or 0)

    # Liabilities
    liability_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.LIABILITY,
        Account.disabled == False,
    ).all()
    liability_ids = [a[0] for a in liability_accounts]

    total_liabilities = 0.0
    if liability_ids:
        liab_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(liability_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_liabilities = float(liab_sum or 0)

    # Equity
    equity_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EQUITY,
        Account.disabled == False,
    ).all()
    equity_ids = [a[0] for a in equity_accounts]

    total_equity = 0.0
    if equity_ids:
        equity_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(equity_ids),
            GLEntry.is_cancelled == False,
        ).scalar()
        total_equity = float(equity_sum or 0)

    # =========== INCOME STATEMENT (YTD) ===========
    # Income
    income_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.INCOME,
        Account.disabled == False,
    ).all()
    income_ids = [a[0] for a in income_accounts]

    total_income = 0.0
    if income_ids:
        income_sum = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(income_ids),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= fy_start,
            GLEntry.posting_date <= today,
        ).scalar()
        total_income = float(income_sum or 0)

    # Expenses
    expense_accounts = db.query(Account.erpnext_id).filter(
        Account.root_type == AccountType.EXPENSE,
        Account.disabled == False,
    ).all()
    expense_ids = [a[0] for a in expense_accounts]

    total_expenses = 0.0
    if expense_ids:
        expense_sum = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(expense_ids),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= fy_start,
            GLEntry.posting_date <= today,
        ).scalar()
        total_expenses = float(expense_sum or 0)

    net_income = total_income - total_expenses

    # =========== BANK ACCOUNTS ===========
    # Fetch all active bank accounts
    bank_accounts_list = db.query(BankAccount).filter(
        BankAccount.disabled == False,
    ).all()

    # Batch query: get all bank balances in a single query (fixes N+1)
    bank_account_names = [ba.account for ba in bank_accounts_list if ba.account]
    balance_map: Dict[str, float] = {}
    if bank_account_names:
        balance_results = db.query(
            GLEntry.account,
            func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0).label("balance")
        ).filter(
            GLEntry.account.in_(bank_account_names),
            GLEntry.is_cancelled == False,
        ).group_by(GLEntry.account).all()
        balance_map = {account: float(balance) for account, balance in balance_results}

    bank_accounts = []
    for ba in bank_accounts_list[:5]:
        account_key = ba.account or ""
        bank_accounts.append(
            {
                "id": ba.id,
                "account_name": ba.account_name,
                "bank_name": ba.bank,
                "account_number": ba.bank_account_no[-4:] if ba.bank_account_no and len(ba.bank_account_no) >= 4 else "****",
                "balance": balance_map.get(account_key, 0.0),
                "currency": ba.currency,
            }
        )

    total_cash = sum(
        balance_map.get(ba.account or "", 0.0)
        for ba in bank_accounts_list
    )

    # =========== COUNTS ===========
    supplier_count = db.query(func.count(Supplier.id)).filter(
        Supplier.disabled == False
    ).scalar() or 0

    gl_entries_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= fy_start,
    ).scalar() or 0

    # =========== RECEIVABLES ===========
    total_receivable_query = db.query(
        func.sum(Invoice.total_amount - Invoice.amount_paid)
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
    )
    if currency:
        total_receivable_query = total_receivable_query.filter(Invoice.currency == currency)
    total_receivable = float(total_receivable_query.scalar() or 0)

    # =========== PAYABLES ===========
    total_payable_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
    )
    if currency:
        total_payable_query = total_payable_query.filter(PurchaseInvoice.currency == currency)
    total_payable = float(total_payable_query.scalar() or 0)

    # =========== TOP RECEIVABLES (5) ===========
    top_receivables = [
        {
            "customer_name": r.customer_name,
            "outstanding": float(r.outstanding),
            "invoice_count": r.count,
        }
        for r in db.query(
            Customer.name.label("customer_name"),
            func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
            func.count(Invoice.id).label("count"),
        ).join(Customer, Invoice.customer_id == Customer.id).filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
            *([Invoice.currency == currency] if currency else []),
        ).group_by(Customer.name).order_by(
            func.sum(Invoice.total_amount - Invoice.amount_paid).desc()
        ).limit(5).all()
    ]

    # =========== TOP PAYABLES (5) ===========
    top_payables = [
        {
            "supplier_name": r.supplier_name,
            "outstanding": float(r.outstanding),
            "bill_count": r.count,
        }
        for r in db.query(
            PurchaseInvoice.supplier_name,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.count(PurchaseInvoice.id).label("count"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            *([PurchaseInvoice.currency == currency] if currency else []),
        ).group_by(PurchaseInvoice.supplier_name).order_by(
            func.sum(PurchaseInvoice.outstanding_amount).desc()
        ).limit(5).all()
    ]

    # =========== FISCAL YEARS ===========
    fiscal_years = [
        {
            "id": fy.id,
            "name": fy.year,
            "start_date": fy.year_start_date.isoformat() if fy.year_start_date else None,
            "end_date": fy.year_end_date.isoformat() if fy.year_end_date else None,
            "is_closed": fy.disabled,
        }
        for fy in db.query(FiscalYear).order_by(FiscalYear.year_start_date.desc()).limit(5).all()
    ]

    # =========== FINANCIAL RATIOS ===========
    current_ratio = round(total_assets / total_liabilities, 2) if total_liabilities > 0 else 0
    debt_to_equity = round(total_liabilities / total_equity, 2) if total_equity > 0 else 0
    profit_margin = round(net_income / total_income * 100, 1) if total_income > 0 else 0

    return {
        "currency": currency,
        "generated_at": now.isoformat(),
        "fiscal_year": {
            "start": fy_start.isoformat(),
            "end": fy_end.isoformat(),
        },

        "balance_sheet": {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "net_worth": total_assets - total_liabilities,
        },

        "income_statement": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_income": net_income,
        },

        "cash": {
            "total": total_cash,
            "bank_accounts": bank_accounts,
        },

        "receivables": {
            "total": total_receivable,
            "top_customers": top_receivables,
        },

        "payables": {
            "total": total_payable,
            "top_suppliers": top_payables,
        },

        "ratios": {
            "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity,
            "profit_margin": profit_margin,
        },

        "counts": {
            "suppliers": supplier_count,
            "gl_entries": gl_entries_count,
        },

        "fiscal_years": fiscal_years,
    }


# =============================================================================
# EXPENSES DASHBOARD - Consolidated (2 calls → 1)
# =============================================================================

@router.get("/expenses", dependencies=[Depends(Require("expenses:read"))])
@cached("dashboard-expenses", ttl=CACHE_TTL["short"])
async def get_expenses_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Expenses Dashboard endpoint.

    Combines data from:
    - Expense claims summary (by status, totals)
    - Cash advances summary (by status, outstanding)
    - Recent claims and advances
    - Trend data
    """
    from app.models.expense_management import (
        ExpenseClaim, ExpenseClaimStatus,
        CashAdvance, CashAdvanceStatus
    )

    now = datetime.now(timezone.utc)
    today = date.today()
    six_months_ago = now - timedelta(days=180)

    # =========== EXPENSE CLAIMS ===========
    claims_by_status = db.query(
        ExpenseClaim.status,
        func.count(ExpenseClaim.id).label("status_count"),
        func.sum(ExpenseClaim.total_claimed_amount).label("status_total")
    ).group_by(ExpenseClaim.status).all()

    claims_status_map: Dict[str, Dict[str, float | int]] = {}
    for row in claims_by_status:
        status_key = row.status.value if row.status else "unknown"
        claims_status_map[status_key] = {
            "count": int(row.status_count or 0),
            "total": float(row.status_total or 0),
        }

    total_claims = sum(value["count"] for value in claims_status_map.values())
    total_claimed_amount = sum(value["total"] for value in claims_status_map.values())

    pending_claim_approvals = db.query(func.count(ExpenseClaim.id)).filter(
        ExpenseClaim.status == ExpenseClaimStatus.PENDING_APPROVAL
    ).scalar() or 0
    pending_advance_approvals = db.query(func.count(CashAdvance.id)).filter(
        CashAdvance.status == CashAdvanceStatus.PENDING_APPROVAL
    ).scalar() or 0
    pending_approvals = pending_claim_approvals + pending_advance_approvals

    # Recent claims
    recent_claims = [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "title": c.title,
            "total_claimed_amount": float(c.total_claimed_amount or 0),
            "status": c.status.value if c.status else None,
            "claim_date": c.claim_date.isoformat() if c.claim_date else None,
        }
        for c in db.query(ExpenseClaim).order_by(
            ExpenseClaim.claim_date.desc()
        ).limit(5).all()
    ]

    # =========== CASH ADVANCES ===========
    advances_by_status = db.query(
        CashAdvance.status,
        func.count(CashAdvance.id).label("status_count"),
        func.sum(CashAdvance.outstanding_amount).label("status_outstanding")
    ).group_by(CashAdvance.status).all()

    advances_status_map: Dict[str, Dict[str, float | int]] = {}
    for advance_row in advances_by_status:
        status_key = advance_row.status.value if advance_row.status else "unknown"
        advances_status_map[status_key] = {
            "count": int(advance_row.status_count or 0),
            "outstanding": float(advance_row.status_outstanding or 0),
        }

    total_advances = sum(value["count"] for value in advances_status_map.values())
    total_outstanding = sum(value["outstanding"] for value in advances_status_map.values())

    # Recent advances
    recent_advances = [
        {
            "id": a.id,
            "advance_number": a.advance_number,
            "purpose": a.purpose,
            "requested_amount": float(a.requested_amount or 0),
            "outstanding_amount": float(a.outstanding_amount or 0),
            "status": a.status.value if a.status else None,
            "request_date": a.request_date.isoformat() if a.request_date else None,
        }
        for a in db.query(CashAdvance).order_by(
            CashAdvance.request_date.desc()
        ).limit(5).all()
    ]

    # =========== TREND (6 months) ===========
    trunc_month = func.date_trunc("month", ExpenseClaim.claim_date)
    claims_trend = [
        {
            "month": r.period,
            "claims": r.count,
            "amount": float(r.total or 0)
        }
        for r in db.query(
            func.to_char(trunc_month, "YYYY-MM").label("period"),
            func.count(ExpenseClaim.id).label("count"),
            func.sum(ExpenseClaim.total_claimed_amount).label("total")
        ).filter(
            ExpenseClaim.claim_date >= six_months_ago
        ).group_by(trunc_month).order_by(trunc_month).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "claims": {
            "total": total_claims,
            "by_status": claims_status_map,
            "total_claimed_amount": total_claimed_amount,
            "recent": recent_claims,
        },

        "advances": {
            "total": total_advances,
            "by_status": advances_status_map,
            "outstanding_amount": total_outstanding,
            "recent": recent_advances,
        },

        "pending_approvals": pending_approvals,
        "trend": claims_trend,
    }


# =============================================================================
# PURCHASING DASHBOARD - Consolidated (8 calls → 1)
# =============================================================================

@router.get("/purchasing", dependencies=[Depends(Require("purchasing:read"))])
@cached("dashboard-purchasing", ttl=CACHE_TTL["short"])
async def get_purchasing_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated Purchasing Dashboard endpoint.

    Combines data from:
    - Purchasing dashboard (AP metrics)
    - Suppliers count
    - Bills count
    - AP Aging analysis
    - Top suppliers by spend
    - Recent payments
    - Recent orders
    - Recent debit notes
    """
    today = date.today()
    start_dt = parse_date_param(start_date, "start_date")
    end_dt = parse_date_param(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    range_start = datetime.combine(start_dt, datetime.min.time()) if start_dt else None
    range_end = datetime.combine(end_dt, datetime.max.time()) if end_dt else None

    def apply_range_filter(query, column):
        if range_start:
            query = query.filter(column >= range_start)
        if range_end:
            query = query.filter(column <= range_end)
        return query

    # =========== MAIN DASHBOARD METRICS ===========
    overdue_cutoff = datetime.combine((end_dt or today), datetime.max.time())
    outstanding_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    if currency:
        outstanding_query = outstanding_query.filter(PurchaseInvoice.currency == currency)
    outstanding_query = apply_range_filter(outstanding_query, PurchaseInvoice.posting_date)
    total_outstanding = float(outstanding_query.scalar() or 0)

    overdue_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount)
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date < overdue_cutoff,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ])
    )
    if currency:
        overdue_query = overdue_query.filter(PurchaseInvoice.currency == currency)
    overdue_query = apply_range_filter(overdue_query, PurchaseInvoice.posting_date)
    total_overdue = float(overdue_query.scalar() or 0)
    overdue_percentage = round(total_overdue / total_outstanding * 100, 1) if total_outstanding > 0 else 0

    # Bills by status
    bills_by_status = db.query(
        PurchaseInvoice.status,
        func.count(PurchaseInvoice.id).label("count"),
        func.sum(PurchaseInvoice.grand_total).label("total"),
    )
    if currency:
        bills_by_status = bills_by_status.filter(PurchaseInvoice.currency == currency)
    bills_by_status = apply_range_filter(bills_by_status, PurchaseInvoice.posting_date)
    bills_by_status = bills_by_status.group_by(PurchaseInvoice.status).all()
    status_breakdown = {
        row.status.value if row.status else "unknown": {
            "count": row.count,
            "total": float(row.total or 0),
        }
        for row in bills_by_status
    }

    # Due this week (relative to range end if provided)
    due_base_date = end_dt or today
    week_end = due_base_date + timedelta(days=7)
    due_start = datetime.combine(due_base_date, datetime.min.time())
    due_end = datetime.combine(week_end, datetime.max.time())
    due_this_week = db.query(
        func.count(PurchaseInvoice.id),
        func.sum(PurchaseInvoice.outstanding_amount),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date >= due_start,
        PurchaseInvoice.due_date <= due_end,
    )
    if currency:
        due_this_week = due_this_week.filter(PurchaseInvoice.currency == currency)
    due_this_week = apply_range_filter(due_this_week, PurchaseInvoice.posting_date)
    due_result = due_this_week.first()
    due_this_week_data = {
        "count": int(due_result[0] or 0) if due_result else 0,
        "total": float(due_result[1] or 0) if due_result else 0,
    }

    # Supplier count
    if range_start or range_end:
        supplier_count_query = db.query(
            func.count(distinct(PurchaseInvoice.supplier_name))
        ).filter(PurchaseInvoice.supplier_name.isnot(None))
        supplier_count_query = apply_range_filter(supplier_count_query, PurchaseInvoice.posting_date)
        if currency:
            supplier_count_query = supplier_count_query.filter(PurchaseInvoice.currency == currency)
        supplier_count = supplier_count_query.scalar() or 0
    else:
        supplier_count = db.query(func.count(Supplier.id)).filter(
            Supplier.disabled == False
        ).scalar() or 0

    # Total bills count
    bills_count_query = db.query(func.count(PurchaseInvoice.id))
    if currency:
        bills_count_query = bills_count_query.filter(PurchaseInvoice.currency == currency)
    bills_count_query = apply_range_filter(bills_count_query, PurchaseInvoice.posting_date)
    total_bills = bills_count_query.scalar() or 0

    # =========== AP AGING ===========
    aging_query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )
    if currency:
        aging_query = aging_query.filter(PurchaseInvoice.currency == currency)
    aging_query = apply_range_filter(aging_query, PurchaseInvoice.posting_date)
    invoices = aging_query.all()

    aging_buckets = {
        "current": {"count": 0, "total": 0.0},
        "1_30": {"count": 0, "total": 0.0},
        "31_60": {"count": 0, "total": 0.0},
        "61_90": {"count": 0, "total": 0.0},
        "over_90": {"count": 0, "total": 0.0},
    }

    aging_base_date = end_dt or today
    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else aging_base_date)
        days = (aging_base_date - due).days if aging_base_date > due else 0

        if days <= 0:
            bucket = "current"
        elif days <= 30:
            bucket = "1_30"
        elif days <= 60:
            bucket = "31_60"
        elif days <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        aging_buckets[bucket]["count"] += 1
        aging_buckets[bucket]["total"] += float(inv.outstanding_amount or 0)

    # =========== TOP SUPPLIERS (5) ===========
    top_suppliers_query = db.query(
        PurchaseInvoice.supplier_name,
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        func.count(PurchaseInvoice.id).label("bill_count"),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
    )
    if currency:
        top_suppliers_query = top_suppliers_query.filter(PurchaseInvoice.currency == currency)
    top_suppliers_query = apply_range_filter(top_suppliers_query, PurchaseInvoice.posting_date)
    top_suppliers_query = top_suppliers_query.group_by(
        PurchaseInvoice.supplier_name
    ).order_by(
        func.sum(PurchaseInvoice.outstanding_amount).desc()
    ).limit(5)

    top_suppliers = [
        {
            "name": row.supplier_name,
            "outstanding": float(row.outstanding),
            "bill_count": row.bill_count,
        }
        for row in top_suppliers_query.all()
    ]

    # =========== RECENT BILLS (5) ===========
    recent_bills_query = db.query(PurchaseInvoice)
    if currency:
        recent_bills_query = recent_bills_query.filter(PurchaseInvoice.currency == currency)
    recent_bills_query = apply_range_filter(recent_bills_query, PurchaseInvoice.posting_date)
    recent_bills = [
        {
            "id": b.id,
            "supplier_name": b.supplier_name or b.supplier,
            "grand_total": float(b.grand_total),
            "outstanding_amount": float(b.outstanding_amount),
            "currency": b.currency,
            "status": b.status.value if b.status else None,
            "posting_date": b.posting_date.isoformat() if b.posting_date else None,
            "due_date": b.due_date.isoformat() if b.due_date else None,
        }
        for b in recent_bills_query.order_by(PurchaseInvoice.posting_date.desc()).limit(5).all()
    ]

    # =========== RECENT PAYMENTS (5) ===========
    recent_payments = [
        {
            "id": p.id,
            "supplier": p.party,
            "amount": float(p.credit - p.debit),
            "posting_date": p.posting_date.isoformat() if p.posting_date else None,
            "voucher_no": p.voucher_no,
        }
        for p in apply_range_filter(
            db.query(GLEntry).filter(
            GLEntry.voucher_type == "Payment Entry",
            GLEntry.party_type == "Supplier",
            GLEntry.is_cancelled == False,
            ),
            GLEntry.posting_date,
        ).order_by(GLEntry.posting_date.desc()).limit(5).all()
    ]

    # =========== RECENT ORDERS (5) ===========
    orders_query = db.query(
        GLEntry.voucher_no,
        GLEntry.party,
        func.min(GLEntry.posting_date).label("date"),
        func.sum(GLEntry.debit).label("total"),
    ).filter(
        GLEntry.voucher_type == "Purchase Order",
        GLEntry.is_cancelled == False,
    )
    orders_query = apply_range_filter(orders_query, GLEntry.posting_date).group_by(
        GLEntry.voucher_no, GLEntry.party
    ).order_by(
        func.min(GLEntry.posting_date).desc()
    ).limit(5)

    recent_orders = [
        {
            "order_no": o.voucher_no,
            "supplier": o.party,
            "date": o.date.isoformat() if o.date else None,
            "total": float(o.total or 0),
        }
        for o in orders_query.all()
    ]

    # =========== RECENT DEBIT NOTES (5) ===========
    debit_notes_query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.is_return == True,
    )
    if currency:
        debit_notes_query = debit_notes_query.filter(PurchaseInvoice.currency == currency)
    debit_notes_query = apply_range_filter(debit_notes_query, PurchaseInvoice.posting_date)

    recent_debit_notes = [
        {
            "id": n.id,
            "supplier": n.supplier_name or n.supplier,
            "grand_total": float(n.grand_total),
            "posting_date": n.posting_date.isoformat() if n.posting_date else None,
            "status": n.status.value if n.status else None,
        }
        for n in debit_notes_query.order_by(PurchaseInvoice.posting_date.desc()).limit(5).all()
    ]

    return {
        "currency": currency,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "summary": {
            "total_outstanding": total_outstanding,
            "total_overdue": total_overdue,
            "overdue_percentage": overdue_percentage,
            "supplier_count": supplier_count,
            "total_bills": total_bills,
            "due_this_week": due_this_week_data,
            "status_breakdown": status_breakdown,
        },

        "aging": {
            "buckets": aging_buckets,
        },

        "top_suppliers": top_suppliers,

        "recent": {
            "bills": recent_bills,
            "payments": recent_payments,
            "orders": recent_orders,
            "debit_notes": recent_debit_notes,
        },
    }

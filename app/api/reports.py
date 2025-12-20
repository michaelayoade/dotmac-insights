"""Consolidated Reports API - Revenue, Expenses, Profitability, Cash Position.

This module provides financial reporting endpoints for:
- Revenue Analytics (MRR, ARR, trends, by-customer)
- Expense Analytics (by category, by cost center, trends)
- Profitability (gross/operating/net margins, trends)
- Cash Position (liquidity, bank balances, runway)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, text, extract
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from app.database import get_db
from app.auth import Require
from app.models.accounting import (
    Account, AccountType, GLEntry, BankAccount, BankTransaction,
    BankTransactionStatus, PurchaseInvoice, JournalEntry, CostCenter,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.subscription import Subscription
from app.models.customer import Customer
from app.cache import cached, CACHE_TTL, get_redis_client

router = APIRouter(prefix="/reports", tags=["reports"])


# ============= HELPERS =============

def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse ISO date string safely."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format. Use YYYY-MM-DD")


def _get_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    months: int = 12
) -> tuple[date, date]:
    """Get date range from params or default to last N months."""
    end = _parse_date(end_date, "end_date") or date.today()
    start = _parse_date(start_date, "start_date")
    if not start:
        start = end - relativedelta(months=months)
    return start, end


def _resolve_currency(db: Session, default: str = "NGN") -> str:
    """Get default currency - can be extended to detect from data."""
    return default


# ============= CACHE METADATA =============


@router.get("/cache-metadata", dependencies=[Depends(Require("reports:read"))])
async def get_reports_cache_metadata() -> Dict[str, Any]:
    """Expose TTL metadata for cached reports endpoints."""
    cache_keys = [
        {"key": "reports-revenue-summary", "ttl_seconds": CACHE_TTL["medium"]},
        {"key": "reports-revenue-trend", "ttl_seconds": CACHE_TTL["medium"]},
        {"key": "reports-expenses-summary", "ttl_seconds": CACHE_TTL["medium"]},
        {"key": "reports-profitability-margins", "ttl_seconds": CACHE_TTL["medium"]},
        {"key": "reports-cash-position", "ttl_seconds": CACHE_TTL["short"]},
        {"key": "reports-cash-forecast", "ttl_seconds": CACHE_TTL["medium"]},
        {"key": "reports-cash-runway", "ttl_seconds": CACHE_TTL["medium"]},
    ]
    client = await get_redis_client()
    return {
        "as_of": datetime.utcnow().isoformat() + "Z",
        "presets": CACHE_TTL,
        "cache_available": client is not None,
        "keys": cache_keys,
    }


# ============= REVENUE ANALYTICS =============

@router.get(
    "/revenue/summary",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-revenue-summary", ttl=CACHE_TTL["medium"])
async def get_revenue_summary(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    currency: Optional[str] = Query(None, description="Currency filter"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revenue summary with MRR, ARR, total revenue, and growth metrics."""
    start, end = _get_date_range(start_date, end_date, months=12)
    currency = currency or _resolve_currency(db)

    # Calculate MRR from active subscriptions
    mrr_query = db.query(func.coalesce(func.sum(Subscription.price), 0)).filter(
        Subscription.status == "active",
        or_(Subscription.currency == currency, Subscription.currency.is_(None))
    )
    mrr = Decimal(str(mrr_query.scalar() or 0))
    arr = mrr * 12

    # Total revenue from payments in period
    total_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_date >= start,
        Payment.payment_date <= end,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")

    # Previous period for growth calculation
    prev_start = start - relativedelta(months=((end - start).days // 30) or 1)
    prev_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_date >= prev_start,
        Payment.payment_date < start,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")

    growth_rate = 0.0
    if prev_revenue and prev_revenue > 0:
        growth_rate = float((total_revenue - prev_revenue) / prev_revenue * 100)

    # Revenue from invoices
    invoiced_revenue = db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
        Invoice.invoice_date >= start,
        Invoice.invoice_date <= end,
        Invoice.status != InvoiceStatus.CANCELLED,
    ).scalar() or Decimal("0")

    # Outstanding AR
    outstanding_ar = db.query(func.coalesce(func.sum(Invoice.balance), 0)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
    ).scalar() or Decimal("0")

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "currency": currency,
        "mrr": float(mrr),
        "arr": float(arr),
        "total_revenue": float(total_revenue),
        "invoiced_revenue": float(invoiced_revenue),
        "outstanding_ar": float(outstanding_ar),
        "growth_rate": round(growth_rate, 2),
        "collection_rate": round(float(total_revenue / invoiced_revenue * 100), 2) if invoiced_revenue else 0,
    }


@router.get(
    "/revenue/trend",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-revenue-trend", ttl=CACHE_TTL["medium"])
async def get_revenue_trend(
    months: int = Query(default=12, le=24, description="Number of months"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    interval: str = Query(default="month", description="Aggregation: month or week"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Monthly or weekly revenue trend from payments."""
    start, end = _get_date_range(start_date, end_date, months)

    if interval == "week":
        # Weekly aggregation
        results = db.query(
            func.date_trunc("week", Payment.payment_date).label("period"),
            func.sum(Payment.amount).label("revenue"),
            func.count(Payment.id).label("payment_count"),
        ).filter(
            Payment.payment_date >= start,
            Payment.payment_date <= end,
            Payment.status == PaymentStatus.COMPLETED,
        ).group_by(
            func.date_trunc("week", Payment.payment_date)
        ).order_by(text("period")).all()
    else:
        # Monthly aggregation
        results = db.query(
            func.date_trunc("month", Payment.payment_date).label("period"),
            func.sum(Payment.amount).label("revenue"),
            func.count(Payment.id).label("payment_count"),
        ).filter(
            Payment.payment_date >= start,
            Payment.payment_date <= end,
            Payment.status == PaymentStatus.COMPLETED,
        ).group_by(
            func.date_trunc("month", Payment.payment_date)
        ).order_by(text("period")).all()

    trend = []
    for row in results:
        trend.append({
            "period": row.period.isoformat() if row.period else None,
            "revenue": float(row.revenue or 0),
            "payment_count": row.payment_count,
        })

    # Calculate totals and averages
    total = sum(t["revenue"] for t in trend)
    avg = total / len(trend) if trend else 0

    return {
        "interval": interval,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "trend": trend,
        "summary": {
            "total": round(total, 2),
            "average": round(avg, 2),
            "periods": len(trend),
        }
    }


@router.get(
    "/revenue/by-customer",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_revenue_by_customer(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    top: int = Query(default=20, le=100, description="Top N customers"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revenue breakdown by top customers."""
    start, end = _get_date_range(start_date, end_date, months=12)

    results = db.query(
        Customer.id,
        Customer.name,
        Customer.customer_type,
        func.sum(Payment.amount).label("total_revenue"),
        func.count(Payment.id).label("payment_count"),
    ).join(
        Payment, Payment.customer_id == Customer.id
    ).filter(
        Payment.payment_date >= start,
        Payment.payment_date <= end,
        Payment.status == PaymentStatus.COMPLETED,
    ).group_by(
        Customer.id, Customer.name, Customer.customer_type
    ).order_by(
        func.sum(Payment.amount).desc()
    ).limit(top).all()

    total_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= start,
        Payment.payment_date <= end,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")

    customers = []
    for row in results:
        pct = float(row.total_revenue / total_revenue * 100) if total_revenue else 0
        customers.append({
            "customer_id": row.id,
            "customer_name": row.name,
            "customer_type": row.customer_type,
            "total_revenue": float(row.total_revenue or 0),
            "payment_count": row.payment_count,
            "percentage": round(pct, 2),
        })

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_revenue": float(total_revenue),
        "customers": customers,
        "concentration": {
            "top_10_pct": round(sum(c["percentage"] for c in customers[:10]), 2),
            "top_20_pct": round(sum(c["percentage"] for c in customers[:20]), 2),
        }
    }


@router.get(
    "/revenue/by-product",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_revenue_by_product(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revenue breakdown by product/service (tariff)."""
    start, end = _get_date_range(start_date, end_date, months=12)

    # MRR by tariff from subscriptions
    mrr_by_tariff = db.query(
        Subscription.tariff_id,
        Subscription.description,
        func.count(Subscription.id).label("subscriber_count"),
        func.sum(Subscription.price).label("mrr"),
    ).filter(
        Subscription.status == "active",
    ).group_by(
        Subscription.tariff_id, Subscription.description
    ).order_by(func.sum(Subscription.price).desc()).all()

    products = []
    total_mrr = sum(float(r.mrr or 0) for r in mrr_by_tariff)
    for row in mrr_by_tariff:
        mrr = float(row.mrr or 0)
        products.append({
            "tariff_id": row.tariff_id,
            "product_name": row.description or f"Tariff {row.tariff_id}",
            "subscriber_count": row.subscriber_count,
            "mrr": mrr,
            "arr": mrr * 12,
            "percentage": round(mrr / total_mrr * 100, 2) if total_mrr else 0,
        })

    return {
        "total_mrr": round(total_mrr, 2),
        "total_arr": round(total_mrr * 12, 2),
        "products": products,
    }


# ============= EXPENSE ANALYTICS =============

@router.get(
    "/expenses/summary",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-expenses-summary", ttl=CACHE_TTL["medium"])
async def get_expense_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Expense summary with totals and breakdown."""
    start, end = _get_date_range(start_date, end_date, months=12)

    # Total expenses from Expense model
    total_expenses = db.query(func.coalesce(func.sum(Expense.total_sanctioned_amount), 0)).filter(
        Expense.posting_date >= start,
        Expense.posting_date <= end,
        Expense.status != ExpenseStatus.CANCELLED,
    ).scalar() or Decimal("0")

    # Expenses from GL (expense accounts)
    gl_expenses = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.EXPENSE,
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # By category
    by_category = db.query(
        Expense.expense_type,
        func.sum(Expense.total_sanctioned_amount).label("amount"),
        func.count(Expense.id).label("count"),
    ).filter(
        Expense.posting_date >= start,
        Expense.posting_date <= end,
        Expense.status != ExpenseStatus.CANCELLED,
    ).group_by(Expense.expense_type).order_by(func.sum(Expense.total_sanctioned_amount).desc()).all()

    categories = [
        {
            "category": row.expense_type or "Uncategorized",
            "total": float(row.amount or 0),
            "count": row.count,
            "percentage": round(float(row.amount / total_expenses * 100), 2) if total_expenses else 0,
        }
        for row in by_category
    ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_expenses": float(total_expenses),
        "gl_expenses": float(gl_expenses),
        "categories": categories,
        "expense_count": sum(c["count"] for c in categories),
    }


@router.get(
    "/expenses/trend",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_expense_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    interval: str = Query(default="month"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Monthly expense trend."""
    start, end = _get_date_range(start_date, end_date, months)

    results = db.query(
        func.date_trunc(interval, Expense.posting_date).label("period"),
        func.sum(Expense.total_sanctioned_amount).label("amount"),
    ).filter(
        Expense.posting_date >= start,
        Expense.posting_date <= end,
        Expense.status != ExpenseStatus.CANCELLED,
    ).group_by(
        func.date_trunc(interval, Expense.posting_date)
    ).order_by(text("period")).all()

    return [
        {
            "period": row.period.isoformat() if row.period else None,
            "total": float(row.amount or 0),
        }
        for row in results
    ]


@router.get(
    "/expenses/by-category",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_expenses_by_category(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Detailed expense breakdown by category."""
    start, end = _get_date_range(start_date, end_date, months=12)

    results = db.query(
        Expense.expense_type,
        func.sum(Expense.total_sanctioned_amount).label("amount"),
        func.count(Expense.id).label("count"),
        func.avg(Expense.total_sanctioned_amount).label("avg_amount"),
    ).filter(
        Expense.posting_date >= start,
        Expense.posting_date <= end,
        Expense.status != ExpenseStatus.CANCELLED,
    ).group_by(Expense.expense_type).order_by(func.sum(Expense.total_sanctioned_amount).desc()).all()

    total = sum(float(r.amount or 0) for r in results)
    categories = [
        {
            "category": row.expense_type or "Uncategorized",
            "total": float(row.amount or 0),
            "percentage": round(float(row.amount / total * 100), 2) if total else 0,
        }
        for row in results
    ]

    return categories


@router.get(
    "/expenses/by-vendor",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_expenses_by_vendor(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    top: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Top vendors by expense amount."""
    start, end = _get_date_range(start_date, end_date, months=12)

    # From purchase invoices
    results = db.query(
        PurchaseInvoice.supplier,
        PurchaseInvoice.supplier_name,
        func.sum(PurchaseInvoice.grand_total).label("amount"),
        func.count(PurchaseInvoice.id).label("invoice_count"),
    ).filter(
        PurchaseInvoice.posting_date >= start,
        PurchaseInvoice.posting_date <= end,
        PurchaseInvoice.docstatus == 1,  # Submitted
    ).group_by(
        PurchaseInvoice.supplier, PurchaseInvoice.supplier_name
    ).order_by(func.sum(PurchaseInvoice.grand_total).desc()).limit(top).all()

    total = sum(float(r.amount or 0) for r in results)
    vendors = [
        {
            "vendor": row.supplier,
            "vendor_name": row.supplier_name or row.supplier,
            "total": float(row.amount or 0),
            "invoice_count": row.invoice_count,
            "percentage": round(float(row.amount / total * 100), 2) if total else 0,
        }
        for row in results
    ]

    return vendors


# ============= PROFITABILITY ANALYSIS =============

@router.get(
    "/profitability/margins",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-profitability-margins", ttl=CACHE_TTL["medium"])
async def get_profitability_margins(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Gross margin, operating margin, and net margin analysis."""
    start, end = _get_date_range(start_date, end_date, months=12)

    # Revenue from GL (Income accounts - credits)
    revenue = db.query(func.coalesce(func.sum(GLEntry.credit - GLEntry.debit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.INCOME,
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # Cost of Goods Sold (specific expense types or account types)
    cogs = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.EXPENSE,
        Account.account_type.in_(["Cost of Goods Sold", "Stock Adjustment"]),
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # Operating expenses (all expense accounts except COGS)
    operating_expenses = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.EXPENSE,
        or_(
            Account.account_type.is_(None),
            ~Account.account_type.in_(["Cost of Goods Sold", "Stock Adjustment"])
        ),
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # Calculate margins
    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    total_expenses = cogs + operating_expenses
    net_profit = revenue - total_expenses

    gross_margin = float(gross_profit / revenue * 100) if revenue else 0
    operating_margin = float(operating_profit / revenue * 100) if revenue else 0
    net_margin = float(net_profit / revenue * 100) if revenue else 0

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "revenue": float(revenue),
        "cogs": float(cogs),
        "gross_profit": float(gross_profit),
        "operating_expenses": float(operating_expenses),
        "operating_profit": float(operating_profit),
        "net_profit": float(net_profit),
        "margins": {
            "gross_margin": round(gross_margin, 2),
            "operating_margin": round(operating_margin, 2),
            "net_margin": round(net_margin, 2),
        }
    }


@router.get(
    "/profitability/trend",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_profitability_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Monthly profitability trend."""
    start, end = _get_date_range(start_date, end_date, months)

    # Get monthly revenue
    revenue_query = db.query(
        func.date_trunc("month", GLEntry.posting_date).label("period"),
        func.sum(GLEntry.credit - GLEntry.debit).label("amount"),
    ).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.INCOME,
        GLEntry.is_cancelled == False,
    ).group_by(func.date_trunc("month", GLEntry.posting_date)).all()

    # Get monthly expenses
    expense_query = db.query(
        func.date_trunc("month", GLEntry.posting_date).label("period"),
        func.sum(GLEntry.debit - GLEntry.credit).label("amount"),
    ).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        GLEntry.posting_date >= start,
        GLEntry.posting_date <= end,
        Account.root_type == AccountType.EXPENSE,
        GLEntry.is_cancelled == False,
    ).group_by(func.date_trunc("month", GLEntry.posting_date)).all()

    # Combine into trend
    revenue_map = {r.period: float(r.amount or 0) for r in revenue_query}
    expense_map = {e.period: float(e.amount or 0) for e in expense_query}

    all_periods = sorted(set(revenue_map.keys()) | set(expense_map.keys()))
    trend = []
    for period in all_periods:
        rev = revenue_map.get(period, 0)
        exp = expense_map.get(period, 0)
        profit = rev - exp
        margin = (profit / rev * 100) if rev else 0
        trend.append({
            "period": period.isoformat() if period else None,
            "revenue": round(rev, 2),
            "expenses": round(exp, 2),
            "profit": round(profit, 2),
            "margin": round(margin, 2),
        })

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "trend": trend,
    }


@router.get(
    "/profitability/by-segment",
    dependencies=[Depends(Require("reports:read"))]
)
async def get_profitability_by_segment(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Profitability analysis by customer segment/type."""
    start, end = _get_date_range(start_date, end_date, months=12)

    # Revenue by customer type
    results = db.query(
        Customer.customer_type,
        func.sum(Payment.amount).label("revenue"),
        func.count(func.distinct(Customer.id)).label("customer_count"),
    ).join(
        Payment, Payment.customer_id == Customer.id
    ).filter(
        Payment.payment_date >= start,
        Payment.payment_date <= end,
        Payment.status == PaymentStatus.COMPLETED,
    ).group_by(Customer.customer_type).all()

    total_revenue = sum(float(r.revenue or 0) for r in results)
    segments = [
        {
            "segment": row.customer_type or "Unknown",
            "revenue": float(row.revenue or 0),
            "customer_count": row.customer_count,
            "avg_revenue_per_customer": round(float(row.revenue / row.customer_count), 2) if row.customer_count else 0,
            "percentage": round(float(row.revenue / total_revenue * 100), 2) if total_revenue else 0,
        }
        for row in results
    ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_revenue": round(total_revenue, 2),
        "segments": sorted(segments, key=lambda x: x["revenue"], reverse=True),
    }


# ============= CASH POSITION / LIQUIDITY =============

@router.get(
    "/cash-position/summary",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-cash-position", ttl=CACHE_TTL["short"])
async def get_cash_position_summary(
    as_of_date: Optional[str] = Query(None, description="Balance as of date"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Current cash position across all bank accounts."""
    as_of = _parse_date(as_of_date, "as_of_date") or date.today()

    # Get bank accounts
    bank_accounts = db.query(BankAccount).filter(
        BankAccount.disabled == False,
    ).all()

    # Calculate balance from GL for each bank account
    accounts_detail = []
    total_cash = Decimal("0")

    for ba in bank_accounts:
        # Get balance from GL entries up to as_of_date
        balance = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).filter(
            GLEntry.account == ba.account,
            GLEntry.posting_date <= as_of,
            GLEntry.is_cancelled == False,
        ).scalar() or Decimal("0")

        accounts_detail.append({
            "account_id": ba.id,
            "account_name": ba.account_name,
            "bank": ba.bank,
            "account_number": ba.bank_account_no,
            "currency": ba.currency,
            "balance": float(balance),
            "is_default": ba.is_default,
        })
        total_cash += balance

    # Get unreconciled bank transactions count
    unreconciled_count = db.query(func.count(BankTransaction.id)).filter(
        BankTransaction.status.in_([BankTransactionStatus.PENDING, BankTransactionStatus.UNRECONCILED]),
    ).scalar() or 0

    return {
        "as_of_date": as_of.isoformat(),
        "total_cash": float(total_cash),
        "account_count": len(accounts_detail),
        "accounts": sorted(accounts_detail, key=lambda x: x["balance"], reverse=True),
        "unreconciled_transactions": unreconciled_count,
    }


@router.get(
    "/cash-position/forecast",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-cash-forecast", ttl=CACHE_TTL["medium"])
async def get_cash_flow_forecast(
    months: int = Query(default=3, le=12, description="Forecast months ahead"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simple cash flow forecast based on historical patterns."""
    today = date.today()

    # Get current cash position
    current_cash = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # Calculate average monthly inflows (last 6 months)
    six_months_ago = today - relativedelta(months=6)
    avg_inflows = db.query(func.coalesce(func.avg(Payment.amount), 0)).filter(
        Payment.payment_date >= six_months_ago,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")

    monthly_inflow = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_date >= six_months_ago,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")
    monthly_inflow = float(monthly_inflow) / 6 if monthly_inflow else 0

    # Calculate average monthly outflows
    monthly_outflow = db.query(func.coalesce(func.sum(Expense.total_sanctioned_amount), 0)).filter(
        Expense.posting_date >= six_months_ago,
        Expense.status != ExpenseStatus.CANCELLED,
    ).scalar() or Decimal("0")
    monthly_outflow = float(monthly_outflow) / 6 if monthly_outflow else 0

    # Outstanding receivables
    outstanding_ar = db.query(func.coalesce(func.sum(Invoice.balance), 0)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
    ).scalar() or Decimal("0")

    # Outstanding payables
    outstanding_ap = db.query(func.coalesce(func.sum(PurchaseInvoice.outstanding_amount), 0)).filter(
        PurchaseInvoice.docstatus == 1,
        PurchaseInvoice.outstanding_amount > 0,
    ).scalar() or Decimal("0")

    # Generate forecast
    net_monthly = monthly_inflow - monthly_outflow
    forecast = []
    running_balance = float(current_cash)

    for i in range(1, months + 1):
        forecast_date = today + relativedelta(months=i)
        running_balance += net_monthly
        forecast.append({
            "month": forecast_date.strftime("%Y-%m"),
            "projected_inflows": round(monthly_inflow, 2),
            "projected_outflows": round(monthly_outflow, 2),
            "net_cash_flow": round(net_monthly, 2),
            "projected_balance": round(running_balance, 2),
        })

    return {
        "current_cash": float(current_cash),
        "outstanding_receivables": float(outstanding_ar),
        "outstanding_payables": float(outstanding_ap),
        "avg_monthly_inflow": round(monthly_inflow, 2),
        "avg_monthly_outflow": round(monthly_outflow, 2),
        "net_monthly_cash_flow": round(net_monthly, 2),
        "forecast": forecast,
    }


@router.get(
    "/cash-position/runway",
    dependencies=[Depends(Require("reports:read"))]
)
@cached("reports-cash-runway", ttl=CACHE_TTL["medium"])
async def get_cash_runway(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate months of cash runway based on burn rate."""
    today = date.today()

    # Current cash
    current_cash = db.query(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).join(
        Account, Account.erpnext_id == GLEntry.account
    ).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    # Average monthly expenses (last 6 months)
    six_months_ago = today - relativedelta(months=6)
    total_expenses = db.query(func.coalesce(func.sum(Expense.total_sanctioned_amount), 0)).filter(
        Expense.posting_date >= six_months_ago,
        Expense.status != ExpenseStatus.CANCELLED,
    ).scalar() or Decimal("0")
    monthly_burn = float(total_expenses) / 6 if total_expenses else 0

    # Average monthly revenue
    total_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_date >= six_months_ago,
        Payment.status == PaymentStatus.COMPLETED,
    ).scalar() or Decimal("0")
    monthly_revenue = float(total_revenue) / 6 if total_revenue else 0

    # Net burn rate
    net_burn = monthly_burn - monthly_revenue

    # Calculate runway
    if net_burn > 0:
        runway_months = float(current_cash) / net_burn
    elif net_burn < 0:
        runway_months = float("inf")  # Cash positive
    else:
        runway_months = float("inf") if float(current_cash) > 0 else 0

    return {
        "current_cash": float(current_cash),
        "monthly_revenue": round(monthly_revenue, 2),
        "monthly_expenses": round(monthly_burn, 2),
        "net_burn_rate": round(net_burn, 2),
        "runway_months": round(runway_months, 1) if runway_months != float("inf") else "Infinite (cash positive)",
        "status": "cash_positive" if net_burn <= 0 else ("healthy" if runway_months > 12 else ("warning" if runway_months > 6 else "critical")),
    }

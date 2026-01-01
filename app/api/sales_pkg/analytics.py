"""
Analytics Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup, 
    Territory, SalesPerson
)
from app.api.sales_pkg.common import _parse_iso_utc, _resolve_currency_or_raise

router = APIRouter()

# =============================================================================
# ANALYTICS
# =============================================================================

@router.get(
    "/analytics/revenue-trend",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Revenue trend (month/week) - single currency",
)
async def get_revenue_trend(
    months: int = Query(default=12, le=36, description="Fallback window if start/end not provided"),
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    interval: str = Query(default="month", description="Aggregation interval: month or week"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue trend from completed payments (single-currency)."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    end_dt = _parse_iso_utc(end_date, "end_date") or datetime.now(timezone.utc)
    start_dt = _parse_iso_utc(start_date, "start_date") or end_dt - timedelta(days=months * 30)

    if interval not in ("month", "week"):
        raise HTTPException(status_code=400, detail="interval must be 'month' or 'week'")

    trunc = func.date_trunc(interval, Payment.payment_date)
    query = db.query(
        func.extract("year", trunc).label("year"),
        func.extract("month", trunc).label("month"),
        func.to_char(trunc, "YYYY-MM" if interval == "month" else "IYYY-IW").label("period"),
        func.sum(Payment.amount).label("revenue"),
        func.count(Payment.id).label("payment_count"),
        func.min(Payment.payment_date).label("period_start"),
        func.max(Payment.payment_date).label("period_end"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        query = query.filter(Payment.currency == currency)

    revenue = (
        query
        .group_by(trunc)
        .order_by(trunc)
        .all()
    )

    return {
        "meta": {
            "interval": interval,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "currency": currency,
        },
        "data": [
            {
                "year": int(r.year),
                "month": int(r.month) if r.month is not None else None,
                "period": r.period,
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
                "revenue": float(r.revenue or 0),
                "payment_count": int(r.payment_count or 0),
            }
            for r in revenue
        ],
    }


@router.get("/analytics/collections", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-collections", ttl=CACHE_TTL["medium"])
async def get_collections_analytics(
    start_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date or datetime (UTC)"),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get collection analytics including payment methods, timing, and daily totals (single-currency)."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    end_dt = _parse_iso_utc(end_date, "end_date") or datetime.now(timezone.utc)
    start_dt = _parse_iso_utc(start_date, "start_date") or end_dt - timedelta(days=30)

    # Payment method distribution
    by_method_query = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        by_method_query = by_method_query.filter(Payment.currency == currency)

    by_method = by_method_query.group_by(Payment.payment_method).all()

    # Payment timing analysis (early/on-time/late)
    days_diff = func.date_part("day", Invoice.due_date - Payment.payment_date)

    timing_query = db.query(
        func.sum(case(
            (and_(Payment.payment_date <= Invoice.due_date, days_diff > 3), 1),
            else_=0
        )).label("early"),
        func.sum(case(
            (and_(Payment.payment_date <= Invoice.due_date, days_diff <= 3), 1),
            else_=0
        )).label("on_time"),
        func.sum(case(
            (Payment.payment_date > Invoice.due_date, 1),
            else_=0
        )).label("late"),
        func.count(Payment.id).label("total"),
    ).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Invoice.due_date.isnot(None),
        Payment.payment_date.isnot(None),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )
    if currency:
        timing_query = timing_query.filter(Payment.currency == currency, Invoice.currency == currency)

    timing = timing_query.one_or_none()

    # Daily totals for charting
    daily = db.query(
        func.date(Payment.payment_date).label("date"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )
    if currency:
        daily = daily.filter(Payment.currency == currency)
    daily_totals = [
        {"date": row.date.isoformat(), "total": float(row.total or 0)}
        for row in daily.group_by(func.date(Payment.payment_date)).order_by(func.date(Payment.payment_date)).all()
    ]

    return {
        "meta": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "currency": currency,
        },
        "by_method": [
            {
                "method": row.payment_method.value if row.payment_method else "unknown",
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in by_method
        ],
        "payment_timing": {
            "early": int(timing.early or 0) if timing else 0,
            "on_time": int(timing.on_time or 0) if timing else 0,
            "late": int(timing.late or 0) if timing else 0,
            "total": int(timing.total or 0) if timing else 0,
        },
        "daily_totals": daily_totals,
    }


@router.get("/aging", dependencies=[Depends(Require("analytics:read"))])
@router.get("/analytics/aging", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-aging", ttl=CACHE_TTL["short"])
async def get_invoice_aging(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoice aging analysis by bucket."""
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    days_overdue = func.date_part("day", func.current_date() - Invoice.due_date)

    aging_bucket = case(
        (Invoice.due_date >= func.current_date(), 'current'),
        (days_overdue <= 30, '1-30 days'),
        (days_overdue <= 60, '31-60 days'),
        (days_overdue <= 90, '61-90 days'),
        else_='over 90 days'
    )

    aging_query = db.query(
        aging_bucket.label("bucket"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.due_date.isnot(None),
    )

    if currency:
        aging_query = aging_query.filter(Invoice.currency == currency)

    aging = aging_query.group_by(aging_bucket).all()

    bucket_order = ["current", "1-30 days", "31-60 days", "61-90 days", "over 90 days"]
    aging_map = {row.bucket: {"count": row.count, "outstanding": float(row.outstanding or 0)} for row in aging}

    buckets = [
        {
            "bucket": b,
            "count": aging_map.get(b, {}).get("count", 0),
            "outstanding": aging_map.get(b, {}).get("outstanding", 0),
        }
        for b in bucket_order
    ]

    total_outstanding = sum(b["outstanding"] for b in buckets)
    at_risk = sum(b["outstanding"] for b in buckets if b["bucket"] != "current")

    total_invoices = sum(b["count"] for b in buckets)

    return {
        "buckets": buckets,
        "summary": {
            "total_outstanding": total_outstanding,
            "at_risk": at_risk,
            "at_risk_percent": round(at_risk / total_outstanding * 100, 1) if total_outstanding > 0 else 0,
            "total_invoices": total_invoices,
        },
    }


@router.get("/analytics/by-currency", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_by_currency(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get revenue breakdown by currency."""
    # MRR by currency
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    by_currency = db.query(
        Subscription.currency,
        func.sum(mrr_case).label("mrr"),
        func.count(Subscription.id).label("subscription_count"),
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Subscription.currency).all()

    # Outstanding by currency
    outstanding = db.query(
        Invoice.currency,
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    ).group_by(Invoice.currency).all()

    outstanding_map = {row.currency: float(row.outstanding or 0) for row in outstanding}

    return {
        "by_currency": [
            {
                "currency": row.currency,
                "mrr": float(row.mrr or 0),
                "arr": float(row.mrr or 0) * 12,
                "subscription_count": row.subscription_count,
                "outstanding": outstanding_map.get(row.currency, 0),
            }
            for row in by_currency
        ],
    }


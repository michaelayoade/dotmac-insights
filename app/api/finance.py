"""
Finance Domain Router

Provides all finance-related endpoints:
- /dashboard - Revenue KPIs, collections, DSO
- /invoices - List, detail invoices
- /payments - List, detail payments
- /credit-notes - List credit notes
- /analytics/* - Revenue trends, aging, collections
- /insights/* - Payment behavior, forecasts
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_, or_, distinct
from typing import Dict, Any, Optional, List, Iterable, cast
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


def _parse_iso_utc(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse an ISO8601 string into an aware UTC datetime."""
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} date: {value}")


def _resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, raise 400."""
    if requested:
        return requested
    currencies = [row[0] for row in db.query(distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    if len(set(currencies)) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple currencies detected; please provide the 'currency' query parameter to avoid mixed-currency aggregates.",
        )
    return cast(Optional[str], currencies[0])


# =============================================================================
# DASHBOARD
# =============================================================================

class RevenueTrendPoint(BaseModel):
    year: int
    month: int
    period: str
    revenue: float
    payment_count: int

@router.get(
    "/dashboard",
    dependencies=[Depends(Require("analytics:read"))],
    summary="Finance dashboard (single-currency)",
    description="Returns revenue KPIs (MRR/ARR), collections, outstanding, DSO, and invoice status counts. "
                "Requires a single currency; if data contains multiple currencies, pass ?currency=.",
)
@cached("finance-dashboard", ttl=CACHE_TTL["short"])
async def get_finance_dashboard(
    currency: Optional[str] = Query(default=None, description="Currency code (required if multiple currencies exist)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Finance dashboard with key revenue and collection metrics.
    Enforces a single currency to avoid mixing figures.
    """
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency)
    # MRR calculation from active subscriptions
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    mrr_query = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if currency:
        mrr_query = mrr_query.filter(Subscription.currency == currency)

    mrr = float(mrr_query.scalar() or 0)
    arr = mrr * 12

    active_subscriptions = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        *( [Subscription.currency == currency] if currency else [] ),
    ).scalar() or 0

    # Invoice summary
    invoice_summary_query = db.query(
        Invoice.status,
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount).label("total")
    )
    if currency:
        invoice_summary_query = invoice_summary_query.filter(Invoice.currency == currency)
    invoice_summary = invoice_summary_query.group_by(Invoice.status).all()

    invoice_by_status = {
        row.status.value: {"count": row.count, "total": float(row.total or 0)}
        for row in invoice_summary
    }

    # Outstanding balance
    outstanding_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    )
    overdue_query = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    if currency:
        outstanding_query = outstanding_query.filter(Invoice.currency == currency)
        overdue_query = overdue_query.filter(Invoice.currency == currency)

    outstanding = outstanding_query.scalar() or 0
    overdue_amount = overdue_query.scalar() or 0

    # Collections last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    collections_30d_query = db.query(func.sum(Payment.amount)).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= thirty_days_ago
    )
    invoiced_30d_query = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= thirty_days_ago
    )
    if currency:
        collections_30d_query = collections_30d_query.filter(Payment.currency == currency)
        invoiced_30d_query = invoiced_30d_query.filter(Invoice.currency == currency)

    collections_30d = collections_30d_query.scalar() or 0
    invoiced_30d = invoiced_30d_query.scalar() or 0

    collection_rate = round(float(collections_30d) / float(invoiced_30d) * 100, 1) if invoiced_30d else 0

    # DSO (Days Sales Outstanding) - simplified calculation
    avg_daily_revenue = float(collections_30d) / 30 if collections_30d else 0
    dso = round(float(outstanding) / avg_daily_revenue, 1) if avg_daily_revenue > 0 else 0

    return {
        "revenue": {
            "mrr": mrr,
            "arr": arr,
            "active_subscriptions": active_subscriptions,
        },
        "collections": {
            "last_30_days": float(collections_30d),
            "invoiced_30_days": float(invoiced_30d),
            "collection_rate": collection_rate,
        },
        "outstanding": {
            "total": float(outstanding),
            "overdue": float(overdue_amount),
        },
        "metrics": {
            "dso": dso,
        },
        "invoices_by_status": invoice_by_status,
    }


# =============================================================================
# NOTE: Invoice, Payment, and Credit Note CRUD endpoints have been removed.
# Use the accounting module instead:
#   - GET /api/v1/accounting/invoices
#   - GET /api/v1/accounting/ar-payments
#   - GET /api/v1/accounting/notes
# The accounting module is the single source of truth for this data.
# =============================================================================


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
    by_method = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        by_method = by_method.filter(Payment.currency == currency)

    by_method_rows = by_method.group_by(Payment.payment_method).all()

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
            for row in by_method_rows
        ],
        "payment_timing": {
            "early": int(timing.early or 0) if timing else 0,
            "on_time": int(timing.on_time or 0) if timing else 0,
            "late": int(timing.late or 0) if timing else 0,
            "total": int(timing.total or 0) if timing else 0,
        },
        "daily_totals": daily_totals,
    }


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


# =============================================================================
# INSIGHTS
# =============================================================================

@router.get("/insights/payment-behavior", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-payment-behavior", ttl=CACHE_TTL["medium"])
async def get_payment_behavior_insights(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze customer payment behavior patterns."""
    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    # Get customers with payment history
    customer_payments_query = db.query(
        Payment.customer_account_id,
        func.count(Payment.id).label("total_payments"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.customer_account_id.isnot(None),
    )
    if currency:
        customer_payments_query = customer_payments_query.filter(Payment.currency == currency)
    customer_payments = customer_payments_query.group_by(Payment.customer_account_id).subquery()

    # Count customers by payment frequency
    customers_with_payments = db.query(func.count(customer_payments.c.customer_account_id)).scalar() or 0

    # Customers with overdue invoices
    customers_overdue_query = db.query(func.count(distinct(Invoice.customer_account_id))).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    )
    if currency:
        customers_overdue_query = customers_overdue_query.filter(Invoice.currency == currency)
    customers_overdue = customers_overdue_query.scalar() or 0

    # Average payment delay for late payments
    late_payments_query = db.query(
        func.avg(func.date_part("day", Payment.payment_date - Invoice.due_date)).label("avg_delay")
    ).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date > Invoice.due_date,
    )
    if currency:
        late_payments_query = late_payments_query.filter(Payment.currency == currency, Invoice.currency == currency)
    late_payments = late_payments_query.scalar() or 0

    # Late payments percentage
    late_count_query = db.query(func.count(Payment.id)).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date > Invoice.due_date,
    )
    total_payments_query = db.query(func.count(Payment.id)).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.payment_date.isnot(None),
    )
    if currency:
        late_count_query = late_count_query.filter(Payment.currency == currency, Invoice.currency == currency)
        total_payments_query = total_payments_query.filter(Payment.currency == currency)

    late_count = late_count_query.scalar() or 0
    total_payments = total_payments_query.scalar() or 0
    late_percent = round(late_count / total_payments * 100, 1) if total_payments else 0

    return {
        "summary": {
            "customers_with_payments": customers_with_payments,
            "customers_with_overdue": customers_overdue,
            "avg_late_payment_delay_days": round(float(late_payments), 1),
            "late_payments_percent": late_percent,
        },
        "recommendations": [
            {
                "priority": "high" if customers_overdue > customers_with_payments * 0.1 else "medium",
                "issue": f"{customers_overdue} customers have overdue invoices",
                "action": "Send payment reminders and review collection process",
            }
        ] if customers_overdue > 0 else [],
    }


@router.get("/insights/forecasts", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-forecasts", ttl=CACHE_TTL["medium"])
async def get_revenue_forecasts(
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simple revenue projections based on current MRR and trends."""
    currency = _resolve_currency_or_raise(db, Subscription.currency, currency)
    # Current MRR
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    mrr_query = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    )
    if currency:
        mrr_query = mrr_query.filter(Subscription.currency == currency)
    current_mrr = mrr_query.scalar() or 0

    # Calculate growth (compare to 30 days ago - simplified)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    new_subs_query = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.start_date >= thirty_days_ago,
    )
    if currency:
        new_subs_query = new_subs_query.filter(Subscription.currency == currency)
    new_subs_30d = new_subs_query.scalar() or 0

    # Simple projection: assume current MRR continues
    mrr_float = float(current_mrr)

    return {
        "currency": currency,
        "current": {
            "mrr": mrr_float,
            "arr": mrr_float * 12,
        },
        "activity_30d": {
            "new_subscriptions": new_subs_30d,
        },
        "projections": {
            "month_1": mrr_float,
            "month_2": mrr_float,
            "month_3": mrr_float,
            "quarter_total": mrr_float * 3,
        },
        "assumptions": [
            "Current MRR remains stable (no churn/upgrade modeled)",
            "Same currency across all subscriptions",
        ],
        "notes": "Projections assume current MRR remains stable. Adjust for expected growth/churn.",
    }

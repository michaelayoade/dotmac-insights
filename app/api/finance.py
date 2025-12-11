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
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.customer import Customer
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# DASHBOARD
# =============================================================================

class RevenueTrendPoint(BaseModel):
    year: int
    month: int
    period: str
    revenue: float
    payment_count: int

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-dashboard", ttl=CACHE_TTL["short"])
async def get_finance_dashboard(
    currency: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Finance dashboard with key revenue and collection metrics.
    """
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
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    # Invoice summary
    invoice_summary = db.query(
        Invoice.status,
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount).label("total")
    ).group_by(Invoice.status).all()

    invoice_by_status = {
        row.status.value: {"count": row.count, "total": float(row.total or 0)}
        for row in invoice_summary
    }

    # Outstanding balance
    outstanding = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    ).scalar() or 0

    overdue_amount = db.query(func.sum(Invoice.total_amount - Invoice.amount_paid)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).scalar() or 0

    # Collections last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    collections_30d = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= thirty_days_ago
    ).scalar() or 0

    invoiced_30d = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= thirty_days_ago
    ).scalar() or 0

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
# DATA ENDPOINTS
# =============================================================================

@router.get("/invoices", dependencies=[Depends(Require("explorer:read"))])
async def list_invoices(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    overdue_only: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List invoices with filtering and pagination."""
    query = db.query(Invoice)

    if status:
        try:
            status_enum = InvoiceStatus(status)
            query = query.filter(Invoice.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if start_date:
        query = query.filter(Invoice.invoice_date >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Invoice.invoice_date <= datetime.fromisoformat(end_date))

    if min_amount:
        query = query.filter(Invoice.total_amount >= min_amount)

    if max_amount:
        query = query.filter(Invoice.total_amount <= max_amount)

    if currency:
        query = query.filter(Invoice.currency == currency)

    if overdue_only:
        query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

    total = query.count()
    invoices = query.order_by(Invoice.invoice_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "total_amount": float(inv.total_amount),
                "amount_paid": float(inv.amount_paid or 0),
                "balance": float(inv.total_amount - (inv.amount_paid or 0)),
                "currency": inv.currency,
                "status": inv.status.value if inv.status else None,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
                "source": inv.source.value if inv.source else None,
            }
            for inv in invoices
        ],
    }


@router.get("/invoices/{invoice_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed invoice information."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Get related payments
    payments = db.query(Payment).filter(Payment.invoice_id == invoice_id).all()

    # Get customer info
    customer = None
    if invoice.customer_id:
        cust = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "description": invoice.description,
        "amount": float(invoice.amount),
        "tax_amount": float(invoice.tax_amount or 0),
        "total_amount": float(invoice.total_amount),
        "amount_paid": float(invoice.amount_paid or 0),
        "balance": float(invoice.total_amount - (invoice.amount_paid or 0)),
        "currency": invoice.currency,
        "status": invoice.status.value if invoice.status else None,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "paid_date": invoice.paid_date.isoformat() if invoice.paid_date else None,
        "days_overdue": invoice.days_overdue,
        "category": invoice.category,
        "source": invoice.source.value if invoice.source else None,
        "external_ids": {
            "splynx_id": invoice.splynx_id,
            "erpnext_id": invoice.erpnext_id,
        },
        "customer": customer,
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
            }
            for p in payments
        ],
    }


@router.get("/payments", dependencies=[Depends(Require("explorer:read"))])
async def list_payments(
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    currency: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payments with filtering and pagination."""
    query = db.query(Payment)

    if status:
        try:
            status_enum = PaymentStatus(status)
            query = query.filter(Payment.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if payment_method:
        try:
            method_enum = PaymentMethod(payment_method)
            query = query.filter(Payment.payment_method == method_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment_method: {payment_method}")

    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)

    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)

    if start_date:
        query = query.filter(Payment.payment_date >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Payment.payment_date <= datetime.fromisoformat(end_date))

    if min_amount:
        query = query.filter(Payment.amount >= min_amount)

    if currency:
        query = query.filter(Payment.currency == currency)

    total = query.count()
    payments = query.order_by(Payment.payment_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "customer_id": p.customer_id,
                "invoice_id": p.invoice_id,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "transaction_reference": p.transaction_reference,
                "source": p.source.value if p.source else None,
            }
            for p in payments
        ],
    }


@router.get("/payments/{payment_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed payment information."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    customer = None
    if payment.customer_id:
        cust = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        if cust:
            customer = {"id": cust.id, "name": cust.name, "email": cust.email}

    invoice = None
    if payment.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if inv:
            invoice = {"id": inv.id, "invoice_number": inv.invoice_number, "total_amount": float(inv.total_amount)}

    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "payment_method": payment.payment_method.value if payment.payment_method else None,
        "status": payment.status.value if payment.status else None,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "transaction_reference": payment.transaction_reference,
        "gateway_reference": payment.gateway_reference,
        "notes": payment.notes,
        "source": payment.source.value if payment.source else None,
        "external_ids": {
            "splynx_id": payment.splynx_id,
            "erpnext_id": payment.erpnext_id,
        },
        "customer": customer,
        "invoice": invoice,
    }


@router.get("/credit-notes", dependencies=[Depends(Require("explorer:read"))])
async def list_credit_notes(
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List credit notes with filtering and pagination."""
    query = db.query(CreditNote)

    if customer_id:
        query = query.filter(CreditNote.customer_id == customer_id)

    if invoice_id:
        query = query.filter(CreditNote.invoice_id == invoice_id)

    if start_date:
        query = query.filter(CreditNote.issue_date >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(CreditNote.issue_date <= datetime.fromisoformat(end_date))

    total = query.count()
    credit_notes = query.order_by(CreditNote.issue_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": cn.id,
                "credit_note_number": cn.credit_number,
                "customer_id": cn.customer_id,
                "invoice_id": cn.invoice_id,
                "amount": float(cn.amount) if cn.amount else 0,
                "currency": cn.currency,
                "date": cn.issue_date.isoformat() if cn.issue_date else None,
                "reason": cn.description,
                "source": None,
            }
            for cn in credit_notes
        ],
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get(
    "/analytics/revenue-trend",
    dependencies=[Depends(Require("analytics:read"))],
    response_model=List[RevenueTrendPoint],
)
async def get_revenue_trend(
    months: int = Query(default=12, le=24),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[RevenueTrendPoint]:
    """Get monthly revenue trend from completed payments."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=months * 30)

    query = db.query(
        extract("year", Payment.payment_date).label("year"),
        extract("month", Payment.payment_date).label("month"),
        func.sum(Payment.amount).label("revenue"),
        func.count(Payment.id).label("payment_count"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt,
    )

    if currency:
        query = query.filter(Payment.currency == currency)

    revenue = (
        query
        .group_by(
            extract("year", Payment.payment_date),
            extract("month", Payment.payment_date),
        )
        .order_by(
            extract("year", Payment.payment_date),
            extract("month", Payment.payment_date),
        )
        .all()
    )

    return [
        RevenueTrendPoint(
            year=int(r.year),
            month=int(r.month),
            period=f"{int(r.year)}-{int(r.month):02d}",
            revenue=float(r.revenue or 0),
            payment_count=int(r.payment_count or 0),
        )
        for r in revenue
    ]


@router.get("/analytics/collections", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-collections", ttl=CACHE_TTL["medium"])
async def get_collections_analytics(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get collection analytics including payment methods and timing."""
    # Payment method distribution
    by_method = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED
    ).group_by(Payment.payment_method).all()

    # Payment timing analysis (early/on-time/late)
    days_diff = func.date_part("day", Invoice.due_date - Payment.payment_date)

    timing = db.query(
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
        Payment.status == PaymentStatus.COMPLETED,
        Invoice.due_date.isnot(None),
        Payment.payment_date.isnot(None),
    ).one()

    return {
        "by_method": [
            {
                "method": row.payment_method.value if row.payment_method else "unknown",
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in by_method
        ],
        "payment_timing": {
            "early": int(timing.early or 0),
            "on_time": int(timing.on_time or 0),
            "late": int(timing.late or 0),
            "total": int(timing.total or 0),
        },
    }


@router.get("/analytics/aging", dependencies=[Depends(Require("analytics:read"))])
@cached("finance-aging", ttl=CACHE_TTL["short"])
async def get_invoice_aging(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoice aging analysis by bucket."""
    days_overdue = func.date_part("day", func.current_date() - Invoice.due_date)

    aging_bucket = case(
        (Invoice.due_date >= func.current_date(), 'current'),
        (days_overdue <= 30, '1-30 days'),
        (days_overdue <= 60, '31-60 days'),
        (days_overdue <= 90, '61-90 days'),
        else_='over 90 days'
    )

    aging = db.query(
        aging_bucket.label("bucket"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.total_amount - Invoice.amount_paid).label("outstanding"),
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.due_date.isnot(None),
    ).group_by(aging_bucket).all()

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

    return {
        "buckets": buckets,
        "summary": {
            "total_outstanding": total_outstanding,
            "at_risk": at_risk,
            "at_risk_percent": round(at_risk / total_outstanding * 100, 1) if total_outstanding > 0 else 0,
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
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze customer payment behavior patterns."""
    # Get customers with payment history
    customer_payments = db.query(
        Payment.customer_id,
        func.count(Payment.id).label("total_payments"),
    ).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.customer_id.isnot(None),
    ).group_by(Payment.customer_id).subquery()

    # Count customers by payment frequency
    customers_with_payments = db.query(func.count(customer_payments.c.customer_id)).scalar() or 0

    # Customers with overdue invoices
    customers_overdue = db.query(func.count(distinct(Invoice.customer_id))).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).scalar() or 0

    # Average payment delay for late payments
    late_payments = db.query(
        func.avg(func.date_part("day", Payment.payment_date - Invoice.due_date)).label("avg_delay")
    ).join(Invoice, Payment.invoice_id == Invoice.id).filter(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date > Invoice.due_date,
    ).scalar() or 0

    return {
        "summary": {
            "customers_with_payments": customers_with_payments,
            "customers_with_overdue": customers_overdue,
            "avg_late_payment_delay_days": round(float(late_payments), 1),
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
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simple revenue projections based on current MRR and trends."""
    # Current MRR
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    current_mrr = db.query(func.sum(mrr_case)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    # Calculate growth (compare to 30 days ago - simplified)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    new_subs_30d = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.start_date >= thirty_days_ago,
    ).scalar() or 0

    # Simple projection: assume current MRR continues
    mrr_float = float(current_mrr)

    return {
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
        "notes": "Projections assume current MRR remains stable. Adjust for expected growth/churn.",
    }

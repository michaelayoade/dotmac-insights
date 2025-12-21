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
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.credit_note import CreditNote
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.customer import Customer
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
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="invoice_date,due_date,total_amount,amount_paid,customer_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List invoices with filtering, search, sort, and pagination (single-currency only)."""
    query = db.query(Invoice)

    if status:
        try:
            status_enum = InvoiceStatus(status)
            query = query.filter(Invoice.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Invoice.invoice_date >= start_dt)

    if end_dt:
        query = query.filter(Invoice.invoice_date <= end_dt)

    if min_amount:
        query = query.filter(Invoice.total_amount >= min_amount)

    if max_amount:
        query = query.filter(Invoice.total_amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)
    if currency:
        query = query.filter(Invoice.currency == currency)

    if overdue_only:
        query = query.filter(Invoice.status == InvoiceStatus.OVERDUE)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Invoice.invoice_number.ilike(like), Invoice.description.ilike(like)))

    sort_map = {
        "invoice_date": Invoice.invoice_date,
        "due_date": Invoice.due_date,
        "total_amount": Invoice.total_amount,
        "amount_paid": Invoice.amount_paid,
        "customer_id": Invoice.customer_id,
        "status": Invoice.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map[sort_by or "invoice_date"]
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    invoice_rows = (
        query.outerjoin(Customer, Invoice.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, Invoice.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "customer_name": customer_name,
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
            for inv, customer_name in invoice_rows
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
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="payment_date,amount,customer_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List payments with filtering, search, sort, and pagination (single-currency only)."""
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

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(Payment.payment_date >= start_dt)

    if end_dt:
        query = query.filter(Payment.payment_date <= end_dt)

    if min_amount:
        query = query.filter(Payment.amount >= min_amount)

    if max_amount:
        query = query.filter(Payment.amount <= max_amount)

    currency = _resolve_currency_or_raise(db, Payment.currency, currency)
    if currency:
        query = query.filter(Payment.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Payment.receipt_number.ilike(like),
                Payment.transaction_reference.ilike(like),
                Payment.gateway_reference.ilike(like),
                Payment.notes.ilike(like),
            )
        )

    sort_map = {
        "payment_date": Payment.payment_date,
        "amount": Payment.amount,
        "customer_id": Payment.customer_id,
        "invoice_id": Payment.invoice_id,
        "status": Payment.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map[sort_by or "payment_date"]
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    payment_rows = (
        query.outerjoin(Customer, Payment.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, Payment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "customer_id": p.customer_id,
                "customer_name": customer_name,
                "invoice_id": p.invoice_id,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "transaction_reference": p.transaction_reference,
                "gateway_reference": p.gateway_reference,
                "notes": p.notes,
                "source": p.source.value if p.source else None,
            }
            for p, customer_name in payment_rows
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
    currency: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default=None, description="issue_date,amount,customer_id,invoice_id,status"),
    sort_dir: Optional[str] = Query(default="desc", description="asc or desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List credit notes with filtering, search, sort, and pagination (single-currency only)."""
    currency = _resolve_currency_or_raise(db, CreditNote.currency, currency)
    query = db.query(CreditNote)

    if customer_id:
        query = query.filter(CreditNote.customer_id == customer_id)

    if invoice_id:
        query = query.filter(CreditNote.invoice_id == invoice_id)

    start_dt = _parse_iso_utc(start_date, "start_date")
    end_dt = _parse_iso_utc(end_date, "end_date")

    if start_dt:
        query = query.filter(CreditNote.issue_date >= start_dt)

    if end_dt:
        query = query.filter(CreditNote.issue_date <= end_dt)

    if currency:
        query = query.filter(CreditNote.currency == currency)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(CreditNote.credit_number.ilike(like), CreditNote.description.ilike(like)))

    sort_map = {
        "issue_date": CreditNote.issue_date,
        "amount": CreditNote.amount,
        "customer_id": CreditNote.customer_id,
        "invoice_id": CreditNote.invoice_id,
        "status": CreditNote.status,
    }
    if sort_by and sort_by not in sort_map:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")
    sort_column = sort_map[sort_by or "issue_date"]
    sort_order = sort_dir.lower() if sort_dir else "desc"
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = query.count()
    credit_note_rows = (
        query.outerjoin(Customer, CreditNote.customer_id == Customer.id)
        .add_columns(Customer.name.label("customer_name"))
        .order_by(order_clause, CreditNote.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": cn.id,
                "credit_note_number": cn.credit_number,
                "customer_id": cn.customer_id,
                "customer_name": customer_name,
                "invoice_id": cn.invoice_id,
                "amount": float(cn.amount) if cn.amount else 0,
                "currency": cn.currency,
                "date": cn.issue_date.isoformat() if cn.issue_date else None,
                "reason": cn.description,
                "status": cn.status.value if cn.status else None,
                "source": "splynx",
                "external_ids": {
                    "splynx_id": cn.splynx_id,
                },
            }
            for cn, customer_name in credit_note_rows
        ],
    }


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
        Payment.customer_id,
        func.count(Payment.id).label("total_payments"),
    ).filter(
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
        Payment.customer_id.isnot(None),
    )
    if currency:
        customer_payments_query = customer_payments_query.filter(Payment.currency == currency)
    customer_payments = customer_payments_query.group_by(Payment.customer_id).subquery()

    # Count customers by payment frequency
    customers_with_payments = db.query(func.count(customer_payments.c.customer_id)).scalar() or 0

    # Customers with overdue invoices
    customers_overdue_query = db.query(func.count(distinct(Invoice.customer_id))).filter(
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

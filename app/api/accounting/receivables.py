"""Accounts Receivable: AR aging, outstanding receivables."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import Require
from app.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus

from .helpers import parse_date, resolve_currency_or_raise

router = APIRouter()


# =============================================================================
# ACCOUNTS RECEIVABLE AGING
# =============================================================================

@router.get("/accounts-receivable", dependencies=[Depends(Require("accounting:read"))])
def get_accounts_receivable(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts receivable aging report.

    Shows outstanding customer invoices by age bucket.

    Args:
        as_of_date: Calculate aging as of this date (default: today)
        customer_id: Filter by customer
        currency: Currency filter

    Returns:
        AR aging with buckets (current, 1-30, 31-60, 61-90, 90+)
    """
    cutoff = parse_date(as_of_date, "as_of_date") or date.today()
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

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


# Alias
@router.get("/receivables-aging", dependencies=[Depends(Require("accounting:read"))])
def get_receivables_aging(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for /accounts-receivable - AR aging report."""
    return get_accounts_receivable(as_of_date, customer_id, currency, db)


# =============================================================================
# OUTSTANDING RECEIVABLES
# =============================================================================

@router.get("/receivables-outstanding", dependencies=[Depends(Require("accounting:read"))])
def get_receivables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Outstanding customer receivables with top customers.

    Args:
        currency: Currency filter
        top: Number of top customers to return

    Returns:
        Outstanding receivables summary with top customers
    """
    as_of = date.today()
    currency = resolve_currency_or_raise(db, Invoice.currency, currency)

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
        "total_invoices": inv_totals.count or 0,
        "top_customers": [
            {
                "customer_id": row.customer_id,
                "customer_name": row.customer_name,
                "outstanding": float(row.outstanding),
            }
            for row in inv_by_customer
        ],
    }

"""
Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel

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
from app.api.sales_pkg.common import _resolve_currency_or_raise

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

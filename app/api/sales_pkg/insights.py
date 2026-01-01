"""
Insights Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, distinct, case
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
from app.api.sales_pkg.common import _resolve_currency_or_raise

router = APIRouter()

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

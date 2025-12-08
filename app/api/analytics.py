from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.pop import Pop
from app.models.employee import Employee

router = APIRouter()


def _get_active_currencies(db: Session, filters: List = None) -> set:
    """Return distinct currencies for active subscriptions after filters."""
    query = (
        db.query(Subscription.currency)
        .outerjoin(Customer, Subscription.customer_id == Customer.id)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    if filters:
        for f in filters:
            query = query.filter(f)
    return {row.currency for row in query.distinct().all() if row.currency}


def _resolve_currency(db: Session, filters: List, currency: Optional[str]) -> Optional[str]:
    """
    Ensure MRR calculations do not mix currencies.
    - If caller supplies currency, use it.
    - If multiple currencies exist after filters and none supplied, raise 400.
    """
    currencies = _get_active_currencies(db, filters)

    if currency:
        return currency

    if len(currencies) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple subscription currencies detected. Provide the 'currency' query parameter to choose one.",
        )

    return currencies.pop() if currencies else None


def calculate_mrr(db: Session, filters: List = None, currency: Optional[str] = None) -> float:
    """
    Calculate Monthly Recurring Revenue normalized by billing cycle and currency.

    - Monthly plans: price as-is
    - Quarterly plans: price / 3
    - Yearly plans: price / 12
    - If multiple currencies exist and none provided, HTTP 400 is raised.
    """
    filters = filters or []
    resolved_currency = _resolve_currency(db, filters, currency)

    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price,
    )

    query = (
        db.query(func.sum(mrr_case))
        .outerjoin(Customer, Subscription.customer_id == Customer.id)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    if resolved_currency:
        query = query.filter(Subscription.currency == resolved_currency)

    for f in filters:
        query = query.filter(f)

    result = query.scalar()
    return float(result or 0)


@router.get("/overview")
async def get_overview(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get high-level overview metrics."""
    # Customer counts
    total_customers = db.query(Customer).count()
    active_customers = db.query(Customer).filter(Customer.status == CustomerStatus.ACTIVE).count()
    churned_customers = db.query(Customer).filter(Customer.status == CustomerStatus.CANCELLED).count()

    resolved_currency = _resolve_currency(db, [], currency)

    # Revenue (MRR from active subscriptions - properly normalized by billing cycle)
    mrr = calculate_mrr(db, currency=resolved_currency)

    # Outstanding balance
    outstanding_result = (
        db.query(func.sum(Invoice.balance))
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
        .scalar()
    )
    outstanding = float(outstanding_result or 0)

    # Open support tickets
    open_tickets = db.query(Conversation).filter(
        Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING])
    ).count()

    # Overdue invoices
    overdue_invoices = db.query(Invoice).filter(Invoice.status == InvoiceStatus.OVERDUE).count()

    # POP count
    pop_count = db.query(Pop).filter(Pop.is_active == True).count()

    return {
        "customers": {
            "total": total_customers,
            "active": active_customers,
            "churned": churned_customers,
            "churn_rate": round(churned_customers / total_customers * 100, 2) if total_customers > 0 else 0,
        },
        "revenue": {
            "mrr": mrr,
            "outstanding": outstanding,
            "overdue_invoices": overdue_invoices,
            "currency": resolved_currency,
        },
        "support": {
            "open_tickets": open_tickets,
        },
        "operations": {
            "pop_count": pop_count,
        },
    }


@router.get("/revenue/trend")
async def get_revenue_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly revenue trend from payments."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)

    payments = (
        db.query(
            extract("year", Payment.payment_date).label("year"),
            extract("month", Payment.payment_date).label("month"),
            func.sum(Payment.amount).label("total"),
            func.count(Payment.id).label("count"),
        )
        .filter(
            Payment.payment_date >= start_date,
            Payment.status == PaymentStatus.COMPLETED,
        )
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
        {
            "year": int(p.year),
            "month": int(p.month),
            "period": f"{int(p.year)}-{int(p.month):02d}",
            "revenue": float(p.total or 0),
            "payment_count": p.count,
        }
        for p in payments
    ]


@router.get("/churn/trend")
async def get_churn_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly churn trend."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)

    churns = (
        db.query(
            extract("year", Customer.cancellation_date).label("year"),
            extract("month", Customer.cancellation_date).label("month"),
            func.count(Customer.id).label("count"),
        )
        .filter(
            Customer.cancellation_date >= start_date,
            Customer.status == CustomerStatus.CANCELLED,
        )
        .group_by(
            extract("year", Customer.cancellation_date),
            extract("month", Customer.cancellation_date),
        )
        .order_by(
            extract("year", Customer.cancellation_date),
            extract("month", Customer.cancellation_date),
        )
        .all()
    )

    return [
        {
            "year": int(c.year),
            "month": int(c.month),
            "period": f"{int(c.year)}-{int(c.month):02d}",
            "churned_count": c.count,
        }
        for c in churns
    ]


@router.get("/pop/performance")
async def get_pop_performance(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get performance metrics by POP."""
    pops = db.query(Pop).filter(Pop.is_active == True).all()

    # Guard against mixed currencies globally unless caller specifies which to use
    _resolve_currency(db, [], currency)

    results = []
    for pop in pops:
        # Customer counts
        total_customers = db.query(Customer).filter(Customer.pop_id == pop.id).count()
        active_customers = db.query(Customer).filter(
            Customer.pop_id == pop.id,
            Customer.status == CustomerStatus.ACTIVE,
        ).count()
        churned_customers = db.query(Customer).filter(
            Customer.pop_id == pop.id,
            Customer.status == CustomerStatus.CANCELLED,
        ).count()

        # Revenue (MRR - properly normalized by billing cycle)
        mrr_filters = [Customer.pop_id == pop.id]
        pop_currency = _resolve_currency(db, mrr_filters, currency)
        mrr_result = calculate_mrr(db, filters=mrr_filters, currency=pop_currency)

        # Open tickets
        open_tickets = (
            db.query(Conversation)
            .join(Customer, Conversation.customer_id == Customer.id)
            .filter(
                Customer.pop_id == pop.id,
                Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]),
            )
            .count()
        )

        # Outstanding balance
        outstanding_result = (
            db.query(func.sum(Invoice.balance))
            .join(Customer, Invoice.customer_id == Customer.id)
            .filter(
                Customer.pop_id == pop.id,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            )
            .scalar()
        )

        churn_rate = (churned_customers / total_customers * 100) if total_customers > 0 else 0

        results.append({
            "id": pop.id,
            "name": pop.name,
            "code": pop.code,
            "city": pop.city,
            "total_customers": total_customers,
            "active_customers": active_customers,
            "churned_customers": churned_customers,
            "churn_rate": round(churn_rate, 2),
            "mrr": float(mrr_result or 0),
            "open_tickets": open_tickets,
            "outstanding": float(outstanding_result or 0),
            "currency": pop_currency,
        })

    # Sort by MRR descending
    results.sort(key=lambda x: x["mrr"], reverse=True)

    return results


@router.get("/support/metrics")
async def get_support_metrics(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get support/ticket metrics."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Total conversations in period
    total = db.query(Conversation).filter(Conversation.created_at >= start_date).count()

    # By status
    open_count = db.query(Conversation).filter(
        Conversation.created_at >= start_date,
        Conversation.status == ConversationStatus.OPEN,
    ).count()

    resolved_count = db.query(Conversation).filter(
        Conversation.created_at >= start_date,
        Conversation.status == ConversationStatus.RESOLVED,
    ).count()

    # Average response time
    avg_response = (
        db.query(func.avg(Conversation.first_response_time_seconds))
        .filter(
            Conversation.created_at >= start_date,
            Conversation.first_response_time_seconds.isnot(None),
        )
        .scalar()
    )

    # Average resolution time
    avg_resolution = (
        db.query(func.avg(Conversation.resolution_time_seconds))
        .filter(
            Conversation.created_at >= start_date,
            Conversation.resolution_time_seconds.isnot(None),
        )
        .scalar()
    )

    # By channel
    by_channel = (
        db.query(
            Conversation.channel,
            func.count(Conversation.id).label("count"),
        )
        .filter(Conversation.created_at >= start_date)
        .group_by(Conversation.channel)
        .all()
    )

    return {
        "period_days": days,
        "total_conversations": total,
        "open": open_count,
        "resolved": resolved_count,
        "resolution_rate": round(resolved_count / total * 100, 2) if total > 0 else 0,
        "avg_first_response_hours": round(float(avg_response or 0) / 3600, 2),
        "avg_resolution_hours": round(float(avg_resolution or 0) / 3600, 2),
        "by_channel": {c.channel: c.count for c in by_channel if c.channel},
    }


@router.get("/invoices/aging")
async def get_invoice_aging(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get invoice aging report."""
    now = datetime.utcnow()

    # Get unpaid invoices
    unpaid = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    ).all()

    aging = {
        "current": {"count": 0, "amount": 0},
        "1_30_days": {"count": 0, "amount": 0},
        "31_60_days": {"count": 0, "amount": 0},
        "61_90_days": {"count": 0, "amount": 0},
        "over_90_days": {"count": 0, "amount": 0},
    }

    for inv in unpaid:
        balance = float(inv.balance or inv.total_amount or 0)
        days = inv.days_overdue

        if days == 0:
            aging["current"]["count"] += 1
            aging["current"]["amount"] += balance
        elif days <= 30:
            aging["1_30_days"]["count"] += 1
            aging["1_30_days"]["amount"] += balance
        elif days <= 60:
            aging["31_60_days"]["count"] += 1
            aging["31_60_days"]["amount"] += balance
        elif days <= 90:
            aging["61_90_days"]["count"] += 1
            aging["61_90_days"]["amount"] += balance
        else:
            aging["over_90_days"]["count"] += 1
            aging["over_90_days"]["amount"] += balance

    total_outstanding = sum(a["amount"] for a in aging.values())

    return {
        "total_outstanding": total_outstanding,
        "aging": aging,
    }


@router.get("/customers/by-plan")
async def get_customers_by_plan(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get customer distribution by plan."""
    resolved_currency = _resolve_currency(db, [], currency)

    # MRR normalized by billing cycle
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    query = (
        db.query(
            Subscription.plan_name,
            func.count(Subscription.id).label("count"),
            func.sum(mrr_case).label("mrr"),
        )
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    if resolved_currency:
        query = query.filter(Subscription.currency == resolved_currency)

    plans = (
        query
        .group_by(Subscription.plan_name)
        .order_by(func.count(Subscription.id).desc())
        .all()
    )

    return [
        {
            "plan_name": p.plan_name,
            "customer_count": p.count,
            "mrr": float(p.mrr or 0),
        }
        for p in plans
    ]

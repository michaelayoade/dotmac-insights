from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case, and_, or_, desc, asc
from typing import Dict, Any, List, Optional, cast
from datetime import datetime, timedelta
from decimal import Decimal

from app.database import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.pop import Pop
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus, Territory
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.expense import Expense, ExpenseStatus
from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier, CostCenter
from app.models.employee import Employee, EmploymentStatus
from app.models.network_monitor import NetworkMonitor, MonitorState
from app.models.ipv4_network import IPv4Network
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


def _get_active_currencies(db: Session, filters: Optional[List[Any]] = None) -> set[str]:
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


def calculate_mrr(db: Session, filters: Optional[List[Any]] = None, currency: Optional[str] = None) -> float:
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


@cached("overview", ttl=CACHE_TTL["short"])
async def _get_overview_impl(currency: Optional[str], db: Session) -> Dict[str, Any]:
    """Implementation of overview metrics (cached)."""
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
    pop_count = db.query(Pop).filter(Pop.is_active.is_(True)).count()

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


@router.get("/overview", dependencies=[Depends(Require("analytics:read"))])
async def get_overview(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get high-level overview metrics."""
    return await _get_overview_impl(currency, db)


@router.get("/revenue/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly revenue trend from payments."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    payments = (
        db.query(
            extract("year", Payment.payment_date).label("year"),
            extract("month", Payment.payment_date).label("month"),
            func.sum(Payment.amount).label("total"),
            func.count(Payment.id).label("count"),
        )
        .filter(
            Payment.payment_date >= start_dt,
            Payment.payment_date <= end_dt,
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


@router.get("/churn/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_churn_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly churn trend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    churns = (
        db.query(
            extract("year", Customer.cancellation_date).label("year"),
            extract("month", Customer.cancellation_date).label("month"),
            func.count(Customer.id).label("count"),
        )
        .filter(
            Customer.cancellation_date >= start_dt,
            Customer.cancellation_date <= end_dt,
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


@cached("pop_performance", ttl=CACHE_TTL["long"])
async def _get_pop_performance_impl(currency: Optional[str], db: Session) -> List[Dict[str, Any]]:
    """Implementation of POP performance metrics (cached - expensive query)."""
    pops = db.query(Pop).filter(Pop.is_active.is_(True)).all()

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
    results.sort(key=lambda x: cast(float, x.get("mrr", 0.0)), reverse=True)

    return results


@router.get("/pop/performance", dependencies=[Depends(Require("analytics:read"))])
async def get_pop_performance(
    currency: Optional[str] = Query(default=None, description="Currency code to use for MRR calculations"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get performance metrics by POP."""
    return await _get_pop_performance_impl(currency, db)


@router.get("/support/metrics", dependencies=[Depends(Require("analytics:read"))])
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


@router.get("/invoices/aging", dependencies=[Depends(Require("analytics:read"))])
async def get_invoice_aging(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get invoice aging report."""
    # Get unpaid invoices
    unpaid = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
    ).all()

    aging: Dict[str, Dict[str, float]] = {
        "current": {"count": 0.0, "amount": 0.0},
        "1_30_days": {"count": 0.0, "amount": 0.0},
        "31_60_days": {"count": 0.0, "amount": 0.0},
        "61_90_days": {"count": 0.0, "amount": 0.0},
        "over_90_days": {"count": 0.0, "amount": 0.0},
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


@router.get("/customers/by-plan", dependencies=[Depends(Require("analytics:read"))])
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


# ==============================================================================
# Revenue Quality Analytics
# ==============================================================================


@cached("dso", ttl=CACHE_TTL["long"])
async def _get_dso_impl(months: int, db: Session) -> Dict[str, Any]:
    """Implementation of DSO calculation (cached - expensive monthly iteration)."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)

    results = []

    for i in range(months):
        period_start = start_date + timedelta(days=i * 30)
        period_end = period_start + timedelta(days=30)

        # Total invoiced in period
        invoiced = (
            db.query(func.sum(Invoice.total_amount))
            .filter(
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date < period_end,
            )
            .scalar()
        ) or Decimal("0")

        # Average receivables (outstanding balance at period end)
        avg_receivables = (
            db.query(func.sum(Invoice.balance))
            .filter(
                Invoice.invoice_date < period_end,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
            )
            .scalar()
        ) or Decimal("0")

        # DSO = (Average Receivables / Revenue) * Days in Period
        dso = float((avg_receivables / invoiced) * 30) if invoiced > 0 else 0

        results.append({
            "year": period_start.year,
            "month": period_start.month,
            "period": f"{period_start.year}-{period_start.month:02d}",
            "dso": round(dso, 1),
            "invoiced": float(invoiced),
            "outstanding": float(avg_receivables),
        })

    return {
        "trend": results,
        "current_dso": results[-1]["dso"] if results else 0,
        "average_dso": round(sum(r["dso"] for r in results) / len(results), 1) if results else 0,
    }


@router.get("/revenue/dso", dependencies=[Depends(Require("analytics:read"))])
async def get_days_sales_outstanding(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate Days Sales Outstanding (DSO) trend - measures collection efficiency."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

        results = []
        current = start_dt
        while current < end_dt:
            period_end = min(current + timedelta(days=30), end_dt)

            invoiced = (
                db.query(func.sum(Invoice.total_amount))
                .filter(
                    Invoice.invoice_date >= current,
                    Invoice.invoice_date < period_end,
                )
                .scalar()
            ) or Decimal("0")

            avg_receivables = (
                db.query(func.sum(Invoice.balance))
                .filter(
                    Invoice.invoice_date < period_end,
                    Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
                )
                .scalar()
            ) or Decimal("0")

            dso = float((avg_receivables / invoiced) * 30) if invoiced > 0 else 0

            results.append({
                "year": current.year,
                "month": current.month,
                "period": f"{current.year}-{current.month:02d}",
                "dso": round(dso, 1),
                "invoiced": float(invoiced),
                "outstanding": float(avg_receivables),
            })

            current = period_end

        return {
            "trend": results,
            "current_dso": results[-1]["dso"] if results else 0,
            "average_dso": round(sum(r["dso"] for r in results) / len(results), 1) if results else 0,
        }

    return await _get_dso_impl(months, db)


@router.get("/revenue/by-territory", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_by_territory(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get MRR and customer distribution by territory/region."""
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    # Group by customer type (territory approximation for ISP)
    by_type = (
        db.query(
            Customer.customer_type,
            func.count(func.distinct(Customer.id)).label("customer_count"),
            func.sum(mrr_case).label("mrr"),
        )
        .join(Subscription, Subscription.customer_id == Customer.id)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .group_by(Customer.customer_type)
        .all()
    )

    return [
        {
            "territory": t.customer_type or "Unknown",
            "customer_count": t.customer_count,
            "mrr": float(t.mrr or 0),
        }
        for t in by_type
    ]


@router.get("/revenue/cohort", dependencies=[Depends(Require("analytics:read"))])
async def get_revenue_cohort(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze revenue by customer signup cohort."""
    from sqlalchemy import literal_column

    # Define cohort expression once and reference by label in GROUP BY
    cohort_expr = func.to_char(func.date_trunc('month', Customer.signup_date), 'YYYY-MM')

    cohorts = (
        db.query(
            cohort_expr.label("cohort_month"),
            func.count(Customer.id).label("total_customers"),
            func.sum(case((Customer.status == CustomerStatus.ACTIVE, 1), else_=0)).label("active"),
            func.sum(case((Customer.status == CustomerStatus.CANCELLED, 1), else_=0)).label("churned"),
        )
        .filter(Customer.signup_date.isnot(None))
        .group_by(literal_column("1"))  # Group by first column (cohort_month)
        .order_by(literal_column("1"))
        .all()
    )

    results = []
    for c in cohorts:
        if c.cohort_month:
            retention = (c.active / c.total_customers * 100) if c.total_customers > 0 else 0
            results.append({
                "cohort": c.cohort_month,
                "total_customers": c.total_customers,
                "active": c.active,
                "churned": c.churned,
                "retention_rate": round(retention, 1),
            })

    return {
        "cohorts": results[-12:],  # Last 12 cohorts
        "summary": {
            "avg_retention": round(sum(r["retention_rate"] for r in results) / len(results), 1) if results else 0,
            "total_cohorts": len(results),
        }
    }


# ==============================================================================
# Collections & Risk Analytics
# ==============================================================================


@router.get("/collections/aging-by-segment", dependencies=[Depends(Require("analytics:read"))])
async def get_aging_by_segment(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get invoice aging breakdown by customer segment (type)."""
    segments: Dict[str, Dict[str, Any]] = {}

    # Get all unpaid invoices with customer info
    unpaid = (
        db.query(Invoice, Customer.customer_type)
        .join(Customer, Invoice.customer_id == Customer.id)
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
        .all()
    )

    for inv, customer_type in unpaid:
        segment = customer_type or "Unknown"
        if segment not in segments:
            segments[segment] = {
                "current": {"count": 0, "amount": 0.0},
                "1_30_days": {"count": 0, "amount": 0.0},
                "31_60_days": {"count": 0, "amount": 0.0},
                "61_90_days": {"count": 0, "amount": 0.0},
                "over_90_days": {"count": 0, "amount": 0.0},
                "total": {"count": 0, "amount": 0.0},
            }

        balance = float(inv.balance or inv.total_amount or 0)
        days = inv.days_overdue

        segments[segment]["total"]["count"] += 1
        segments[segment]["total"]["amount"] += balance

        if days == 0:
            bucket = "current"
        elif days <= 30:
            bucket = "1_30_days"
        elif days <= 60:
            bucket = "31_60_days"
        elif days <= 90:
            bucket = "61_90_days"
        else:
            bucket = "over_90_days"

        segments[segment][bucket]["count"] += 1
        segments[segment][bucket]["amount"] += balance

    return {
        "by_segment": segments,
        "total_outstanding": sum(s["total"]["amount"] for s in segments.values()),
    }


@router.get("/collections/credit-notes", dependencies=[Depends(Require("analytics:read"))])
async def get_credit_notes_summary(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get credit notes issued trend and summary."""
    start_date = datetime.utcnow() - timedelta(days=months * 30)

    # Monthly trend
    trend = (
        db.query(
            extract("year", CreditNote.issue_date).label("year"),
            extract("month", CreditNote.issue_date).label("month"),
            func.count(CreditNote.id).label("count"),
            func.sum(CreditNote.amount).label("total"),
        )
        .filter(CreditNote.issue_date >= start_date)
        .group_by(
            extract("year", CreditNote.issue_date),
            extract("month", CreditNote.issue_date),
        )
        .order_by(
            extract("year", CreditNote.issue_date),
            extract("month", CreditNote.issue_date),
        )
        .all()
    )

    # Summary by status
    by_status = (
        db.query(
            CreditNote.status,
            func.count(CreditNote.id).label("count"),
            func.sum(CreditNote.amount).label("total"),
        )
        .group_by(CreditNote.status)
        .all()
    )

    return {
        "trend": [
            {
                "year": int(t.year),
                "month": int(t.month),
                "period": f"{int(t.year)}-{int(t.month):02d}",
                "count": t.count,
                "total": float(t.total or 0),
            }
            for t in trend
        ],
        "by_status": {s.status.value: {"count": s.count, "total": float(s.total or 0)} for s in by_status},
        "total_issued": sum(float(t.total or 0) for t in trend),
    }


# ==============================================================================
# Sales Pipeline Analytics
# ==============================================================================


@cached("sales_pipeline", ttl=CACHE_TTL["medium"])
async def _get_sales_pipeline_impl(db: Session) -> Dict[str, Any]:
    """Implementation of sales pipeline metrics (cached)."""
    # Quotations summary
    quotations = (
        db.query(
            Quotation.status,
            func.count(Quotation.id).label("count"),
            func.sum(Quotation.grand_total).label("value"),
        )
        .group_by(Quotation.status)
        .all()
    )

    # Sales Orders summary
    orders = (
        db.query(
            SalesOrder.status,
            func.count(SalesOrder.id).label("count"),
            func.sum(SalesOrder.grand_total).label("value"),
        )
        .group_by(SalesOrder.status)
        .all()
    )

    # Calculate conversion rates
    total_quotations = sum(q.count for q in quotations)
    ordered_quotations = sum(q.count for q in quotations if q.status == QuotationStatus.ORDERED)
    completed_orders = sum(o.count for o in orders if o.status == SalesOrderStatus.COMPLETED)

    return {
        "quotations": {
            "by_status": {q.status.value: {"count": q.count, "value": float(q.value or 0)} for q in quotations},
            "total": total_quotations,
            "total_value": sum(float(q.value or 0) for q in quotations),
        },
        "orders": {
            "by_status": {o.status.value: {"count": o.count, "value": float(o.value or 0)} for o in orders},
            "total": sum(o.count for o in orders),
            "total_value": sum(float(o.value or 0) for o in orders),
        },
        "conversion": {
            "quotation_to_order_rate": round(ordered_quotations / total_quotations * 100, 1) if total_quotations > 0 else 0,
            "orders_completed": completed_orders,
        },
    }


@router.get("/sales/pipeline", dependencies=[Depends(Require("analytics:read"))])
async def get_sales_pipeline(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get sales pipeline funnel: Quotations → Orders → Invoices."""
    return await _get_sales_pipeline_impl(db)


@router.get("/sales/quotation-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_quotation_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly quotation creation and conversion trend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    trend = (
        db.query(
            extract("year", Quotation.transaction_date).label("year"),
            extract("month", Quotation.transaction_date).label("month"),
            func.count(Quotation.id).label("total"),
            func.sum(case((Quotation.status == QuotationStatus.ORDERED, 1), else_=0)).label("converted"),
            func.sum(case((Quotation.status == QuotationStatus.LOST, 1), else_=0)).label("lost"),
            func.sum(Quotation.grand_total).label("value"),
        )
        .filter(Quotation.transaction_date >= start_dt, Quotation.transaction_date <= end_dt)
        .group_by(
            extract("year", Quotation.transaction_date),
            extract("month", Quotation.transaction_date),
        )
        .order_by(
            extract("year", Quotation.transaction_date),
            extract("month", Quotation.transaction_date),
        )
        .all()
    )

    return [
        {
            "year": int(t.year),
            "month": int(t.month),
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "total": t.total,
            "converted": t.converted,
            "lost": t.lost,
            "value": float(t.value or 0),
            "conversion_rate": round(t.converted / t.total * 100, 1) if t.total > 0 else 0,
        }
        for t in trend
    ]


# ==============================================================================
# Support/SLA Analytics
# ==============================================================================


@cached("sla_attainment", ttl=CACHE_TTL["medium"])
async def _get_sla_attainment_impl(days: int, db: Session) -> Dict[str, Any]:
    """Implementation of SLA attainment metrics (cached - fetches all tickets)."""
    start_date = datetime.utcnow() - timedelta(days=days)

    tickets = db.query(Ticket).filter(Ticket.created_at >= start_date).all()

    total = len(tickets)
    resolved_in_sla = 0
    overdue = 0
    response_times = []
    resolution_times = []

    for t in tickets:
        # Check SLA compliance
        if t.resolution_by and t.resolution_date:
            if t.resolution_date <= t.resolution_by:
                resolved_in_sla += 1
            else:
                overdue += 1

        # Collect timing metrics
        if t.time_to_resolution_hours:
            resolution_times.append(t.time_to_resolution_hours)

        if t.first_responded_on and t.opening_date:
            response_hours = (t.first_responded_on - t.opening_date).total_seconds() / 3600
            response_times.append(response_hours)

    # By priority breakdown
    by_priority = (
        db.query(
            Ticket.priority,
            func.count(Ticket.id).label("count"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(Ticket.priority)
        .all()
    )

    return {
        "period_days": days,
        "total_tickets": total,
        "sla_attainment": {
            "met": resolved_in_sla,
            "breached": overdue,
            "rate": round(resolved_in_sla / (resolved_in_sla + overdue) * 100, 1) if (resolved_in_sla + overdue) > 0 else 0,
        },
        "avg_response_hours": round(sum(response_times) / len(response_times), 2) if response_times else 0,
        "avg_resolution_hours": round(sum(resolution_times) / len(resolution_times), 2) if resolution_times else 0,
        "by_priority": {p.priority.value: p.count for p in by_priority},
    }


@router.get("/support/sla-attainment", dependencies=[Depends(Require("analytics:read"))])
async def get_sla_attainment(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get SLA attainment metrics for tickets."""
    return await _get_sla_attainment_impl(days, db)


@router.get("/support/agent-productivity", dependencies=[Depends(Require("analytics:read"))])
async def get_agent_productivity(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get ticket handling metrics by assigned employee/agent."""
    start_date = datetime.utcnow() - timedelta(days=days)

    agents = (
        db.query(
            Employee.id,
            Employee.name,
            Employee.department,
            func.count(Ticket.id).label("total_tickets"),
            func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
            func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
            func.avg(
                func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600
            ).label("avg_resolution_hours"),
        )
        .join(Ticket, Ticket.assigned_employee_id == Employee.id)
        .filter(Ticket.created_at >= start_date)
        .group_by(Employee.id, Employee.name, Employee.department)
        .order_by(desc("total_tickets"))
        .all()
    )

    return [
        {
            "employee_id": a.id,
            "name": a.name,
            "department": a.department,
            "total_tickets": a.total_tickets,
            "resolved": a.resolved or 0,
            "closed": a.closed or 0,
            "resolution_rate": round((a.resolved or 0) / a.total_tickets * 100, 1) if a.total_tickets > 0 else 0,
            "avg_resolution_hours": round(float(a.avg_resolution_hours or 0), 2),
        }
        for a in agents
    ]


@router.get("/support/by-type", dependencies=[Depends(Require("analytics:read"))])
async def get_tickets_by_type(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ticket distribution by type/category."""
    start_date = datetime.utcnow() - timedelta(days=days)

    by_type = (
        db.query(
            Ticket.ticket_type,
            func.count(Ticket.id).label("count"),
            func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(Ticket.ticket_type)
        .order_by(desc("count"))
        .all()
    )

    return {
        "by_type": [
            {
                "type": t.ticket_type or "Unclassified",
                "count": t.count,
                "resolved": t.resolved or 0,
                "resolution_rate": round((t.resolved or 0) / t.count * 100, 1) if t.count > 0 else 0,
            }
            for t in by_type
        ],
        "total": sum(t.count for t in by_type),
    }


# ==============================================================================
# Network/Service Analytics
# ==============================================================================


@router.get("/network/device-status", dependencies=[Depends(Require("analytics:read"))])
async def get_network_device_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get network device status summary."""
    devices = db.query(NetworkMonitor).filter(NetworkMonitor.active == True).all()

    total = len(devices)
    up = sum(1 for d in devices if d.ping_state == MonitorState.UP)
    down = sum(1 for d in devices if d.ping_state == MonitorState.DOWN)
    unknown = sum(1 for d in devices if d.ping_state == MonitorState.UNKNOWN)

    # By location
    by_location = (
        db.query(
            NetworkMonitor.location_id,
            func.count(NetworkMonitor.id).label("total"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.UP, 1), else_=0)).label("up"),
            func.sum(case((NetworkMonitor.ping_state == MonitorState.DOWN, 1), else_=0)).label("down"),
        )
        .filter(NetworkMonitor.active == True)
        .group_by(NetworkMonitor.location_id)
        .all()
    )

    return {
        "summary": {
            "total": total,
            "up": up,
            "down": down,
            "unknown": unknown,
            "uptime_percent": round(up / total * 100, 1) if total > 0 else 0,
        },
        "by_location": [
            {
                "location_id": loc.location_id,
                "total": loc.total,
                "up": loc.up or 0,
                "down": loc.down or 0,
            }
            for loc in by_location if loc.location_id
        ],
    }


@router.get("/network/ip-utilization", dependencies=[Depends(Require("analytics:read"))])
async def get_ip_utilization(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get IP address pool utilization."""
    networks = db.query(IPv4Network).all()

    results = []
    total_capacity = 0
    total_used = 0

    for net in networks:
        # Calculate capacity based on mask
        capacity = 2 ** (32 - net.mask) - 2 if net.mask < 31 else 2 ** (32 - net.mask)
        used = net.used or 0

        total_capacity += capacity
        total_used += used

        results.append({
            "network": net.cidr,
            "title": net.title,
            "type": net.type_of_usage,
            "capacity": capacity,
            "used": used,
            "available": capacity - used,
            "utilization_percent": round(used / capacity * 100, 1) if capacity > 0 else 0,
        })

    # Sort by utilization
    results.sort(key=lambda x: x["utilization_percent"], reverse=True)

    return {
        "networks": results[:20],  # Top 20 by utilization
        "summary": {
            "total_networks": len(networks),
            "total_capacity": total_capacity,
            "total_used": total_used,
            "total_available": total_capacity - total_used,
            "overall_utilization": round(total_used / total_capacity * 100, 1) if total_capacity > 0 else 0,
        },
    }


# ==============================================================================
# Expense/Cost Analytics
# ==============================================================================


@router.get("/expenses/by-category", dependencies=[Depends(Require("analytics:read"))])
async def get_expenses_by_category(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense breakdown by category."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    by_category = (
        db.query(
            Expense.category,
            func.count(Expense.id).label("count"),
            func.sum(Expense.total_sanctioned_amount).label("total"),
        )
        .filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(Expense.category)
        .order_by(desc("total"))
        .all()
    )

    return {
        "by_category": [
            {
                "category": c.category or "Uncategorized",
                "count": c.count,
                "total": float(c.total or 0),
            }
            for c in by_category
        ],
        "total_expenses": sum(float(c.total or 0) for c in by_category),
    }


@router.get("/expenses/by-cost-center", dependencies=[Depends(Require("analytics:read"))])
async def get_expenses_by_cost_center(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get expense breakdown by cost center (department)."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    by_cost_center = (
        db.query(
            Expense.cost_center,
            func.count(Expense.id).label("count"),
            func.sum(Expense.total_sanctioned_amount).label("total"),
        )
        .filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(Expense.cost_center)
        .order_by(desc("total"))
        .all()
    )

    return {
        "by_cost_center": [
            {
                "cost_center": cc.cost_center or "Unassigned",
                "count": cc.count,
                "total": float(cc.total or 0),
            }
            for cc in by_cost_center
        ],
        "total_expenses": sum(float(cc.total or 0) for cc in by_cost_center),
    }


@router.get("/expenses/trend", dependencies=[Depends(Require("analytics:read"))])
async def get_expense_trend(
    months: int = Query(default=12, le=24),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly expense trend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    trend = (
        db.query(
            extract("year", Expense.expense_date).label("year"),
            extract("month", Expense.expense_date).label("month"),
            func.count(Expense.id).label("count"),
            func.sum(Expense.total_sanctioned_amount).label("total"),
        )
        .filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(
            extract("year", Expense.expense_date),
            extract("month", Expense.expense_date),
        )
        .order_by(
            extract("year", Expense.expense_date),
            extract("month", Expense.expense_date),
        )
        .all()
    )

    return [
        {
            "year": int(t.year),
            "month": int(t.month),
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "count": t.count,
            "total": float(t.total or 0),
        }
        for t in trend
    ]


@router.get("/expenses/vendor-spend", dependencies=[Depends(Require("analytics:read"))])
async def get_vendor_spend(
    months: int = Query(default=12, le=24),
    limit: int = Query(default=20, le=50),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get top vendors by purchase invoice spend."""
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=months * 30)

    vendors = (
        db.query(
            PurchaseInvoice.supplier,
            PurchaseInvoice.supplier_name,
            func.count(PurchaseInvoice.id).label("invoice_count"),
            func.sum(PurchaseInvoice.grand_total).label("total_spend"),
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        )
        .filter(
            PurchaseInvoice.posting_date >= start_dt,
            PurchaseInvoice.posting_date <= end_dt,
            PurchaseInvoice.docstatus == 1,  # Submitted
        )
        .group_by(PurchaseInvoice.supplier, PurchaseInvoice.supplier_name)
        .order_by(desc("total_spend"))
        .limit(limit)
        .all()
    )

    return {
        "vendors": [
            {
                "supplier": v.supplier,
                "supplier_name": v.supplier_name,
                "invoice_count": v.invoice_count,
                "total_spend": float(v.total_spend or 0),
                "outstanding": float(v.outstanding or 0),
            }
            for v in vendors
        ],
        "total_spend": sum(float(v.total_spend or 0) for v in vendors),
    }


# ==============================================================================
# People/Operations Analytics
# ==============================================================================


@router.get("/people/tickets-per-employee", dependencies=[Depends(Require("analytics:read"))])
async def get_tickets_per_employee(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ticket handling distribution per employee."""
    start_date = datetime.utcnow() - timedelta(days=days)

    by_employee = (
        db.query(
            Employee.id,
            Employee.name,
            Employee.department,
            func.count(Ticket.id).label("total_tickets"),
            func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label("open"),
        )
        .outerjoin(Ticket, and_(
            Ticket.assigned_employee_id == Employee.id,
            Ticket.created_at >= start_date,
        ))
        .filter(Employee.status == EmploymentStatus.ACTIVE)
        .group_by(Employee.id, Employee.name, Employee.department)
        .order_by(desc("total_tickets"))
        .all()
    )

    # Calculate averages
    total_tickets = sum(e.total_tickets or 0 for e in by_employee)
    active_employees = len([e for e in by_employee if (e.total_tickets or 0) > 0])

    return {
        "by_employee": [
            {
                "employee_id": e.id,
                "name": e.name,
                "department": e.department,
                "total_tickets": e.total_tickets or 0,
                "resolved": e.resolved or 0,
                "open": e.open or 0,
            }
            for e in by_employee[:20]  # Top 20
        ],
        "summary": {
            "total_tickets": total_tickets,
            "active_employees": active_employees,
            "avg_tickets_per_employee": round(total_tickets / active_employees, 1) if active_employees > 0 else 0,
        },
    }


@router.get("/people/by-department", dependencies=[Depends(Require("analytics:read"))])
async def get_metrics_by_department(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get ticket and expense metrics aggregated by department."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Employee counts by department
    employee_counts = (
        db.query(
            Employee.department,
            func.count(Employee.id).label("employee_count"),
        )
        .filter(Employee.status == EmploymentStatus.ACTIVE)
        .group_by(Employee.department)
        .all()
    )

    # Tickets by department (through assigned employee)
    ticket_counts = (
        db.query(
            Employee.department,
            func.count(Ticket.id).label("ticket_count"),
        )
        .join(Ticket, Ticket.assigned_employee_id == Employee.id)
        .filter(Ticket.created_at >= start_date)
        .group_by(Employee.department)
        .all()
    )

    # Expenses by department (cost center approximation)
    expense_totals = (
        db.query(
            Expense.cost_center,
            func.sum(Expense.total_sanctioned_amount).label("expense_total"),
        )
        .filter(
            Expense.expense_date >= start_date,
            Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
        )
        .group_by(Expense.cost_center)
        .all()
    )

    # Combine data
    departments: Dict[str, Dict[str, Any]] = {}

    for ec in employee_counts:
        dept = ec.department or "Unassigned"
        departments[dept] = {
            "department": dept,
            "employee_count": ec.employee_count,
            "ticket_count": 0,
            "expense_total": 0.0,
        }

    for tc in ticket_counts:
        dept = tc.department or "Unassigned"
        if dept in departments:
            departments[dept]["ticket_count"] = tc.ticket_count

    for et in expense_totals:
        # Try to match cost center to department
        cost_center = et.cost_center or "Unassigned"
        if cost_center in departments:
            departments[cost_center]["expense_total"] = float(et.expense_total or 0)

    return list(departments.values())

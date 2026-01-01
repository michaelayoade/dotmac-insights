"""
Analytics Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, extract, case, distinct, Date, select
from typing import Dict, Any, Optional, List
from itertools import groupby
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.pop import Pop
from app.models.router import Router
from app.models.customer_usage import CustomerUsage
from app.models.credit_note import CreditNote
from app.models.project import Project, ProjectStatus
from app.models.ipv4_address import IPv4Address
from app.models.customer_note import CustomerNote
from app.models.ticket_message import TicketMessage
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.api.customers.common import _calculate_tenure_days, _parse_date, _normalize_status

router = APIRouter()

# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/blocked", dependencies=[Depends(Require("analytics:read"))])
@cached("customers-blocked-analytics", ttl=CACHE_TTL["short"])
async def get_blocked_analytics(
    days: int = Query(default=90, le=365, description="Analysis period in days"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Comprehensive blocked customer analytics for recovery targeting.

    Provides insights on:
    - Overview: Total blocked, MRR at risk, trends
    - By tenure: How long were they customers before blocking
    - By plan: Which plans have highest blocking rates
    - By location: Geographic distribution of blocked customers
    - By days blocked: Segmentation by blocking duration
    - Recovery candidates: Recent blocks with good payment history
    - Top at risk: Highest MRR blocked customers
    """
    today = date.today()
    period_start = today - timedelta(days=days)

    # -------------------------------------------------------------------------
    # OVERVIEW - Total blocked customers and MRR at risk
    # -------------------------------------------------------------------------
    blocked_customers = db.query(Customer).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).all()

    total_blocked = len(blocked_customers)
    total_mrr_at_risk = sum(float(c.mrr or 0) for c in blocked_customers)

    # Blocked in last 30/60/90 days (by looking at subscription end dates or status change)
    # We'll use subscription end_date as proxy for when blocking occurred
    blocked_recent = db.query(
        func.sum(case((Subscription.end_date >= today - timedelta(days=30), 1), else_=0)).label("last_30d"),
        func.sum(case((and_(Subscription.end_date >= today - timedelta(days=60), Subscription.end_date < today - timedelta(days=30)), 1), else_=0)).label("days_30_60"),
        func.sum(case((and_(Subscription.end_date >= today - timedelta(days=90), Subscription.end_date < today - timedelta(days=60)), 1), else_=0)).label("days_60_90"),
    ).join(Customer).filter(
        Customer.status == CustomerStatus.SUSPENDED,
        Subscription.end_date.isnot(None),
    ).first()

    # Active vs blocked ratio
    active_count = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    overview = {
        "total_blocked": total_blocked,
        "total_mrr_at_risk": total_mrr_at_risk,
        "active_customers": active_count,
        "blocked_rate": round(total_blocked / (total_blocked + active_count) * 100, 2) if (total_blocked + active_count) > 0 else 0,
        "blocked_by_period": {
            "last_30_days": int(blocked_recent.last_30d or 0) if blocked_recent else 0,
            "30_to_60_days": int(blocked_recent.days_30_60 or 0) if blocked_recent else 0,
            "60_to_90_days": int(blocked_recent.days_60_90 or 0) if blocked_recent else 0,
        },
    }

    # -------------------------------------------------------------------------
    # BY TENURE - How long were they customers before blocking
    # -------------------------------------------------------------------------
    tenure_buckets = db.query(
        case(
            (func.date_part("day", func.current_date() - Customer.signup_date) < 30, "0-30 days"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 90, "1-3 months"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 180, "3-6 months"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 365, "6-12 months"),
            else_="12+ months"
        ).label("tenure_bucket"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.status == CustomerStatus.SUSPENDED,
        Customer.signup_date.isnot(None),
    ).group_by("tenure_bucket").all()

    by_tenure = [
        {"tenure": t.tenure_bucket, "count": t.count, "mrr": float(t.mrr or 0)}
        for t in tenure_buckets
    ]

    # -------------------------------------------------------------------------
    # BY PLAN - Which plans have highest blocking
    # -------------------------------------------------------------------------
    # Get last active plan for blocked customers
    last_plan_sub = (
        db.query(
            Subscription.customer_id,
            Subscription.plan_name,
            Subscription.price,
            func.row_number().over(
                partition_by=Subscription.customer_id,
                order_by=Subscription.end_date.desc()
            ).label("rn")
        )
        .filter(Subscription.end_date.isnot(None))
        .subquery()
    )

    plan_stats = db.query(
        last_plan_sub.c.plan_name,
        func.count(Customer.id).label("blocked_count"),
        func.sum(last_plan_sub.c.price).label("mrr_at_risk"),
    ).join(Customer, Customer.id == last_plan_sub.c.customer_id).filter(
        Customer.status == CustomerStatus.SUSPENDED,
        last_plan_sub.c.rn == 1,
    ).group_by(last_plan_sub.c.plan_name).order_by(func.count(Customer.id).desc()).limit(10).all()

    by_plan = [
        {"plan": p.plan_name or "Unknown", "count": p.blocked_count, "mrr": float(p.mrr_at_risk or 0)}
        for p in plan_stats
    ]

    # -------------------------------------------------------------------------
    # BY LOCATION - Geographic distribution
    # -------------------------------------------------------------------------
    location_stats = db.query(
        Pop.name.label("pop_name"),
        Pop.id.label("pop_id"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).join(Pop, Pop.id == Customer.pop_id, isouter=True).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).group_by(Pop.id, Pop.name).order_by(func.count(Customer.id).desc()).all()

    by_location = [
        {"pop_id": l.pop_id, "pop_name": l.pop_name or "Unknown", "count": l.count, "mrr": float(l.mrr or 0)}
        for l in location_stats
    ]

    # -------------------------------------------------------------------------
    # BY DAYS BLOCKED - Segmentation by duration
    # -------------------------------------------------------------------------
    # Use last subscription end_date as proxy for blocking date
    days_blocked_sub = (
        db.query(
            Subscription.customer_id,
            func.max(Subscription.end_date).label("blocked_since"),
        )
        .filter(Subscription.end_date.isnot(None))
        .group_by(Subscription.customer_id)
        .subquery()
    )

    duration_stats = db.query(
        case(
            (func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 7, "0-7 days"),
            (func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 14, "8-14 days"),
            (func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 30, "15-30 days"),
            (func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 60, "31-60 days"),
            (func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 90, "61-90 days"),
            else_="90+ days"
        ).label("duration_bucket"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).join(days_blocked_sub, days_blocked_sub.c.customer_id == Customer.id).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).group_by("duration_bucket").all()

    by_duration = [
        {"duration": d.duration_bucket, "count": d.count, "mrr": float(d.mrr or 0)}
        for d in duration_stats
    ]

    # -------------------------------------------------------------------------
    # RECOVERY CANDIDATES - Recent blocks with good payment history
    # -------------------------------------------------------------------------
    # Customers blocked <= 30 days with prior payment history
    payment_history = (
        db.query(
            Payment.customer_id,
            func.count(Payment.id).label("payment_count"),
            func.sum(Payment.amount).label("total_paid"),
            func.max(Payment.payment_date).label("last_payment"),
        )
        .filter(Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]))
        .group_by(Payment.customer_id)
        .subquery()
    )

    recovery_candidates = (
        db.query(
            Customer,
            days_blocked_sub.c.blocked_since,
            payment_history.c.payment_count,
            payment_history.c.total_paid,
            payment_history.c.last_payment,
        )
        .join(days_blocked_sub, days_blocked_sub.c.customer_id == Customer.id)
        .join(payment_history, payment_history.c.customer_id == Customer.id, isouter=True)
        .filter(
            Customer.status == CustomerStatus.SUSPENDED,
            func.date_part("day", func.current_date() - days_blocked_sub.c.blocked_since) <= 30,
        )
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    recovery_list = [
        {
            "id": r.Customer.id,
            "name": r.Customer.name,
            "email": r.Customer.email,
            "phone": r.Customer.phone,
            "mrr": float(r.Customer.mrr or 0),
            "blocked_since": r.blocked_since.isoformat() if r.blocked_since else None,
            "days_blocked": (today - r.blocked_since.date()).days if r.blocked_since else None,
            "payment_history": {
                "total_payments": r.payment_count or 0,
                "total_paid": float(r.total_paid or 0),
                "last_payment": r.last_payment.isoformat() if r.last_payment else None,
            },
        }
        for r in recovery_candidates
    ]

    # -------------------------------------------------------------------------
    # TOP AT RISK - Highest MRR blocked customers
    # -------------------------------------------------------------------------
    top_at_risk = (
        db.query(
            Customer,
            days_blocked_sub.c.blocked_since,
            last_plan_sub.c.plan_name,
        )
        .join(days_blocked_sub, days_blocked_sub.c.customer_id == Customer.id, isouter=True)
        .join(last_plan_sub, and_(last_plan_sub.c.customer_id == Customer.id, last_plan_sub.c.rn == 1), isouter=True)
        .filter(Customer.status == CustomerStatus.SUSPENDED)
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    top_risk_list = [
        {
            "id": t.Customer.id,
            "name": t.Customer.name,
            "email": t.Customer.email,
            "phone": t.Customer.phone,
            "mrr": float(t.Customer.mrr or 0),
            "last_plan": t.plan_name,
            "blocked_since": t.blocked_since.isoformat() if t.blocked_since else None,
            "days_blocked": (today - t.blocked_since.date()).days if t.blocked_since else None,
            "tenure_days": _calculate_tenure_days(t.Customer.signup_date),
        }
        for t in top_at_risk
    ]

    return {
        "overview": overview,
        "by_tenure": by_tenure,
        "by_plan": by_plan,
        "by_location": by_location,
        "by_duration": by_duration,
        "recovery_candidates": recovery_list,
        "top_at_risk": top_risk_list,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/active", dependencies=[Depends(Require("analytics:read"))])
@cached("customers-active-analytics", ttl=CACHE_TTL["short"])
async def get_active_analytics(
    days: int = Query(default=30, le=90, description="Lookback period for activity analysis"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Comprehensive active customer analytics with service health indicators.

    Provides insights on:
    - Overview: Total active, MRR, growth metrics
    - By tenure: Customer age distribution
    - By plan: Plan distribution among active customers
    - By location: POP distribution
    - Service health: Customers with potential service issues
    - Payment risk: Active customers with billing concerns
    - Top customers: Highest MRR active customers
    """
    today = date.today()
    lookback_start = today - timedelta(days=days)

    # -------------------------------------------------------------------------
    # OVERVIEW - Active customer metrics
    # -------------------------------------------------------------------------
    active_customers = db.query(Customer).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).all()

    total_active = len(active_customers)
    total_mrr = sum(float(c.mrr or 0) for c in active_customers)

    # New customers in last 30 days
    new_30d = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.signup_date >= today - timedelta(days=30),
    ).scalar() or 0

    # Active customer counts by type
    by_type = db.query(
        Customer.customer_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).group_by(Customer.customer_type).all()

    overview = {
        "total_active": total_active,
        "total_mrr": total_mrr,
        "avg_mrr": round(total_mrr / total_active, 2) if total_active > 0 else 0,
        "new_last_30_days": new_30d,
        "by_type": [
            {"type": t.customer_type.value if t.customer_type else "unknown", "count": t.count, "mrr": float(t.mrr or 0)}
            for t in by_type
        ],
    }

    # -------------------------------------------------------------------------
    # BY TENURE - Customer age distribution
    # -------------------------------------------------------------------------
    tenure_buckets = db.query(
        case(
            (func.date_part("day", func.current_date() - Customer.signup_date) < 30, "0-30 days"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 90, "1-3 months"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 180, "3-6 months"),
            (func.date_part("day", func.current_date() - Customer.signup_date) < 365, "6-12 months"),
            else_="12+ months"
        ).label("tenure_bucket"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.signup_date.isnot(None),
    ).group_by("tenure_bucket").all()

    by_tenure = [
        {"tenure": t.tenure_bucket, "count": t.count, "mrr": float(t.mrr or 0)}
        for t in tenure_buckets
    ]

    # -------------------------------------------------------------------------
    # BY PLAN - Current active subscriptions by plan
    # -------------------------------------------------------------------------
    plan_stats = db.query(
        Subscription.plan_name,
        func.count(func.distinct(Subscription.customer_id)).label("customer_count"),
        func.sum(Subscription.price).label("mrr"),
    ).join(Customer).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Subscription.status == SubscriptionStatus.ACTIVE,
        or_(Subscription.end_date.is_(None), Subscription.end_date >= today),
    ).group_by(Subscription.plan_name).order_by(func.count(func.distinct(Subscription.customer_id)).desc()).limit(15).all()

    by_plan = [
        {"plan": p.plan_name or "Unknown", "customers": p.customer_count, "mrr": float(p.mrr or 0)}
        for p in plan_stats
    ]

    # -------------------------------------------------------------------------
    # BY LOCATION - Geographic distribution
    # -------------------------------------------------------------------------
    location_stats = db.query(
        Pop.name.label("pop_name"),
        Pop.id.label("pop_id"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).join(Pop, Pop.id == Customer.pop_id, isouter=True).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).group_by(Pop.id, Pop.name).order_by(func.count(Customer.id).desc()).all()

    by_location = [
        {"pop_id": loc.pop_id, "pop_name": loc.pop_name or "Unknown", "count": loc.count, "mrr": float(loc.mrr or 0)}
        for loc in location_stats
    ]

    # -------------------------------------------------------------------------
    # LAST SEEN / SERVICE HEALTH - Identify customers with usage issues
    # -------------------------------------------------------------------------
    # Get last usage date per customer
    last_usage_sub = (
        db.query(
            CustomerUsage.customer_id,
            func.max(CustomerUsage.usage_date).label("last_seen"),
            func.sum(CustomerUsage.download_bytes + CustomerUsage.upload_bytes).label("total_bytes"),
        )
        .filter(CustomerUsage.usage_date >= lookback_start)
        .group_by(CustomerUsage.customer_id)
        .subquery()
    )

    # Active PAYING customers with NO usage in lookback period (potential service issues)
    no_usage_customers = (
        db.query(Customer)
        .outerjoin(last_usage_sub, last_usage_sub.c.customer_id == Customer.id)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.mrr > 0,  # Only paying customers
            last_usage_sub.c.last_seen.is_(None),
        )
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    # Active PAYING customers with very low usage (< 100MB in period)
    low_usage_customers = (
        db.query(
            Customer,
            last_usage_sub.c.last_seen,
            last_usage_sub.c.total_bytes,
        )
        .join(last_usage_sub, last_usage_sub.c.customer_id == Customer.id)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.mrr > 0,  # Only paying customers
            last_usage_sub.c.total_bytes < 100 * 1024 * 1024,  # Less than 100MB
        )
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    # PAYING customers not seen in last 7 days but had prior usage
    stale_customers = (
        db.query(
            Customer,
            last_usage_sub.c.last_seen,
            last_usage_sub.c.total_bytes,
        )
        .join(last_usage_sub, last_usage_sub.c.customer_id == Customer.id)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.mrr > 0,  # Only paying customers
            last_usage_sub.c.last_seen < today - timedelta(days=7),
        )
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    service_health = {
        "no_recent_usage": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "mrr": float(c.mrr or 0),
                "pop_id": c.pop_id,
                "days_since_signup": _calculate_tenure_days(c.signup_date),
            }
            for c in no_usage_customers
        ],
        "low_usage": [
            {
                "id": c.Customer.id,
                "name": c.Customer.name,
                "email": c.Customer.email,
                "mrr": float(c.Customer.mrr or 0),
                "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                "usage_mb": round((c.total_bytes or 0) / (1024 * 1024), 2),
            }
            for c in low_usage_customers
        ],
        "inactive_7_days": [
            {
                "id": c.Customer.id,
                "name": c.Customer.name,
                "email": c.Customer.email,
                "mrr": float(c.Customer.mrr or 0),
                "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                "days_offline": (today - c.last_seen).days if c.last_seen else None,
            }
            for c in stale_customers
        ],
    }

    # -------------------------------------------------------------------------
    # PAYMENT RISK - Active customers with billing concerns
    # -------------------------------------------------------------------------
    # Customers blocking soon (within 7 days)
    blocking_soon = (
        db.query(Customer)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.days_until_blocking.isnot(None),
            Customer.days_until_blocking <= 7,
        )
        .order_by(Customer.days_until_blocking.asc())
        .limit(20)
        .all()
    )

    # Active customers with overdue invoices
    overdue_sub = (
        db.query(
            Invoice.customer_id,
            func.count(Invoice.id).label("overdue_count"),
            func.sum(Invoice.balance).label("overdue_amount"),
        )
        .filter(Invoice.status == InvoiceStatus.OVERDUE)
        .group_by(Invoice.customer_id)
        .subquery()
    )

    customers_with_overdue = (
        db.query(
            Customer,
            overdue_sub.c.overdue_count,
            overdue_sub.c.overdue_amount,
        )
        .join(overdue_sub, overdue_sub.c.customer_id == Customer.id)
        .filter(Customer.status == CustomerStatus.ACTIVE)
        .order_by(overdue_sub.c.overdue_amount.desc())
        .limit(20)
        .all()
    )

    # Negative deposit balance
    negative_deposit = (
        db.query(Customer)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.deposit_balance < 0,
        )
        .order_by(Customer.deposit_balance.asc())
        .limit(20)
        .all()
    )

    payment_risk = {
        "blocking_within_7_days": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "mrr": float(c.mrr or 0),
                "days_until_blocking": c.days_until_blocking,
                "blocking_date": c.blocking_date.isoformat() if c.blocking_date else None,
            }
            for c in blocking_soon
        ],
        "with_overdue_invoices": [
            {
                "id": c.Customer.id,
                "name": c.Customer.name,
                "email": c.Customer.email,
                "mrr": float(c.Customer.mrr or 0),
                "overdue_count": c.overdue_count,
                "overdue_amount": float(c.overdue_amount or 0),
            }
            for c in customers_with_overdue
        ],
        "negative_deposit": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "mrr": float(c.mrr or 0),
                "deposit_balance": float(c.deposit_balance or 0),
            }
            for c in negative_deposit
        ],
    }

    # -------------------------------------------------------------------------
    # TOP CUSTOMERS - Highest MRR active customers (paying only)
    # -------------------------------------------------------------------------
    top_customers = (
        db.query(Customer)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Customer.mrr > 0,  # Only paying customers
        )
        .order_by(Customer.mrr.desc())
        .limit(20)
        .all()
    )

    # Get last usage for top customers
    top_customer_ids = [c.id for c in top_customers]
    top_usage = {}
    if top_customer_ids:
        usage_results = (
            db.query(
                CustomerUsage.customer_id,
                func.max(CustomerUsage.usage_date).label("last_seen"),
            )
            .filter(CustomerUsage.customer_id.in_(top_customer_ids))
            .group_by(CustomerUsage.customer_id)
            .all()
        )
        top_usage = {r.customer_id: r.last_seen for r in usage_results}

    top_list = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "mrr": float(c.mrr or 0),
            "customer_type": c.customer_type.value if c.customer_type else None,
            "tenure_days": _calculate_tenure_days(c.signup_date),
            "last_seen": top_usage[c.id].isoformat() if c.id in top_usage and top_usage[c.id] else None,
            "pop_id": c.pop_id,
        }
        for c in top_customers
    ]

    # -------------------------------------------------------------------------
    # RECENT TICKETS - Active customers with open support issues
    # -------------------------------------------------------------------------
    open_tickets = (
        db.query(
            Customer,
            func.count(Ticket.id).label("open_tickets"),
        )
        .join(Ticket, Ticket.customer_id == Customer.id)
        .filter(
            Customer.status == CustomerStatus.ACTIVE,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        )
        .group_by(Customer.id)
        .order_by(func.count(Ticket.id).desc())
        .limit(20)
        .all()
    )

    support_concerns = [
        {
            "id": c.Customer.id,
            "name": c.Customer.name,
            "email": c.Customer.email,
            "mrr": float(c.Customer.mrr or 0),
            "open_tickets": c.open_tickets,
        }
        for c in open_tickets
    ]

    return {
        "overview": overview,
        "by_tenure": by_tenure,
        "by_plan": by_plan,
        "by_location": by_location,
        "service_health": service_health,
        "payment_risk": payment_risk,
        "top_customers": top_list,
        "support_concerns": support_concerns,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/signup-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_signup_trend(
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    interval: str = Query(default="month", pattern="^(month|week)$"),
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get new customer signup trend with configurable interval. Supports partial date filters.

    Derives signup date from customer's first subscription start_date
    when signup_date is not available.
    """
    end_dt = _parse_date(end_date, "end_date") or datetime.now(timezone.utc)
    start_dt = _parse_date(start_date, "start_date") or (end_dt - timedelta(days=months * 30))

    # Subquery to get each customer's first subscription date (derived signup)
    first_sub = (
        db.query(
            Subscription.customer_id,
            func.min(Subscription.start_date).label("first_start")
        )
        .group_by(Subscription.customer_id)
        .subquery()
    )

    # Use COALESCE: prefer signup_date, fall back to first subscription date
    effective_signup = func.coalesce(Customer.signup_date, first_sub.c.first_start)

    period_expr = func.date_trunc("week" if interval == "week" else "month", effective_signup)

    signups = (
        db.query(
            period_expr.label("period_start"),
            func.count(Customer.id).label("count"),
        )
        .outerjoin(first_sub, first_sub.c.customer_id == Customer.id)
        .filter(
            effective_signup >= start_dt,
            effective_signup <= end_dt,
        )
        .group_by(period_expr)
        .order_by(period_expr)
        .all()
    )

    data = []
    for s in signups:
        period_start: datetime = s.period_start
        label = period_start.strftime("%Y-W%U") if interval == "week" else period_start.strftime("%Y-%m")
        data.append({"period": label, "signups": s.count})

    return {
        "period": {"start": start_dt.date().isoformat(), "end": end_dt.date().isoformat()},
        "interval": interval,
        "data": data,
        "note": "Signup date uses customer.signup_date when present, otherwise the first subscription start_date.",
    }


@router.get("/analytics/cohort", dependencies=[Depends(Require("analytics:read"))])
async def get_customer_cohort(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Analyze customer retention by signup cohort.

    Derives signup date from customer's first subscription start_date
    when signup_date is not available.
    """
    from sqlalchemy import literal_column

    # Subquery to get each customer's first subscription date
    first_sub = (
        db.query(
            Subscription.customer_id,
            func.min(Subscription.start_date).label("first_start")
        )
        .group_by(Subscription.customer_id)
        .subquery()
    )

    # Use COALESCE: prefer signup_date, fall back to first subscription date
    effective_signup = func.coalesce(Customer.signup_date, first_sub.c.first_start)
    cohort_expr = func.to_char(func.date_trunc('month', effective_signup), 'YYYY-MM')

    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    cohorts = (
        db.query(
            cohort_expr.label("cohort_month"),
            func.count(Customer.id).label("total_customers"),
            func.sum(case((Customer.status == CustomerStatus.ACTIVE, 1), else_=0)).label("active"),
            func.sum(case((Customer.status == CustomerStatus.SUSPENDED, 1), else_=0)).label("blocked"),
            func.sum(case((Customer.status == CustomerStatus.INACTIVE, 1), else_=0)).label("inactive"),
            func.sum(case((Customer.status == CustomerStatus.INACTIVE, 1), else_=0)).label("churned"),
            func.sum(case((Customer.status == CustomerStatus.PROSPECT, 1), else_=0)).label("new"),
            func.sum(Customer.mrr).label("total_mrr"),
        )
        .outerjoin(first_sub, first_sub.c.customer_id == Customer.id)
        .filter(effective_signup.isnot(None), effective_signup >= cutoff)
        .group_by(literal_column("1"))
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
                "by_status": {
                    "active": c.active or 0,
                    "blocked": c.blocked or 0,
                    "inactive": c.inactive or 0,
                    "churned": c.churned or 0,
                    "new": c.new or 0,
                },
                "active": c.active or 0,
                "churned": c.churned or 0,
                "retention_rate": round(retention, 1),
                "total_mrr": float(c.total_mrr or 0),
            })

    # Calculate totals across all cohorts
    total_active = sum(r["by_status"]["active"] for r in results)
    total_blocked = sum(r["by_status"]["blocked"] for r in results)
    total_inactive = sum(r["by_status"]["inactive"] for r in results)
    total_churned = sum(r["by_status"]["churned"] for r in results)
    total_new = sum(r["by_status"]["new"] for r in results)
    total_customers = sum(r["total_customers"] for r in results)

    return {
        "period_months": months,
        "cohorts": results,
        "summary": {
            "total_cohorts": len(results),
            "total_customers": total_customers,
            "by_status": {
                "active": total_active,
                "blocked": total_blocked,
                "inactive": total_inactive,
                "churned": total_churned,
                "new": total_new,
            },
            "avg_retention": round(sum(r["retention_rate"] for r in results) / len(results), 1) if results else 0,
        }
    }


@router.get("/analytics/by-plan", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_plan(
    currency: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get customer distribution by subscription plan.

    Only counts currently active subscriptions (status=ACTIVE and either no end_date
    or end_date >= today). Returns unique customer counts and total MRR per plan.
    """
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    # Filter for truly active subscriptions (not expired)
    active_filter = and_(
        Subscription.status == SubscriptionStatus.ACTIVE,
        or_(
            Subscription.end_date.is_(None),
            Subscription.end_date >= func.current_date()
        )
    )

    query = (
        db.query(
            Subscription.plan_name,
            func.count(func.distinct(Subscription.customer_id)).label("customer_count"),
            func.count(Subscription.id).label("subscription_count"),
            func.sum(mrr_case).label("mrr"),
        )
        .filter(active_filter)
    )

    if currency:
        query = query.filter(Subscription.currency == currency)

    plans = (
        query
        .group_by(Subscription.plan_name)
        .order_by(func.count(func.distinct(Subscription.customer_id)).desc())
        .all()
    )

    return [
        {
            "plan_name": p.plan_name,
            "customer_count": p.customer_count,
            "subscription_count": p.subscription_count,
            "mrr": float(p.mrr or 0),
        }
        for p in plans
    ]


@router.get("/analytics/by-type", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_type(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer distribution by type with MRR breakdown."""
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    by_type = (
        db.query(
            Customer.customer_type,
            func.count(func.distinct(Customer.id)).label("customer_count"),
            func.sum(mrr_case).label("mrr"),
        )
        .outerjoin(Subscription, and_(
            Subscription.customer_id == Customer.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ))
        .filter(Customer.status == CustomerStatus.ACTIVE)
        .group_by(Customer.customer_type)
        .all()
    )

    return {
        "by_type": [
            {
                "type": row.customer_type.value if row.customer_type else "unknown",
                "customer_count": row.customer_count,
                "mrr": float(row.mrr or 0),
            }
            for row in by_type
        ],
        "total_active": sum(row.customer_count for row in by_type),
    }


@router.get("/analytics/by-location", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_location(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer distribution by city/location."""
    by_city = (
        db.query(
            Customer.city,
            func.count(Customer.id).label("count"),
            func.sum(Customer.mrr).label("total_mrr"),
        )
        .filter(Customer.city.isnot(None), Customer.city != "")
        .group_by(Customer.city)
        .order_by(func.count(Customer.id).desc())
        .limit(limit)
        .all()
    )

    return {
        "by_city": [
            {
                "city": row.city,
                "count": row.count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in by_city
        ],
    }


@router.get("/analytics/by-pop", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_pop(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Customer distribution by POP."""
    total_active = db.query(func.count(Customer.id)).filter(Customer.status == CustomerStatus.ACTIVE).scalar() or 0

    pop_rows = (
        db.query(
            Pop.id,
            Pop.name,
            func.count(Customer.id).label("customer_count"),
            func.sum(Customer.mrr).label("mrr"),
        )
        .join(Customer, Customer.pop_id == Pop.id)
        .filter(Customer.status == CustomerStatus.ACTIVE)
        .group_by(Pop.id, Pop.name)
        .order_by(func.count(Customer.id).desc())
        .all()
    )

    return {
        "total_active_customers": total_active,
        "by_pop": [
            {
                "pop_id": row.id,
                "pop_name": row.name,
                "customer_count": row.customer_count,
                "percent": round(row.customer_count / total_active * 100, 2) if total_active else 0,
                "mrr": float(row.mrr or 0),
            }
            for row in pop_rows
        ],
    }


@router.get("/analytics/by-router", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_router(
    pop_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Customer distribution by access router (via active subscriptions)."""
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    query = (
        db.query(
            Router.id.label("router_id"),
            Router.title.label("router_name"),
            Router.pop_id.label("pop_id"),
            func.count(func.distinct(Subscription.customer_id)).label("customer_count"),
            func.count(Subscription.id).label("subscription_count"),
            func.sum(mrr_case).label("mrr"),
        )
        .join(Subscription, Subscription.router_id == Router.id)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    if pop_id:
        query = query.filter(Router.pop_id == pop_id)

    rows = query.group_by(Router.id, Router.title, Router.pop_id).order_by(func.count(func.distinct(Subscription.customer_id)).desc()).all()

    return [
        {
            "router_id": r.router_id,
            "router_name": r.router_name,
            "pop_id": r.pop_id,
            "customer_count": r.customer_count,
            "subscription_count": r.subscription_count,
            "mrr": float(r.mrr or 0),
        }
        for r in rows
    ]


@router.get("/analytics/by-ticket-volume", dependencies=[Depends(Require("analytics:read"))])
async def get_customers_by_ticket_volume(
    days: int = Query(default=30, le=180),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bucket customers by ticket volume in the last N days."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    ticket_counts = (
        db.query(
            Ticket.customer_id,
            func.count(Ticket.id).label("count"),
        )
        .filter(
            Ticket.customer_id.isnot(None),
            Ticket.created_at >= start_dt,
        )
        .group_by(Ticket.customer_id)
        .all()
    )

    buckets = {
        "none": 0,
        "one": 0,
        "two_to_three": 0,
        "four_to_five": 0,
        "six_plus": 0,
    }

    for row in ticket_counts:
        c = int(getattr(row, "count", 0) or 0)
        if c == 0:
            buckets["none"] += 1
        elif c == 1:
            buckets["one"] += 1
        elif c <= 3:
            buckets["two_to_three"] += 1
        elif c <= 5:
            buckets["four_to_five"] += 1
        else:
            buckets["six_plus"] += 1

    return {
        "period_days": days,
        "buckets": buckets,
    }


@router.get("/analytics/data-quality/outreach", dependencies=[Depends(Require("analytics:read"))])
async def get_data_quality_outreach(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Identify customers missing email/phone grouped by POP, plan, and customer type, plus linkage gaps."""
    # Missing contact grouped by POP
    missing_contact_by_pop = (
        db.query(
            Pop.name.label("pop_name"),
            func.count(Customer.id).label("missing_count"),
        )
        .join(Pop, Customer.pop_id == Pop.id)
        .filter(or_(Customer.email.is_(None), Customer.email == "", Customer.phone.is_(None), Customer.phone == ""))
        .group_by(Pop.name)
        .all()
    )

    # Missing contact grouped by plan (active subs)
    missing_contact_by_plan = (
        db.query(
            Subscription.plan_name,
            func.count(func.distinct(Customer.id)).label("missing_count"),
        )
        .join(Customer, Subscription.customer_id == Customer.id)
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            or_(Customer.email.is_(None), Customer.email == "", Customer.phone.is_(None), Customer.phone == ""),
        )
        .group_by(Subscription.plan_name)
        .all()
    )

    # Missing contact grouped by customer type
    missing_contact_by_type = (
        db.query(
            Customer.customer_type,
            func.count(Customer.id).label("missing_count"),
        )
        .filter(or_(Customer.email.is_(None), Customer.email == "", Customer.phone.is_(None), Customer.phone == ""))
        .group_by(Customer.customer_type)
        .all()
    )

    # Linkage gaps by type
    linkage_gaps = (
        db.query(
            Customer.customer_type,
            func.sum(case((Customer.splynx_id.is_(None), 1), else_=0)).label("missing_splynx"),
            func.sum(case((Customer.erpnext_id.is_(None), 1), else_=0)).label("missing_erpnext"),
            func.sum(case((Customer.chatwoot_contact_id.is_(None), 1), else_=0)).label("missing_chatwoot"),
            func.count(Customer.id).label("total"),
        )
        .group_by(Customer.customer_type)
        .all()
    )

    return {
        "missing_contact": {
            "by_pop": [
                {"pop_name": row.pop_name, "missing_count": row.missing_count}
                for row in missing_contact_by_pop
            ],
            "by_plan": [
                {"plan_name": row.plan_name, "missing_count": row.missing_count}
                for row in missing_contact_by_plan
            ],
            "by_type": [
                {"customer_type": row.customer_type.value if row.customer_type else "unknown", "missing_count": row.missing_count}
                for row in missing_contact_by_type
            ],
        },
        "linkage_gaps": [
            {
                "customer_type": row.customer_type.value if row.customer_type else "unknown",
                "missing_splynx": int(row.missing_splynx or 0),
                "missing_erpnext": int(row.missing_erpnext or 0),
                "missing_chatwoot": int(row.missing_chatwoot or 0),
                "total": int(row.total or 0),
            }
            for row in linkage_gaps
        ],
    }


@router.get("/analytics/revenue/overdue", dependencies=[Depends(Require("analytics:read"))])
async def get_overdue_by_segment(
    pop_id: Optional[int] = None,
    plan_name: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Overdue invoices segmented by POP and plan."""
    overdue_query = (
        db.query(
            Customer.pop_id,
            Subscription.plan_name,
            func.count(Invoice.id).label("invoice_count"),
            func.sum(Invoice.balance).label("balance"),
        )
        .join(Customer, Invoice.customer_id == Customer.id)
        .outerjoin(Subscription, Subscription.customer_id == Customer.id)
        .filter(Invoice.status == InvoiceStatus.OVERDUE)
    )

    if pop_id:
        overdue_query = overdue_query.filter(Customer.pop_id == pop_id)
    if plan_name:
        overdue_query = overdue_query.filter(Subscription.plan_name == plan_name)

    rows = overdue_query.group_by(Customer.pop_id, Subscription.plan_name).all()

    return {
        "by_segment": [
            {
                "pop_id": r.pop_id,
                "plan_name": r.plan_name,
                "invoice_count": r.invoice_count,
                "balance": float(r.balance or 0),
            }
            for r in rows
        ]
    }


@router.get("/analytics/revenue/payment-timeliness", dependencies=[Depends(Require("analytics:read"))])
async def get_payment_timeliness(
    days: int = Query(default=180, le=365),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Payment timeliness cohorts by customer type and plan."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    days_diff = func.date_part("day", Invoice.due_date - Payment.payment_date)

    query = (
        db.query(
            Customer.customer_type,
            Subscription.plan_name,
            func.sum(case((and_(Payment.payment_date <= Invoice.due_date, days_diff > 3), 1), else_=0)).label("early"),
            func.sum(case((and_(Payment.payment_date <= Invoice.due_date, days_diff <= 3), 1), else_=0)).label("on_time"),
            func.sum(case((Payment.payment_date > Invoice.due_date, 1), else_=0)).label("late"),
            func.count(Payment.id).label("total"),
        )
        .join(Customer, Payment.customer_id == Customer.id)
        .outerjoin(Subscription, and_(Subscription.customer_id == Customer.id, Subscription.status == SubscriptionStatus.ACTIVE))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date.isnot(None),
            Invoice.due_date.isnot(None),
            Payment.payment_date >= start_dt,
        )
        .group_by(Customer.customer_type, Subscription.plan_name)
    )

    rows = query.all()

    results = []
    for r in rows:
        total = int(r.total or 0)
        results.append(
            {
                "customer_type": r.customer_type.value if r.customer_type else "unknown",
                "plan_name": r.plan_name,
                "early": int(r.early or 0),
                "on_time": int(r.on_time or 0),
                "late": int(r.late or 0),
                "total": total,
                "on_time_rate": round(((r.early or 0) + (r.on_time or 0)) / total * 100, 2) if total else 0,
            }
        )

    return results



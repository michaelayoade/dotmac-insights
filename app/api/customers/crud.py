"""
Crud Endpoints
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
# DATA ENDPOINTS (List, Detail, Search)
# =============================================================================

@router.get("/", dependencies=[Depends(Require("explorer:read"))])
async def list_customers(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    billing_type: Optional[str] = None,
    pop_id: Optional[int] = None,
    search: Optional[str] = None,
    has_overdue: Optional[bool] = None,
    signup_start: Optional[str] = Query(default=None, description="Filter by signup date start (YYYY-MM-DD)"),
    signup_end: Optional[str] = Query(default=None, description="Filter by signup date end (YYYY-MM-DD)"),
    cohort: Optional[str] = Query(default=None, description="Filter by signup cohort month (YYYY-MM)"),
    city: Optional[str] = None,
    base_station: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List customers with filtering and pagination.

    Filters:
    - status: active, suspended, cancelled, inactive
    - customer_type: residential, business, enterprise
    - billing_type: prepaid, postpaid
    - pop_id: Filter by POP
    - search: Search name, email, phone, account number
    - has_overdue: Filter customers with overdue invoices
    - signup_start/signup_end: Filter by signup date range (YYYY-MM-DD)
    - cohort: Filter by signup month (YYYY-MM), e.g. "2025-01"
    - city: Filter by city
    - base_station: Filter by base station
    """
    query = db.query(Customer)

    if status:
        status_lower = status.lower()
        status_map = {
            "active": CustomerStatus.ACTIVE,
            "inactive": CustomerStatus.INACTIVE,
            "blocked": CustomerStatus.SUSPENDED,
            "new": CustomerStatus.PROSPECT,
        }
        status_enum = status_map.get(status_lower)
        if not status_enum:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.filter(Customer.status == status_enum)

    if customer_type:
        try:
            type_enum = CustomerType(customer_type)
            query = query.filter(Customer.customer_type == type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid customer_type: {customer_type}")

    if billing_type:
        try:
            billing_enum = BillingType(billing_type)
            query = query.filter(Customer.billing_type == billing_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid billing_type: {billing_type}")

    if pop_id:
        query = query.filter(Customer.pop_id == pop_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Customer.name.ilike(search_term),
                Customer.email.ilike(search_term),
                Customer.phone.ilike(search_term),
                Customer.account_number.ilike(search_term),
            )
        )

    if has_overdue is True:
        overdue_customer_ids = db.query(distinct(Invoice.customer_id)).filter(
            Invoice.status == InvoiceStatus.OVERDUE
        ).subquery()
        query = query.filter(Customer.id.in_(select(overdue_customer_ids.c.customer_id)))

    # Signup date filters
    if cohort:
        # Parse cohort format YYYY-MM
        try:
            cohort_start = datetime.strptime(cohort, "%Y-%m").date()
            # Get last day of month
            if cohort_start.month == 12:
                cohort_end = date(cohort_start.year + 1, 1, 1) - timedelta(days=1)
            else:
                cohort_end = date(cohort_start.year, cohort_start.month + 1, 1) - timedelta(days=1)
            query = query.filter(
                Customer.signup_date >= cohort_start,
                Customer.signup_date <= cohort_end,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cohort format. Use YYYY-MM (e.g., 2025-01)")
    else:
        if signup_start:
            try:
                start_date = datetime.strptime(signup_start, "%Y-%m-%d").date()
                query = query.filter(Customer.signup_date >= start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid signup_start format. Use YYYY-MM-DD")
        if signup_end:
            try:
                end_date = datetime.strptime(signup_end, "%Y-%m-%d").date()
                query = query.filter(Customer.signup_date <= end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid signup_end format. Use YYYY-MM-DD")

    if city:
        query = query.filter(Customer.city.ilike(f"%{city}%"))

    if base_station:
        query = query.filter(Customer.base_station.ilike(f"%{base_station}%"))

    total = query.count()
    customers = query.order_by(Customer.name).offset(offset).limit(limit).all()

    # Get overdue invoice counts for these customers
    customer_ids = [c.id for c in customers]
    overdue_counts = {}
    if customer_ids:
        overdue_data = db.query(
            Invoice.customer_id,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.balance).label("amount"),
        ).filter(
            Invoice.customer_id.in_(customer_ids),
            Invoice.status == InvoiceStatus.OVERDUE,
        ).group_by(Invoice.customer_id).all()
        overdue_counts = {r.customer_id: {"count": r.count, "amount": float(r.amount or 0)} for r in overdue_data}

    return {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "status": _normalize_status(c.status),
                "customer_type": c.customer_type.value if c.customer_type else None,
                "mrr": float(c.mrr or 0),
                "signup_date": c.signup_date.isoformat() if c.signup_date else None,
                "activation_date": c.activation_date.isoformat() if c.activation_date else None,
                "city": c.city,
                "state": c.state,
                "pop_id": c.pop_id,
                "base_station": c.base_station,
                "billing_health": {
                    "days_until_blocking": c.days_until_blocking,
                    "blocking_date": c.blocking_date.isoformat() if c.blocking_date else None,
                    "deposit_balance": float(c.deposit_balance or 0),
                    "overdue_invoices": overdue_counts.get(c.id, {}).get("count", 0),
                    "overdue_amount": overdue_counts.get(c.id, {}).get("amount", 0),
                },
            }
            for c in customers
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# NOTE: /blocked must be defined BEFORE /{customer_id} to avoid route conflict
@router.get("/blocked", dependencies=[Depends(Require("analytics:read"))])
async def get_blocked_customers(
    min_days_blocked: Optional[int] = Query(default=None, ge=0, description="Minimum days since blocking"),
    max_days_blocked: Optional[int] = Query(default=None, ge=0, description="Maximum days since blocking"),
    pop_id: Optional[int] = None,
    plan: Optional[str] = Query(default=None, description="Filter by last plan name"),
    min_mrr: Optional[float] = Query(default=None, ge=0, description="Minimum MRR"),
    sort_by: str = Query(default="mrr", pattern="^(mrr|days_blocked|tenure)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List blocked customers with filtering and sorting for recovery targeting.

    Filters:
    - min_days_blocked/max_days_blocked: Duration of blocking
    - pop_id: Filter by POP location
    - plan: Filter by last active plan
    - min_mrr: Filter by minimum MRR value

    Sort options: mrr (default), days_blocked, tenure
    """
    today = date.today()

    # Get last subscription end_date as proxy for blocking date
    last_sub = (
        db.query(
            Subscription.customer_id.label("customer_id"),
            func.max(Subscription.end_date).label("blocked_since"),
            func.max(Subscription.plan_name).label("last_plan"),
        )
        .filter(Subscription.end_date.isnot(None))
        .group_by(Subscription.customer_id)
        .subquery()
    )

    query = (
        db.query(Customer, last_sub.c.blocked_since, last_sub.c.last_plan)
        .join(last_sub, last_sub.c.customer_id == Customer.id, isouter=True)
        .filter(Customer.status == CustomerStatus.SUSPENDED)
    )

    # Apply filters
    if pop_id:
        query = query.filter(Customer.pop_id == pop_id)

    if plan:
        query = query.filter(last_sub.c.last_plan.ilike(f"%{plan}%"))

    if min_mrr is not None:
        query = query.filter(Customer.mrr >= min_mrr)

    if min_days_blocked is not None:
        query = query.filter(
            func.date_part("day", func.current_date() - last_sub.c.blocked_since) >= min_days_blocked
        )
    if max_days_blocked is not None:
        query = query.filter(
            func.date_part("day", func.current_date() - last_sub.c.blocked_since) <= max_days_blocked
        )

    # Sorting
    if sort_by == "mrr":
        query = query.order_by(Customer.mrr.desc().nullslast())
    elif sort_by == "days_blocked":
        query = query.order_by(last_sub.c.blocked_since.asc().nullslast())
    elif sort_by == "tenure":
        query = query.order_by(Customer.signup_date.asc().nullslast())

    total = query.count()
    blocked = query.offset(offset).limit(limit).all()

    # Bulk fetch payment history
    customer_ids = [row.Customer.id for row in blocked]
    payment_summary = {}
    invoice_summary = {}

    if customer_ids:
        # Payment history
        payment_summary = {
            row.customer_id: {
                "total_paid": float(row.total_paid or 0),
                "payment_count": row.payment_count,
                "last_payment_date": row.last_payment_date,
            }
            for row in db.query(
                Payment.customer_id,
                func.sum(Payment.amount).label("total_paid"),
                func.count(Payment.id).label("payment_count"),
                func.max(Payment.payment_date).label("last_payment_date"),
            ).filter(
                Payment.customer_id.in_(customer_ids),
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            ).group_by(Payment.customer_id)
        }

        # Outstanding balance
        invoice_summary = {
            row.customer_id: {
                "outstanding": float(row.outstanding or 0),
                "overdue_count": row.overdue_count,
            }
            for row in db.query(
                Invoice.customer_id,
                func.sum(Invoice.balance).label("outstanding"),
                func.count(Invoice.id).label("overdue_count"),
            ).filter(
                Invoice.customer_id.in_(customer_ids),
                Invoice.status == InvoiceStatus.OVERDUE,
            ).group_by(Invoice.customer_id)
        }

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters_applied": {
            "min_days_blocked": min_days_blocked,
            "max_days_blocked": max_days_blocked,
            "pop_id": pop_id,
            "plan": plan,
            "min_mrr": min_mrr,
        },
        "data": [
            {
                "id": row.Customer.id,
                "name": row.Customer.name,
                "email": row.Customer.email,
                "phone": row.Customer.phone,
                "pop_id": row.Customer.pop_id,
                "mrr": float(row.Customer.mrr or 0),
                "signup_date": row.Customer.signup_date.isoformat() if row.Customer.signup_date else None,
                "tenure_days": _calculate_tenure_days(row.Customer.signup_date),
                "blocked_since": row.blocked_since.isoformat() if row.blocked_since else None,
                "days_blocked": (today - row.blocked_since.date()).days if row.blocked_since else None,
                "last_plan": row.last_plan,
                "payment_history": payment_summary.get(row.Customer.id, {
                    "total_paid": 0,
                    "payment_count": 0,
                    "last_payment_date": None,
                }),
                "outstanding": invoice_summary.get(row.Customer.id, {
                    "outstanding": 0,
                    "overdue_count": 0,
                }),
            }
            for row in blocked
        ],
    }


@router.get("/{customer_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_customer(
    customer_id: int,
    invoice_limit: int = Query(default=20, ge=1, le=100),
    conversation_limit: int = Query(default=20, ge=1, le=100),
    subscription_limit: int = Query(default=10, ge=1, le=100),
    ticket_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed customer information including related data."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get subscriptions (limited)
    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.customer_id == customer_id)
        .order_by(Subscription.start_date.desc())
        .limit(subscription_limit)
        .all()
    )

    # Totals for invoices/payments
    # Use Invoice.total_amount for total invoiced
    invoiced_total = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.customer_id == customer_id
    ).scalar() or 0.0

    # Use Payment table for paid total (more accurate than Invoice.amount_paid
    # which may not be in sync with actual payments)
    paid_from_payments = db.query(func.sum(Payment.amount)).filter(
        Payment.customer_id == customer_id,
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
    ).scalar() or 0.0

    # Also get Invoice.amount_paid as a fallback/comparison
    paid_from_invoices = db.query(func.sum(Invoice.amount_paid)).filter(
        Invoice.customer_id == customer_id
    ).scalar() or 0.0

    # Use whichever is higher (some systems track in invoices, some in payments)
    paid_total = max(float(paid_from_payments), float(paid_from_invoices))

    # Get recent invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id)
        .order_by(Invoice.invoice_date.desc())
        .limit(invoice_limit)
        .all()
    )

    # Get conversations
    conversations = (
        db.query(Conversation)
        .filter(Conversation.customer_id == customer_id)
        .order_by(Conversation.created_at.desc())
        .limit(conversation_limit)
        .all()
    )

    tickets = (
        db.query(Ticket)
        .filter(Ticket.customer_id == customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(ticket_limit)
        .all()
    )

    # Calculate metrics
    total_invoiced = float(invoiced_total or 0)
    total_paid = float(paid_total or 0)
    outstanding = total_invoiced - total_paid

    open_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.customer_id == customer_id,
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).scalar() or 0

    total_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.customer_id == customer_id
    ).scalar() or 0

    pop = None
    if customer.pop_id:
        pop_obj = db.query(Pop).filter(Pop.id == customer.pop_id).first()
        if pop_obj:
            pop = {"id": pop_obj.id, "name": pop_obj.name}

    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "phone_secondary": customer.phone_secondary,
        "address": customer.address,
        "city": customer.city,
        "state": customer.state,
        "status": _normalize_status(customer.status),
        "customer_type": customer.customer_type.value if customer.customer_type else None,
        "billing_type": customer.billing_type.value if customer.billing_type else None,
        "account_number": customer.account_number,
        "signup_date": customer.signup_date.isoformat() if customer.signup_date else None,
        "activation_date": customer.activation_date.isoformat() if customer.activation_date else None,
        "cancellation_date": customer.cancellation_date.isoformat() if customer.cancellation_date else None,
        "tenure_days": _calculate_tenure_days(customer.signup_date),
        "pop": pop,
        "mrr": float(customer.mrr or 0),
        "invoiced_total": total_invoiced,
        "paid_total": total_paid,
        "outstanding_balance": outstanding,
        "external_ids": {
            "splynx_id": customer.splynx_id,
            "erpnext_id": customer.erpnext_id,
            "chatwoot_contact_id": customer.chatwoot_contact_id,
        },
        "billing_health": {
            "days_until_blocking": customer.days_until_blocking,
            "blocking_date": customer.blocking_date.isoformat() if customer.blocking_date else None,
            "deposit_balance": float(customer.deposit_balance or 0),
            "payment_per_month": float(customer.payment_per_month or 0),
        },
        "metrics": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding": outstanding,
            "open_tickets": open_tickets,
            "total_conversations": total_conversations,
        },
        "subscriptions": [
            {
                "id": s.id,
                "plan_name": s.plan_name,
                "price": float(s.price) if s.price else 0,
                "status": s.status.value if s.status else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "download_speed": s.download_speed,
                "upload_speed": s.upload_speed,
            }
            for s in subscriptions
        ],
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "total_amount": float(inv.total_amount) if inv.total_amount else 0,
                "amount_paid": float(inv.amount_paid or 0),
                "status": inv.status.value if inv.status else None,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
            }
            for inv in invoices
        ],
        "recent_tickets": [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
        "recent_conversations": [
            {
                "id": c.id,
                "chatwoot_id": c.chatwoot_id,
                "status": c.status.value if c.status else None,
                "channel": c.channel,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "message_count": c.message_count,
            }
            for c in conversations
        ],
    }


@router.get("/{customer_id}/usage", dependencies=[Depends(Require("analytics:read"))])
async def get_customer_usage(
    customer_id: int,
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    days: int = Query(default=30, ge=1, le=365, description="Days of history (if no date range)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get bandwidth usage history for a customer.

    Returns daily upload/download data from Splynx traffic counters.
    Includes per-subscription breakdown and totals.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Parse date range
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else end_dt - timedelta(days=days)

    # Get usage records
    usage_records = (
        db.query(CustomerUsage)
        .filter(
            CustomerUsage.customer_id == customer_id,
            CustomerUsage.usage_date >= start_dt,
            CustomerUsage.usage_date <= end_dt,
        )
        .order_by(CustomerUsage.usage_date.desc())
        .all()
    )

    # Calculate totals
    total_upload = sum(r.upload_bytes for r in usage_records)
    total_download = sum(r.download_bytes for r in usage_records)

    # Group by date for daily totals
    daily_usage = {}
    for r in usage_records:
        date_key = r.usage_date.isoformat()
        if date_key not in daily_usage:
            daily_usage[date_key] = {"upload_bytes": 0, "download_bytes": 0}
        daily_usage[date_key]["upload_bytes"] += r.upload_bytes
        daily_usage[date_key]["download_bytes"] += r.download_bytes

    # Convert to list sorted by date
    daily_data = [
        {
            "date": date_key,
            "upload_bytes": data["upload_bytes"],
            "download_bytes": data["download_bytes"],
            "upload_gb": round(data["upload_bytes"] / (1024**3), 2),
            "download_gb": round(data["download_bytes"] / (1024**3), 2),
            "total_gb": round((data["upload_bytes"] + data["download_bytes"]) / (1024**3), 2),
        }
        for date_key, data in sorted(daily_usage.items())
    ]

    # Get subscription breakdown (aggregate by subscription)
    subscription_usage = {}
    for r in usage_records:
        sub_id = r.subscription_id or 0
        if sub_id not in subscription_usage:
            subscription_usage[sub_id] = {"upload_bytes": 0, "download_bytes": 0, "days": 0}
        subscription_usage[sub_id]["upload_bytes"] += r.upload_bytes
        subscription_usage[sub_id]["download_bytes"] += r.download_bytes
        subscription_usage[sub_id]["days"] += 1

    # Get subscription details for display
    sub_ids = [sid for sid in subscription_usage.keys() if sid > 0]
    subs_map = {}
    if sub_ids:
        subs = db.query(Subscription).filter(Subscription.id.in_(sub_ids)).all()
        subs_map = {s.id: s for s in subs}

    by_subscription = [
        {
            "subscription_id": sub_id if sub_id > 0 else None,
            "plan_name": subs_map[sub_id].plan_name if sub_id in subs_map else "Unknown",
            "upload_gb": round(data["upload_bytes"] / (1024**3), 2),
            "download_gb": round(data["download_bytes"] / (1024**3), 2),
            "total_gb": round((data["upload_bytes"] + data["download_bytes"]) / (1024**3), 2),
            "days_with_data": data["days"],
        }
        for sub_id, data in subscription_usage.items()
    ]

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "period": {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "days": (end_dt - start_dt).days + 1,
        },
        "totals": {
            "upload_bytes": total_upload,
            "download_bytes": total_download,
            "upload_gb": round(total_upload / (1024**3), 2),
            "download_gb": round(total_download / (1024**3), 2),
            "total_gb": round((total_upload + total_download) / (1024**3), 2),
        },
        "daily": daily_data,
        "by_subscription": by_subscription,
    }



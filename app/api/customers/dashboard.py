"""
Dashboard Endpoints
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
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("customers-dashboard", ttl=CACHE_TTL["short"])
async def get_customer_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Customer dashboard - aggregate summary mirroring Customer 360 structure.

    Provides a high-level view across all domains:
    - Overview: Customer counts, status distribution, growth
    - Finance: Revenue, outstanding, billing health
    - Services: Subscriptions, usage
    - Support: Tickets
    - Projects: Active projects
    - CRM: Conversations
    """
    today = date.today()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # -------------------------------------------------------------------------
    # OVERVIEW - Customer counts and status
    # -------------------------------------------------------------------------
    status_counts = db.query(
        Customer.status,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).group_by(Customer.status).all()

    status_map: Dict[CustomerStatus, Dict[str, float | int]] = {
        s.status: {"count": int(getattr(s, "count", 0) or 0), "mrr": float(s.mrr or 0)}
        for s in status_counts
    }
    total_customers: int = sum(int(s["count"]) for s in status_map.values())
    total_mrr: float = sum(float(s["mrr"]) for s in status_map.values())

    # By type distribution
    type_counts = db.query(
        Customer.customer_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr"),
    ).group_by(Customer.customer_type).all()

    # Growth - signups and churn
    new_last_30 = db.query(func.count(Customer.id)).filter(
        Customer.signup_date.isnot(None),
        Customer.signup_date >= thirty_days_ago.date()
    ).scalar() or 0

    churned_last_30 = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date.isnot(None),
        Customer.cancellation_date >= thirty_days_ago.date()
    ).scalar() or 0

    overview = {
        "total_customers": total_customers,
        "total_mrr": total_mrr,
        "by_status": {
            "active": status_map.get(CustomerStatus.ACTIVE, {}).get("count", 0),
            "blocked": status_map.get(CustomerStatus.SUSPENDED, {}).get("count", 0),
            "inactive": status_map.get(CustomerStatus.INACTIVE, {}).get("count", 0),
            "new": status_map.get(CustomerStatus.PROSPECT, {}).get("count", 0),
        },
        "by_type": [
            {
                "type": t.customer_type.value if t.customer_type else "unknown",
                "count": t.count,
                "mrr": float(t.mrr or 0),
            }
            for t in type_counts
        ],
        "growth_30d": {
            "new_signups": new_last_30,
            "churned": churned_last_30,
            "net_change": new_last_30 - churned_last_30,
        },
    }

    # -------------------------------------------------------------------------
    # FINANCE - Revenue, invoices, payments, billing health
    # -------------------------------------------------------------------------
    # Invoice stats
    invoice_stats = db.query(
        func.count(Invoice.id).label("total_invoices"),
        func.sum(Invoice.total_amount).label("total_invoiced"),
        func.sum(Invoice.amount_paid).label("total_paid"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, Invoice.balance), else_=0)).label("overdue_amount"),
    ).first()

    customers_with_overdue = db.query(func.count(distinct(Invoice.customer_id))).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).scalar() or 0

    # Billing health - blocking risk
    blocking_stats = db.query(
        func.sum(case((Customer.days_until_blocking <= 1, 1), else_=0)).label("blocking_today"),
        func.sum(case((and_(Customer.days_until_blocking > 1, Customer.days_until_blocking <= 3), 1), else_=0)).label("blocking_3d"),
        func.sum(case((and_(Customer.days_until_blocking > 3, Customer.days_until_blocking <= 7), 1), else_=0)).label("blocking_7d"),
        func.sum(case((Customer.days_until_blocking <= 7, Customer.mrr), else_=0)).label("mrr_at_risk"),
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.days_until_blocking.isnot(None),
        Customer.days_until_blocking >= 0,
    ).first()

    negative_deposit = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.deposit_balance.isnot(None),
        Customer.deposit_balance < 0
    ).scalar() or 0

    finance = {
        "revenue": {
            "total_mrr": total_mrr,
            "active_mrr": status_map.get(CustomerStatus.ACTIVE, {}).get("mrr", 0),
        },
        "invoices": {
            "total_invoiced": float(invoice_stats.total_invoiced or 0) if invoice_stats else 0,
            "total_paid": float(invoice_stats.total_paid or 0) if invoice_stats else 0,
            "outstanding": float((invoice_stats.total_invoiced or 0) - (invoice_stats.total_paid or 0)) if invoice_stats else 0,
            "overdue_count": (invoice_stats.overdue_count or 0) if invoice_stats else 0,
            "overdue_amount": float(invoice_stats.overdue_amount or 0) if invoice_stats else 0,
            "customers_with_overdue": customers_with_overdue,
        },
        "billing_health": {
            "blocking_today": int(blocking_stats.blocking_today or 0) if blocking_stats else 0,
            "blocking_in_3_days": int(blocking_stats.blocking_3d or 0) if blocking_stats else 0,
            "blocking_in_7_days": int(blocking_stats.blocking_7d or 0) if blocking_stats else 0,
            "total_at_risk": int((blocking_stats.blocking_today or 0) + (blocking_stats.blocking_3d or 0) + (blocking_stats.blocking_7d or 0)) if blocking_stats else 0,
            "mrr_at_risk": float(blocking_stats.mrr_at_risk or 0) if blocking_stats else 0,
            "negative_deposit": negative_deposit,
        },
    }

    # -------------------------------------------------------------------------
    # SERVICES - Subscriptions and usage
    # -------------------------------------------------------------------------
    subscription_stats = db.query(
        func.count(Subscription.id).label("total"),
        func.sum(case((Subscription.status == SubscriptionStatus.ACTIVE, 1), else_=0)).label("active"),
        func.sum(case((Subscription.status == SubscriptionStatus.ACTIVE, Subscription.price), else_=0)).label("active_mrr"),
    ).first()

    # Usage last 30 days
    usage_stats = db.query(
        func.sum(CustomerUsage.upload_bytes).label("upload"),
        func.sum(CustomerUsage.download_bytes).label("download"),
        func.count(distinct(CustomerUsage.customer_id)).label("customers_with_data"),
    ).filter(CustomerUsage.usage_date >= (today - timedelta(days=30))).first()

    services = {
        "subscriptions": {
            "total": (subscription_stats.total or 0) if subscription_stats else 0,
            "active": (subscription_stats.active or 0) if subscription_stats else 0,
            "active_mrr": float(subscription_stats.active_mrr or 0) if subscription_stats else 0,
        },
        "usage_30d": {
            "total_upload_gb": round((usage_stats.upload or 0) / (1024**3), 2) if usage_stats else 0,
            "total_download_gb": round((usage_stats.download or 0) / (1024**3), 2) if usage_stats else 0,
            "total_gb": round(((usage_stats.upload or 0) + (usage_stats.download or 0)) / (1024**3), 2) if usage_stats else 0,
            "customers_with_data": (usage_stats.customers_with_data or 0) if usage_stats else 0,
        },
    }

    # -------------------------------------------------------------------------
    # SUPPORT - Tickets
    # -------------------------------------------------------------------------
    ticket_stats = db.query(
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label("open"),
        func.sum(case((Ticket.status == TicketStatus.REPLIED, 1), else_=0)).label("replied"),
        func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
    ).first()

    tickets_last_30 = db.query(func.count(Ticket.id)).filter(
        Ticket.created_at >= thirty_days_ago
    ).scalar() or 0

    customers_with_open_tickets = db.query(func.count(distinct(Ticket.customer_id))).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).scalar() or 0

    support = {
        "tickets": {
            "total": ticket_stats.total if ticket_stats else 0,
            "open": ticket_stats.open if ticket_stats else 0,
            "replied": ticket_stats.replied if ticket_stats else 0,
            "closed": ticket_stats.closed if ticket_stats else 0,
            "created_last_30d": tickets_last_30,
        },
        "customers_with_open_tickets": customers_with_open_tickets,
    }

    # -------------------------------------------------------------------------
    # PROJECTS
    # -------------------------------------------------------------------------
    project_stats = db.query(
        func.count(Project.id).label("total"),
        func.sum(case((Project.status == ProjectStatus.OPEN, 1), else_=0)).label("active"),
        func.sum(case((Project.status == ProjectStatus.COMPLETED, 1), else_=0)).label("completed"),
    ).first()

    projects = {
        "total": project_stats.total if project_stats else 0,
        "active": project_stats.active if project_stats else 0,
        "completed": project_stats.completed if project_stats else 0,
    }

    # -------------------------------------------------------------------------
    # CRM - Conversations
    # -------------------------------------------------------------------------
    conversation_stats = db.query(
        func.count(Conversation.id).label("total"),
        func.sum(case((Conversation.status == ConversationStatus.OPEN, 1), else_=0)).label("open"),
    ).first()

    conversations_last_30 = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= thirty_days_ago
    ).scalar() or 0

    crm = {
        "conversations": {
            "total": conversation_stats.total if conversation_stats else 0,
            "open": conversation_stats.open if conversation_stats else 0,
            "created_last_30d": conversations_last_30,
        },
    }

    return {
        "overview": overview,
        "finance": finance,
        "services": services,
        "support": support,
        "projects": projects,
        "crm": crm,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }



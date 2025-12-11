"""
Customer Domain Router

Provides all customer-related endpoints:
- /dashboard - Key metrics and summary (mirrors 360 structure)
- /360/{id} - Customer 360 view (all domains consolidated)
- / - List, search, filter customers
- /{id} - Customer detail with related data
- /{id}/usage - Bandwidth usage history
- /blocked - Blocked customers list for recovery targeting
- /analytics/blocked - Comprehensive blocked customer analytics
- /analytics/* - Signup trends, cohorts, distribution
- /insights/* - Segments, health, completeness
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, extract, case, distinct, Date, select
from typing import Dict, Any, Optional, List
from itertools import groupby
from datetime import datetime, date, timedelta
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

router = APIRouter()


def _calculate_tenure_days(signup_date) -> Optional[int]:
    """Calculate tenure days from signup date (accepts date or datetime)."""
    if not signup_date:
        return None
    if isinstance(signup_date, datetime):
        signup_date = signup_date.date()
    if isinstance(signup_date, date):
        return (date.today() - signup_date).days
    return None


def _parse_date(value: Optional[str], field: str) -> Optional[datetime]:
    """Parse ISO date string safely and raise HTTP 400 on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {value}")


def _normalize_status(status: Optional[CustomerStatus]) -> Optional[str]:
    """Map internal status enums to frontend display values."""
    if status is None:
        return None
    mapping = {
        CustomerStatus.ACTIVE: "active",
        CustomerStatus.INACTIVE: "inactive",   # Splynx "disabled"
        CustomerStatus.SUSPENDED: "blocked",   # Splynx "blocked"
        CustomerStatus.PROSPECT: "new",        # Splynx "new"
    }
    return mapping.get(status, "inactive")


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
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

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
        "generated_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# CUSTOMER 360 VIEW
# =============================================================================

@router.get("/360/{customer_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_customer_360(
    customer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Comprehensive 360-degree customer view.

    Consolidates all customer data across domains:
    - Profile: Basic customer info, location, external IDs
    - Finance: Invoices, payments, credit notes, billing health
    - Services: Subscriptions, usage statistics
    - Network: IP addresses, router assignments
    - Support: Tickets with recent messages
    - Projects: Installation and service projects
    - CRM: Conversations, notes, interaction history
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    today = date.today()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)

    # -------------------------------------------------------------------------
    # PROFILE
    # -------------------------------------------------------------------------
    pop_data = None
    if customer.pop_id:
        pop = db.query(Pop).filter(Pop.id == customer.pop_id).first()
        if pop:
            pop_data = {"id": pop.id, "name": pop.name, "address": pop.address}

    profile = {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "billing_email": customer.billing_email,
        "phone": customer.phone,
        "phone_secondary": customer.phone_secondary,
        "address": customer.address,
        "address_2": customer.address_2,
        "city": customer.city,
        "state": customer.state,
        "zip_code": customer.zip_code,
        "country": customer.country,
        "gps": customer.gps,
        "latitude": customer.latitude,
        "longitude": customer.longitude,
        "status": _normalize_status(customer.status),
        "customer_type": customer.customer_type.value if customer.customer_type else None,
        "billing_type": customer.billing_type.value if customer.billing_type else None,
        "account_number": customer.account_number,
        "contract_number": customer.contract_number,
        "vat_id": customer.vat_id,
        "base_station": customer.base_station,
        "building_type": customer.building_type,
        "partner_id": customer.partner_id,
        "added_by": customer.added_by,
        "referrer": customer.referrer,
        "labels": customer.labels.split(",") if customer.labels else [],
        "notes": customer.notes,
        "pop": pop_data,
        "dates": {
            "signup": customer.signup_date.isoformat() if customer.signup_date else None,
            "activation": customer.activation_date.isoformat() if customer.activation_date else None,
            "cancellation": customer.cancellation_date.isoformat() if customer.cancellation_date else None,
            "contract_end": customer.contract_end_date.isoformat() if customer.contract_end_date else None,
            "last_online": customer.last_online.isoformat() if customer.last_online else None,
        },
        "tenure_days": _calculate_tenure_days(customer.signup_date),
        "external_ids": {
            "splynx_id": customer.splynx_id,
            "erpnext_id": customer.erpnext_id,
            "chatwoot_contact_id": customer.chatwoot_contact_id,
            "zoho_id": customer.zoho_id,
        },
    }

    # -------------------------------------------------------------------------
    # FINANCE
    # -------------------------------------------------------------------------
    # Invoice summary
    invoice_stats = db.query(
        func.count(Invoice.id).label("total_count"),
        func.sum(Invoice.total_amount).label("total_amount"),
        func.sum(Invoice.amount_paid).label("total_paid"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
        func.sum(case((Invoice.status == InvoiceStatus.OVERDUE, Invoice.balance), else_=0)).label("overdue_amount"),
    ).filter(Invoice.customer_id == customer_id).first()

    # Recent invoices
    recent_invoices = db.query(Invoice).filter(
        Invoice.customer_id == customer_id
    ).order_by(Invoice.invoice_date.desc()).limit(10).all()

    # Payment summary
    payment_stats = db.query(
        func.count(Payment.id).label("total_count"),
        func.sum(Payment.amount).label("total_amount"),
        func.max(Payment.payment_date).label("last_payment_date"),
    ).filter(Payment.customer_id == customer_id).first()

    # Recent payments
    recent_payments = db.query(Payment).filter(
        Payment.customer_id == customer_id
    ).order_by(Payment.payment_date.desc()).limit(10).all()

    # Credit notes
    credit_note_stats = db.query(
        func.count(CreditNote.id).label("count"),
        func.sum(CreditNote.amount).label("total"),
    ).filter(CreditNote.customer_id == customer_id).first()

    finance = {
        "summary": {
            "mrr": float(customer.mrr or 0),
            "total_invoiced": float(invoice_stats.total_amount or 0) if invoice_stats else 0,
            "total_paid": float(invoice_stats.total_paid or 0) if invoice_stats else 0,
            "outstanding_balance": float((invoice_stats.total_amount or 0) - (invoice_stats.total_paid or 0)) if invoice_stats else 0,
            "overdue_invoices": invoice_stats.overdue_count if invoice_stats else 0,
            "overdue_amount": float(invoice_stats.overdue_amount or 0) if invoice_stats else 0,
            "credit_notes": credit_note_stats.count if credit_note_stats else 0,
            "credit_note_total": float(credit_note_stats.total or 0) if credit_note_stats else 0,
            "payment_count": payment_stats.total_count if payment_stats else 0,
            "last_payment_date": payment_stats.last_payment_date.isoformat() if payment_stats and payment_stats.last_payment_date else None,
        },
        "billing_health": {
            "days_until_blocking": customer.days_until_blocking,
            "blocking_date": customer.blocking_date.isoformat() if customer.blocking_date else None,
            "deposit_balance": float(customer.deposit_balance or 0),
            "payment_per_month": float(customer.payment_per_month or 0),
        },
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "total_amount": float(inv.total_amount or 0),
                "amount_paid": float(inv.amount_paid or 0),
                "balance": float(inv.balance or 0),
                "status": inv.status.value if inv.status else None,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
            }
            for inv in recent_invoices
        ],
        "recent_payments": [
            {
                "id": p.id,
                "amount": float(p.amount or 0),
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_method": p.payment_method,
                "status": p.status.value if p.status else None,
                "reference": p.transaction_reference,
            }
            for p in recent_payments
        ],
    }

    # -------------------------------------------------------------------------
    # SERVICES
    # -------------------------------------------------------------------------
    subscriptions = db.query(Subscription).filter(
        Subscription.customer_id == customer_id
    ).order_by(Subscription.start_date.desc()).all()

    active_subs = [s for s in subscriptions if s.status == SubscriptionStatus.ACTIVE]

    # Usage stats (last 30 days)
    usage_stats = db.query(
        func.sum(CustomerUsage.upload_bytes).label("upload"),
        func.sum(CustomerUsage.download_bytes).label("download"),
        func.count(CustomerUsage.id).label("days_with_data"),
    ).filter(
        CustomerUsage.customer_id == customer_id,
        CustomerUsage.usage_date >= (today - timedelta(days=30)),
    ).first()

    services = {
        "summary": {
            "total_subscriptions": len(subscriptions),
            "active_subscriptions": len(active_subs),
            "total_mrr": sum(float(s.price or 0) for s in active_subs),
        },
        "usage_30d": {
            "upload_gb": round((usage_stats.upload or 0) / (1024**3), 2) if usage_stats else 0,
            "download_gb": round((usage_stats.download or 0) / (1024**3), 2) if usage_stats else 0,
            "total_gb": round(((usage_stats.upload or 0) + (usage_stats.download or 0)) / (1024**3), 2) if usage_stats else 0,
            "days_with_data": usage_stats.days_with_data if usage_stats else 0,
        },
        "subscriptions": [
            {
                "id": s.id,
                "plan_name": s.plan_name,
                "description": s.description,
                "price": float(s.price or 0),
                "status": s.status.value if s.status else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "download_speed": s.download_speed,
                "upload_speed": s.upload_speed,
                "router_id": s.router_id,
                "ipv4_address": s.ipv4_address,
            }
            for s in subscriptions
        ],
    }

    # -------------------------------------------------------------------------
    # NETWORK
    # -------------------------------------------------------------------------
    ip_addresses = db.query(IPv4Address).filter(
        IPv4Address.customer_id == customer_id
    ).all()

    # Get unique router IDs from subscriptions
    router_ids = list(set(s.router_id for s in subscriptions if s.router_id))
    routers = []
    if router_ids:
        router_records = db.query(Router).filter(Router.id.in_(router_ids)).all()
        routers = [
            {
                "id": r.id,
                "name": r.title,
                "ip": r.address,
                "location_id": r.location_id,
                "model": r.model,
                "status": r.status,
            }
            for r in router_records
        ]

    network = {
        "ip_addresses": [
            {
                "id": ip.id,
                "ip": ip.ip,
                "hostname": ip.hostname,
                "status": ip.status,
                "is_used": ip.is_used,
                "last_check": ip.last_check.isoformat() if ip.last_check else None,
            }
            for ip in ip_addresses
        ],
        "routers": routers,
        "summary": {
            "total_ips": len(ip_addresses),
            "active_ips": sum(1 for ip in ip_addresses if ip.is_used),
            "routers_count": len(routers),
        },
    }

    # -------------------------------------------------------------------------
    # SUPPORT
    # -------------------------------------------------------------------------
    tickets = db.query(Ticket).filter(
        Ticket.customer_id == customer_id
    ).order_by(Ticket.created_at.desc()).limit(20).all()

    open_tickets = [t for t in tickets if t.status in [TicketStatus.OPEN, TicketStatus.REPLIED]]

    # Ticket stats
    ticket_stats = db.query(
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label("open"),
        func.sum(case((Ticket.status == TicketStatus.REPLIED, 1), else_=0)).label("replied"),
        func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
    ).filter(Ticket.customer_id == customer_id).first()

    # Recent ticket messages for open tickets
    ticket_messages_map: Dict[int, List[Dict[str, Any]]] = {}
    if open_tickets:
        open_ticket_ids = [t.splynx_id for t in open_tickets if t.splynx_id]
        if open_ticket_ids:
            recent_messages = db.query(TicketMessage).filter(
                TicketMessage.splynx_ticket_id.in_(open_ticket_ids)
            ).order_by(TicketMessage.created_at.desc()).limit(50).all()
            for msg in recent_messages:
                ticket_id = int(msg.splynx_ticket_id) if msg.splynx_ticket_id else 0
                if ticket_id not in ticket_messages_map:
                    ticket_messages_map[ticket_id] = []
                if len(ticket_messages_map[ticket_id]) < 3:
                    ticket_messages_map[ticket_id].append({
                        "id": msg.id,
                        "message": msg.message[:200] if msg.message else None,
                        "author": msg.author_name,
                        "is_admin": msg.author_type == "admin",
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    })

    support = {
        "summary": {
            "total_tickets": ticket_stats.total if ticket_stats else 0,
            "open_tickets": ticket_stats.open if ticket_stats else 0,
            "replied_tickets": ticket_stats.replied if ticket_stats else 0,
            "closed_tickets": ticket_stats.closed if ticket_stats else 0,
        },
        "tickets": [
            {
                "id": t.id,
                "splynx_id": t.splynx_id,
                "subject": t.subject,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
                "assigned_to": t.assigned_to,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                "recent_messages": ticket_messages_map.get(int(t.splynx_id) if t.splynx_id else 0, []),
            }
            for t in tickets
        ],
    }

    # -------------------------------------------------------------------------
    # PROJECTS
    # -------------------------------------------------------------------------
    projects = db.query(Project).filter(
        Project.customer_id == customer_id
    ).order_by(Project.created_at.desc()).all()

    active_projects = [p for p in projects if p.status == ProjectStatus.OPEN]

    projects_section = {
        "summary": {
            "total_projects": len(projects),
            "active_projects": len(active_projects),
            "completed_projects": sum(1 for p in projects if p.status == ProjectStatus.COMPLETED),
        },
        "projects": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "name": p.project_name,
                "type": p.project_type,
                "status": p.status.value if p.status else None,
                "priority": p.priority.value if p.priority else None,
                "percent_complete": float(p.percent_complete or 0),
                "expected_start": p.expected_start_date.isoformat() if p.expected_start_date else None,
                "expected_end": p.expected_end_date.isoformat() if p.expected_end_date else None,
                "actual_start": p.actual_start_date.isoformat() if p.actual_start_date else None,
                "actual_end": p.actual_end_date.isoformat() if p.actual_end_date else None,
                "is_overdue": p.is_overdue,
                "estimated_cost": float(p.estimated_costing or 0),
                "actual_cost": float(p.total_costing_amount or 0),
            }
            for p in projects
        ],
    }

    # -------------------------------------------------------------------------
    # CRM
    # -------------------------------------------------------------------------
    # Conversations (Chatwoot)
    conversations = db.query(Conversation).filter(
        Conversation.customer_id == customer_id
    ).order_by(Conversation.created_at.desc()).limit(20).all()

    conv_stats = db.query(
        func.count(Conversation.id).label("total"),
        func.sum(case((Conversation.status == ConversationStatus.OPEN, 1), else_=0)).label("open"),
    ).filter(Conversation.customer_id == customer_id).first()

    # Customer notes (Splynx)
    notes = db.query(CustomerNote).filter(
        CustomerNote.customer_id == customer_id
    ).order_by(CustomerNote.note_datetime.desc().nullslast()).limit(20).all()

    crm = {
        "summary": {
            "total_conversations": conv_stats.total if conv_stats else 0,
            "open_conversations": conv_stats.open if conv_stats else 0,
            "total_notes": len(notes),
        },
        "conversations": [
            {
                "id": c.id,
                "chatwoot_id": c.chatwoot_id,
                "status": c.status.value if c.status else None,
                "channel": c.channel,
                "assignee": c.assigned_agent_name,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "last_activity": c.last_activity_at.isoformat() if c.last_activity_at else None,
            }
            for c in conversations
        ],
        "notes": [
            {
                "id": n.id,
                "type": n.note_type,
                "title": n.title,
                "comment": n.comment[:300] if n.comment else None,
                "is_pinned": n.is_pinned,
                "is_done": n.is_done,
                "created_at": n.note_datetime.isoformat() if n.note_datetime else None,
            }
            for n in notes
        ],
    }

    # -------------------------------------------------------------------------
    # TIMELINE (recent activity across all domains)
    # -------------------------------------------------------------------------
    timeline = []

    # Add recent invoices to timeline
    for inv in recent_invoices[:5]:
        timeline.append({
            "type": "invoice",
            "date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "title": f"Invoice {inv.invoice_number}",
            "description": f"Amount: {float(inv.total_amount or 0):,.2f} - {inv.status.value if inv.status else 'unknown'}",
            "status": inv.status.value if inv.status else None,
        })

    # Add recent payments to timeline
    for p in recent_payments[:5]:
        timeline.append({
            "type": "payment",
            "date": p.payment_date.isoformat() if p.payment_date else None,
            "title": f"Payment received",
            "description": f"Amount: {float(p.amount or 0):,.2f} via {p.payment_method or 'unknown'}",
            "status": "completed",
        })

    # Add recent tickets to timeline
    for t in tickets[:5]:
        timeline.append({
            "type": "ticket",
            "date": t.created_at.isoformat() if t.created_at else None,
            "title": t.subject or "Support ticket",
            "description": f"Priority: {t.priority.value if t.priority else 'normal'} - {t.status.value if t.status else 'unknown'}",
            "status": t.status.value if t.status else None,
        })

    # Add recent conversations to timeline
    for c in conversations[:5]:
        timeline.append({
            "type": "conversation",
            "date": c.created_at.isoformat() if c.created_at else None,
            "title": f"{c.channel or 'Chat'} conversation",
            "description": f"{c.message_count or 0} messages",
            "status": c.status.value if c.status else None,
        })

    # Sort timeline by date descending
    timeline.sort(key=lambda x: x["date"] or "", reverse=True)

    return {
        "customer_id": customer_id,
        "profile": profile,
        "finance": finance,
        "services": services,
        "network": network,
        "support": support,
        "projects": projects_section,
        "crm": crm,
        "timeline": timeline[:20],
        "generated_at": datetime.utcnow().isoformat(),
    }


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
    offset: int = 0,
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
    offset: int = 0,
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
                Payment.status == PaymentStatus.COMPLETED,
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
        Payment.status == PaymentStatus.COMPLETED
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
        .filter(Payment.status == PaymentStatus.COMPLETED)
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
        "generated_at": datetime.utcnow().isoformat(),
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
        "generated_at": datetime.utcnow().isoformat(),
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
    end_dt = _parse_date(end_date, "end_date") or datetime.utcnow()
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

    cutoff = datetime.utcnow() - timedelta(days=months * 30)

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
    start_dt = datetime.utcnow() - timedelta(days=days)

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
    start_dt = datetime.utcnow() - timedelta(days=days)

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
            Payment.status == PaymentStatus.COMPLETED,
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


# =============================================================================
# INSIGHTS
# =============================================================================

@router.get("/insights/segments", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-segments", ttl=CACHE_TTL["medium"])
async def get_customer_segments(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Advanced customer segmentation across multiple dimensions.

    Segments by: status, type, billing type, tenure, MRR tier, location.
    """
    # Status distribution
    status_dist = db.query(
        Customer.status,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).group_by(Customer.status).all()

    # Customer type distribution
    type_dist = db.query(
        Customer.customer_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).group_by(Customer.customer_type).all()

    # Billing type distribution
    billing_dist = db.query(
        Customer.billing_type,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).group_by(Customer.billing_type).all()

    # Tenure segments - derive from first subscription if signup_date missing
    first_sub = (
        db.query(
            Subscription.customer_id,
            func.min(Subscription.start_date).label("first_start")
        )
        .group_by(Subscription.customer_id)
        .subquery()
    )

    effective_signup = func.coalesce(Customer.signup_date, first_sub.c.first_start)
    days_since_signup = func.date_part("day", func.current_date() - effective_signup)
    tenure_bucket = case(
        (days_since_signup <= 30, 'New (0-30 days)'),
        (days_since_signup <= 90, 'Growing (31-90 days)'),
        (days_since_signup <= 365, 'Established (91-365 days)'),
        (days_since_signup <= 730, 'Loyal (1-2 years)'),
        else_='Long-term (2+ years)'
    )

    tenure_data = (
        db.query(
            tenure_bucket.label("segment"),
            func.count(Customer.id).label("count"),
        )
        .outerjoin(first_sub, first_sub.c.customer_id == Customer.id)
        .filter(effective_signup.isnot(None))
        .group_by(tenure_bucket)
        .all()
    )

    segment_order = [
        "New (0-30 days)",
        "Growing (31-90 days)",
        "Established (91-365 days)",
        "Loyal (1-2 years)",
        "Long-term (2+ years)",
    ]
    tenure_map = {row.segment: row.count for row in tenure_data}
    tenure_segments = [{"segment": seg, "count": tenure_map.get(seg, 0)} for seg in segment_order]

    # MRR segments - single aggregated query
    mrr_bucket = case(
        (or_(Customer.mrr.is_(None), Customer.mrr == 0), 'No MRR'),
        (Customer.mrr < 10000, 'Low (<10K)'),
        (Customer.mrr < 50000, 'Medium (10K-50K)'),
        (Customer.mrr < 200000, 'High (50K-200K)'),
        else_='Enterprise (200K+)'
    )

    mrr_data = (
        db.query(
            mrr_bucket.label("segment"),
            func.count(Customer.id).label("count"),
        )
        .group_by(mrr_bucket)
        .all()
    )

    mrr_order = ["No MRR", "Low (<10K)", "Medium (10K-50K)", "High (50K-200K)", "Enterprise (200K+)"]
    mrr_map = {row.segment: row.count for row in mrr_data}
    mrr_segments = [{"segment": seg, "count": mrr_map.get(seg, 0)} for seg in mrr_order]

    # Top cities
    city_dist = db.query(
        Customer.city,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).filter(Customer.city.isnot(None)).group_by(Customer.city).order_by(
        func.count(Customer.id).desc()
    ).limit(limit).all()

    return {
        "by_status": [
            {
                "status": _normalize_status(row.status) or "unknown",
                "count": row.count,
                "total_mrr": float(row.total_mrr or 0),
            }
            for row in status_dist
        ],
        "by_type": [
            {
                "type": row.customer_type.value if row.customer_type else "unknown",
                "count": row.count,
                "total_mrr": float(row.total_mrr or 0),
            }
            for row in type_dist
        ],
        "by_billing": [
            {
                "billing_type": row.billing_type.value if row.billing_type else "unknown",
                "count": row.count,
                "total_mrr": float(row.total_mrr or 0),
            }
            for row in billing_dist
        ],
        "by_tenure": tenure_segments,
        "by_mrr": mrr_segments,
        "by_city": [
            {
                "city": row.city,
                "count": row.count,
                "total_mrr": float(row.total_mrr or 0),
            }
            for row in city_dist
        ],
    }


@router.get("/insights/health", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-health", ttl=CACHE_TTL["short"])
async def get_customer_health(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Customer health analysis including payment behavior, support needs, and risk indicators.
    """
    total_active = db.query(Customer).filter(Customer.status == CustomerStatus.ACTIVE).count()

    # Payment behavior analysis
    customers_with_overdue = db.query(distinct(Invoice.customer_id)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).count()

    # Payment timing - SQL aggregated
    days_early = func.date_part("day", Invoice.due_date - Invoice.paid_date)
    payment_timing = db.query(
        func.sum(case(
            (and_(Invoice.paid_date <= Invoice.due_date, days_early > 3), 1),
            else_=0
        )).label("early"),
        func.sum(case(
            (and_(Invoice.paid_date <= Invoice.due_date, days_early <= 3), 1),
            else_=0
        )).label("on_time"),
        func.sum(case(
            (Invoice.paid_date > Invoice.due_date, 1),
            else_=0
        )).label("late"),
        func.count(Invoice.id).label("total_paid"),
    ).filter(
        Invoice.status == InvoiceStatus.PAID,
        Invoice.paid_date.isnot(None),
        Invoice.due_date.isnot(None)
    ).one()

    early_payments = int(payment_timing.early or 0)
    on_time_payments = int(payment_timing.on_time or 0)
    late_payments = int(payment_timing.late or 0)
    total_paid = int(payment_timing.total_paid or 0)

    # Support intensity (tickets per customer in last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    tickets_subq = db.query(
        Ticket.customer_id,
        func.count(Ticket.id).label("ticket_count")
    ).filter(
        Ticket.customer_id.isnot(None),
        Ticket.created_at >= thirty_days_ago
    ).group_by(Ticket.customer_id).subquery()

    ticket_intensity = db.query(
        func.count(tickets_subq.c.customer_id).label("customers_with_tickets"),
        func.sum(case((tickets_subq.c.ticket_count >= 3, 1), else_=0)).label("high_support")
    ).one()

    customers_with_tickets = int(ticket_intensity.customers_with_tickets or 0)
    high_support_customers = int(ticket_intensity.high_support or 0)

    # Churn indicators
    recently_cancelled = db.query(Customer).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date >= thirty_days_ago.date()
    ).count()

    recently_suspended = db.query(Customer).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).count()

    # Billing health - blocking risk analysis
    blocking_stats = db.query(
        func.count(Customer.id).label("total"),
        func.sum(Customer.mrr).label("mrr"),
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.days_until_blocking.isnot(None),
        Customer.days_until_blocking >= 0,
        Customer.days_until_blocking <= 7
    ).first()

    blocking_by_tier = db.query(
        case(
            (Customer.days_until_blocking <= 1, "blocking_today"),
            (Customer.days_until_blocking <= 3, "blocking_3_days"),
            else_="blocking_7_days"
        ).label("tier"),
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr")
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.days_until_blocking.isnot(None),
        Customer.days_until_blocking >= 0,
        Customer.days_until_blocking <= 7
    ).group_by("tier").all()

    tier_map = {row.tier: {"count": row.count, "mrr": float(row.mrr or 0)} for row in blocking_by_tier}

    # Negative deposit customers
    negative_deposit = db.query(
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("mrr")
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.deposit_balance.isnot(None),
        Customer.deposit_balance < 0
    ).first()

    return {
        "total_active_customers": total_active,
        "payment_behavior": {
            "customers_with_overdue": customers_with_overdue,
            "overdue_rate": round(customers_with_overdue / total_active * 100, 1) if total_active > 0 else 0,
            "payment_timing": {
                "early": early_payments,
                "on_time": on_time_payments,
                "late": late_payments,
                "total_paid_invoices": total_paid,
                "on_time_rate": round((early_payments + on_time_payments) / total_paid * 100, 1) if total_paid > 0 else 0,
            },
        },
        "support_intensity": {
            "customers_with_tickets_30d": customers_with_tickets,
            "high_support_customers": high_support_customers,
            "high_support_rate": round(high_support_customers / total_active * 100, 1) if total_active > 0 else 0,
        },
        "churn_indicators": {
            "recently_cancelled_30d": recently_cancelled,
            "currently_suspended": recently_suspended,
            "at_risk_total": customers_with_overdue + recently_suspended,
        },
        "billing_health": {
            "blocking_in_7_days": {
                "total": blocking_stats.total if blocking_stats else 0,
                "mrr_at_risk": float(blocking_stats.mrr or 0) if blocking_stats else 0,
            },
            "by_urgency": {
                "blocking_today": tier_map.get("blocking_today", {"count": 0, "mrr": 0}),
                "blocking_3_days": tier_map.get("blocking_3_days", {"count": 0, "mrr": 0}),
                "blocking_7_days": tier_map.get("blocking_7_days", {"count": 0, "mrr": 0}),
            },
            "negative_deposit": {
                "count": negative_deposit.count if negative_deposit else 0,
                "mrr": float(negative_deposit.mrr or 0) if negative_deposit else 0,
            },
        },
    }


@router.get("/insights/completeness", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-completeness", ttl=CACHE_TTL["medium"])
async def get_customer_completeness(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Data completeness analysis for customer records.
    Shows field fill rates and recommendations.
    """
    total_customers = db.query(Customer).count()

    if total_customers == 0:
        return {"error": "No customer data available", "total_customers": 0}

    # Field completeness counts
    fields = {
        "email": db.query(Customer).filter(Customer.email.isnot(None), Customer.email != "").count(),
        "phone": db.query(Customer).filter(Customer.phone.isnot(None), Customer.phone != "").count(),
        "address": db.query(Customer).filter(Customer.address.isnot(None), Customer.address != "").count(),
        "city": db.query(Customer).filter(Customer.city.isnot(None), Customer.city != "").count(),
        "state": db.query(Customer).filter(Customer.state.isnot(None), Customer.state != "").count(),
        "gps_coordinates": db.query(Customer).filter(
            and_(Customer.latitude.isnot(None), Customer.longitude.isnot(None))
        ).count(),
        "pop_assigned": db.query(Customer).filter(Customer.pop_id.isnot(None)).count(),
        "account_number": db.query(Customer).filter(Customer.account_number.isnot(None)).count(),
        "signup_date": db.query(Customer).filter(Customer.signup_date.isnot(None)).count(),
    }

    # System linkage
    linkage = {
        "splynx_linked": db.query(Customer).filter(Customer.splynx_id.isnot(None)).count(),
        "erpnext_linked": db.query(Customer).filter(Customer.erpnext_id.isnot(None)).count(),
        "chatwoot_linked": db.query(Customer).filter(Customer.chatwoot_contact_id.isnot(None)).count(),
    }

    # Calculate scores
    critical_fields = ["email", "phone", "signup_date"]
    critical_score = sum(fields[f] for f in critical_fields) / (len(critical_fields) * total_customers) * 100
    all_fields_score = sum(fields.values()) / (len(fields) * total_customers) * 100

    # Generate recommendations
    recommendations = []
    if fields["email"] < total_customers * 0.95:
        recommendations.append({
            "priority": "high",
            "field": "email",
            "issue": f"Missing email for {total_customers - fields['email']} customers",
            "action": "Collect emails during support interactions",
        })
    if fields["gps_coordinates"] < total_customers * 0.5:
        recommendations.append({
            "priority": "medium",
            "field": "gps_coordinates",
            "issue": f"Missing GPS for {total_customers - fields['gps_coordinates']} customers",
            "action": "Geocode addresses or collect during installation",
        })
    if fields["pop_assigned"] < total_customers * 0.8:
        recommendations.append({
            "priority": "medium",
            "field": "pop_assigned",
            "issue": f"{total_customers - fields['pop_assigned']} customers without POP",
            "action": "Assign customers to nearest POP based on location",
        })

    return {
        "total_customers": total_customers,
        "scores": {
            "critical_completeness": round(critical_score, 1),
            "overall_completeness": round(all_fields_score, 1),
        },
        "fields": {
            field: {
                "count": count,
                "percent": round(count / total_customers * 100, 1),
                "missing": total_customers - count,
            }
            for field, count in fields.items()
        },
        "system_linkage": {
            key: {
                "count": count,
                "percent": round(count / total_customers * 100, 1),
            }
            for key, count in linkage.items()
        },
        "recommendations": recommendations,
    }


@router.get("/insights/plan-changes", dependencies=[Depends(Require("analytics:read"))])
async def get_plan_changes_insights(
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Analyze plan changes (upgrades/downgrades/lateral moves) over the past N months.
    """
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    subs = (
        db.query(Subscription)
        .filter(
            Subscription.start_date.isnot(None),
            Subscription.start_date >= start_dt,
        )
        .order_by(Subscription.customer_id, Subscription.start_date)
        .all()
    )

    transitions: List[Dict[str, Any]] = []
    customers_with_changes = set()

    for _, cust_subs in groupby(subs, key=lambda s: s.customer_id):
        history = list(cust_subs)
        if len(history) < 2:
            continue
        customers_with_changes.add(history[0].customer_id)
        history = sorted(history, key=lambda s: s.start_date or datetime.min)
        for prev, curr in zip(history, history[1:]):
            prev_price = float(prev.price or 0)
            curr_price = float(curr.price or 0)
            if curr_price > prev_price:
                change_type = "upgrade"
            elif curr_price < prev_price:
                change_type = "downgrade"
            else:
                change_type = "lateral"
            transitions.append(
                {
                    "customer_id": curr.customer_id,
                    "from_plan": prev.plan_name,
                    "to_plan": curr.plan_name,
                    "price_change": round(curr_price - prev_price, 2),
                    "change_type": change_type,
                    "date": (curr.start_date or end_dt).date().isoformat(),
                }
            )

    upgrades = sum(1 for t in transitions if t["change_type"] == "upgrade")
    downgrades = sum(1 for t in transitions if t["change_type"] == "downgrade")
    lateral = sum(1 for t in transitions if t["change_type"] == "lateral")

    upgrade_mrr = sum(t["price_change"] for t in transitions if t["change_type"] == "upgrade")
    downgrade_mrr = sum(abs(t["price_change"]) for t in transitions if t["change_type"] == "downgrade")
    net_mrr = upgrade_mrr - downgrade_mrr

    active_customers = db.query(func.count(Customer.id)).filter(Customer.status == CustomerStatus.ACTIVE).scalar() or 0

    transition_counts: Dict[str, Dict[str, Any]] = {}
    for t in transitions:
        key = f"{t['from_plan']} -> {t['to_plan']}"
        if key not in transition_counts:
            transition_counts[key] = {"count": 0, "type": t["change_type"]}
        transition_counts[key]["count"] += 1

    common_transitions = sorted(
        [
            {"transition": k, "count": v["count"], "type": v["type"]}
            for k, v in transition_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:20]

    recent_changes = sorted(transitions, key=lambda t: t["date"], reverse=True)[:20]

    customers_changed = len(customers_with_changes)
    total_changes = len(transitions)

    upgrade_rate = round(upgrades / active_customers * 100, 2) if active_customers else 0
    downgrade_rate = round(downgrades / active_customers * 100, 2) if active_customers else 0
    upgrade_to_downgrade_ratio = round(upgrades / downgrades, 2) if downgrades else (upgrades if upgrades else 0)

    return {
        "period_months": months,
        "summary": {
            "customers_with_plan_changes": customers_changed,
            "total_changes": total_changes,
            "upgrades": upgrades,
            "downgrades": downgrades,
            "lateral_moves": lateral,
        },
        "revenue_impact": {
            "upgrade_mrr_gained": round(upgrade_mrr, 2),
            "downgrade_mrr_lost": round(downgrade_mrr, 2),
            "net_mrr_change": round(net_mrr, 2),
        },
        "rates": {
            "upgrade_rate": upgrade_rate,
            "downgrade_rate": downgrade_rate,
            "upgrade_to_downgrade_ratio": upgrade_to_downgrade_ratio,
        },
        "common_transitions": common_transitions,
        "recent_changes": recent_changes,
    }


@router.get("/insights/plan-changes", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-plan-changes", ttl=CACHE_TTL["medium"])
async def get_plan_change_insights(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Analyze plan upgrades, downgrades, and changes.

    Identifies customers who changed plans by looking at subscription history
    where the same customer has multiple subscription records with different
    plans over time.
    """
    start_dt = datetime.utcnow() - timedelta(days=months * 30)

    # Get customers with multiple different plans (indicating plan changes)
    # Subquery: customers with >1 distinct plan names
    plan_changes_subq = (
        db.query(
            Subscription.customer_id,
            func.count(func.distinct(Subscription.plan_name)).label("plan_count")
        )
        .filter(Subscription.start_date >= start_dt)
        .group_by(Subscription.customer_id)
        .having(func.count(func.distinct(Subscription.plan_name)) > 1)
        .subquery()
    )

    customers_with_changes = db.query(func.count(plan_changes_subq.c.customer_id)).scalar() or 0

    # Get the actual plan transitions
    # For each customer, find consecutive subscriptions with different plans
    plan_transitions = (
        db.query(
            Subscription.customer_id,
            Subscription.plan_name,
            Subscription.price,
            Subscription.start_date,
        )
        .filter(
            Subscription.start_date >= start_dt,
            Subscription.customer_id.in_(
                db.query(plan_changes_subq.c.customer_id)
            )
        )
        .order_by(Subscription.customer_id, Subscription.start_date)
        .all()
    )

    # Analyze transitions
    upgrades = 0
    downgrades = 0
    lateral_moves = 0
    upgrade_revenue = 0.0
    downgrade_revenue = 0.0
    transition_details: List[Dict[str, Any]] = []

    current_customer: Optional[int] = None
    prev_plan: Optional[str] = None
    prev_price: float = 0.0

    for sub in plan_transitions:
        if sub.customer_id != current_customer:
            # New customer
            current_customer = sub.customer_id
            prev_plan = sub.plan_name
            prev_price = float(sub.price or 0)
        else:
            # Same customer, check for plan change
            if sub.plan_name != prev_plan:
                current_price = float(sub.price or 0)
                price_diff = current_price - prev_price

                if price_diff > 0:
                    upgrades += 1
                    upgrade_revenue += price_diff
                    change_type = "upgrade"
                elif price_diff < 0:
                    downgrades += 1
                    downgrade_revenue += abs(price_diff)
                    change_type = "downgrade"
                else:
                    lateral_moves += 1
                    change_type = "lateral"

                if len(transition_details) < 50:  # Limit details
                    transition_details.append({
                        "customer_id": sub.customer_id,
                        "from_plan": prev_plan,
                        "to_plan": sub.plan_name,
                        "price_change": price_diff,
                        "change_type": change_type,
                        "date": sub.start_date.isoformat() if sub.start_date else None,
                    })

                prev_plan = sub.plan_name
                prev_price = current_price

    total_changes = upgrades + downgrades + lateral_moves

    # Most common upgrades/downgrades by plan
    from_to_counts = {}
    for t in transition_details:
        key = f"{t['from_plan']} → {t['to_plan']}"
        if key not in from_to_counts:
            from_to_counts[key] = {"count": 0, "type": t["change_type"]}
        from_to_counts[key]["count"] += 1

    common_transitions = sorted(
        [{"transition": k, "count": v["count"], "type": v["type"]} for k, v in from_to_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]

    return {
        "period_months": months,
        "summary": {
            "customers_with_plan_changes": customers_with_changes,
            "total_changes": total_changes,
            "upgrades": upgrades,
            "downgrades": downgrades,
            "lateral_moves": lateral_moves,
        },
        "revenue_impact": {
            "upgrade_mrr_gained": round(upgrade_revenue, 2),
            "downgrade_mrr_lost": round(downgrade_revenue, 2),
            "net_mrr_change": round(upgrade_revenue - downgrade_revenue, 2),
        },
        "rates": {
            "upgrade_rate": round(upgrades / total_changes * 100, 1) if total_changes > 0 else 0,
            "downgrade_rate": round(downgrades / total_changes * 100, 1) if total_changes > 0 else 0,
            "upgrade_to_downgrade_ratio": round(upgrades / downgrades, 2) if downgrades > 0 else upgrades,
        },
        "common_transitions": common_transitions,
        "recent_changes": transition_details[:20],
    }

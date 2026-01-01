"""
Customer 360 Endpoints
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
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

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
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }



"""
Deep Insights API - Comprehensive analytics for data relationships,
completeness, and actionable intelligence.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query  # Depends still needed for get_db
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct, and_, or_, extract, text, cast
from sqlalchemy.sql.sqltypes import Date
from sqlalchemy.sql import label
from typing import Dict, Any, List, Optional
from itertools import groupby
from datetime import datetime, timedelta
from decimal import Decimal

from app.database import get_db
from app.config import settings
from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.credit_note import CreditNote
from app.models.pop import Pop
from app.models.employee import Employee
from app.models.tariff import Tariff
from app.models.lead import Lead
from app.models.project import Project
from app.models.router import Router
from app.models.customer_note import CustomerNote
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_statement_timeout(db: Session) -> None:
    """Apply per-request statement timeout for Postgres connections."""
    timeout_ms = getattr(settings, "analytics_statement_timeout_ms", None)
    if not timeout_ms or not db.bind or db.bind.dialect.name != "postgresql":
        return
    try:
        db.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": timeout_ms})
    except Exception:
        # Rollback the failed transaction to allow subsequent queries to work
        db.rollback()
        return


# ============================================================================
# DATA COMPLETENESS & QUALITY
# ============================================================================

@router.get("/data-completeness", dependencies=[Depends(Require("analytics:read"))])
@cached("data-completeness", ttl=CACHE_TTL["medium"], include_principal=True)
async def get_data_completeness(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Comprehensive data completeness analysis across all entities.
    Shows what data is available, missing, and the quality score.
    """
    _apply_statement_timeout(db)
    total_customers = db.query(Customer).count()

    if total_customers == 0:
        return {"error": "No customer data available", "total_customers": 0}

    # Customer field completeness
    customer_fields = {
        "email": db.query(Customer).filter(Customer.email.isnot(None), Customer.email != "").count(),
        "billing_email": db.query(Customer).filter(Customer.billing_email.isnot(None)).count(),
        "phone": db.query(Customer).filter(Customer.phone.isnot(None), Customer.phone != "").count(),
        "phone_secondary": db.query(Customer).filter(Customer.phone_secondary.isnot(None)).count(),
        "address": db.query(Customer).filter(Customer.address.isnot(None), Customer.address != "").count(),
        "city": db.query(Customer).filter(Customer.city.isnot(None), Customer.city != "").count(),
        "state": db.query(Customer).filter(Customer.state.isnot(None), Customer.state != "").count(),
        "zip_code": db.query(Customer).filter(Customer.zip_code.isnot(None)).count(),
        "gps_coordinates": db.query(Customer).filter(
            and_(Customer.latitude.isnot(None), Customer.longitude.isnot(None))
        ).count(),
        "pop_assigned": db.query(Customer).filter(Customer.pop_id.isnot(None)).count(),
        "account_number": db.query(Customer).filter(Customer.account_number.isnot(None)).count(),
        "signup_date": db.query(Customer).filter(Customer.signup_date.isnot(None)).count(),
    }

    # System linkage
    system_linkage = {
        "splynx_linked": db.query(Customer).filter(Customer.splynx_id.isnot(None)).count(),
        "erpnext_linked": db.query(Customer).filter(Customer.erpnext_id.isnot(None)).count(),
        "chatwoot_linked": db.query(Customer).filter(Customer.chatwoot_contact_id.isnot(None)).count(),
        "zoho_linked": db.query(Customer).filter(Customer.zoho_id.isnot(None)).count(),
    }

    # Calculate completeness percentages
    critical_fields = ["email", "phone", "address", "city"]
    critical_score = sum(customer_fields[f] for f in critical_fields) / (len(critical_fields) * total_customers) * 100

    all_fields_score = sum(customer_fields.values()) / (len(customer_fields) * total_customers) * 100

    # Subscription completeness
    total_subs = db.query(Subscription).count()
    sub_completeness = {
        "total": total_subs,
        "with_tariff": db.query(Subscription).filter(Subscription.tariff_id.isnot(None)).count(),
        "with_router": db.query(Subscription).filter(Subscription.router_id.isnot(None)).count(),
        "with_ip_assigned": db.query(Subscription).filter(
            or_(Subscription.ipv4_address.isnot(None), Subscription.ipv6_address.isnot(None))
        ).count(),
        "with_mac_address": db.query(Subscription).filter(Subscription.mac_address.isnot(None)).count(),
    }

    # Invoice/Payment linking
    total_invoices = db.query(Invoice).count()
    total_payments = db.query(Payment).count()

    invoice_quality = {
        "total": total_invoices,
        "with_customer": db.query(Invoice).filter(Invoice.customer_id.isnot(None)).count(),
        "orphaned": db.query(Invoice).filter(Invoice.customer_id.is_(None)).count(),
        "with_due_date": db.query(Invoice).filter(Invoice.due_date.isnot(None)).count(),
    }

    payment_quality = {
        "total": total_payments,
        "with_customer": db.query(Payment).filter(Payment.customer_id.isnot(None)).count(),
        "with_invoice": db.query(Payment).filter(Payment.invoice_id.isnot(None)).count(),
        "orphaned": db.query(Payment).filter(
            and_(Payment.customer_id.is_(None), Payment.invoice_id.is_(None))
        ).count(),
    }

    # Conversation/Ticket linking
    total_convos = db.query(Conversation).count()
    total_tickets = db.query(Ticket).count()

    support_quality = {
        "conversations": {
            "total": total_convos,
            "linked_to_customer": db.query(Conversation).filter(Conversation.customer_id.isnot(None)).count(),
            "orphaned": db.query(Conversation).filter(Conversation.customer_id.is_(None)).count(),
        },
        "tickets": {
            "total": total_tickets,
            "linked_to_customer": db.query(Ticket).filter(Ticket.customer_id.isnot(None)).count(),
            "orphaned": db.query(Ticket).filter(Ticket.customer_id.is_(None)).count(),
            "assigned_to_employee": db.query(Ticket).filter(Ticket.assigned_employee_id.isnot(None)).count(),
        }
    }

    return {
        "summary": {
            "total_customers": total_customers,
            "critical_completeness_score": round(critical_score, 1),
            "overall_completeness_score": round(all_fields_score, 1),
            "grade": "A" if critical_score >= 90 else "B" if critical_score >= 75 else "C" if critical_score >= 60 else "D" if critical_score >= 40 else "F",
        },
        "customer_fields": {
            field: {
                "count": count,
                "percent": round(count / total_customers * 100, 1),
                "missing": total_customers - count,
            }
            for field, count in customer_fields.items()
        },
        "system_linkage": {
            system: {
                "count": count,
                "percent": round(count / total_customers * 100, 1),
            }
            for system, count in system_linkage.items()
        },
        "subscriptions": sub_completeness,
        "invoices": invoice_quality,
        "payments": payment_quality,
        "support": support_quality,
        "recommendations": _generate_completeness_recommendations(customer_fields, total_customers, system_linkage),
    }


def _generate_completeness_recommendations(fields: Dict, total: int, linkage: Dict) -> List[Dict]:
    """Generate actionable recommendations based on data completeness."""
    recommendations = []

    if fields["email"] / total < 0.9:
        recommendations.append({
            "priority": "high",
            "category": "contact",
            "issue": f"Missing email for {total - fields['email']} customers ({round((1 - fields['email']/total) * 100, 1)}%)",
            "action": "Run email collection campaign or sync from external systems",
            "impact": "Critical for billing notifications and communication",
        })

    if fields["phone"] / total < 0.85:
        recommendations.append({
            "priority": "high",
            "category": "contact",
            "issue": f"Missing phone for {total - fields['phone']} customers",
            "action": "Collect phone numbers during customer interactions",
            "impact": "Needed for support and urgent communications",
        })

    if fields["gps_coordinates"] / total < 0.5:
        recommendations.append({
            "priority": "medium",
            "category": "location",
            "issue": f"Missing GPS coordinates for {total - fields['gps_coordinates']} customers",
            "action": "Geocode customer addresses or collect during installation",
            "impact": "Improves network planning and service area analysis",
        })

    if fields["pop_assigned"] / total < 0.95:
        recommendations.append({
            "priority": "high",
            "category": "network",
            "issue": f"{total - fields['pop_assigned']} customers without POP assignment",
            "action": "Assign customers to nearest POP based on location",
            "impact": "Critical for network capacity planning",
        })

    if linkage["chatwoot_linked"] / total < 0.7:
        recommendations.append({
            "priority": "medium",
            "category": "integration",
            "issue": f"{total - linkage['chatwoot_linked']} customers not linked to Chatwoot",
            "action": "Run customer matching between systems using email/phone",
            "impact": "Enables unified customer support view",
        })

    return recommendations


# ============================================================================
# CUSTOMER INSIGHTS & SEGMENTATION
# ============================================================================

@router.get("/customer-segments", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-segments", ttl=CACHE_TTL["medium"], include_principal=True)
async def get_customer_segments(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Advanced customer segmentation based on multiple dimensions.
    """
    _apply_statement_timeout(db)
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

    # Tenure segments - single aggregated query
    days_since_signup = func.date_part("day", func.current_date() - Customer.signup_date)
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
        .filter(Customer.signup_date.isnot(None))
        .group_by(tenure_bucket)
        .all()
    )

    # Ensure all segments are represented in order
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

    # Geographic distribution (top cities)
    city_dist = db.query(
        Customer.city,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).filter(Customer.city.isnot(None)).group_by(Customer.city).order_by(
        func.count(Customer.id).desc()
    ).limit(limit).all()

    # POP distribution
    pop_dist = db.query(
        Pop.name,
        Pop.city,
        func.count(Customer.id).label("customer_count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).join(Customer, Customer.pop_id == Pop.id).group_by(
        Pop.id, Pop.name, Pop.city
    ).order_by(func.count(Customer.id).desc()).limit(limit).all()

    return {
        "by_status": [
            {
                "status": row.status.value if row.status else "unknown",
                "count": row.count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in status_dist
        ],
        "by_type": [
            {
                "type": row.customer_type.value if row.customer_type else "unknown",
                "count": row.count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in type_dist
        ],
        "by_billing_type": [
            {
                "billing_type": row.billing_type.value if row.billing_type else "unknown",
                "count": row.count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in billing_dist
        ],
        "by_tenure": tenure_segments,
        "by_mrr_tier": mrr_segments,
        "by_city": [
            {
                "city": row.city or "Unknown",
                "count": row.count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in city_dist
        ],
        "by_pop": [
            {
                "pop_name": row.name,
                "city": row.city,
                "customer_count": row.customer_count,
                "mrr": float(row.total_mrr or 0),
            }
            for row in pop_dist
        ],
    }


@router.get("/customer-health", dependencies=[Depends(Require("analytics:read"))])
@cached("customer-health", ttl=CACHE_TTL["short"], include_principal=True)
async def get_customer_health(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Customer health analysis including payment behavior, support needs, and risk indicators.
    """
    _apply_statement_timeout(db)
    total_active = db.query(Customer).filter(Customer.status == CustomerStatus.ACTIVE).count()

    # Payment behavior analysis
    # Customers with overdue invoices
    customers_with_overdue = db.query(distinct(Invoice.customer_id)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).count()

    # Average payment timing - keep processing in SQL to avoid loading all invoices
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

    # Support intensity (tickets per customer)
    tickets_per_customer = db.query(
        Ticket.customer_id,
        func.count(Ticket.id).label("ticket_count")
    ).filter(
        Ticket.customer_id.isnot(None),
        Ticket.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(Ticket.customer_id).subquery()

    ticket_intensity = db.query(
        func.count(tickets_per_customer.c.customer_id).label("customers_with_tickets_30d"),
        func.sum(case((tickets_per_customer.c.ticket_count >= 3, 1), else_=0)).label("high_support_customers")
    ).one()
    customers_with_tickets_30d = int(ticket_intensity.customers_with_tickets_30d or 0)
    high_support_customers = int(ticket_intensity.high_support_customers or 0)

    # Conversation activity
    convos_per_customer = db.query(
        Conversation.customer_id,
        func.count(Conversation.id).label("convo_count")
    ).filter(
        Conversation.customer_id.isnot(None),
        Conversation.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(Conversation.customer_id).subquery()

    convo_intensity = db.query(
        func.count(convos_per_customer.c.customer_id).label("customers_with_conversations_30d")
    ).one()
    customers_with_conversations_30d = int(convo_intensity.customers_with_conversations_30d or 0)

    # Churn indicators
    recently_cancelled = db.query(Customer).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date >= datetime.utcnow() - timedelta(days=30)
    ).count()

    recently_suspended = db.query(Customer).filter(
        Customer.status == CustomerStatus.SUSPENDED
    ).count()

    # Inactive customers (no recent activity)
    customers_with_recent_payment = db.query(distinct(Payment.customer_id)).filter(
        Payment.payment_date >= datetime.utcnow() - timedelta(days=60)
    ).count()

    return {
        "summary": {
            "total_active_customers": total_active,
            "healthy_percent": round((total_active - customers_with_overdue - high_support_customers) / max(total_active, 1) * 100, 1),
        },
        "payment_behavior": {
            "customers_with_overdue": customers_with_overdue,
            "overdue_percent": round(customers_with_overdue / max(total_active, 1) * 100, 1),
            "payment_timing": {
                "early": early_payments,
                "on_time": on_time_payments,
                "late": late_payments,
                "total_paid_invoices": total_paid,
            },
            "payment_timing_distribution": {
                "early_percent": round(early_payments / max(total_paid, 1) * 100, 1),
                "on_time_percent": round(on_time_payments / max(total_paid, 1) * 100, 1),
                "late_percent": round(late_payments / max(total_paid, 1) * 100, 1),
            },
        },
        "support_intensity": {
            "customers_with_tickets_30d": customers_with_tickets_30d,
            "high_support_customers": high_support_customers,
            "customers_with_conversations_30d": customers_with_conversations_30d,
        },
        "churn_indicators": {
            "recently_cancelled_30d": recently_cancelled,
            "currently_suspended": recently_suspended,
            "inactive_60d": total_active - customers_with_recent_payment,
        },
        "risk_segments": {
            "at_risk": customers_with_overdue + recently_suspended,
            "high_maintenance": high_support_customers,
            "churned_30d": recently_cancelled,
        }
    }


@router.get("/churn-risk", dependencies=[Depends(Require("analytics:read"))])
async def get_churn_risk(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Alias endpoint summarizing churn risks."""
    _apply_statement_timeout(db)
    overdue_customers = db.query(distinct(Invoice.customer_id)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).count()
    recently_cancelled = db.query(Customer).filter(
        Customer.status == CustomerStatus.INACTIVE,
        Customer.cancellation_date >= datetime.utcnow() - timedelta(days=30)
    ).count()
    suspended = db.query(Customer).filter(Customer.status == CustomerStatus.SUSPENDED).count()
    high_ticket_customers = db.query(func.count(Customer.id)).join(
        Ticket, Ticket.customer_id == Customer.id
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).group_by(Customer.id).having(func.count(Ticket.id) >= 3).count()

    return {
        "summary": {
            "overdue_customers": overdue_customers,
            "recent_cancellations_30d": recently_cancelled,
            "suspended_customers": suspended,
            "high_ticket_customers": high_ticket_customers,
        }
    }


@router.get("/plan-changes", dependencies=[Depends(Require("analytics:read"))])
async def get_plan_changes(
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Plan change insights (upgrade/downgrade/lateral) over the past N months."""
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


# ============================================================================
# RELATIONSHIP ANALYSIS
# ============================================================================

@router.get("/relationship-map", dependencies=[Depends(Require("analytics:read"))])
@cached("relationship-map", ttl=CACHE_TTL["medium"], include_principal=True)
async def get_relationship_map(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Analyze relationships between entities and identify orphaned/unlinked records.
    """
    _apply_statement_timeout(db)
    # Entity counts
    entities = {
        "customers": db.query(Customer).count(),
        "subscriptions": db.query(Subscription).count(),
        "invoices": db.query(Invoice).count(),
        "payments": db.query(Payment).count(),
        "conversations": db.query(Conversation).count(),
        "tickets": db.query(Ticket).count(),
        "credit_notes": db.query(CreditNote).count(),
        "projects": db.query(Project).count(),
        "employees": db.query(Employee).count(),
        "pops": db.query(Pop).count(),
        "tariffs": db.query(Tariff).count(),
        "routers": db.query(Router).count(),
        "leads": db.query(Lead).count(),
    }

    # Relationship coverage
    relationships = {
        "subscriptions_to_customers": {
            "linked": db.query(Subscription).filter(Subscription.customer_id.isnot(None)).count(),
            "orphaned": db.query(Subscription).filter(Subscription.customer_id.is_(None)).count(),
        },
        "subscriptions_to_tariffs": {
            "linked": db.query(Subscription).filter(Subscription.tariff_id.isnot(None)).count(),
            "orphaned": db.query(Subscription).filter(Subscription.tariff_id.is_(None)).count(),
        },
        "invoices_to_customers": {
            "linked": db.query(Invoice).filter(Invoice.customer_id.isnot(None)).count(),
            "orphaned": db.query(Invoice).filter(Invoice.customer_id.is_(None)).count(),
        },
        "payments_to_customers": {
            "linked": db.query(Payment).filter(Payment.customer_id.isnot(None)).count(),
            "orphaned": db.query(Payment).filter(Payment.customer_id.is_(None)).count(),
        },
        "payments_to_invoices": {
            "linked": db.query(Payment).filter(Payment.invoice_id.isnot(None)).count(),
            "unlinked": db.query(Payment).filter(Payment.invoice_id.is_(None)).count(),
        },
        "conversations_to_customers": {
            "linked": db.query(Conversation).filter(Conversation.customer_id.isnot(None)).count(),
            "orphaned": db.query(Conversation).filter(Conversation.customer_id.is_(None)).count(),
        },
        "tickets_to_customers": {
            "linked": db.query(Ticket).filter(Ticket.customer_id.isnot(None)).count(),
            "orphaned": db.query(Ticket).filter(Ticket.customer_id.is_(None)).count(),
        },
        "tickets_to_employees": {
            "assigned": db.query(Ticket).filter(Ticket.assigned_employee_id.isnot(None)).count(),
            "unassigned": db.query(Ticket).filter(Ticket.assigned_employee_id.is_(None)).count(),
        },
        "customers_to_pops": {
            "linked": db.query(Customer).filter(Customer.pop_id.isnot(None)).count(),
            "orphaned": db.query(Customer).filter(Customer.pop_id.is_(None)).count(),
        },
        "leads_converted": {
            "converted": db.query(Lead).filter(Lead.customer_id.isnot(None)).count(),
            "not_converted": db.query(Lead).filter(Lead.customer_id.is_(None)).count(),
        },
    }

    # Calculate relationship health scores
    relationship_scores = {}
    for rel_name, data in relationships.items():
        total = data.get("linked", 0) + data.get("orphaned", data.get("unlinked", data.get("unassigned", data.get("not_converted", 0))))
        if total > 0:
            linked = data.get("linked", data.get("assigned", data.get("converted", 0)))
            relationship_scores[rel_name] = round(linked / total * 100, 1)
        else:
            relationship_scores[rel_name] = 100.0

    # Customer with most complete data
    avg_relationships_per_customer = db.query(
        func.count(distinct(Subscription.id)).label("subs"),
        func.count(distinct(Invoice.id)).label("invoices"),
        func.count(distinct(Payment.id)).label("payments"),
        func.count(distinct(Conversation.id)).label("conversations"),
        func.count(distinct(Ticket.id)).label("tickets"),
    ).select_from(Customer).outerjoin(
        Subscription, Subscription.customer_id == Customer.id
    ).outerjoin(
        Invoice, Invoice.customer_id == Customer.id
    ).outerjoin(
        Payment, Payment.customer_id == Customer.id
    ).outerjoin(
        Conversation, Conversation.customer_id == Customer.id
    ).outerjoin(
        Ticket, Ticket.customer_id == Customer.id
    ).first()

    return {
        "entity_counts": entities,
        "relationships": relationships,
        "relationship_health_scores": relationship_scores,
        "average_overall_score": round(sum(relationship_scores.values()) / len(relationship_scores), 1),
    }


# ============================================================================
# FINANCIAL INSIGHTS
# ============================================================================

@router.get("/financial-insights", dependencies=[Depends(Require("analytics:read"))])
@cached("financial-insights", ttl=CACHE_TTL["medium"], include_principal=True)
async def get_financial_insights(
    months: int = Query(default=12, le=36),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Deep financial analysis including revenue patterns, payment behavior, and forecasting indicators.
    """
    _apply_statement_timeout(db)
    try:
        # Total MRR
        total_mrr = db.query(func.sum(Customer.mrr)).filter(
            Customer.status == CustomerStatus.ACTIVE
        ).scalar() or 0

        # Revenue by customer type
        mrr_by_type = db.query(
            Customer.customer_type,
            func.sum(Customer.mrr).label("mrr"),
            func.count(Customer.id).label("count")
        ).filter(
            Customer.status == CustomerStatus.ACTIVE
        ).group_by(Customer.customer_type).all()

        # Invoice aging
        aging_buckets: Dict[str, Dict[str, Any]] = {
            "current": {"count": 0, "amount": 0.0},
            "1_30_days": {"count": 0, "amount": 0.0},
            "31_60_days": {"count": 0, "amount": 0.0},
            "61_90_days": {"count": 0, "amount": 0.0},
            "over_90_days": {"count": 0, "amount": 0.0},
        }

        days_overdue = func.date_part("day", func.current_date() - cast(Invoice.due_date, Date))
        invoice_balance = func.coalesce(Invoice.total_amount, 0) - func.coalesce(Invoice.amount_paid, 0)
        aging_bucket = case(
            (days_overdue <= 0, "current"),
            (days_overdue <= 30, "1_30_days"),
            (days_overdue <= 60, "31_60_days"),
            (days_overdue <= 90, "61_90_days"),
            else_="over_90_days",
        )

        overdue_by_bucket = db.query(
            aging_bucket.label("bucket"),
            func.count(Invoice.id).label("count"),
            func.sum(invoice_balance).label("amount")
        ).filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.due_date.isnot(None)
        ).group_by(
            aging_bucket
        ).all()

        for row in overdue_by_bucket:
            aging_buckets[row.bucket]["count"] = row.count
            aging_buckets[row.bucket]["amount"] = float(row.amount or 0)

        # Payment method distribution
        payment_methods = db.query(
            Payment.payment_method,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("total")
        ).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
        ).group_by(Payment.payment_method).all()

        # Credit notes impact
        total_credits = db.query(func.sum(CreditNote.amount)).filter(
            CreditNote.status.in_(["issued", "applied"])
        ).scalar() or 0

        # Monthly revenue trend
        revenue_trend = db.query(
            extract('year', Payment.payment_date).label('year'),
            extract('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('total')
        ).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date.isnot(None),
            Payment.payment_date >= datetime.utcnow() - timedelta(days=months * 30)
        ).group_by(
            extract('year', Payment.payment_date),
            extract('month', Payment.payment_date)
        ).order_by(
            extract('year', Payment.payment_date),
            extract('month', Payment.payment_date)
        ).all()

        return {
            "mrr": {
                "total": float(total_mrr),
                "by_customer_type": [
                    {
                        "type": row.customer_type.value if row.customer_type else "unknown",
                        "mrr": float(row.mrr or 0),
                        "customer_count": row.count,
                        "avg_mrr": round(float(row.mrr or 0) / max(int(getattr(row, "count", 1) or 1), 1), 2),
                    }
                    for row in mrr_by_type
                ],
            },
            "invoice_aging": aging_buckets,
            "total_outstanding": sum(b["amount"] for b in aging_buckets.values()),
            "payment_methods": [
                {
                    "method": row.payment_method.value if row.payment_method else "unknown",
                    "count": row.count,
                    "total": float(row.total or 0),
                }
                for row in payment_methods
            ],
            "credit_notes_issued": float(total_credits),
            "revenue_trend": [
                {
                    "year": int(row.year),
                    "month": int(row.month),
                    "period": f"{int(row.year)}-{int(row.month):02d}",
                    "revenue": float(row.total or 0),
                }
                for row in revenue_trend
            ],
        }
    except Exception as exc:
        logger.exception("financial_insights_failed", extra={"error": str(exc)})
        return {"error": "financial insights unavailable"}


# ============================================================================
# OPERATIONAL INSIGHTS
# ============================================================================

@router.get("/operational-insights", dependencies=[Depends(Require("analytics:read"))])
@cached("operational-insights", ttl=CACHE_TTL["short"], include_principal=True)
async def get_operational_insights(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Operational metrics including support performance, network utilization, and employee productivity.
    """
    _apply_statement_timeout(db)
    since = datetime.utcnow() - timedelta(days=days)

    # Ticket analysis
    ticket_stats = db.query(
        func.count(Ticket.id).label("total"),
        func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
        func.avg(case(
            (
                and_(Ticket.status == TicketStatus.RESOLVED, Ticket.resolution_date.isnot(None)),
                func.extract('epoch', Ticket.resolution_date - Ticket.created_at) / 3600
            ),
            else_=None
        )).label("avg_resolution_hours"),
    ).filter(
        Ticket.created_at >= since
    ).one()
    total_tickets = int(ticket_stats.total or 0)
    resolved_tickets = int(ticket_stats.resolved or 0)
    avg_resolution_hours = float(ticket_stats.avg_resolution_hours or 0)

    tickets_by_priority_rows = db.query(
        Ticket.priority,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.created_at >= since
    ).group_by(Ticket.priority).all()
    tickets_by_priority = {
        (row.priority.value if row.priority else "unknown"): row.count
        for row in tickets_by_priority_rows
    }

    # Conversation analysis
    convo_stats = db.query(
        func.count(Conversation.id).label("total"),
        func.sum(case((Conversation.status == ConversationStatus.RESOLVED, 1), else_=0)).label("resolved"),
        func.avg(case(
            (
                and_(Conversation.status == ConversationStatus.RESOLVED, Conversation.first_response_time_seconds.isnot(None)),
                Conversation.first_response_time_seconds / 3600.0
            ),
            else_=None
        )).label("avg_first_response_hours"),
    ).filter(
        Conversation.created_at >= since
    ).one()
    total_conversations = int(convo_stats.total or 0)
    resolved_convos = int(convo_stats.resolved or 0)
    avg_response_hours = float(convo_stats.avg_first_response_hours or 0)

    by_channel_rows = db.query(
        Conversation.channel,
        func.count(Conversation.id).label("count")
    ).filter(
        Conversation.created_at >= since
    ).group_by(Conversation.channel).all()
    by_channel = {row.channel or "unknown": row.count for row in by_channel_rows}

    # Employee productivity (tickets handled)
    employee_tickets = db.query(
        Employee.name,
        func.count(Ticket.id).label("ticket_count")
    ).join(
        Ticket, Ticket.assigned_employee_id == Employee.id
    ).filter(
        Ticket.created_at >= since
    ).group_by(Employee.id, Employee.name).order_by(
        func.count(Ticket.id).desc()
    ).limit(10).all()

    # POP utilization
    pop_stats = db.query(
        Pop.name,
        Pop.city,
        func.count(Customer.id).label("customer_count"),
        func.sum(case((Customer.status == CustomerStatus.ACTIVE, 1), else_=0)).label("active_customers")
    ).outerjoin(
        Customer, Customer.pop_id == Pop.id
    ).group_by(Pop.id, Pop.name, Pop.city).all()

    return {
        "period_days": days,
        "tickets": {
            "total": total_tickets,
            "resolved": resolved_tickets,
            "resolution_rate": round(resolved_tickets / max(total_tickets, 1) * 100, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "by_priority": tickets_by_priority,
        },
        "conversations": {
            "total": total_conversations,
            "resolved": resolved_convos,
            "resolution_rate": round(resolved_convos / max(total_conversations, 1) * 100, 1),
            "avg_first_response_hours": round(avg_response_hours, 1),
            "by_channel": by_channel,
        },
        "employee_productivity": [
            {"name": row.name, "tickets_handled": row.ticket_count}
            for row in employee_tickets
        ],
        "pop_utilization": [
            {
                "name": row.name,
                "city": row.city,
                "total_customers": row.customer_count,
                "active_customers": row.active_customers or 0,
            }
            for row in pop_stats
        ],
    }


@router.get("/network-health", dependencies=[Depends(Require("analytics:read"))])
async def get_network_health(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Alias endpoint summarizing network health (avoids 404)."""
    _apply_statement_timeout(db)
    pop_stats = db.query(
        Pop.id,
        Pop.name,
        Pop.city,
        func.count(Customer.id).label("customers"),
        func.sum(case((Customer.status == CustomerStatus.ACTIVE, 1), else_=0)).label("active_customers"),
    ).outerjoin(
        Customer, Customer.pop_id == Pop.id
    ).group_by(
        Pop.id, Pop.name, Pop.city
    ).order_by(func.count(Customer.id).desc()).limit(50).all()

    routers = db.query(func.count(Router.id)).scalar() or 0
    pops = db.query(func.count(Pop.id)).scalar() or 0

    return {
        "summary": {
            "pops": pops,
            "routers": routers,
            "avg_customers_per_pop": round(
                (sum(r.customers or 0 for r in pop_stats) / max(len(pop_stats), 1)), 2
            ),
        },
        "by_pop": [
            {
                "id": row.id,
                "name": row.name,
                "city": row.city,
                "customers": row.customers,
                "active_customers": row.active_customers or 0,
            }
            for row in pop_stats
        ],
    }


# ============================================================================
# ANOMALY & PATTERN DETECTION
# ============================================================================

@router.get("/anomalies", dependencies=[Depends(Require("analytics:read"))])
@cached("anomalies", ttl=CACHE_TTL["medium"], include_principal=True)
async def detect_anomalies(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Detect data anomalies and patterns that may indicate issues.
    """
    _apply_statement_timeout(db)
    anomalies: List[Dict[str, Any]] = []
    patterns: List[Dict[str, Any]] = []

    # Check for customers with subscriptions but no invoices in 90 days
    active_with_sub_no_invoice = db.query(Customer).join(
        Subscription, Subscription.customer_id == Customer.id
    ).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).outerjoin(
        Invoice, and_(
            Invoice.customer_id == Customer.id,
            Invoice.invoice_date >= datetime.utcnow() - timedelta(days=90)
        )
    ).filter(Invoice.id.is_(None)).count()

    if active_with_sub_no_invoice > 0:
        anomalies.append({
            "type": "billing",
            "severity": "high",
            "description": f"{active_with_sub_no_invoice} active customers with subscriptions but no invoices in 90 days",
            "action": "Review billing configuration for these customers",
        })

    # Payments without invoices
    orphan_payments = db.query(Payment).filter(
        Payment.invoice_id.is_(None),
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
    ).count()

    if orphan_payments > 0:
        patterns.append({
            "type": "payment_pattern",
            "description": f"{orphan_payments} completed payments not linked to invoices",
            "insight": "May indicate advance payments or reconciliation issues",
        })

    # Customers with many open tickets
    high_ticket_base = db.query(
        Customer.id.label("id"),
        Customer.name.label("name"),
        func.count(Ticket.id).label("open_tickets")
    ).join(
        Ticket, Ticket.customer_id == Customer.id
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).group_by(Customer.id, Customer.name).having(
        func.count(Ticket.id) >= 5
    )
    high_ticket_sub = high_ticket_base.subquery()
    high_ticket_total = db.query(func.count()).select_from(high_ticket_sub).scalar() or 0
    high_ticket_customers = db.query(
        high_ticket_sub.c.id,
        high_ticket_sub.c.name,
        high_ticket_sub.c.open_tickets
    ).order_by(
        high_ticket_sub.c.open_tickets.desc()
    ).limit(25).all()

    if high_ticket_total:
        anomalies.append({
            "type": "support",
            "severity": "medium",
            "description": f"{high_ticket_total} customers have 5+ open tickets",
            "customers": [{"id": c.id, "name": c.name, "tickets": c.open_tickets} for c in high_ticket_customers[:5]],
        })

    # Duplicate customer detection (same email or phone)
    duplicate_email_sub = db.query(
        Customer.email
    ).filter(
        Customer.email.isnot(None),
        Customer.email != ""
    ).group_by(Customer.email).having(func.count(Customer.id) > 1).subquery()
    duplicate_emails = db.query(func.count()).select_from(duplicate_email_sub).scalar() or 0

    if duplicate_emails:
        anomalies.append({
            "type": "data_quality",
            "severity": "medium",
            "description": f"{duplicate_emails} email addresses used by multiple customers",
            "action": "Review and merge duplicate customer records",
        })

    duplicate_phone_sub = db.query(
        Customer.phone
    ).filter(
        Customer.phone.isnot(None),
        Customer.phone != ""
    ).group_by(Customer.phone).having(func.count(Customer.id) > 1).subquery()
    duplicate_phones = db.query(func.count()).select_from(duplicate_phone_sub).scalar() or 0

    if duplicate_phones:
        anomalies.append({
            "type": "data_quality",
            "severity": "low",
            "description": f"{duplicate_phones} phone numbers used by multiple customers",
            "action": "Review potential duplicate records",
        })

    # Very old unresolved tickets
    old_tickets = db.query(Ticket).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        Ticket.created_at < datetime.utcnow() - timedelta(days=30)
    ).count()

    if old_tickets > 0:
        anomalies.append({
            "type": "support",
            "severity": "high",
            "description": f"{old_tickets} tickets open for more than 30 days",
            "action": "Review and escalate stale tickets",
        })

    # Subscription price anomalies (outliers)
    avg_price = db.query(func.avg(Subscription.price)).filter(
        Subscription.price.isnot(None),
        Subscription.price > 0
    ).scalar() or 0

    if avg_price > 0:
        high_price_subs = db.query(Subscription).filter(
            Subscription.price > avg_price * 5
        ).count()

        if high_price_subs > 0:
            patterns.append({
                "type": "pricing",
                "description": f"{high_price_subs} subscriptions with price 5x above average",
                "insight": "May be enterprise customers or data entry errors",
            })

    return {
        "anomalies": anomalies,
        "patterns": patterns,
        "summary": {
            "total_anomalies": len(anomalies),
            "high_severity": len([a for a in anomalies if a["severity"] == "high"]),
            "medium_severity": len([a for a in anomalies if a["severity"] == "medium"]),
            "low_severity": len([a for a in anomalies if a["severity"] == "low"]),
        }
    }


# ============================================================================
# DATA AVAILABILITY REPORT
# ============================================================================

@router.get("/data-availability", dependencies=[Depends(Require("analytics:read"))])
@cached("data-availability", ttl=CACHE_TTL["short"], include_principal=True)
async def get_data_availability(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Report on what data is available vs what's needed for comprehensive analytics.
    """
    _apply_statement_timeout(db)

    # Check data freshness
    latest_sync = db.query(func.max(Customer.last_synced_at)).scalar()

    # Data availability by source
    sources = {
        "splynx": {
            "customers": db.query(Customer).filter(Customer.splynx_id.isnot(None)).count(),
            "subscriptions": db.query(Subscription).filter(Subscription.splynx_id.isnot(None)).count(),
            "invoices": db.query(Invoice).filter(Invoice.splynx_id.isnot(None)).count(),
            "payments": db.query(Payment).filter(Payment.splynx_id.isnot(None)).count(),
            "tickets": db.query(Ticket).filter(Ticket.splynx_id.isnot(None)).count(),
        },
        "erpnext": {
            "customers": db.query(Customer).filter(Customer.erpnext_id.isnot(None)).count(),
            "invoices": db.query(Invoice).filter(Invoice.erpnext_id.isnot(None)).count(),
            "payments": db.query(Payment).filter(Payment.erpnext_id.isnot(None)).count(),
            "employees": db.query(Employee).filter(Employee.erpnext_id.isnot(None)).count(),
            "tickets": db.query(Ticket).filter(Ticket.erpnext_id.isnot(None)).count(),
        },
        "chatwoot": {
            "customers": db.query(Customer).filter(Customer.chatwoot_contact_id.isnot(None)).count(),
            "conversations": db.query(Conversation).filter(Conversation.chatwoot_id.isnot(None)).count(),
        },
    }

    # What data is missing that we need
    missing_data = []

    total_customers = db.query(Customer).count()

    # Critical missing data
    no_contact = db.query(Customer).filter(
        and_(
            or_(Customer.email.is_(None), Customer.email == ""),
            or_(Customer.phone.is_(None), Customer.phone == "")
        )
    ).count()

    if no_contact > 0:
        missing_data.append({
            "entity": "customers",
            "field": "contact_info",
            "count": no_contact,
            "impact": "critical",
            "description": "Customers without email AND phone - cannot be contacted",
        })

    no_location = db.query(Customer).filter(
        and_(Customer.latitude.is_(None), Customer.longitude.is_(None)),
        or_(Customer.address.is_(None), Customer.address == "")
    ).count()

    if no_location > 0:
        missing_data.append({
            "entity": "customers",
            "field": "location",
            "count": no_location,
            "impact": "high",
            "description": "Customers without address or GPS coordinates",
        })

    # Subscriptions without network info
    no_network = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.ipv4_address.is_(None),
        Subscription.mac_address.is_(None)
    ).count()

    if no_network > 0:
        missing_data.append({
            "entity": "subscriptions",
            "field": "network_assignment",
            "count": no_network,
            "impact": "medium",
            "description": "Active subscriptions without IP or MAC address",
        })

    return {
        "last_sync": latest_sync.isoformat() if latest_sync else None,
        "data_by_source": sources,
        "missing_critical_data": missing_data,
        "totals": {
            "customers": total_customers,
            "subscriptions": db.query(Subscription).count(),
            "invoices": db.query(Invoice).count(),
            "payments": db.query(Payment).count(),
            "conversations": db.query(Conversation).count(),
            "tickets": db.query(Ticket).count(),
        },
    }

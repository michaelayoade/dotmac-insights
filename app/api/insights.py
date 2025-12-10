"""
Deep Insights API - Comprehensive analytics for data relationships,
completeness, and actionable intelligence.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query  # Depends still needed for get_db
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct, and_, or_, extract, text
from sqlalchemy.sql import label
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from app.database import get_db
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
from app.auth import Require

router = APIRouter()


# ============================================================================
# DATA COMPLETENESS & QUALITY
# ============================================================================

@router.get("/data-completeness", dependencies=[Depends(Require("analytics:read"))])
async def get_data_completeness(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive data completeness analysis across all entities.
    Shows what data is available, missing, and the quality score.
    """
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
async def get_customer_segments(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Advanced customer segmentation based on multiple dimensions.
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

    # Tenure segments
    today = datetime.utcnow().date()
    tenure_segments = []
    for label_name, min_days, max_days in [
        ("New (0-30 days)", 0, 30),
        ("Growing (31-90 days)", 31, 90),
        ("Established (91-365 days)", 91, 365),
        ("Loyal (1-2 years)", 366, 730),
        ("Long-term (2+ years)", 731, 9999),
    ]:
        if max_days == 9999:
            count = db.query(Customer).filter(
                Customer.signup_date.isnot(None),
                func.julianday(today) - func.julianday(Customer.signup_date) >= min_days
            ).count()
        else:
            count = db.query(Customer).filter(
                Customer.signup_date.isnot(None),
                func.julianday(today) - func.julianday(Customer.signup_date) >= min_days,
                func.julianday(today) - func.julianday(Customer.signup_date) <= max_days
            ).count()
        tenure_segments.append({"segment": label_name, "count": count})

    # MRR segments
    mrr_segments = []
    for label_name, min_mrr, max_mrr in [
        ("No MRR", 0, 0),
        ("Low (<10K)", 1, 10000),
        ("Medium (10K-50K)", 10000, 50000),
        ("High (50K-200K)", 50000, 200000),
        ("Enterprise (200K+)", 200000, 999999999),
    ]:
        if min_mrr == 0 and max_mrr == 0:
            count = db.query(Customer).filter(
                or_(Customer.mrr.is_(None), Customer.mrr == 0)
            ).count()
        elif max_mrr == 999999999:
            count = db.query(Customer).filter(Customer.mrr >= min_mrr).count()
        else:
            count = db.query(Customer).filter(
                Customer.mrr >= min_mrr,
                Customer.mrr < max_mrr
            ).count()
        mrr_segments.append({"segment": label_name, "count": count})

    # Geographic distribution (top cities)
    city_dist = db.query(
        Customer.city,
        func.count(Customer.id).label("count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).filter(Customer.city.isnot(None)).group_by(Customer.city).order_by(
        func.count(Customer.id).desc()
    ).limit(15).all()

    # POP distribution
    pop_dist = db.query(
        Pop.name,
        Pop.city,
        func.count(Customer.id).label("customer_count"),
        func.sum(Customer.mrr).label("total_mrr")
    ).join(Customer, Customer.pop_id == Pop.id).group_by(
        Pop.id, Pop.name, Pop.city
    ).order_by(func.count(Customer.id).desc()).all()

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
async def get_customer_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Customer health analysis including payment behavior, support needs, and risk indicators.
    """
    total_active = db.query(Customer).filter(Customer.status == CustomerStatus.ACTIVE).count()

    # Payment behavior analysis
    # Customers with overdue invoices
    customers_with_overdue = db.query(distinct(Invoice.customer_id)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).count()

    # Average payment timing
    paid_invoices = db.query(Invoice).filter(
        Invoice.status == InvoiceStatus.PAID,
        Invoice.paid_date.isnot(None),
        Invoice.due_date.isnot(None)
    ).all()

    early_payments = 0
    on_time_payments = 0
    late_payments = 0
    for inv in paid_invoices:
        if inv.paid_date <= inv.due_date:
            if (inv.due_date - inv.paid_date).days > 3:
                early_payments += 1
            else:
                on_time_payments += 1
        else:
            late_payments += 1

    total_paid = early_payments + on_time_payments + late_payments

    # Support intensity (tickets per customer)
    tickets_30d = db.query(
        Ticket.customer_id,
        func.count(Ticket.id).label("ticket_count")
    ).filter(
        Ticket.customer_id.isnot(None),
        Ticket.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(Ticket.customer_id).all()

    high_support_customers = sum(1 for t in tickets_30d if t.ticket_count >= 3)

    # Conversation activity
    convos_30d = db.query(
        Conversation.customer_id,
        func.count(Conversation.id).label("convo_count")
    ).filter(
        Conversation.customer_id.isnot(None),
        Conversation.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(Conversation.customer_id).all()

    # Churn indicators
    recently_cancelled = db.query(Customer).filter(
        Customer.status == CustomerStatus.CANCELLED,
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
            "customers_with_tickets_30d": len(tickets_30d),
            "high_support_customers": high_support_customers,
            "customers_with_conversations_30d": len(convos_30d),
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


# ============================================================================
# RELATIONSHIP ANALYSIS
# ============================================================================

@router.get("/relationship-map", dependencies=[Depends(Require("analytics:read"))])
async def get_relationship_map(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Analyze relationships between entities and identify orphaned/unlinked records.
    """
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
async def get_financial_insights(
    months: int = Query(default=12, le=36),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deep financial analysis including revenue patterns, payment behavior, and forecasting indicators.
    """
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
    today = datetime.utcnow().date()
    aging_buckets = {
        "current": {"count": 0, "amount": 0},
        "1_30_days": {"count": 0, "amount": 0},
        "31_60_days": {"count": 0, "amount": 0},
        "61_90_days": {"count": 0, "amount": 0},
        "over_90_days": {"count": 0, "amount": 0},
    }

    overdue_invoices = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
        Invoice.due_date.isnot(None)
    ).all()

    for inv in overdue_invoices:
        days_overdue = (today - inv.due_date.date() if hasattr(inv.due_date, 'date') else today - inv.due_date).days if inv.due_date else 0
        balance = float(inv.total_amount or 0) - float(inv.amount_paid or 0)

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30_days"
        elif days_overdue <= 60:
            bucket = "31_60_days"
        elif days_overdue <= 90:
            bucket = "61_90_days"
        else:
            bucket = "over_90_days"

        aging_buckets[bucket]["count"] += 1
        aging_buckets[bucket]["amount"] += balance

    # Payment method distribution
    payment_methods = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).filter(
        Payment.status == PaymentStatus.COMPLETED
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
        Payment.status == PaymentStatus.COMPLETED,
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
                    "avg_mrr": round(float(row.mrr or 0) / max(row.count, 1), 2),
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


# ============================================================================
# OPERATIONAL INSIGHTS
# ============================================================================

@router.get("/operational-insights", dependencies=[Depends(Require("analytics:read"))])
async def get_operational_insights(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Operational metrics including support performance, network utilization, and employee productivity.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Ticket analysis
    tickets = db.query(Ticket).filter(Ticket.created_at >= since).all()
    total_tickets = len(tickets)

    resolved_tickets = [t for t in tickets if t.status == TicketStatus.RESOLVED]
    avg_resolution_hours = 0
    if resolved_tickets:
        resolution_times = [
            (t.resolution_date - t.created_at).total_seconds() / 3600
            for t in resolved_tickets
            if t.resolution_date and t.created_at
        ]
        if resolution_times:
            avg_resolution_hours = sum(resolution_times) / len(resolution_times)

    # Tickets by priority
    tickets_by_priority = {}
    for t in tickets:
        priority = t.priority.value if t.priority else "unknown"
        if priority not in tickets_by_priority:
            tickets_by_priority[priority] = 0
        tickets_by_priority[priority] += 1

    # Conversation analysis
    conversations = db.query(Conversation).filter(Conversation.created_at >= since).all()
    total_conversations = len(conversations)

    resolved_convos = [c for c in conversations if c.status == ConversationStatus.RESOLVED]
    avg_response_hours = 0
    if resolved_convos:
        response_times = [
            c.first_response_time_seconds / 3600
            for c in resolved_convos
            if c.first_response_time_seconds
        ]
        if response_times:
            avg_response_hours = sum(response_times) / len(response_times)

    # By channel
    by_channel = {}
    for c in conversations:
        channel = c.channel or "unknown"
        if channel not in by_channel:
            by_channel[channel] = 0
        by_channel[channel] += 1

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
            "resolved": len(resolved_tickets),
            "resolution_rate": round(len(resolved_tickets) / max(total_tickets, 1) * 100, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "by_priority": tickets_by_priority,
        },
        "conversations": {
            "total": total_conversations,
            "resolved": len(resolved_convos),
            "resolution_rate": round(len(resolved_convos) / max(total_conversations, 1) * 100, 1),
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


# ============================================================================
# ANOMALY & PATTERN DETECTION
# ============================================================================

@router.get("/anomalies", dependencies=[Depends(Require("analytics:read"))])
async def detect_anomalies(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Detect data anomalies and patterns that may indicate issues.
    """
    anomalies = []
    patterns = []

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
        Payment.status == PaymentStatus.COMPLETED
    ).count()

    if orphan_payments > 0:
        patterns.append({
            "type": "payment_pattern",
            "description": f"{orphan_payments} completed payments not linked to invoices",
            "insight": "May indicate advance payments or reconciliation issues",
        })

    # Customers with many open tickets
    high_ticket_customers = db.query(
        Customer.id,
        Customer.name,
        func.count(Ticket.id).label("open_tickets")
    ).join(
        Ticket, Ticket.customer_id == Customer.id
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).group_by(Customer.id, Customer.name).having(
        func.count(Ticket.id) >= 5
    ).all()

    if high_ticket_customers:
        anomalies.append({
            "type": "support",
            "severity": "medium",
            "description": f"{len(high_ticket_customers)} customers have 5+ open tickets",
            "customers": [{"id": c.id, "name": c.name, "tickets": c.open_tickets} for c in high_ticket_customers[:5]],
        })

    # Duplicate customer detection (same email or phone)
    duplicate_emails = db.query(
        Customer.email,
        func.count(Customer.id).label("count")
    ).filter(
        Customer.email.isnot(None),
        Customer.email != ""
    ).group_by(Customer.email).having(func.count(Customer.id) > 1).all()

    if duplicate_emails:
        anomalies.append({
            "type": "data_quality",
            "severity": "medium",
            "description": f"{len(duplicate_emails)} email addresses used by multiple customers",
            "action": "Review and merge duplicate customer records",
        })

    duplicate_phones = db.query(
        Customer.phone,
        func.count(Customer.id).label("count")
    ).filter(
        Customer.phone.isnot(None),
        Customer.phone != ""
    ).group_by(Customer.phone).having(func.count(Customer.id) > 1).all()

    if duplicate_phones:
        anomalies.append({
            "type": "data_quality",
            "severity": "low",
            "description": f"{len(duplicate_phones)} phone numbers used by multiple customers",
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
async def get_data_availability(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Report on what data is available vs what's needed for comprehensive analytics.
    """

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

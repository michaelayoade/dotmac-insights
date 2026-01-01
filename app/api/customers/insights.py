"""
Insights Endpoints
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
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
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
    end_dt = datetime.now(timezone.utc)
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
    start_dt = datetime.now(timezone.utc) - timedelta(days=months * 30)

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

"""Network Analytics API endpoints.

Complex analytics endpoints that combine data from multiple services.
Note: These endpoints use services where possible but may include
additional aggregation logic for complex analytics.
"""
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct, or_

from app.database import get_db
from app.cache import cached, CACHE_TTL
from app.models.pop import Pop
from app.models.router import Router
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.party import CustomerAccount

from app.services.network import PopService, RouterService, IPAddressService

from ._deps import (
    get_pop_service,
    get_router_service,
    get_ip_address_service,
    RequireAnalyticsRead,
)

router = APIRouter(prefix="/analytics", tags=["network"])


@router.get("/dashboard", dependencies=[RequireAnalyticsRead])
@cached("network-dashboard", ttl=CACHE_TTL["short"])
async def get_network_dashboard(
    pop_service: PopService = Depends(get_pop_service),
    router_service: RouterService = Depends(get_router_service),
    ip_service: IPAddressService = Depends(get_ip_address_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Network dashboard with infrastructure and customer distribution metrics."""
    # Use services for basic stats
    pop_stats = pop_service.get_overview_stats()
    router_stats = router_service.get_overview_stats()
    ip_stats = ip_service.get_stats()

    # Customer distribution (requires more complex query)
    customers_with_pop = db.query(func.count(distinct(Subscription.party_id))).join(
        Router, Subscription.router_id == Router.id
    ).filter(
        Router.pop_id.isnot(None),
        Subscription.status == SubscriptionStatus.ACTIVE,
    ).scalar() or 0

    total_customers = db.query(func.count(distinct(Subscription.party_id))).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    customers_without_pop = total_customers - customers_with_pop

    # Top POPs by customer count
    top_pops = db.query(
        Pop.name,
        func.count(distinct(Subscription.party_id)).label("customer_count")
    ).join(Router, Router.pop_id == Pop.id).join(
        Subscription, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Pop.id, Pop.name).order_by(
        func.count(distinct(Subscription.party_id)).desc()
    ).limit(10).all()

    # Network-related tickets
    network_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        or_(
            Ticket.ticket_type.ilike("%network%"),
            Ticket.ticket_type.ilike("%connectivity%"),
            Ticket.issue_type.ilike("%network%"),
        )
    ).scalar() or 0

    return {
        "infrastructure": {
            "total_pops": pop_stats["total"],
            "active_pops": pop_stats["active"],
            "total_routers": router_stats["total"],
            "total_ips": ip_stats["total_ips"],
            "used_ips": ip_stats["used_ips"],
        },
        "customer_distribution": {
            "with_pop_assigned": customers_with_pop,
            "without_pop_assigned": customers_without_pop,
            "assignment_rate": round(customers_with_pop / total_customers * 100, 1) if total_customers > 0 else 0,
        },
        "top_pops": [
            {"name": p.name, "customer_count": p.customer_count}
            for p in top_pops
        ],
        "health": {
            "network_tickets_open": network_tickets,
        },
    }


@router.get("/pop-performance", dependencies=[RequireAnalyticsRead])
@cached("network-pop-perf", ttl=CACHE_TTL["medium"])
async def get_pop_performance(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get comprehensive POP performance metrics."""
    # MRR calculation
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    # Party-to-POP mapping subquery
    party_pop = (
        db.query(
            Subscription.party_id.label("party_id"),
            func.min(Router.pop_id).label("pop_id"),
        )
        .join(Router, Subscription.router_id == Router.id)
        .filter(Router.pop_id.isnot(None))
        .group_by(Subscription.party_id)
        .subquery()
    )

    active_party_pop = (
        db.query(
            Subscription.party_id.label("party_id"),
            func.min(Router.pop_id).label("pop_id"),
        )
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Router.pop_id.isnot(None),
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .group_by(Subscription.party_id)
        .subquery()
    )

    total_customers_by_pop = db.query(
        party_pop.c.pop_id,
        func.count(distinct(party_pop.c.party_id)).label("customer_count"),
    ).group_by(party_pop.c.pop_id).subquery()

    active_customers_by_pop = db.query(
        active_party_pop.c.pop_id,
        func.count(distinct(active_party_pop.c.party_id)).label("active"),
    ).group_by(active_party_pop.c.pop_id).subquery()

    # MRR by POP
    mrr_data = db.query(
        Router.pop_id,
        func.sum(mrr_case).label("mrr"),
    ).join(Subscription, Subscription.router_id == Router.id).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Router.pop_id).subquery()

    # Tickets by POP (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    ticket_data = db.query(
        party_pop.c.pop_id,
        func.count(Ticket.id).label("ticket_count"),
    ).join(CustomerAccount, Ticket.customer_account_id == CustomerAccount.id).join(
        party_pop, party_pop.c.party_id == CustomerAccount.party_id
    ).filter(
        Ticket.created_at >= thirty_days_ago
    ).group_by(party_pop.c.pop_id).subquery()

    # Router counts by POP
    router_data = db.query(
        Router.pop_id,
        func.count(Router.id).label("router_count"),
    ).group_by(Router.pop_id).subquery()

    # Combine all
    pops = db.query(
        Pop.id,
        Pop.name,
        Pop.city,
        Pop.is_active,
        func.coalesce(total_customers_by_pop.c.customer_count, 0).label("total_customers"),
        func.coalesce(active_customers_by_pop.c.active, 0).label("active_customers"),
        func.coalesce(mrr_data.c.mrr, 0).label("mrr"),
        func.coalesce(ticket_data.c.ticket_count, 0).label("tickets_30d"),
        func.coalesce(router_data.c.router_count, 0).label("router_count"),
    ).outerjoin(
        total_customers_by_pop, Pop.id == total_customers_by_pop.c.pop_id
    ).outerjoin(
        active_customers_by_pop, Pop.id == active_customers_by_pop.c.pop_id
    ).outerjoin(
        mrr_data, Pop.id == mrr_data.c.pop_id
    ).outerjoin(
        ticket_data, Pop.id == ticket_data.c.pop_id
    ).outerjoin(
        router_data, Pop.id == router_data.c.pop_id
    ).order_by(func.coalesce(total_customers_by_pop.c.customer_count, 0).desc()).all()

    return [
        {
            "pop_id": p.id,
            "name": p.name,
            "city": p.city,
            "is_active": p.is_active,
            "total_customers": p.total_customers,
            "active_customers": p.active_customers,
            "churned_customers": max(p.total_customers - p.active_customers, 0),
            "churn_rate": round((p.total_customers - p.active_customers) / p.total_customers * 100, 1) if p.total_customers > 0 else 0,
            "mrr": float(p.mrr),
            "tickets_30d": p.tickets_30d,
            "router_count": p.router_count,
        }
        for p in pops
    ]


@router.get("/customer-distribution", dependencies=[RequireAnalyticsRead])
async def get_customer_distribution(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer distribution across POPs."""
    total_active = db.query(func.count(distinct(Subscription.party_id))).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    with_pop = db.query(func.count(distinct(Subscription.party_id))).join(
        Router, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Router.pop_id.isnot(None)
    ).scalar() or 0

    # Distribution by POP
    distribution = db.query(
        Pop.name,
        func.count(distinct(Subscription.party_id)).label("count")
    ).join(Router, Router.pop_id == Pop.id).join(
        Subscription, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Pop.id, Pop.name).order_by(
        func.count(distinct(Subscription.party_id)).desc()
    ).all()

    return {
        "summary": {
            "total_active_customers": total_active,
            "with_pop_assigned": with_pop,
            "without_pop_assigned": total_active - with_pop,
            "assignment_rate": round(with_pop / total_active * 100, 1) if total_active > 0 else 0,
        },
        "by_pop": [
            {
                "pop_name": d.name,
                "customer_count": d.count,
                "percent": round(d.count / total_active * 100, 1) if total_active > 0 else 0,
            }
            for d in distribution
        ],
    }


@router.get("/health", dependencies=[RequireAnalyticsRead])
@cached("network-health", ttl=CACHE_TTL["short"])
async def get_network_health(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Network health analysis with recommendations."""
    # POPs without routers
    pops_without_routers = db.query(func.count(Pop.id)).filter(
        Pop.is_active.is_(True),
        ~Pop.id.in_(db.query(Router.pop_id).filter(Router.pop_id.isnot(None)))
    ).scalar() or 0

    total_active_pops = db.query(func.count(Pop.id)).filter(
        Pop.is_active.is_(True)
    ).scalar() or 0

    # Customers without POP
    customers_without_pop = db.query(func.count(distinct(Subscription.party_id))).outerjoin(
        Router, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        or_(Router.pop_id.is_(None), Subscription.router_id.is_(None)),
    ).scalar() or 0

    total_active_customers = db.query(func.count(distinct(Subscription.party_id))).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    # Network-related tickets
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    network_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.created_at >= thirty_days_ago,
        or_(
            Ticket.ticket_type.ilike("%network%"),
            Ticket.ticket_type.ilike("%connectivity%"),
            Ticket.ticket_type.ilike("%router%"),
            Ticket.issue_type.ilike("%network%"),
        )
    ).scalar() or 0

    total_tickets_30d = db.query(func.count(Ticket.id)).filter(
        Ticket.created_at >= thirty_days_ago
    ).scalar() or 1

    # Generate recommendations
    recommendations = []

    if pops_without_routers > 0:
        recommendations.append({
            "priority": "high",
            "issue": f"{pops_without_routers} active POPs have no routers",
            "action": "Assign routers to POPs or deactivate unused POPs",
        })

    if total_active_customers > 0 and customers_without_pop > total_active_customers * 0.2:
        recommendations.append({
            "priority": "medium",
            "issue": f"{customers_without_pop} customers ({round(customers_without_pop/total_active_customers*100, 1)}%) have no POP assigned",
            "action": "Assign customers to nearest POP based on location",
        })

    if network_tickets > total_tickets_30d * 0.3:
        recommendations.append({
            "priority": "high",
            "issue": f"Network issues account for {round(network_tickets/total_tickets_30d*100, 1)}% of tickets",
            "action": "Review network infrastructure and common failure points",
        })

    return {
        "infrastructure": {
            "pops_without_routers": pops_without_routers,
            "total_active_pops": total_active_pops,
        },
        "customer_assignment": {
            "without_pop": customers_without_pop,
            "total_active": total_active_customers,
            "unassigned_percent": round(customers_without_pop / total_active_customers * 100, 1) if total_active_customers > 0 else 0,
        },
        "support": {
            "network_tickets_30d": network_tickets,
            "total_tickets_30d": total_tickets_30d,
            "network_ticket_percent": round(network_tickets / total_tickets_30d * 100, 1) if total_tickets_30d > 0 else 0,
        },
        "recommendations": recommendations,
    }

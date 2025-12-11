"""
Network Domain Router

Provides all network-related endpoints:
- /dashboard - Device status, customer distribution
- /pops - List, detail POPs
- /routers - List, detail routers
- /analytics/* - POP performance, device status
- /insights/* - Network health
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.pop import Pop
from app.models.router import Router
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.ticket import Ticket, TicketStatus
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("network-dashboard", ttl=CACHE_TTL["short"])
async def get_network_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Network dashboard with infrastructure and customer distribution metrics.
    """
    # POP counts
    total_pops = db.query(func.count(Pop.id)).scalar() or 0
    active_pops = db.query(func.count(Pop.id)).filter(Pop.is_active.is_(True)).scalar() or 0

    # Router counts
    total_routers = db.query(func.count(Router.id)).scalar() or 0

    # Customer distribution
    customers_with_pop = db.query(func.count(Customer.id)).filter(
        Customer.pop_id.isnot(None)
    ).scalar() or 0

    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    customers_without_pop = total_customers - customers_with_pop

    # Customers per POP (top 10)
    top_pops = db.query(
        Pop.name,
        func.count(Customer.id).label("customer_count")
    ).outerjoin(Customer, Customer.pop_id == Pop.id).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).group_by(Pop.id, Pop.name).order_by(func.count(Customer.id).desc()).limit(10).all()

    # Active tickets related to network
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
            "total_pops": total_pops,
            "active_pops": active_pops,
            "total_routers": total_routers,
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


# =============================================================================
# DATA ENDPOINTS
# =============================================================================

@router.get("/pops", dependencies=[Depends(Require("explorer:read"))])
async def list_pops(
    active_only: bool = False,
    city: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List POPs with customer and router counts."""
    # Subquery for customer counts
    customer_counts = db.query(
        Customer.pop_id,
        func.count(Customer.id).label("customer_count")
    ).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).group_by(Customer.pop_id).subquery()

    # Subquery for router counts
    router_counts = db.query(
        Router.pop_id,
        func.count(Router.id).label("router_count")
    ).group_by(Router.pop_id).subquery()

    query = db.query(
        Pop,
        func.coalesce(customer_counts.c.customer_count, 0).label("customer_count"),
        func.coalesce(router_counts.c.router_count, 0).label("router_count"),
    ).outerjoin(
        customer_counts, Pop.id == customer_counts.c.pop_id
    ).outerjoin(
        router_counts, Pop.id == router_counts.c.pop_id
    )

    if active_only:
        query = query.filter(Pop.is_active.is_(True))

    if city:
        query = query.filter(Pop.city.ilike(f"%{city}%"))

    if state:
        query = query.filter(Pop.state.ilike(f"%{state}%"))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Pop.name.ilike(search_term),
                Pop.code.ilike(search_term),
            )
        )

    total = query.count()
    pops = query.order_by(Pop.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.Pop.id,
                "name": p.Pop.name,
                "code": p.Pop.code,
                "city": p.Pop.city,
                "state": p.Pop.state,
                "is_active": p.Pop.is_active,
                "customer_count": p.customer_count,
                "router_count": p.router_count,
                "latitude": p.Pop.latitude,
                "longitude": p.Pop.longitude,
            }
            for p in pops
        ],
    }


@router.get("/pops/{pop_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_pop(
    pop_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed POP information with customers and routers."""
    pop = db.query(Pop).filter(Pop.id == pop_id).first()

    if not pop:
        raise HTTPException(status_code=404, detail="POP not found")

    # Customer stats
    customer_count = db.query(func.count(Customer.id)).filter(
        Customer.pop_id == pop_id,
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    # MRR from this POP
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    pop_mrr = db.query(func.sum(mrr_case)).join(
        Customer, Subscription.customer_id == Customer.id
    ).filter(
        Customer.pop_id == pop_id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    # Routers at this POP
    routers = db.query(Router).filter(Router.pop_id == pop_id).all()

    # Open tickets for this POP's customers
    open_tickets = db.query(func.count(Ticket.id)).join(
        Customer, Ticket.customer_id == Customer.id
    ).filter(
        Customer.pop_id == pop_id,
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
    ).scalar() or 0

    return {
        "id": pop.id,
        "name": pop.name,
        "code": pop.code,
        "address": pop.address,
        "city": pop.city,
        "state": pop.state,
        "latitude": pop.latitude,
        "longitude": pop.longitude,
        "is_active": pop.is_active,
        "external_ids": {
            "splynx_id": pop.splynx_id,
        },
        "metrics": {
            "customer_count": customer_count,
            "mrr": float(pop_mrr),
            "router_count": len(routers),
            "open_tickets": open_tickets,
        },
        "routers": [
            {
                "id": r.id,
                "title": r.title,
                "ip": r.ip,
                "nas_ip": r.nas_ip,
                "status": r.status,
            }
            for r in routers
        ],
    }


@router.get("/routers", dependencies=[Depends(Require("explorer:read"))])
async def list_routers(
    pop_id: Optional[int] = None,
    nas_type: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List routers with filtering."""
    query = db.query(Router)

    if pop_id:
        query = query.filter(Router.pop_id == pop_id)

    if nas_type:
        query = query.filter(Router.nas_type == nas_type)

    if status:
        query = query.filter(Router.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Router.title.ilike(search_term),
                Router.ip.ilike(search_term),
                Router.nas_ip.ilike(search_term),
            )
        )

    total = query.count()
    routers = query.order_by(Router.title).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "title": r.title,
                "model": r.model,
                "ip": r.ip,
                "nas_ip": r.nas_ip,
                "nas_type": r.nas_type,
                "pop_id": r.pop_id,
                "status": r.status,
                "splynx_id": r.splynx_id,
            }
            for r in routers
        ],
    }


@router.get("/routers/{router_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_router(
    router_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed router information."""
    router_obj = db.query(Router).filter(Router.id == router_id).first()

    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")

    pop = None
    if router_obj.pop_id:
        pop_obj = db.query(Pop).filter(Pop.id == router_obj.pop_id).first()
        if pop_obj:
            pop = {"id": pop_obj.id, "name": pop_obj.name}

    return {
        "id": router_obj.id,
        "title": router_obj.title,
        "model": router_obj.model,
        "ip": router_obj.ip,
        "nas_ip": router_obj.nas_ip,
        "nas_type": router_obj.nas_type,
        "address": router_obj.address,
        "gps": router_obj.gps,
        "status": router_obj.status,
        "configuration": {
            "authorization_method": router_obj.authorization_method,
            "accounting_method": router_obj.accounting_method,
            "radius_coa_port": router_obj.radius_coa_port,
            "radius_accounting_interval": router_obj.radius_accounting_interval,
            "api_port": router_obj.api_port,
            "ssh_port": router_obj.ssh_port,
        },
        "external_ids": {
            "splynx_id": router_obj.splynx_id,
            "location_id": router_obj.location_id,
        },
        "pop": pop,
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/pop-performance", dependencies=[Depends(Require("analytics:read"))])
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

    # Customer counts by POP
    customer_data = db.query(
        Customer.pop_id,
        func.count(Customer.id).label("customer_count"),
        func.sum(case((Customer.status == CustomerStatus.ACTIVE, 1), else_=0)).label("active"),
        func.sum(case((Customer.status == CustomerStatus.INACTIVE, 1), else_=0)).label("churned"),
    ).group_by(Customer.pop_id).subquery()

    # MRR by POP
    mrr_data = db.query(
        Customer.pop_id,
        func.sum(mrr_case).label("mrr"),
    ).join(Subscription, Subscription.customer_id == Customer.id).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Customer.pop_id).subquery()

    # Tickets by POP
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    ticket_data = db.query(
        Customer.pop_id,
        func.count(Ticket.id).label("ticket_count"),
    ).join(Ticket, Ticket.customer_id == Customer.id).filter(
        Ticket.created_at >= thirty_days_ago
    ).group_by(Customer.pop_id).subquery()

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
        func.coalesce(customer_data.c.customer_count, 0).label("total_customers"),
        func.coalesce(customer_data.c.active, 0).label("active_customers"),
        func.coalesce(customer_data.c.churned, 0).label("churned_customers"),
        func.coalesce(mrr_data.c.mrr, 0).label("mrr"),
        func.coalesce(ticket_data.c.ticket_count, 0).label("tickets_30d"),
        func.coalesce(router_data.c.router_count, 0).label("router_count"),
    ).outerjoin(
        customer_data, Pop.id == customer_data.c.pop_id
    ).outerjoin(
        mrr_data, Pop.id == mrr_data.c.pop_id
    ).outerjoin(
        ticket_data, Pop.id == ticket_data.c.pop_id
    ).outerjoin(
        router_data, Pop.id == router_data.c.pop_id
    ).order_by(func.coalesce(customer_data.c.customer_count, 0).desc()).all()

    return [
        {
            "pop_id": p.id,
            "name": p.name,
            "city": p.city,
            "is_active": p.is_active,
            "total_customers": p.total_customers,
            "active_customers": p.active_customers,
            "churned_customers": p.churned_customers,
            "churn_rate": round(p.churned_customers / p.total_customers * 100, 1) if p.total_customers > 0 else 0,
            "mrr": float(p.mrr),
            "tickets_30d": p.tickets_30d,
            "router_count": p.router_count,
        }
        for p in pops
    ]


@router.get("/analytics/customer-distribution", dependencies=[Depends(Require("analytics:read"))])
async def get_customer_distribution(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer distribution across POPs."""
    total_active = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    with_pop = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.pop_id.isnot(None)
    ).scalar() or 0

    # Distribution by POP
    distribution = db.query(
        Pop.name,
        func.count(Customer.id).label("count")
    ).join(Customer, Customer.pop_id == Pop.id).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).group_by(Pop.id, Pop.name).order_by(func.count(Customer.id).desc()).all()

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
                "percent": round(int(getattr(d, "count", 0) or 0) / total_active * 100, 1) if total_active > 0 and getattr(d, "count", 0) else 0,
            }
            for d in distribution
        ],
    }


# =============================================================================
# INSIGHTS
# =============================================================================

@router.get("/insights/health", dependencies=[Depends(Require("analytics:read"))])
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

    # Customers without POP
    customers_without_pop = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.pop_id.is_(None)
    ).scalar() or 0

    total_active_customers = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE
    ).scalar() or 0

    # Network-related tickets
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
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

    if customers_without_pop > total_active_customers * 0.2:
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
            "total_active_pops": db.query(func.count(Pop.id)).filter(Pop.is_active.is_(True)).scalar() or 0,
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

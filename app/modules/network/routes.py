"""
Network Routes - SSR + HTMX for ISP Infrastructure.

Permission Requirements:
- network:read - View POPs, routers, IP networks
- network:write - Modify network configurations
- analytics:read - View network analytics
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, case, or_, and_
from sqlalchemy.orm import Session, selectinload

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.pop import Pop
from app.models.router import Router
from app.models.ipv4_network import IPv4Network
from app.models.ipv4_address import IPv4Address
from app.models.party import Party
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.ticket import Ticket, TicketStatus
from app.core.security import is_htmx_request

# Permission dependencies
RequireNetworkRead = Depends(require_scope("network:read"))
RequireNetworkWrite = Depends(require_scope("network:write"))
RequireAnalyticsRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/network", tags=["network"])
templates = get_template_env()


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def network_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Network dashboard with infrastructure overview and health metrics."""
    # POP counts
    total_pops = db.query(func.count(Pop.id)).scalar() or 0
    active_pops = db.query(func.count(Pop.id)).filter(Pop.is_active.is_(True)).scalar() or 0

    # Router counts
    total_routers = db.query(func.count(Router.id)).scalar() or 0

    # IP Network stats
    total_networks = db.query(func.count(IPv4Network.id)).scalar() or 0
    total_ips = db.query(func.count(IPv4Address.id)).scalar() or 0
    used_ips = db.query(func.count(IPv4Address.id)).filter(IPv4Address.is_used.is_(True)).scalar() or 0

    # Customer distribution (via active subscriptions)
    active_subscriptions = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).subquery()

    customers_with_pop = (
        db.query(func.count(func.distinct(active_subscriptions.c.party_id)))
        .join(Router, active_subscriptions.c.router_id == Router.id)
        .filter(Router.pop_id.isnot(None))
        .scalar()
        or 0
    )

    total_customers = (
        db.query(func.count(func.distinct(active_subscriptions.c.party_id)))
        .scalar()
        or 0
    )

    customers_without_pop = (
        db.query(func.count(func.distinct(active_subscriptions.c.party_id)))
        .filter(active_subscriptions.c.router_id.is_(None))
        .scalar()
        or 0
    )

    # Top 10 POPs by customer count
    customer_counts = db.query(
        Router.pop_id.label("pop_id"),
        func.count(func.distinct(Subscription.party_id)).label("customer_count")
    ).join(
        Router, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Router.pop_id).subquery()

    top_pops = db.query(
        Pop.id,
        Pop.name,
        Pop.city,
        func.coalesce(customer_counts.c.customer_count, 0).label("customer_count")
    ).outerjoin(
        customer_counts, Pop.id == customer_counts.c.pop_id
    ).filter(
        Pop.is_active.is_(True)
    ).order_by(func.coalesce(customer_counts.c.customer_count, 0).desc()).limit(10).all()

    # Network health - POPs without routers
    pops_without_routers = db.query(func.count(Pop.id)).filter(
        Pop.is_active.is_(True),
        ~Pop.id.in_(db.query(Router.pop_id).filter(Router.pop_id.isnot(None)))
    ).scalar() or 0

    # Network-related tickets
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    network_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.created_at >= thirty_days_ago,
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        or_(
            Ticket.ticket_type.ilike("%network%"),
            Ticket.ticket_type.ilike("%connectivity%"),
            Ticket.issue_type.ilike("%network%"),
        )
    ).scalar() or 0

    # Build recommendations
    recommendations = []
    if pops_without_routers > 0:
        recommendations.append({
            "priority": "high",
            "icon": "router",
            "title": f"{pops_without_routers} POPs without routers",
            "description": "Active POPs should have at least one router assigned",
        })

    if customers_without_pop > total_customers * 0.1 and total_customers > 0:
        pct = round(customers_without_pop / total_customers * 100, 1)
        recommendations.append({
            "priority": "medium",
            "icon": "location",
            "title": f"{customers_without_pop} customers without POP",
            "description": f"{pct}% of active customers have no POP assigned",
        })

    if network_tickets > 10:
        recommendations.append({
            "priority": "medium",
            "icon": "ticket",
            "title": f"{network_tickets} network tickets (30d)",
            "description": "Review network infrastructure for common issues",
        })

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Network"
    context["breadcrumbs"] = build_breadcrumbs([{"label": "Network"}])

    # Stats
    context["stats"] = {
        "total_pops": total_pops,
        "active_pops": active_pops,
        "total_routers": total_routers,
        "total_networks": total_networks,
        "total_ips": total_ips,
        "used_ips": used_ips,
        "ip_utilization": round(used_ips / total_ips * 100, 1) if total_ips > 0 else 0,
        "customers_with_pop": customers_with_pop,
        "customers_without_pop": customers_without_pop,
        "assignment_rate": round(customers_with_pop / total_customers * 100, 1) if total_customers > 0 else 0,
        "network_tickets": network_tickets,
    }
    context["top_pops"] = top_pops
    context["recommendations"] = recommendations

    template = templates.get_template("modules/network/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# POP MANAGEMENT
# =============================================================================

@router.get("/pops", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def pops_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    city: Optional[str] = Query(None, description="Filter by city"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """POP list page with customer and router counts."""
    # Subquery for customer counts
    customer_counts = db.query(
        Router.pop_id.label("pop_id"),
        func.count(func.distinct(Subscription.party_id)).label("customer_count")
    ).join(
        Router, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Router.pop_id).subquery()

    # Subquery for router counts
    router_counts = db.query(
        Router.pop_id,
        func.count(Router.id).label("router_count")
    ).group_by(Router.pop_id).subquery()

    # Main query
    query = db.query(
        Pop,
        func.coalesce(customer_counts.c.customer_count, 0).label("customer_count"),
        func.coalesce(router_counts.c.router_count, 0).label("router_count"),
    ).outerjoin(
        customer_counts, Pop.id == customer_counts.c.pop_id
    ).outerjoin(
        router_counts, Pop.id == router_counts.c.pop_id
    )

    # Filters
    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(
            Pop.name.ilike(search_term),
            Pop.code.ilike(search_term),
            Pop.city.ilike(search_term),
        ))

    if city:
        query = query.filter(Pop.city.ilike(f"%{city}%"))

    if status == "active":
        query = query.filter(Pop.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(Pop.is_active.is_(False))

    # Count total
    total = query.count()

    # Sort and paginate
    query = query.order_by(func.coalesce(customer_counts.c.customer_count, 0).desc())
    offset = (page - 1) * per_page
    pops = query.offset(offset).limit(per_page).all()

    # Get unique cities for filter
    cities = db.query(Pop.city).filter(Pop.city.isnot(None)).distinct().order_by(Pop.city).all()

    context = get_base_context(request, response, user, csrf_token)
    context["pops"] = pops
    context["search_query"] = q or ""
    context["current_city"] = city
    context["current_status"] = status
    context["cities"] = [c[0] for c in cities if c[0]]
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/network/templates/partials/pops_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Points of Presence"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "POPs"},
    ])

    template = templates.get_template("modules/network/templates/pages/pops_list.html")
    return HTMLResponse(template.render(context))


@router.get("/pops/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def pops_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """POPs table partial for HTMX."""
    return await pops_list(request, response, user, csrf_token, db, q, city, status, page, per_page)


@router.get("/pops/{pop_id}", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def pop_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    pop_id: int,
):
    """POP detail page with metrics, routers, and customers."""
    pop = db.query(Pop).filter(Pop.id == pop_id).first()
    if not pop:
        raise HTTPException(status_code=404, detail="POP not found")

    active_party_ids = (
        db.query(Subscription.party_id.label("party_id"))
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Router.pop_id == pop_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .subquery()
    )

    # Customer stats
    customer_count = (
        db.query(func.count(func.distinct(active_party_ids.c.party_id)))
        .scalar()
        or 0
    )

    # MRR calculation
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )
    pop_mrr = (
        db.query(func.sum(mrr_case))
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Router.pop_id == pop_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .scalar()
        or 0
    )

    # Routers at this POP
    routers = db.query(Router).filter(Router.pop_id == pop_id).all()

    # Open tickets for this POP's customers
    open_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.party_id.in_(active_party_ids),
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
        )
        .scalar()
        or 0
    )

    # Recent customers (top 10)
    recent_customers = (
        db.query(Party)
        .join(Subscription, Subscription.party_id == Party.id)
        .join(Router, Subscription.router_id == Router.id)
        .filter(
            Router.pop_id == pop_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Party.created_at.desc())
        .distinct(Party.id)
        .limit(10)
        .all()
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = pop.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "POPs", "url": "/network/pops"},
        {"label": pop.name},
    ])

    context["pop"] = pop
    context["metrics"] = {
        "customer_count": customer_count,
        "mrr": float(pop_mrr),
        "router_count": len(routers),
        "open_tickets": open_tickets,
    }
    context["routers"] = routers
    context["recent_customers"] = recent_customers

    template = templates.get_template("modules/network/templates/pages/pop_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ROUTER MANAGEMENT
# =============================================================================

@router.get("/routers", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def routers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    pop_id: Optional[int] = Query(None, description="Filter by POP"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Router list page."""
    query = db.query(Router).outerjoin(Pop, Router.pop_id == Pop.id)

    # Filters
    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(
            Router.title.ilike(search_term),
            Router.ip.ilike(search_term),
            Router.nas_ip.ilike(search_term),
            Router.model.ilike(search_term),
        ))

    if pop_id:
        query = query.filter(Router.pop_id == pop_id)

    if status:
        query = query.filter(Router.status == status)

    # Count total
    total = query.count()

    # Sort and paginate
    query = query.order_by(Router.title)
    offset = (page - 1) * per_page
    routers = query.offset(offset).limit(per_page).all()

    # Get POPs for filter dropdown
    pops = db.query(Pop.id, Pop.name).filter(Pop.is_active.is_(True)).order_by(Pop.name).all()

    # Get unique statuses for filter
    statuses = db.query(Router.status).filter(Router.status.isnot(None)).distinct().all()

    context = get_base_context(request, response, user, csrf_token)
    context["routers"] = routers
    context["search_query"] = q or ""
    context["current_pop_id"] = pop_id
    context["current_status"] = status
    context["pops"] = pops
    context["statuses"] = [s[0] for s in statuses if s[0]]
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/network/templates/partials/routers_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Routers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "Routers"},
    ])

    template = templates.get_template("modules/network/templates/pages/routers_list.html")
    return HTMLResponse(template.render(context))


@router.get("/routers/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def routers_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    pop_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Routers table partial for HTMX."""
    return await routers_list(request, response, user, csrf_token, db, q, pop_id, status, page, per_page)


@router.get("/routers/{router_id}", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def router_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    router_id: int,
):
    """Router detail page with configuration and active sessions."""
    router_obj = db.query(Router).filter(Router.id == router_id).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")

    # Get POP info
    pop = None
    if router_obj.pop_id:
        pop = db.query(Pop).filter(Pop.id == router_obj.pop_id).first()

    # Count customers using this router (via subscriptions)
    customer_count = db.query(func.count(Subscription.id)).filter(
        Subscription.router_id == router_id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    # Get active subscriptions on this router (for sessions view)
    active_subscriptions = db.query(Subscription).options(
        selectinload(Subscription.customer)
    ).filter(
        Subscription.router_id == router_id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).order_by(Subscription.plan_name).limit(50).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = router_obj.title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "Routers", "url": "/network/routers"},
        {"label": router_obj.title},
    ])

    context["router"] = router_obj
    context["pop"] = pop
    context["customer_count"] = customer_count
    context["active_subscriptions"] = active_subscriptions

    template = templates.get_template("modules/network/templates/pages/router_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# IP ADDRESS MANAGEMENT
# =============================================================================

@router.get("/ip", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_management(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """IP Address management overview."""
    # Network stats
    total_networks = db.query(func.count(IPv4Network.id)).scalar() or 0
    root_networks = db.query(func.count(IPv4Network.id)).filter(
        IPv4Network.network_type == "rootnet"
    ).scalar() or 0
    end_networks = db.query(func.count(IPv4Network.id)).filter(
        IPv4Network.network_type == "endnet"
    ).scalar() or 0

    # IP stats
    total_ips = db.query(func.count(IPv4Address.id)).scalar() or 0
    used_ips = db.query(func.count(IPv4Address.id)).filter(IPv4Address.is_used.is_(True)).scalar() or 0
    available_ips = total_ips - used_ips

    # Networks by usage type
    networks_by_usage = db.query(
        IPv4Network.type_of_usage,
        func.count(IPv4Network.id).label("count")
    ).filter(
        IPv4Network.type_of_usage.isnot(None)
    ).group_by(IPv4Network.type_of_usage).all()

    # Top networks by usage
    top_networks = db.query(IPv4Network).filter(
        IPv4Network.network_type == "endnet"
    ).order_by(IPv4Network.used.desc().nullslast()).limit(10).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "IP Management"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "IP Management"},
    ])

    context["stats"] = {
        "total_networks": total_networks,
        "root_networks": root_networks,
        "end_networks": end_networks,
        "total_ips": total_ips,
        "used_ips": used_ips,
        "available_ips": available_ips,
        "utilization": round(used_ips / total_ips * 100, 1) if total_ips > 0 else 0,
    }
    context["networks_by_usage"] = networks_by_usage
    context["top_networks"] = top_networks

    template = templates.get_template("modules/network/templates/pages/ip_management.html")
    return HTMLResponse(template.render(context))


@router.get("/ip/networks/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_networks_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    network_type: Optional[str] = Query(None),
    usage_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """IPv4 networks table partial for HTMX."""
    return await ip_networks_list(request, response, user, csrf_token, db, q, network_type, usage_type, page, per_page)


@router.get("/ip/networks", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_networks_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    network_type: Optional[str] = Query(None),
    usage_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """IPv4 networks list."""
    query = db.query(IPv4Network)

    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(
            IPv4Network.network.ilike(search_term),
            IPv4Network.title.ilike(search_term),
        ))

    if network_type:
        query = query.filter(IPv4Network.network_type == network_type)

    if usage_type:
        query = query.filter(IPv4Network.type_of_usage == usage_type)

    total = query.count()
    query = query.order_by(IPv4Network.network)
    offset = (page - 1) * per_page
    networks = query.offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["networks"] = networks
    context["search_query"] = q or ""
    context["current_network_type"] = network_type
    context["current_usage_type"] = usage_type
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/network/templates/partials/networks_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "IPv4 Networks"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "IP Management", "url": "/network/ip"},
        {"label": "Networks"},
    ])

    template = templates.get_template("modules/network/templates/pages/networks_list.html")
    return HTMLResponse(template.render(context))


@router.get("/ip/addresses/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_addresses_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
):
    """IPv4 addresses table partial for HTMX."""
    return await ip_addresses_list(request, response, user, csrf_token, db, q, status, page, per_page)


@router.get("/ip/addresses", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_addresses_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
):
    """IPv4 addresses list."""
    query = db.query(IPv4Address).outerjoin(Party, IPv4Address.party_id == Party.id)

    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(
            IPv4Address.ip.ilike(search_term),
            IPv4Address.hostname.ilike(search_term),
            IPv4Address.title.ilike(search_term),
        ))

    if status == "used":
        query = query.filter(IPv4Address.is_used.is_(True))
    elif status == "available":
        query = query.filter(IPv4Address.is_used.is_(False))

    total = query.count()
    query = query.order_by(IPv4Address.ip)
    offset = (page - 1) * per_page
    addresses = query.offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["addresses"] = addresses
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/network/templates/partials/addresses_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "IP Addresses"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "IP Management", "url": "/network/ip"},
        {"label": "Addresses"},
    ])

    template = templates.get_template("modules/network/templates/pages/addresses_list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def network_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Network analytics - POP performance and customer distribution."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # MRR calculation case
    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price
    )

    # Customer counts by POP (via subscriptions)
    customer_data = db.query(
        Router.pop_id.label("pop_id"),
        func.count(func.distinct(Subscription.party_id)).label("customer_count"),
        func.count(func.distinct(case((Subscription.status == SubscriptionStatus.ACTIVE, Subscription.party_id)))).label("active"),
        func.count(func.distinct(case((Subscription.status != SubscriptionStatus.ACTIVE, Subscription.party_id)))).label("churned"),
    ).join(
        Router, Subscription.router_id == Router.id
    ).group_by(Router.pop_id).subquery()

    # MRR by POP
    mrr_data = db.query(
        Router.pop_id.label("pop_id"),
        func.sum(mrr_case).label("mrr"),
    ).join(
        Router, Subscription.router_id == Router.id
    ).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).group_by(Router.pop_id).subquery()

    # Tickets by POP
    party_by_pop = db.query(
        Subscription.party_id.label("party_id"),
        Router.pop_id.label("pop_id"),
    ).join(
        Router, Subscription.router_id == Router.id
    ).subquery()

    ticket_data = db.query(
        party_by_pop.c.pop_id,
        func.count(Ticket.id).label("ticket_count"),
    ).join(
        Ticket, Ticket.party_id == party_by_pop.c.party_id
    ).filter(
        Ticket.created_at >= thirty_days_ago
    ).group_by(party_by_pop.c.pop_id).subquery()

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

    # Aggregate totals
    total_customers = sum(p.total_customers for p in pops)
    total_active = sum(p.active_customers for p in pops)
    total_mrr = sum(float(p.mrr) for p in pops)
    total_tickets = sum(p.tickets_30d for p in pops)

    # Customers without POP
    customers_without_pop = (
        db.query(func.count(func.distinct(Subscription.party_id)))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.router_id.is_(None),
        )
        .scalar()
        or 0
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Network Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "Analytics"},
    ])

    context["totals"] = {
        "total_customers": total_customers,
        "active_customers": total_active,
        "total_mrr": total_mrr,
        "total_tickets": total_tickets,
        "customers_without_pop": customers_without_pop,
        "pop_count": len(pops),
        "assignment_rate": round((total_active - customers_without_pop) / total_active * 100, 1) if total_active > 0 else 0,
    }

    context["pop_performance"] = [
        {
            "id": p.id,
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
            "customer_percent": round(p.active_customers / total_active * 100, 1) if total_active > 0 else 0,
        }
        for p in pops
    ]

    template = templates.get_template("modules/network/templates/pages/analytics.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# NETWORK HEALTH INSIGHTS
# =============================================================================

@router.get("/health", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def network_health(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Network health insights - infrastructure issues and recommendations."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # POPs without routers
    pops_without_routers = db.query(Pop).outerjoin(
        Router, Pop.id == Router.pop_id
    ).filter(
        Pop.is_active.is_(True),
        Router.id.is_(None)
    ).all()

    # POPs with high ticket counts (potential issues)
    party_by_pop = db.query(
        Subscription.party_id.label("party_id"),
        Router.pop_id.label("pop_id"),
    ).join(
        Router, Subscription.router_id == Router.id
    ).subquery()

    high_ticket_pops = db.query(
        Pop.id,
        Pop.name,
        Pop.city,
        func.count(Ticket.id).label("ticket_count"),
        func.count(func.distinct(party_by_pop.c.party_id)).label("customer_count"),
    ).outerjoin(
        party_by_pop, party_by_pop.c.pop_id == Pop.id
    ).outerjoin(
        Ticket, Ticket.party_id == party_by_pop.c.party_id
    ).filter(
        Pop.is_active.is_(True),
        Ticket.created_at >= thirty_days_ago
    ).group_by(Pop.id, Pop.name, Pop.city).having(
        func.count(Ticket.id) > 10
    ).order_by(func.count(Ticket.id).desc()).limit(10).all()

    # Networks with high utilization (>80%)
    high_util_networks = db.query(IPv4Network).filter(
        IPv4Network.network_type == "endnet",
        IPv4Network.total > 0,
        IPv4Network.used > 0,
        (IPv4Network.used * 100 / IPv4Network.total) > 80
    ).order_by((IPv4Network.used * 100 / IPv4Network.total).desc()).limit(15).all()

    # Routers with no active subscriptions (underutilized)
    routers_no_subs = db.query(Router).outerjoin(
        Subscription, and_(
            Subscription.router_id == Router.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    ).filter(
        Subscription.id.is_(None)
    ).limit(20).all()

    # Customers without POP assignment
    customers_no_pop = (
        db.query(func.count(func.distinct(Subscription.party_id)))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.router_id.is_(None),
        )
        .scalar()
        or 0
    )

    # Overall health score
    issues = []
    if pops_without_routers:
        issues.append({"type": "critical", "message": f"{len(pops_without_routers)} POPs have no routers"})
    if high_util_networks:
        issues.append({"type": "warning", "message": f"{len(high_util_networks)} networks above 80% utilization"})
    if customers_no_pop > 0:
        issues.append({"type": "info", "message": f"{customers_no_pop} active customers have no POP assignment"})
    if routers_no_subs:
        issues.append({"type": "info", "message": f"{len(routers_no_subs)} routers have no active subscriptions"})

    # Calculate health score (simplified)
    critical_count = sum(1 for i in issues if i["type"] == "critical")
    warning_count = sum(1 for i in issues if i["type"] == "warning")
    health_score = max(0, 100 - (critical_count * 20) - (warning_count * 10))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Network Health"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "Health"},
    ])

    context["health_score"] = health_score
    context["issues"] = issues
    context["pops_without_routers"] = pops_without_routers
    context["high_ticket_pops"] = [
        {
            "id": p.id,
            "name": p.name,
            "city": p.city,
            "ticket_count": p.ticket_count,
            "customer_count": p.customer_count,
            "ticket_ratio": round(p.ticket_count / max(p.customer_count, 1), 2),
        }
        for p in high_ticket_pops
    ]
    context["high_util_networks"] = high_util_networks
    context["routers_no_subs"] = routers_no_subs
    context["customers_no_pop"] = customers_no_pop

    template = templates.get_template("modules/network/templates/pages/health.html")
    return HTMLResponse(template.render(context))

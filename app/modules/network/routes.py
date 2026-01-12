"""
Network Routes - SSR + HTMX for ISP Infrastructure.

Permission Requirements:
- network:read - View POPs, routers, IP networks
- network:write - Modify network configurations
- analytics:read - View network analytics

All routes delegate to services in app/services/network/.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request

# Import services
from app.services.network import (
    PopService,
    RouterService,
    IPv4NetworkService,
    IPAddressService,
    PopFilters,
    RouterFilters,
    IPv4NetworkFilters,
    IPv4AddressFilters,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError
from app.services.network.dashboard_service import NetworkDashboardService

# Permission dependencies
RequireNetworkRead = Depends(require_scope("network:read"))
RequireNetworkWrite = Depends(require_scope("network:write"))
RequireAnalyticsRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/network", tags=["network"])
templates = get_template_env()


# =============================================================================
# Service Providers
# =============================================================================

def get_pop_service(db: DB) -> PopService:
    return PopService(db)


def get_router_service(db: DB) -> RouterService:
    return RouterService(db)


def get_ipv4_network_service(db: DB) -> IPv4NetworkService:
    return IPv4NetworkService(db)


def get_ip_address_service(db: DB) -> IPAddressService:
    return IPAddressService(db)


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
    pop_service = get_pop_service(db)
    dashboard_service = NetworkDashboardService(db)
    router_service = get_router_service(db)
    ip_service = get_ip_address_service(db)
    network_service = get_ipv4_network_service(db)
    dashboard_service = NetworkDashboardService(db)

    # Use services for stats
    pop_stats = pop_service.get_overview_stats()
    router_stats = router_service.get_overview_stats()
    ip_stats = ip_service.get_stats()
    network_stats = network_service.get_stats()

    # Customer distribution
    customers_with_pop, total_customers = dashboard_service.get_customer_distribution()
    customers_without_pop = total_customers - customers_with_pop

    # Top 10 POPs by customer count
    top_pops = dashboard_service.get_top_pops(limit=10)

    # Network health
    pops_without_routers = pop_stats["total"] - router_stats["with_pop"]

    # Network-related tickets
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    network_tickets = dashboard_service.get_network_ticket_count(thirty_days_ago)

    # Build recommendations
    recommendations = []
    if pops_without_routers > 0:
        recommendations.append({
            "priority": "high", "icon": "router",
            "title": f"{pops_without_routers} POPs without routers",
            "description": "Active POPs should have at least one router assigned",
        })
    if customers_without_pop > total_customers * 0.1 and total_customers > 0:
        pct = round(customers_without_pop / total_customers * 100, 1)
        recommendations.append({
            "priority": "medium", "icon": "location",
            "title": f"{customers_without_pop} customers without POP",
            "description": f"{pct}% of active customers have no POP assigned",
        })
    if network_tickets > 10:
        recommendations.append({
            "priority": "medium", "icon": "ticket",
            "title": f"{network_tickets} network tickets (30d)",
            "description": "Review network infrastructure for common issues",
        })

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Network"
    context["breadcrumbs"] = build_breadcrumbs([{"label": "Network"}])
    context["stats"] = {
        "total_pops": pop_stats["total"],
        "active_pops": pop_stats["active"],
        "total_routers": router_stats["total"],
        "total_networks": network_stats["total_networks"],
        "total_ips": ip_stats["total_ips"],
        "used_ips": ip_stats["used_ips"],
        "ip_utilization": ip_stats["utilization"],
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
    q: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """POP list page with customer and router counts."""
    pop_service = get_pop_service(db)
    dashboard_service = NetworkDashboardService(db)

    # Map status filter
    is_active = None
    if status == "active":
        is_active = True
    elif status == "inactive":
        is_active = False

    filters = PopFilters(search=q, city=city, is_active=is_active)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = pop_service.list_pops(filters, pagination)

    enriched = dashboard_service.get_pop_enrichment([p.id for p in result.items])

    cities = pop_service.get_cities()

    context = get_base_context(request, response, user, csrf_token)
    context["pops"] = enriched
    context["search_query"] = q or ""
    context["current_city"] = city
    context["current_status"] = status
    context["cities"] = cities
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    request: Request, response: Response, user: SessionUser, csrf_token: CSRFToken, db: DB,
    q: Optional[str] = Query(None), city: Optional[str] = Query(None),
    status: Optional[str] = Query(None), page: int = Query(1, ge=1),
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
    pop_service = get_pop_service(db)
    router_service = get_router_service(db)
    dashboard_service = NetworkDashboardService(db)

    try:
        pop = pop_service.get_pop(pop_id)
        stats = pop_service.get_pop_stats(pop_id)
        routers = router_service.get_routers_for_pop(pop_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="POP not found")

    recent_customers = dashboard_service.get_recent_customers(pop_id, limit=10)

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
        "customer_count": stats.customer_count,
        "mrr": float(stats.mrr),
        "router_count": stats.router_count,
        "open_tickets": 0,
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
    q: Optional[str] = Query(None),
    pop_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Router list page."""
    router_service = get_router_service(db)
    pop_service = get_pop_service(db)
    dashboard_service = NetworkDashboardService(db)

    filters = RouterFilters(search=q, pop_id=pop_id, status=status)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = router_service.list_routers(filters, pagination, include_pop=True)

    # Get POPs for filter dropdown
    pops_result = pop_service.list_pops(PopFilters(is_active=True), PaginationParams(limit=500))
    pops = [(p.id, p.name) for p in pops_result.items]

    # Get unique statuses
    statuses = dashboard_service.get_router_statuses()

    context = get_base_context(request, response, user, csrf_token)
    context["routers"] = result.items
    context["search_query"] = q or ""
    context["current_pop_id"] = pop_id
    context["current_status"] = status
    context["pops"] = pops
    context["statuses"] = statuses
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    request: Request, response: Response, user: SessionUser, csrf_token: CSRFToken, db: DB,
    q: Optional[str] = Query(None), pop_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None), page: int = Query(1, ge=1),
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
    router_service = get_router_service(db)
    dashboard_service = NetworkDashboardService(db)

    try:
        router_obj = router_service.get_router(router_id, include_pop=True)
        stats = router_service.get_router_stats(router_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Router not found")

    active_subscriptions = dashboard_service.list_active_subscriptions(router_id, limit=50)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = router_obj.title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "Routers", "url": "/network/routers"},
        {"label": router_obj.title},
    ])
    context["router"] = router_obj
    context["pop"] = router_obj.pop
    context["customer_count"] = stats.active_subscriptions
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
    network_service = get_ipv4_network_service(db)
    ip_service = get_ip_address_service(db)
    dashboard_service = NetworkDashboardService(db)

    network_stats = network_service.get_stats()
    ip_stats = ip_service.get_stats()

    networks_by_usage = dashboard_service.get_networks_by_usage()
    top_networks = dashboard_service.get_top_networks(limit=10)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "IP Management"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Network", "url": "/network"},
        {"label": "IP Management"},
    ])
    context["stats"] = {
        "total_networks": network_stats["total_networks"],
        "root_networks": network_stats["root_networks"],
        "end_networks": network_stats["end_networks"],
        "total_ips": ip_stats["total_ips"],
        "used_ips": ip_stats["used_ips"],
        "available_ips": ip_stats["available_ips"],
        "utilization": ip_stats["utilization"],
    }
    context["networks_by_usage"] = networks_by_usage
    context["top_networks"] = top_networks

    template = templates.get_template("modules/network/templates/pages/ip_management.html")
    return HTMLResponse(template.render(context))


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
    network_service = get_ipv4_network_service(db)

    filters = IPv4NetworkFilters(search=q, network_type=network_type, type_of_usage=usage_type)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = network_service.list_networks(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["networks"] = result.items
    context["search_query"] = q or ""
    context["current_network_type"] = network_type
    context["current_usage_type"] = usage_type
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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


@router.get("/ip/networks/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_networks_table(
    request: Request, response: Response, user: SessionUser, csrf_token: CSRFToken, db: DB,
    q: Optional[str] = Query(None), network_type: Optional[str] = Query(None),
    usage_type: Optional[str] = Query(None), page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """IPv4 networks table partial for HTMX."""
    return await ip_networks_list(request, response, user, csrf_token, db, q, network_type, usage_type, page, per_page)


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
    ip_service = get_ip_address_service(db)

    is_used = None
    if status == "used":
        is_used = True
    elif status == "available":
        is_used = False

    filters = IPv4AddressFilters(search=q, is_used=is_used)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = ip_service.list_addresses(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["addresses"] = result.items
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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


@router.get("/ip/addresses/table", response_class=HTMLResponse, dependencies=[RequireNetworkRead])
async def ip_addresses_table(
    request: Request, response: Response, user: SessionUser, csrf_token: CSRFToken, db: DB,
    q: Optional[str] = Query(None), status: Optional[str] = Query(None),
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=10, le=200),
):
    """IPv4 addresses table partial for HTMX."""
    return await ip_addresses_list(request, response, user, csrf_token, db, q, status, page, per_page)


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
    pop_service = get_pop_service(db)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    dashboard_service = NetworkDashboardService(db)

    # Get all POPs with stats
    from app.models.pop import Pop
    pops_result = pop_service.list_pops(None, PaginationParams(limit=500))

    pop_performance = []
    total_customers = 0
    total_active = 0
    total_mrr = 0.0
    total_tickets = 0

    for pop in pops_result.items:
        stats = pop_service.get_pop_stats(pop.id)

        tickets_30d = dashboard_service.get_pop_ticket_count(pop.id, thirty_days_ago)

        pop_performance.append({
            "id": pop.id,
            "name": pop.name,
            "city": pop.city,
            "is_active": pop.is_active,
            "total_customers": stats.customer_count,
            "active_customers": stats.customer_count,
            "churned_customers": 0,
            "churn_rate": 0,
            "mrr": float(stats.mrr),
            "tickets_30d": tickets_30d,
            "router_count": stats.router_count,
        })
        total_customers += stats.customer_count
        total_active += stats.customer_count
        total_mrr += float(stats.mrr)
        total_tickets += tickets_30d

    # Add customer percentages
    for p in pop_performance:
        p["customer_percent"] = round(p["active_customers"] / total_active * 100, 1) if total_active > 0 else 0

    # Sort by customer count
    pop_performance.sort(key=lambda x: x["total_customers"], reverse=True)

    # Customers without POP
    customers_without_pop = dashboard_service.get_customers_without_pop()

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
        "pop_count": len(pop_performance),
        "assignment_rate": round((total_active - customers_without_pop) / total_active * 100, 1) if total_active > 0 else 0,
    }
    context["pop_performance"] = pop_performance

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
    pop_service = get_pop_service(db)
    router_service = get_router_service(db)
    ip_service = get_ip_address_service(db)
    dashboard_service = NetworkDashboardService(db)

    pop_stats = pop_service.get_overview_stats()
    router_stats = router_service.get_overview_stats()
    ip_stats = ip_service.get_stats()

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    pops_without_routers = dashboard_service.get_pops_without_routers()
    high_util_networks = dashboard_service.get_high_util_networks(limit=15)
    routers_no_subs = dashboard_service.get_routers_without_subscriptions(limit=20)
    customers_no_pop = dashboard_service.get_customers_without_pop()

    # Build issues list
    issues = []
    if pops_without_routers:
        issues.append({"type": "critical", "message": f"{len(pops_without_routers)} POPs have no routers"})
    if high_util_networks:
        issues.append({"type": "warning", "message": f"{len(high_util_networks)} networks above 80% utilization"})
    if customers_no_pop > 0:
        issues.append({"type": "info", "message": f"{customers_no_pop} active customers have no POP assignment"})
    if routers_no_subs:
        issues.append({"type": "info", "message": f"{len(routers_no_subs)} routers have no active subscriptions"})

    # Health score
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
    context["high_util_networks"] = high_util_networks
    context["routers_no_subs"] = routers_no_subs
    context["customers_no_pop"] = customers_no_pop

    template = templates.get_template("modules/network/templates/pages/health.html")
    return HTMLResponse(template.render(context))

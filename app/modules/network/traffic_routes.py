"""
Traffic Visualization Routes - Bandwidth Monitoring.

Provides traffic graphs and analytics for:
- Router-level traffic overview
- Interface-level detailed graphs
- Historical bandwidth analysis

Permission Requirements:
- network:read - View traffic data
- analytics:read - View traffic analytics
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone
import json

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from app.web.dependencies import SessionUser, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request

# Import services
from app.services.network import (
    TrafficGraphService,
    RouterService,
    PopService,
)

# Permission dependencies
RequireNetworkRead = Depends(require_scope("network:read"))
RequireAnalyticsRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/network/traffic", tags=["traffic"])
templates = get_template_env()


# =============================================================================
# Service Providers
# =============================================================================

def get_traffic_service(db: DB) -> TrafficGraphService:
    return TrafficGraphService(db)


def get_router_service(db: DB) -> RouterService:
    return RouterService(db)


def get_pop_service(db: DB) -> PopService:
    return PopService(db)


# =============================================================================
# TRAFFIC DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse)
async def traffic_dashboard(
    request: Request,
    db: DB,
    user: SessionUser,
    pop_id: Optional[int] = Query(None),
    _auth: None = RequireNetworkRead,
):
    """Traffic overview dashboard with aggregate stats."""
    traffic_service = get_traffic_service(db)
    pop_service = get_pop_service(db)

    # Get top interfaces
    top_interfaces = await traffic_service.get_top_interfaces(
        limit=10,
        pop_id=pop_id,
    )

    # Get NOC stats for aggregate traffic
    stats = await traffic_service.get_noc_dashboard_stats()

    # Get POPs for filter dropdown
    pops, _ = await pop_service.list(limit=100)

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "Traffic", "href": "/network/traffic"},
        ]),
        "top_interfaces": top_interfaces,
        "stats": stats,
        "pops": pops,
        "pop_id": pop_id,
    }

    template = templates.get_template("network/traffic/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/router/{router_id}", response_class=HTMLResponse)
async def router_traffic(
    request: Request,
    router_id: int,
    db: DB,
    user: SessionUser,
    hours: int = Query(24, ge=1, le=168),
    _auth: None = RequireNetworkRead,
):
    """Router traffic detail with all interfaces."""
    traffic_service = get_traffic_service(db)
    router_service = get_router_service(db)

    # Get router info
    router_info = await router_service.get(router_id)
    if not router_info:
        return HTMLResponse("<p>Router not found</p>", status_code=404)

    # Time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Get traffic summary
    summary = await traffic_service.get_router_traffic(
        router_id=router_id,
        start_time=start_time,
        end_time=end_time,
    )

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "Traffic", "href": "/network/traffic"},
            {"label": router_info.name or f"Router {router_id}", "href": f"/network/traffic/router/{router_id}"},
        ]),
        "router": router_info,
        "summary": summary,
        "hours": hours,
        "start_time": start_time,
        "end_time": end_time,
    }

    template = templates.get_template("network/traffic/pages/router_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/router/{router_id}/interface/{interface_index}", response_class=HTMLResponse)
async def interface_traffic(
    request: Request,
    router_id: int,
    interface_index: int,
    db: DB,
    user: SessionUser,
    hours: int = Query(24, ge=1, le=168),
    _auth: None = RequireNetworkRead,
):
    """Interface traffic detail with graph."""
    traffic_service = get_traffic_service(db)
    router_service = get_router_service(db)

    # Get router info
    router_info = await router_service.get(router_id)
    if not router_info:
        return HTMLResponse("<p>Router not found</p>", status_code=404)

    # Time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Get traffic data
    traffic_data = await traffic_service.get_interface_traffic(
        router_id=router_id,
        interface_index=interface_index,
        start_time=start_time,
        end_time=end_time,
    )

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "Traffic", "href": "/network/traffic"},
            {"label": router_info.name or f"Router {router_id}", "href": f"/network/traffic/router/{router_id}"},
            {"label": traffic_data.interface_name or f"Interface {interface_index}"},
        ]),
        "router": router_info,
        "interface_index": interface_index,
        "traffic_data": traffic_data,
        "chart_data": json.dumps(traffic_data.to_chart_data()),
        "hours": hours,
        "start_time": start_time,
        "end_time": end_time,
    }

    template = templates.get_template("network/traffic/pages/interface_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# API ENDPOINTS FOR CHARTS
# =============================================================================

@router.get("/api/graph/{router_id}", response_class=JSONResponse)
async def get_traffic_graph_data(
    request: Request,
    router_id: int,
    db: DB,
    user: SessionUser,
    interface_index: Optional[int] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    resolution: str = Query("auto"),
    _auth: None = RequireNetworkRead,
):
    """Get traffic graph data as JSON for Chart.js."""
    traffic_service = get_traffic_service(db)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    if interface_index is not None:
        traffic_data = await traffic_service.get_interface_traffic(
            router_id=router_id,
            interface_index=interface_index,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
        )
    else:
        # Aggregate router traffic
        summary = await traffic_service.get_router_traffic(
            router_id=router_id,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
        )
        # Return aggregate data
        return JSONResponse({
            "router_id": router_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "aggregate_rx_rate_bps": summary.aggregate_rx_rate_bps,
            "aggregate_tx_rate_bps": summary.aggregate_tx_rate_bps,
            "interfaces": [
                {
                    "name": iface.interface_name,
                    "index": iface.interface_index,
                    "current_rx_rate_bps": iface.current_rx_rate_bps,
                    "current_tx_rate_bps": iface.current_tx_rate_bps,
                    "oper_status": iface.oper_status,
                }
                for iface in summary.interfaces
            ],
        })

    return JSONResponse({
        "router_id": router_id,
        "interface_index": interface_index,
        "interface_name": traffic_data.interface_name,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "resolution": traffic_data.resolution,
        "summary": {
            "avg_rx_rate_bps": traffic_data.avg_rx_rate_bps,
            "avg_tx_rate_bps": traffic_data.avg_tx_rate_bps,
            "max_rx_rate_bps": traffic_data.max_rx_rate_bps,
            "max_tx_rate_bps": traffic_data.max_tx_rate_bps,
            "p95_rx_rate_bps": traffic_data.p95_rx_rate_bps,
            "p95_tx_rate_bps": traffic_data.p95_tx_rate_bps,
            "total_rx_bytes": traffic_data.total_rx_bytes,
            "total_tx_bytes": traffic_data.total_tx_bytes,
        },
        "chart": traffic_data.to_chart_data(),
    })


@router.get("/api/top-interfaces", response_class=JSONResponse)
async def get_top_interfaces_api(
    request: Request,
    db: DB,
    user: SessionUser,
    limit: int = Query(10, ge=1, le=50),
    pop_id: Optional[int] = Query(None),
    metric: str = Query("total_rate"),
    _auth: None = RequireNetworkRead,
):
    """Get top interfaces by traffic as JSON."""
    traffic_service = get_traffic_service(db)

    top_interfaces = await traffic_service.get_top_interfaces(
        limit=limit,
        pop_id=pop_id,
        metric=metric,
    )

    return JSONResponse({
        "interfaces": [
            {
                "router_id": iface.router_id,
                "router_name": iface.router_name,
                "interface_index": iface.interface_index,
                "interface_name": iface.interface_name,
                "rx_rate_bps": iface.rx_rate_bps,
                "tx_rate_bps": iface.tx_rate_bps,
                "total_rate_bps": iface.total_rate_bps,
                "utilization_percent": iface.utilization_percent,
            }
            for iface in top_interfaces
        ],
    })


# =============================================================================
# HTMX PARTIALS
# =============================================================================

@router.get("/partials/router-summary/{router_id}", response_class=HTMLResponse)
async def router_summary_partial(
    request: Request,
    router_id: int,
    db: DB,
    user: SessionUser,
    hours: int = Query(24),
    _auth: None = RequireNetworkRead,
):
    """HTMX partial for router traffic summary."""
    traffic_service = get_traffic_service(db)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    summary = await traffic_service.get_router_traffic(
        router_id=router_id,
        start_time=start_time,
        end_time=end_time,
    )

    context = {"summary": summary, "hours": hours}
    template = templates.get_template("network/traffic/partials/router_summary.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/interface-list/{router_id}", response_class=HTMLResponse)
async def interface_list_partial(
    request: Request,
    router_id: int,
    db: DB,
    user: SessionUser,
    hours: int = Query(24),
    _auth: None = RequireNetworkRead,
):
    """HTMX partial for interface list with traffic stats."""
    traffic_service = get_traffic_service(db)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    summary = await traffic_service.get_router_traffic(
        router_id=router_id,
        start_time=start_time,
        end_time=end_time,
    )

    context = {"interfaces": summary.interfaces, "router_id": router_id}
    template = templates.get_template("network/traffic/partials/interface_list.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/top-interfaces", response_class=HTMLResponse)
async def top_interfaces_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    limit: int = Query(10),
    pop_id: Optional[int] = Query(None),
    _auth: None = RequireNetworkRead,
):
    """HTMX partial for top interfaces table."""
    traffic_service = get_traffic_service(db)

    top_interfaces = await traffic_service.get_top_interfaces(
        limit=limit,
        pop_id=pop_id,
    )

    context = {"top_interfaces": top_interfaces}
    template = templates.get_template("network/traffic/partials/top_interfaces.html")
    return HTMLResponse(template.render(context))

"""
NOC Dashboard Routes - Network Operations Center.

Provides real-time monitoring views for:
- Device status grid
- Active alerts
- Active incidents
- Traffic overview

Permission Requirements:
- noc:read - View NOC dashboard
- noc:write - Acknowledge alerts, manage incidents
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse

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
    AlertService,
    AlertFilters,
)

# Permission dependencies
RequireNOCRead = Depends(require_scope("noc:read"))
RequireNOCWrite = Depends(require_scope("noc:write"))

router = APIRouter(prefix="/network/noc", tags=["noc"])
templates = get_template_env()


# =============================================================================
# Service Providers
# =============================================================================

def get_traffic_service(db: DB) -> TrafficGraphService:
    return TrafficGraphService(db)


def get_alert_service(db: DB) -> AlertService:
    return AlertService(db)


# =============================================================================
# NOC DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse)
async def noc_dashboard(
    request: Request,
    db: DB,
    user: SessionUser,
    _auth: None = RequireNOCRead,
):
    """NOC dashboard with real-time device status and alerts."""
    traffic_service = get_traffic_service(db)
    alert_service = get_alert_service(db)

    # Get dashboard data
    stats = await traffic_service.get_noc_dashboard_stats()
    devices = await traffic_service.get_device_status_cards(limit=24)
    alerts = await traffic_service.get_recent_alerts(limit=10)
    incidents = await traffic_service.get_active_incidents(limit=5)
    top_interfaces = await traffic_service.get_top_interfaces(limit=5)

    # Get alert stats
    alert_stats = await alert_service.get_stats()

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "NOC Dashboard", "href": "/network/noc"},
        ]),
        "stats": stats,
        "devices": devices,
        "alerts": alerts,
        "incidents": incidents,
        "top_interfaces": top_interfaces,
        "alert_stats": alert_stats,
        "refresh_interval": 30,  # seconds
    }

    template = templates.get_template("network/noc/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/devices", response_class=HTMLResponse)
async def noc_devices(
    request: Request,
    db: DB,
    user: SessionUser,
    pop_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    _auth: None = RequireNOCRead,
):
    """Device status grid view."""
    traffic_service = get_traffic_service(db)

    devices = await traffic_service.get_device_status_cards(
        pop_id=pop_id,
        status_filter=status,
        limit=100,
    )

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "NOC", "href": "/network/noc"},
            {"label": "Devices", "href": "/network/noc/devices"},
        ]),
        "devices": devices,
        "pop_id": pop_id,
        "status_filter": status,
    }

    if is_htmx_request(request):
        template = templates.get_template("network/noc/partials/device_grid.html")
    else:
        template = templates.get_template("network/noc/pages/devices.html")

    return HTMLResponse(template.render(context))


@router.get("/alerts", response_class=HTMLResponse)
async def noc_alerts(
    request: Request,
    db: DB,
    user: SessionUser,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _auth: None = RequireNOCRead,
):
    """Active alerts list view."""
    alert_service = get_alert_service(db)
    traffic_service = get_traffic_service(db)

    filters = AlertFilters()
    if severity:
        filters.severity = severity
    if status:
        filters.status = status
    else:
        filters.statuses = ["active", "acknowledged"]

    alerts = await alert_service.list_alerts(filters, limit=50)
    stats = await alert_service.get_stats()

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "NOC", "href": "/network/noc"},
            {"label": "Alerts", "href": "/network/noc/alerts"},
        ]),
        "alerts": alerts,
        "stats": stats,
        "severity_filter": severity,
        "status_filter": status,
    }

    if is_htmx_request(request):
        template = templates.get_template("network/noc/partials/alerts_table.html")
    else:
        template = templates.get_template("network/noc/pages/alerts.html")

    return HTMLResponse(template.render(context))


@router.get("/incidents", response_class=HTMLResponse)
async def noc_incidents(
    request: Request,
    db: DB,
    user: SessionUser,
    status: Optional[str] = Query(None),
    _auth: None = RequireNOCRead,
):
    """Active incidents list view."""
    traffic_service = get_traffic_service(db)

    incidents = await traffic_service.get_active_incidents(limit=20)

    context = {
        **get_base_context(request, user),
        **get_navigation_context("network"),
        "breadcrumbs": build_breadcrumbs([
            {"label": "Network", "href": "/network"},
            {"label": "NOC", "href": "/network/noc"},
            {"label": "Incidents", "href": "/network/noc/incidents"},
        ]),
        "incidents": incidents,
        "status_filter": status,
    }

    if is_htmx_request(request):
        template = templates.get_template("network/noc/partials/incidents_table.html")
    else:
        template = templates.get_template("network/noc/pages/incidents.html")

    return HTMLResponse(template.render(context))


# =============================================================================
# HTMX PARTIALS
# =============================================================================

@router.get("/partials/stats", response_class=HTMLResponse)
async def noc_stats_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    _auth: None = RequireNOCRead,
):
    """HTMX partial for dashboard stats cards."""
    traffic_service = get_traffic_service(db)
    stats = await traffic_service.get_noc_dashboard_stats()

    context = {"stats": stats}
    template = templates.get_template("network/noc/partials/stats_cards.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/device-grid", response_class=HTMLResponse)
async def noc_device_grid_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    pop_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    _auth: None = RequireNOCRead,
):
    """HTMX partial for device status grid."""
    traffic_service = get_traffic_service(db)
    devices = await traffic_service.get_device_status_cards(
        pop_id=pop_id,
        status_filter=status,
        limit=24,
    )

    context = {"devices": devices}
    template = templates.get_template("network/noc/partials/device_grid.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/alerts-list", response_class=HTMLResponse)
async def noc_alerts_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    limit: int = Query(10),
    severity: Optional[str] = Query(None),
    _auth: None = RequireNOCRead,
):
    """HTMX partial for recent alerts list."""
    traffic_service = get_traffic_service(db)
    alerts = await traffic_service.get_recent_alerts(limit=limit, severity=severity)

    context = {"alerts": alerts}
    template = templates.get_template("network/noc/partials/alerts_list.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/incidents-list", response_class=HTMLResponse)
async def noc_incidents_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    limit: int = Query(5),
    _auth: None = RequireNOCRead,
):
    """HTMX partial for active incidents list."""
    traffic_service = get_traffic_service(db)
    incidents = await traffic_service.get_active_incidents(limit=limit)

    context = {"incidents": incidents}
    template = templates.get_template("network/noc/partials/incidents_list.html")
    return HTMLResponse(template.render(context))


@router.get("/partials/top-interfaces", response_class=HTMLResponse)
async def noc_top_interfaces_partial(
    request: Request,
    db: DB,
    user: SessionUser,
    limit: int = Query(5),
    pop_id: Optional[int] = Query(None),
    _auth: None = RequireNOCRead,
):
    """HTMX partial for top interfaces by traffic."""
    traffic_service = get_traffic_service(db)
    top_interfaces = await traffic_service.get_top_interfaces(
        limit=limit,
        pop_id=pop_id,
    )

    context = {"top_interfaces": top_interfaces}
    template = templates.get_template("network/noc/partials/top_interfaces.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ALERT ACTIONS
# =============================================================================

@router.post("/alerts/{alert_id}/acknowledge", response_class=HTMLResponse)
async def acknowledge_alert(
    request: Request,
    alert_id: int,
    db: DB,
    user: SessionUser,
    _auth: None = RequireNOCWrite,
):
    """Acknowledge an alert."""
    alert_service = get_alert_service(db)

    # Get employee ID from user
    employee_id = getattr(user, "employee_id", None)

    # Get note from form
    form = await request.form()
    note = form.get("note", "")

    alert = await alert_service.acknowledge_alert(
        alert_id=alert_id,
        employee_id=employee_id or 0,
        note=note or None,
    )
    await db.commit()

    if alert:
        context = {"alert": alert, "success": True, "message": "Alert acknowledged"}
    else:
        context = {"success": False, "message": "Alert not found"}

    template = templates.get_template("network/noc/partials/alert_row.html")
    return HTMLResponse(template.render(context))


@router.post("/alerts/{alert_id}/resolve", response_class=HTMLResponse)
async def resolve_alert(
    request: Request,
    alert_id: int,
    db: DB,
    user: SessionUser,
    _auth: None = RequireNOCWrite,
):
    """Resolve an alert."""
    alert_service = get_alert_service(db)

    employee_id = getattr(user, "employee_id", None)

    form = await request.form()
    note = form.get("note", "")

    alert = await alert_service.resolve_alert(
        alert_id=alert_id,
        employee_id=employee_id,
        note=note or None,
        auto=False,
    )
    await db.commit()

    if alert:
        context = {"alert": alert, "success": True, "message": "Alert resolved"}
    else:
        context = {"success": False, "message": "Alert not found"}

    template = templates.get_template("network/noc/partials/alert_row.html")
    return HTMLResponse(template.render(context))

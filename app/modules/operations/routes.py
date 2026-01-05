"""
Operations Module Routes - Aggregates operations sub-modules.

Consolidates:
- Projects (/operations/projects)
- Field Service (/operations/field-service)
- Inventory (/operations/inventory)
- Assets (/operations/assets)
- Vehicles (/operations/vehicles)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse
from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

from app.services.operations import OperationsDashboardService

# Import sub-module routers
from app.modules.projects.routes import (
    router as projects_router,
    dashboard_router as projects_dashboard_router,
    tasks_router as projects_tasks_router,
    milestones_router as projects_milestones_router,
)
from app.modules.projects.gantt_routes import router as projects_gantt_router
from app.modules.field_service.routes import router as field_service_router
from app.modules.field_service.calendar_routes import router as field_service_calendar_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.assets.routes import router as assets_router
from app.modules.vehicles.routes import router as vehicles_router

RequireOperationsRead = Depends(require_scope("operations:read"))
templates = get_template_env()

# Main operations router - serves as landing/dashboard
router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_class=HTMLResponse)
async def operations_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Operations dashboard - landing page for operations module."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Operations"
    context["now"] = datetime.utcnow()

    stats_service = OperationsDashboardService(db, principal=user)
    counts = stats_service.get_dashboard_counts()

    stats = [
        {
            "key": "projects",
            "label": "Active Projects",
            "value": f"{counts['active_projects']:,}",
            "subtext": "In progress",
            "icon": "folder",
            "icon_bg": "bg-blue-50",
            "icon_color": "text-blue-600",
            "href": "/operations/projects",
        },
        {
            "key": "field_service",
            "label": "Service Orders",
            "value": f"{counts['open_orders']:,}",
            "subtext": "Open orders",
            "icon": "truck",
            "icon_bg": "bg-amber-50",
            "icon_color": "text-amber-600",
            "href": "/operations/field-service",
        },
        {
            "key": "inventory",
            "label": "Warehouses",
            "value": f"{counts['warehouse_count']:,}",
            "subtext": "Active locations",
            "icon": "package",
            "icon_bg": "bg-emerald-50",
            "icon_color": "text-emerald-600",
            "href": "/operations/inventory",
        },
        {
            "key": "assets",
            "label": "Active Assets",
            "value": f"{counts['active_assets']:,}",
            "subtext": "In service",
            "icon": "box",
            "icon_bg": "bg-purple-50",
            "icon_color": "text-purple-600",
            "href": "/operations/assets",
        },
        {
            "key": "vehicles",
            "label": "Fleet Vehicles",
            "value": f"{counts['vehicle_count']:,}",
            "subtext": "Active fleet",
            "icon": "truck",
            "icon_bg": "bg-cyan-50",
            "icon_color": "text-cyan-600",
            "href": "/operations/vehicles",
        },
    ]

    context["stats"] = stats

    # Quick links to sub-modules
    context["quick_links"] = [
        {"label": "Projects", "href": "/operations/projects", "icon": "folder", "description": "Manage projects and tasks"},
        {"label": "Field Service", "href": "/operations/field-service", "icon": "truck", "description": "Service orders and technicians"},
        {"label": "Inventory", "href": "/operations/inventory", "icon": "package", "description": "Warehouses and stock"},
        {"label": "Assets", "href": "/operations/assets", "icon": "box", "description": "Fixed assets tracking"},
        {"label": "Vehicles", "href": "/operations/vehicles", "icon": "truck", "description": "Fleet management"},
    ]

    template = templates.get_template("modules/operations/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# Include sub-module routers under /operations prefix
# Note: Each sub-router already has its own prefix (e.g., /projects)
# so the full path becomes /operations/projects
router.include_router(projects_router)
router.include_router(projects_dashboard_router)
router.include_router(projects_tasks_router)
router.include_router(projects_milestones_router)
router.include_router(projects_gantt_router)
router.include_router(field_service_router)
router.include_router(field_service_calendar_router)
router.include_router(inventory_router)
router.include_router(assets_router)
router.include_router(vehicles_router)

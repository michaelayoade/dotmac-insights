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
from sqlalchemy import func

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Import models for dashboard stats
from app.models.project import Project, ProjectStatus
from app.models.field_service import ServiceOrder, ServiceOrderStatus
from app.models.inventory import Warehouse, StockEntry
from app.models.asset import Asset, AssetStatus
from app.models.vehicle import Vehicle

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

    # Gather stats across all operations sub-modules
    stats = []

    # Active Projects
    active_projects = db.query(func.count(Project.id)).filter(
        Project.status.in_([
            ProjectStatus.OPEN,
            ProjectStatus.ON_HOLD,
        ])
    ).scalar() or 0
    stats.append({
        "key": "projects",
        "label": "Active Projects",
        "value": f"{active_projects:,}",
        "subtext": "In progress",
        "icon": "folder",
        "icon_bg": "bg-blue-50",
        "icon_color": "text-blue-600",
        "href": "/operations/projects",
    })

    # Open Service Orders
    open_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([
            ServiceOrderStatus.DRAFT,
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.IN_PROGRESS,
        ])
    ).scalar() or 0
    stats.append({
        "key": "field_service",
        "label": "Service Orders",
        "value": f"{open_orders:,}",
        "subtext": "Open orders",
        "icon": "truck",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/operations/field-service",
    })

    # Warehouses (active = not disabled)
    warehouse_count = db.query(func.count(Warehouse.id)).filter(
        Warehouse.disabled == False,
        Warehouse.is_deleted == False,
    ).scalar() or 0
    stats.append({
        "key": "inventory",
        "label": "Warehouses",
        "value": f"{warehouse_count:,}",
        "subtext": "Active locations",
        "icon": "package",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/operations/inventory",
    })

    # Active Assets (in service = submitted, partially/fully depreciated)
    active_assets = db.query(func.count(Asset.id)).filter(
        Asset.status.in_([
            AssetStatus.SUBMITTED,
            AssetStatus.PARTIALLY_DEPRECIATED,
            AssetStatus.FULLY_DEPRECIATED,
        ])
    ).scalar() or 0
    stats.append({
        "key": "assets",
        "label": "Active Assets",
        "value": f"{active_assets:,}",
        "subtext": "In service",
        "icon": "box",
        "icon_bg": "bg-purple-50",
        "icon_color": "text-purple-600",
        "href": "/operations/assets",
    })

    # Vehicles
    vehicle_count = db.query(func.count(Vehicle.id)).filter(
        Vehicle.is_active == True
    ).scalar() or 0
    stats.append({
        "key": "vehicles",
        "label": "Fleet Vehicles",
        "value": f"{vehicle_count:,}",
        "subtext": "Active fleet",
        "icon": "truck",
        "icon_bg": "bg-cyan-50",
        "icon_color": "text-cyan-600",
        "href": "/operations/vehicles",
    })

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

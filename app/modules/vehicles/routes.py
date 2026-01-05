"""
Vehicles module web routes.

Provides SSR pages for fleet management.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from typing import Optional

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.services.fleet import VehicleService, VehicleFilters, VehicleNotFoundError
from app.services.types import PaginationParams

router = APIRouter(prefix="/vehicles", tags=["vehicles-web"])
templates = get_template_env()

RequireVehiclesRead = Depends(require_scope("vehicles:read"))
RequireVehiclesWrite = Depends(require_scope("vehicles:write"))


@router.get("", response_class=HTMLResponse, dependencies=[RequireVehiclesRead])
async def vehicles_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by active status"),
    fuel_type: Optional[str] = Query(None, description="Filter by fuel type"),
    make: Optional[str] = Query(None, description="Filter by make"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("license_plate", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Vehicles list page."""
    service = VehicleService(db)

    # Convert status filter to is_active boolean
    is_active: Optional[bool] = None
    if status == "active":
        is_active = True
    elif status == "inactive":
        is_active = False

    filters = VehicleFilters(
        search=q,
        make=make,
        fuel_type=fuel_type,
        is_active=is_active,
        sort_by=sort,
        sort_order=dir,
    )
    pagination = PaginationParams(page=page, limit=per_page)

    result = service.list_vehicles(filters, pagination)
    vehicles = result.items
    total = result.total

    # Get distinct fuel types for filter dropdown
    fuel_types = service.get_distinct_fuel_types()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Fleet Management"
    context["vehicles"] = vehicles
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["fuel_type_filter"] = fuel_type or ""
    context["make_filter"] = make or ""
    context["sort"] = sort
    context["dir"] = dir
    context["fuel_types"] = fuel_types

    # Check if HTMX request
    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/vehicles/templates/partials/vehicles_table.html")
    else:
        template = templates.get_template("modules/vehicles/templates/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireVehiclesRead])
async def vehicles_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    fuel_type: Optional[str] = Query(None),
    make: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("license_plate"),
    dir: str = Query("asc"),
):
    """Vehicles table partial for HTMX."""
    return await vehicles_list(
        request, response, user, csrf_token, db,
        q, status, fuel_type, make, page, per_page, sort, dir
    )


@router.get("/{vehicle_id}", response_class=HTMLResponse, dependencies=[RequireVehiclesRead])
async def vehicle_detail(
    vehicle_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Vehicle detail page."""
    service = VehicleService(db)

    try:
        vehicle = service.get_vehicle(vehicle_id)
    except VehicleNotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Vehicle not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Vehicle: {vehicle.license_plate}"
    context["vehicle"] = vehicle

    template = templates.get_template("modules/vehicles/templates/pages/detail.html")
    return HTMLResponse(template.render(context))

"""
Asset Management Routes.

Handles SSR pages for fixed assets, categories, and depreciation tracking.
Business logic is delegated to services in app/services/assets/.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.web.dependencies import SessionUser, CSRFToken, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.auth import Principal
from app.models.asset import AssetStatus
from app.services.assets import (
    AssetService,
    AssetCategoryService,
    DepreciationService,
    AssetCapitalizationService,
    AssetDisposalService,
    AssetMaintenanceService,
    AssetFilters,
    CategoryFilters,
    DisposalData,
    DisposalType,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/assets", tags=["assets"])
templates = get_template_env()

RequireAssetsRead = Depends(require_scope("assets:read"))
RequireAssetsWrite = Depends(require_scope("assets:write"))

TEMPLATE_PATH = "modules/assets/templates"


# ============= SERVICE DEPENDENCY PROVIDERS =============

def get_asset_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:read")),
) -> AssetService:
    return AssetService(db, principal)


def get_category_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:read")),
) -> AssetCategoryService:
    return AssetCategoryService(db, principal)


def get_depreciation_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:read")),
) -> DepreciationService:
    return DepreciationService(db, principal)


def get_capitalization_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:read")),
) -> AssetCapitalizationService:
    return AssetCapitalizationService(db, principal)


def get_disposal_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:write")),
) -> AssetDisposalService:
    return AssetDisposalService(db, principal)


def get_maintenance_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("assets:read")),
) -> AssetMaintenanceService:
    return AssetMaintenanceService(db, principal)


# ============= ASSETS LIST =============

@router.get("", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def assets_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: AssetService = Depends(get_asset_service),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("asset_name"),
    dir: str = Query("asc"),
):
    """Assets list page."""
    # Parse status if provided
    status_enum = None
    if status:
        try:
            status_enum = AssetStatus(status)
        except ValueError:
            pass

    # Build filters
    filters = AssetFilters(
        search=q,
        status=status_enum,
        category=category,
        location=location,
        include_disposed=False,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get assets via service
    result = service.list_assets(filters, pagination)

    # Get filter options via service
    filter_options = service.get_filter_options()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Assets"
    context["assets"] = result.items
    context["q"] = q
    context["status"] = status
    context["category"] = category
    context["location"] = location
    context["sort"] = sort
    context["dir"] = dir
    context["category_options"] = filter_options["categories"]
    context["location_options"] = filter_options["locations"]
    context["pagination"] = {
        "page": page,
        "per_page": per_page,
        "total": result.total,
        "total_pages": (result.total + per_page - 1) // per_page,
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        template = templates.get_template(f"{TEMPLATE_PATH}/partials/assets_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def assets_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: AssetService = Depends(get_asset_service),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("asset_name"),
    dir: str = Query("asc"),
):
    """Assets table partial for HTMX."""
    return await assets_list(
        request, response, user, csrf_token, service,
        q, status, category, location, page, per_page, sort, dir
    )


@router.get("/categories", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def categories_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: AssetCategoryService = Depends(get_category_service),
):
    """Asset categories list page."""
    result = service.list_categories(
        filters=CategoryFilters(),
        pagination=PaginationParams(offset=0, limit=1000),
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Asset Categories"
    context["categories"] = result.items

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/categories_list.html")
    return HTMLResponse(template.render(context))


@router.get("/depreciation", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def depreciation_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    depreciation_service: DepreciationService = Depends(get_depreciation_service),
    maintenance_service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Depreciation dashboard page."""
    # Get pending depreciation entries
    pending = depreciation_service.get_pending_depreciation()
    total_pending = sum(p.depreciation_amount for p in pending)

    # Get alert summary
    alert_summary = maintenance_service.get_alert_summary(days_ahead=30)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Depreciation"
    context["pending_entries"] = pending
    context["total_pending_amount"] = total_pending
    context["alert_summary"] = alert_summary

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/depreciation.html")
    return HTMLResponse(template.render(context))


@router.get("/maintenance", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def maintenance_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Maintenance dashboard page."""
    # Get assets requiring maintenance
    assets_needing_maintenance = service.get_assets_requiring_maintenance()
    assets_in_maintenance = service.get_assets_in_maintenance()

    # Get expiring warranties and insurance
    expiring_warranties = service.get_expiring_warranties(days_ahead=30)
    expiring_insurance = service.get_expiring_insurance(days_ahead=30)

    # Get alert summary
    alert_summary = service.get_alert_summary(days_ahead=30)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Asset Maintenance"
    context["assets_needing_maintenance"] = assets_needing_maintenance
    context["assets_in_maintenance"] = assets_in_maintenance
    context["expiring_warranties"] = expiring_warranties
    context["expiring_insurance"] = expiring_insurance
    context["alert_summary"] = alert_summary

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/maintenance.html")
    return HTMLResponse(template.render(context))


@router.get("/cwip", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def cwip_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: AssetCapitalizationService = Depends(get_capitalization_service),
):
    """Capital Work in Progress dashboard."""
    # Get CWIP assets
    cwip_assets = service.get_cwip_assets()
    cwip_summary = service.get_cwip_summary()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Capital Work in Progress"
    context["cwip_assets"] = cwip_assets
    context["cwip_summary"] = cwip_summary

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/cwip.html")
    return HTMLResponse(template.render(context))


@router.get("/{asset_id:int}", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def asset_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
    depreciation_service: DepreciationService = Depends(get_depreciation_service),
):
    """Asset detail page."""
    try:
        asset = service.get_asset(asset_id, include_schedules=True)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Asset not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get pending depreciation for this asset
    pending_depreciation = depreciation_service.get_pending_depreciation_for_asset(asset_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = asset.asset_name
    context["asset"] = asset
    context["depreciation_schedules"] = sorted(
        asset.depreciation_schedules,
        key=lambda x: x.schedule_date or x.id
    )
    context["finance_books"] = asset.finance_books
    context["pending_depreciation"] = pending_depreciation
    context["pending_depreciation_count"] = len(pending_depreciation)
    context["pending_depreciation_amount"] = sum(p.depreciation_amount for p in pending_depreciation)

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/categories/{category_id:int}", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def category_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    category_id: int,
    service: AssetCategoryService = Depends(get_category_service),
):
    """Asset category detail page."""
    try:
        category = service.get_category(category_id)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Asset category not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get assets in this category via service
    assets, asset_count = service.get_assets_in_category(
        category.asset_category_name, limit=50, offset=0
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = category.asset_category_name
    context["category"] = category
    context["finance_books"] = category.finance_books
    context["assets"] = assets
    context["asset_count"] = asset_count

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/category_detail.html")
    return HTMLResponse(template.render(context))

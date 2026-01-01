"""
Asset Management Routes.

Handles SSR pages for fixed assets, categories, and depreciation tracking.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.database import get_db
from app.web.dependencies import SessionUser, CSRFToken, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.models.asset import Asset, AssetCategory, AssetStatus

router = APIRouter(prefix="/assets", tags=["assets"])
templates = get_template_env()

RequireAssetsRead = Depends(require_scope("assets:read"))
RequireAssetsWrite = Depends(require_scope("assets:write"))

TEMPLATE_PATH = "modules/assets/templates"


# ============= ASSETS LIST =============

@router.get("", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def assets_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
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
    query = db.query(Asset)

    # Search
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Asset.asset_name.ilike(search),
                Asset.item_code.ilike(search),
                Asset.serial_no.ilike(search),
                Asset.location.ilike(search),
            )
        )

    # Filters
    if status:
        try:
            query = query.filter(Asset.status == AssetStatus(status))
        except ValueError:
            pass
    if category:
        query = query.filter(Asset.asset_category == category)
    if location:
        query = query.filter(Asset.location == location)

    # Sorting
    sort_col = getattr(Asset, sort, Asset.asset_name)
    query = query.order_by(desc(sort_col) if dir == "desc" else asc(sort_col))

    # Pagination
    total = query.count()
    assets = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get filter options
    categories = db.query(Asset.asset_category).distinct().filter(Asset.asset_category.isnot(None)).all()
    locations = db.query(Asset.location).distinct().filter(Asset.location.isnot(None)).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Assets"
    context["assets"] = assets
    context["q"] = q
    context["status"] = status
    context["category"] = category
    context["location"] = location
    context["sort"] = sort
    context["dir"] = dir
    context["category_options"] = [{"value": c[0], "label": c[0]} for c in categories if c[0]]
    context["location_options"] = [{"value": l[0], "label": l[0]} for l in locations if l[0]]
    context["pagination"] = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
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
    db: Session = Depends(get_db),
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
        request, response, user, csrf_token, db,
        q, status, category, location, page, per_page, sort, dir
    )


@router.get("/categories", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def categories_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
):
    """Asset categories list page."""
    categories = db.query(AssetCategory).order_by(AssetCategory.asset_category_name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Asset Categories"
    context["categories"] = categories

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/categories_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{asset_id:int}", response_class=HTMLResponse, dependencies=[RequireAssetsRead])
async def asset_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Asset detail page."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Asset not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = asset.asset_name
    context["asset"] = asset
    context["depreciation_schedules"] = asset.depreciation_schedules
    context["finance_books"] = asset.finance_books

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/detail.html")
    return HTMLResponse(template.render(context))

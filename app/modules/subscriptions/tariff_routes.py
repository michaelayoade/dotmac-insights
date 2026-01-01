"""
Tariff Routes - Tariff/Plan Management with SSR + HTMX.

Permission Requirements:
- subscriptions:read - View tariffs
- subscriptions:write - Update tariffs (non-Splynx only)
"""
from __future__ import annotations

from typing import Optional, Any, cast
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.sql import ColumnElement

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.tariff import Tariff, TariffType
from app.models.subscription import Subscription
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Permission dependencies
RequireSubscriptionsRead = Depends(require_scope("subscriptions:read"))
RequireSubscriptionsWrite = Depends(require_scope("subscriptions:write"))

router = APIRouter(prefix="/subscriptions/tariffs", tags=["tariffs"])
templates = get_template_env()


def get_tariff_type_options():
    """Get tariff type options for filter dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in TariffType
    ]


def format_speed(speed: Optional[int]) -> str:
    """Format speed in Mbps or Gbps."""
    if not speed:
        return "-"
    if speed >= 1000:
        return f"{speed / 1000:.0f} Gbps"
    return f"{speed} Mbps"


# =============================================================================
# TARIFF LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def tariffs_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    tariff_type: Optional[str] = Query(None, description="Filter by tariff type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("title", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Tariffs list page."""
    query = db.query(Tariff).filter(Tariff.enabled == True)

    # Search
    if q:
        search_filter = or_(
            Tariff.title.ilike(f"%{q}%"),
            Tariff.service_name.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if tariff_type:
        try:
            type_enum = TariffType(tariff_type)
            query = query.filter(Tariff.tariff_type == type_enum)
        except ValueError:
            pass

    # Count total
    total = query.count()

    # Sort
    sort_mapping = {
        "title": Tariff.title,
        "price": Tariff.price,
        "tariff_type": Tariff.tariff_type,
        "created_at": Tariff.created_at,
    }
    order_column: ColumnElement[Any] = cast(ColumnElement[Any], sort_mapping.get(sort, Tariff.title))
    if dir == "desc":
        order_column = order_column.desc()
    query = query.order_by(order_column)

    # Paginate
    offset = (page - 1) * per_page
    tariffs = query.offset(offset).limit(per_page).all()

    # Get subscription counts per tariff
    subscription_counts = {}
    for tariff in tariffs:
        count = db.query(func.count(Subscription.id)).filter(
            Subscription.tariff_id == tariff.id
        ).scalar() or 0
        subscription_counts[tariff.id] = count

    # Stats
    total_tariffs = db.query(Tariff).filter(Tariff.enabled == True).count()
    internet_tariffs = db.query(Tariff).filter(
        Tariff.enabled == True,
        Tariff.tariff_type == TariffType.INTERNET
    ).count()

    stats = {
        "total": total_tariffs,
        "internet": internet_tariffs,
        "recurring": db.query(Tariff).filter(
            Tariff.enabled == True,
            Tariff.tariff_type == TariffType.RECURRING
        ).count(),
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["tariffs"] = tariffs
    context["subscription_counts"] = subscription_counts
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_tariff_type"] = tariff_type
    context["tariff_type_options"] = get_tariff_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["format_speed"] = format_speed

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/subscriptions/templates/partials/tariffs_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Tariffs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": "Tariffs"},
    ])

    template = templates.get_template("modules/subscriptions/templates/pages/tariffs_list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def tariffs_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    tariff_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("title"),
    dir: str = Query("asc"),
):
    """Tariffs table partial for HTMX updates."""
    return await tariffs_list(
        request, response, user, csrf_token, db,
        q, tariff_type, page, per_page, sort, dir
    )


# =============================================================================
# TARIFF DETAIL
# =============================================================================

@router.get("/{tariff_id}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def tariff_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tariff_id: int,
):
    """Tariff detail page with analytics."""
    tariff = db.query(Tariff).filter(Tariff.id == tariff_id).first()

    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    # Get subscriptions using this tariff
    subscription_count = db.query(func.count(Subscription.id)).filter(
        Subscription.tariff_id == tariff.id
    ).scalar() or 0

    # Active subscriptions with this tariff
    active_count = db.query(func.count(Subscription.id)).filter(
        Subscription.tariff_id == tariff.id,
        Subscription.status == "active"
    ).scalar() or 0

    # Revenue from this tariff (active subscriptions)
    from app.models.subscription import SubscriptionStatus
    monthly_revenue = db.query(func.sum(Subscription.price)).filter(
        Subscription.tariff_id == tariff.id,
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "monthly"
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = tariff.title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": "Tariffs", "href": "/subscriptions/tariffs"},
        {"label": tariff.title},
    ])
    context["tariff"] = tariff
    context["subscription_count"] = subscription_count
    context["active_count"] = active_count
    context["monthly_revenue"] = float(monthly_revenue)
    context["format_speed"] = format_speed

    template = templates.get_template("modules/subscriptions/templates/pages/tariff_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TARIFF TOGGLE
# =============================================================================

@router.patch("/{tariff_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def tariff_toggle(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    tariff_id: int,
):
    """Toggle tariff enabled/disabled status."""
    tariff = db.query(Tariff).filter(Tariff.id == tariff_id).first()

    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    tariff.enabled = not tariff.enabled
    db.commit()

    status = "enabled" if tariff.enabled else "disabled"

    if is_htmx_request(request):
        htmx_toast(response, f"Tariff '{tariff.title}' {status}", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/tariffs/{tariff.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Tariff '{tariff.title}' {status}", "success")
    return RedirectResponse(url=f"/subscriptions/tariffs/{tariff.id}", status_code=303)

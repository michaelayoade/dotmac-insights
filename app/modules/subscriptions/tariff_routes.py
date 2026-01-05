"""
Tariff Routes - Tariff/Plan Management with SSR + HTMX.

Permission Requirements:
- subscriptions:read - View tariffs
- subscriptions:write - Update tariffs (non-Splynx only)
"""
from __future__ import annotations

from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.tariff import Tariff, TariffType
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.errors import NotFoundError
from app.services.subscriptions import TariffService
from app.services.types import PaginationParams
from app.services.subscriptions.web_services import TariffWebService

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
    enabled_only: bool = Query(True, description="Show only enabled tariffs"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("title", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Tariffs list page."""
    svc = TariffService(db, principal=user)
    web_svc = TariffWebService(db, svc)

    # Get tariffs using service
    result = svc.list_tariffs(
        tariff_type=tariff_type,
        enabled_only=enabled_only,
        search=q,
        pagination=PaginationParams(page=page, per_page=per_page),
    )

    # Get subscription counts per tariff
    subscription_counts = {}
    for tariff in result.items:
        subscription_counts[tariff.id] = svc.get_subscription_count(tariff.id)

    # Get overview stats
    stats = svc.get_overview_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["tariffs"] = result.items
    context["subscription_counts"] = subscription_counts
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_tariff_type"] = tariff_type
    context["enabled_only"] = enabled_only
    context["tariff_type_options"] = get_tariff_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)
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
    enabled_only: bool = Query(True),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("title"),
    dir: str = Query("asc"),
):
    """Tariffs table partial for HTMX updates."""
    return await tariffs_list(
        request, response, user, csrf_token, db,
        q, tariff_type, enabled_only, page, per_page, sort, dir
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
    svc = TariffService(db, principal=user)

    try:
        tariff = svc.get_tariff(tariff_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tariff not found")

    # Get tariff stats using service
    tariff_stats = svc.get_tariff_stats(tariff_id)

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
    context["subscription_count"] = tariff_stats.get("total_subscriptions", 0)
    context["active_count"] = tariff_stats.get("active_subscriptions", 0)
    context["monthly_revenue"] = float(tariff_stats.get("monthly_revenue", Decimal("0")))
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
    svc = TariffService(db, principal=user)

    try:
        tariff = svc.get_tariff(tariff_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tariff not found")

    # Toggle status
    tariff = web_svc.toggle_enabled(tariff_id)

    status = "enabled" if tariff.enabled else "disabled"

    if is_htmx_request(request):
        htmx_toast(response, f"Tariff '{tariff.title}' {status}", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/tariffs/{tariff.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Tariff '{tariff.title}' {status}", "success")
    return RedirectResponse(url=f"/subscriptions/tariffs/{tariff.id}", status_code=303)

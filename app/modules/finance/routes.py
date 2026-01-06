"""
Finance Module Routes - Dashboard, Analytics & Insights with SSR + HTMX.

Permission Requirements:
- analytics:read - View finance pages and reports

Routes are thin wrappers around FinanceService.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request
from app.services.finance import FinanceService
from app.services.errors import ValidationError

# Permission dependencies
RequireFinanceRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/finance", tags=["finance"])
templates = get_template_env()


def _format_currency(value: float, symbol: str = "₦") -> str:
    """Format a number as currency."""
    if value >= 1_000_000:
        return f"{symbol}{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{symbol}{value / 1_000:.1f}K"
    return f"{symbol}{value:,.0f}"


# =============================================================================
# DASHBOARD
# =============================================================================


@router.get("", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def finance_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Finance dashboard - landing page with KPIs."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Finance Dashboard"

    try:
        service = FinanceService(db)
        dashboard = service.get_dashboard(currency=currency)
        aging = service.get_invoice_aging_analysis(currency=currency)

        # Build stats cards
        stats = [
            {
                "key": "mrr",
                "label": "MRR",
                "value": _format_currency(dashboard.revenue.mrr),
                "subtext": f"ARR: {_format_currency(dashboard.revenue.arr)}",
                "icon": "repeat",
                "icon_bg": "bg-blue-50",
                "icon_color": "text-blue-600",
            },
            {
                "key": "subscriptions",
                "label": "Active Subscriptions",
                "value": f"{dashboard.revenue.active_subscriptions:,}",
                "subtext": "Recurring revenue",
                "icon": "users",
                "icon_bg": "bg-green-50",
                "icon_color": "text-green-600",
            },
            {
                "key": "collections",
                "label": "Collections (30d)",
                "value": _format_currency(dashboard.collections.collections_30d),
                "subtext": f"{dashboard.collections.collection_rate}% rate",
                "icon": "credit-card",
                "icon_bg": "bg-emerald-50",
                "icon_color": "text-emerald-600",
            },
            {
                "key": "outstanding",
                "label": "Outstanding",
                "value": _format_currency(dashboard.collections.outstanding_total),
                "subtext": f"{_format_currency(dashboard.collections.outstanding_overdue)} overdue",
                "icon": "clock",
                "icon_bg": "bg-amber-50",
                "icon_color": "text-amber-600",
            },
            {
                "key": "dso",
                "label": "DSO",
                "value": f"{dashboard.collections.dso:.0f} days",
                "subtext": "Days Sales Outstanding",
                "icon": "calendar",
                "icon_bg": "bg-purple-50",
                "icon_color": "text-purple-600",
            },
            {
                "key": "at_risk",
                "label": "At Risk",
                "value": _format_currency(aging.at_risk),
                "subtext": f"{aging.at_risk_percent:.1f}% of outstanding",
                "icon": "alert-triangle",
                "icon_bg": "bg-red-50",
                "icon_color": "text-red-600",
            },
        ]

        context["stats"] = stats
        context["dashboard"] = dashboard
        context["aging"] = aging
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["stats"] = []
        context["dashboard"] = None
        context["aging"] = None
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance"},
        ])

    template = templates.get_template("modules/finance/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ANALYTICS
# =============================================================================


@router.get("/analytics", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def analytics_overview(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """Analytics overview page - redirects to collections."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/finance/analytics/collections", status_code=302)


@router.get("/analytics/collections", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def analytics_collections(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Collections analytics page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Collections Analytics"

    try:
        service = FinanceService(db)
        result = service.get_collections_analytics(currency=currency)

        context["collections"] = result
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["collections"] = None
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Analytics"},
            {"label": "Collections"},
        ])

    template = templates.get_template("modules/finance/templates/pages/collections.html")
    return HTMLResponse(template.render(context))


@router.get("/analytics/aging", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def analytics_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Invoice aging report page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Invoice Aging Report"

    try:
        service = FinanceService(db)
        result = service.get_invoice_aging_analysis(currency=currency)

        context["aging"] = result
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["aging"] = None
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Analytics"},
            {"label": "Aging Report"},
        ])

    template = templates.get_template("modules/finance/templates/pages/aging.html")
    return HTMLResponse(template.render(context))


@router.get("/analytics/revenue", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def analytics_revenue(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    interval: str = Query("month", description="month or week"),
    months: int = Query(12, description="Number of months"),
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Revenue trends page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Revenue Trends"

    try:
        service = FinanceService(db)
        result = service.get_revenue_trend(
            interval=interval,
            months=months,
            currency=currency,
        )

        context["revenue_trend"] = result
        context["interval"] = interval
        context["months"] = months
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["revenue_trend"] = None
        context["interval"] = interval
        context["months"] = months
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Analytics"},
            {"label": "Revenue Trends"},
        ])

    template = templates.get_template("modules/finance/templates/pages/revenue.html")
    return HTMLResponse(template.render(context))


@router.get("/analytics/currency", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def analytics_currency(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Multi-currency breakdown page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Revenue by Currency"

    service = FinanceService(db)
    result = service.get_revenue_by_currency()

    context["by_currency"] = result
    context["error"] = None

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Analytics"},
            {"label": "By Currency"},
        ])

    template = templates.get_template("modules/finance/templates/pages/currency.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# INSIGHTS
# =============================================================================


@router.get("/insights", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def insights_overview(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """Insights overview page - redirects to behavior."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/finance/insights/behavior", status_code=302)


@router.get("/insights/behavior", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def insights_behavior(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Payment behavior insights page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Payment Behavior"

    try:
        service = FinanceService(db)
        result = service.analyze_payment_behavior(currency=currency)

        context["behavior"] = result
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["behavior"] = None
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Insights"},
            {"label": "Payment Behavior"},
        ])

    template = templates.get_template("modules/finance/templates/pages/behavior.html")
    return HTMLResponse(template.render(context))


@router.get("/insights/forecasts", response_class=HTMLResponse, dependencies=[RequireFinanceRead])
async def insights_forecasts(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    currency: Optional[str] = Query(None, description="Currency filter"),
):
    """Revenue forecasts page."""
    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Revenue Forecasts"

    try:
        service = FinanceService(db)
        result = service.forecast_revenue(currency=currency)

        context["forecast"] = result
        context["currency"] = currency
        context["error"] = None

    except ValidationError as e:
        context["forecast"] = None
        context["currency"] = currency
        context["error"] = e.message

    if not is_htmx_request(request):
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/finance"},
            {"label": "Insights"},
            {"label": "Forecasts"},
        ])

    template = templates.get_template("modules/finance/templates/pages/forecasts.html")
    return HTMLResponse(template.render(context))

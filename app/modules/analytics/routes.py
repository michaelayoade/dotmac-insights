"""
Analytics Routes - SSR Dashboard and Reports.

Permission Requirements:
- analytics:read - View all analytics dashboards and reports
"""
from __future__ import annotations

from typing import Optional, Dict, Any, cast

from fastapi import APIRouter, Request, Response, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request
from app.auth import Principal

# Import analytics API implementations
from app.api.analytics import (
    _get_overview_impl,
    _get_dso_impl,
    get_invoice_aging,
    get_revenue_by_territory,
    get_customer_summary,
    get_support_metrics,
    get_expenses_by_category,
    get_sla_attainment,
    get_agent_productivity,
)
from app.api.insights import (
    get_data_completeness,
    get_customer_segments,
    get_customer_health,
    detect_anomalies,
)

# Permission dependencies
RequireAnalyticsRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = get_template_env()


# =============================================================================
# Main Dashboard
# =============================================================================


@router.get("", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def analytics_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period: int = Query(30, description="Days to analyze"),
):
    """Main analytics dashboard with overview stats from all domains."""
    # Fetch overview data
    overview = cast(Dict[str, Any], await _get_overview_impl(currency=None, db=db, principal=user))

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["overview"] = overview
    context["period"] = period

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/stats_grid.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/stats", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def analytics_stats_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period: int = Query(30),
):
    """HTMX endpoint for refreshing stats grid only."""
    overview = cast(Dict[str, Any], await _get_overview_impl(currency=None, db=db, principal=user))

    context = get_base_context(request, response, user, csrf_token)
    context["overview"] = overview
    context["period"] = period

    template = templates.get_template("modules/analytics/templates/partials/stats_grid.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Revenue Analytics
# =============================================================================


@router.get("/revenue", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def revenue_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    months: int = Query(12, le=24),
):
    """Revenue analytics page with MRR, DSO, trends, aging."""
    # Fetch data
    overview = cast(Dict[str, Any], await _get_overview_impl(currency=None, db=db, principal=user))
    dso = cast(Dict[str, Any], await _get_dso_impl(months=months, db=db, principal=user))
    aging = await get_invoice_aging(db=db)
    territories = await get_revenue_by_territory(months=months, db=db)

    context = get_base_context(request, response, user, csrf_token)
    context["revenue"] = overview.get("revenue", {})
    context["dso"] = dso
    context["aging"] = aging
    context["territories"] = territories
    context["months"] = months

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/revenue_metrics.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Revenue Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Revenue"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/revenue.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Customer Analytics
# =============================================================================


@router.get("/customers", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def customer_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Customer analytics with segments, health, churn risk."""
    # Fetch data
    customers = await get_customer_summary(db=db, principal=user)
    segments = await get_customer_segments(db=db, principal=user)
    health = await get_customer_health(db=db, principal=user)

    context = get_base_context(request, response, user, csrf_token)
    context["customers"] = customers
    context["segments"] = segments
    context["health"] = health

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/customer_segments.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Customers"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/customers.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Support Analytics
# =============================================================================


@router.get("/support", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def support_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    days: int = Query(30, le=90),
):
    """Support analytics with SLA, metrics, agent productivity."""
    # Fetch data
    metrics = await get_support_metrics(days=days, db=db)
    sla = cast(Dict[str, Any], await get_sla_attainment(days=days, db=db, principal=user))
    agents = await get_agent_productivity(days=days, db=db)

    context = get_base_context(request, response, user, csrf_token)
    context["metrics"] = metrics
    context["sla"] = sla
    context["agents"] = agents
    context["days"] = days

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/support_metrics.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Support"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/support.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# HR Analytics
# =============================================================================


@router.get("/hr", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def hr_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """HR analytics with leave, attendance, payroll, recruitment."""
    # Import HR analytics
    from app.api.hr.analytics import (
        hr_dashboard,
        leave_trend,
        payroll_trend,
        recruitment_funnel,
    )

    # Fetch data
    dashboard = await hr_dashboard(db=db)
    leave = await leave_trend(months=6, db=db)
    payroll = await payroll_trend(db=db)
    recruitment = await recruitment_funnel(db=db)

    context = get_base_context(request, response, user, csrf_token)
    context["dashboard"] = dashboard
    context["leave_trend"] = leave
    context["payroll_trend"] = payroll
    context["recruitment"] = recruitment

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/hr_dashboard.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "HR Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "HR"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/hr.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Operations Analytics
# =============================================================================


@router.get("/operations", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def operations_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    months: int = Query(12, le=24),
):
    """Operations analytics: Field Service, Expenses."""
    # Fetch expenses data
    expenses = await get_expenses_by_category(months=months, db=db)

    context = get_base_context(request, response, user, csrf_token)
    context["expenses"] = expenses
    context["months"] = months

    # Try to get field service data if available
    try:
        from app.api.field_service.analytics import get_analytics_dashboard
        fs_dashboard = await get_analytics_dashboard(db=db)
        context["field_service"] = fs_dashboard
    except Exception:
        context["field_service"] = None

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/operations_metrics.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Operations Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Operations"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/operations.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Data Insights
# =============================================================================


@router.get("/insights", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def insights_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Data quality, anomalies, and actionable insights."""
    # Fetch data
    completeness = await get_data_completeness(db=db, principal=user)
    anomalies = await detect_anomalies(db=db, principal=user)

    context = get_base_context(request, response, user, csrf_token)
    context["completeness"] = completeness
    context["anomalies"] = anomalies

    if is_htmx_request(request):
        template = templates.get_template("modules/analytics/templates/partials/data_quality.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Insights"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Insights"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/insights.html")
    return HTMLResponse(template.render(context))

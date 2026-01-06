"""
Analytics Routes - SSR Dashboard and Reports.

Permission Requirements:
- analytics:read - View all analytics dashboards and reports
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, cast

from fastapi import APIRouter, Request, Response, Query, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request
from app.services.analytics import AnalyticsService
from app.services.field_service import FieldServiceAnalyticsService, AnalyticsFilters
from app.services.hr import HRAnalyticsService
from app.services.insights import InsightsService

# Permission dependencies
RequireAnalyticsRead = Depends(require_scope("analytics:read"))

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = get_template_env()


def _parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    """Parse a date string (YYYY-MM-DD) into a UTC datetime."""
    if not value:
        return None
    try:
        base = datetime.fromisoformat(value)
        if end_of_day:
            base = base.replace(hour=23, minute=59, second=59)
        else:
            base = base.replace(hour=0, minute=0, second=0)
        return base.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _previous_period(start_dt: datetime, end_dt: datetime) -> tuple[datetime, datetime]:
    """Calculate the previous period range of equal length."""
    delta = end_dt - start_dt
    prev_end = start_dt - timedelta(seconds=1)
    prev_start = prev_end - delta
    return prev_start, prev_end


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
    analytics = AnalyticsService(db, principal=user)
    overview = cast(Dict[str, Any], await analytics.get_overview(currency=None))

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
    analytics = AnalyticsService(db, principal=user)
    overview = cast(Dict[str, Any], await analytics.get_overview(currency=None))

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
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Revenue analytics page with MRR, DSO, trends, aging."""
    # Fetch data
    analytics = AnalyticsService(db, principal=user)
    overview = cast(Dict[str, Any], await analytics.get_overview(currency=None))
    dso = cast(Dict[str, Any], await analytics.get_dso(months=months, start_date=start_date, end_date=end_date))
    aging = await analytics.get_invoice_aging()
    territories = await analytics.get_revenue_by_territory(months=months)
    revenue_trend = await analytics.get_revenue_trend(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )
    plans = await analytics.get_customers_by_plan()
    cohorts = await analytics.get_revenue_cohort()

    context = get_base_context(request, response, user, csrf_token)
    context["revenue"] = overview.get("revenue", {})
    context["dso"] = dso
    context["aging"] = aging
    context["territories"] = territories
    context["revenue_trend"] = revenue_trend
    context["plans"] = plans
    context["cohorts"] = cohorts
    context["months"] = months
    context["start_date"] = start_date
    context["end_date"] = end_date

    comparison = None
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date, end_of_day=True)
    if parsed_start and parsed_end:
        prev_start, prev_end = _previous_period(parsed_start, parsed_end)
        current_total = analytics.get_revenue_total(parsed_start, parsed_end)
        previous_total = analytics.get_revenue_total(prev_start, prev_end)
        comparison = {
            "current": current_total,
            "previous": previous_total,
            "period": {
                "start": parsed_start.date().isoformat(),
                "end": parsed_end.date().isoformat(),
            },
        }
    context["comparison"] = comparison

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
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Support analytics with SLA, metrics, agent productivity."""
    # Fetch data
    analytics = AnalyticsService(db, principal=user)
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date, end_of_day=True)
    metrics = await analytics.get_support_metrics(
        days=days,
        start_date=parsed_start,
        end_date=parsed_end,
    )
    range_days = days
    if parsed_start and parsed_end:
        range_days = max((parsed_end - parsed_start).days, 1)
    sla = cast(Dict[str, Any], await analytics.get_sla_attainment(days=range_days))
    agents = await analytics.get_agent_productivity(days=range_days)
    ticket_types = await analytics.get_tickets_by_type(days=range_days)

    context = get_base_context(request, response, user, csrf_token)
    context["metrics"] = metrics
    context["sla"] = sla
    context["agents"] = agents
    context["ticket_types"] = ticket_types
    context["days"] = days
    context["start_date"] = start_date
    context["end_date"] = end_date

    comparison = None
    if parsed_start and parsed_end:
        prev_start, prev_end = _previous_period(parsed_start, parsed_end)
        current_total = analytics.get_support_total(parsed_start, parsed_end)
        previous_total = analytics.get_support_total(prev_start, prev_end)
        comparison = {
            "current": current_total,
            "previous": previous_total,
            "period": {
                "start": parsed_start.date().isoformat(),
                "end": parsed_end.date().isoformat(),
            },
        }
    context["comparison"] = comparison

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

    hr_service = HRAnalyticsService(db, principal=user)

    # Fetch data
    dashboard = await hr_dashboard(db=db)
    leave = await leave_trend(months=6, db=db)
    payroll = await payroll_trend(db=db)
    recruitment = await recruitment_funnel(db=db)
    workforce = hr_service.get_workforce_analytics()
    turnover = hr_service.get_turnover_analytics()

    context = get_base_context(request, response, user, csrf_token)
    context["dashboard"] = dashboard
    context["leave_trend"] = leave
    context["payroll_trend"] = payroll
    context["recruitment"] = recruitment
    context["workforce"] = workforce
    context["turnover"] = turnover

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
# Customer Analytics
# =============================================================================


@router.get("/customers", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def customer_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    months: int = Query(12, le=24),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Customer analytics with summary stats, segments, and health indicators."""
    analytics = AnalyticsService(db, principal=user)
    insights = InsightsService(db, principal=user)

    customers = await analytics.get_customer_summary()
    segments = insights.get_customer_segments()
    health = insights.get_customer_health()
    churn = await analytics.get_churn_trend(months=months, start_date=start_date, end_date=end_date)

    segments_context = {
        "by_status": {
            item["status"]: {"count": item["count"], "mrr": item.get("mrr", 0)}
            for item in segments.by_status
        },
        "by_type": {
            item["type"]: {"count": item["count"], "mrr": item.get("mrr", 0)}
            for item in segments.by_type
        },
        "by_tenure": segments.by_tenure,
        "by_mrr_tier": segments.by_mrr_tier,
        "by_city": segments.by_city,
        "by_pop": segments.by_pop,
    }

    health_context = {
        "overdue_customers": health.payment_behavior.customers_with_overdue,
        "overdue_percent": health.payment_behavior.overdue_percent,
        "high_support_customers": health.support_intensity.high_support_customers,
        "recent_cancellations": health.churn_indicators.recently_cancelled_30d,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["customers"] = customers
    context["segments"] = segments_context
    context["health"] = health_context
    context["churn"] = churn
    context["months"] = months
    context["start_date"] = start_date
    context["end_date"] = end_date

    comparison = None
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date, end_of_day=True)
    if parsed_start and parsed_end:
        prev_start, prev_end = _previous_period(parsed_start, parsed_end)
        current_growth = analytics.get_customer_growth(parsed_start, parsed_end)
        previous_growth = analytics.get_customer_growth(prev_start, prev_end)
        comparison = {
            "current": current_growth,
            "previous": previous_growth,
            "period": {
                "start": parsed_start.date().isoformat(),
                "end": parsed_end.date().isoformat(),
            },
        }
    context["comparison"] = comparison

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Customers"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/customers.html")
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
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Operations analytics for field service and expense performance."""
    analytics = AnalyticsService(db, principal=user)
    field_service_service = FieldServiceAnalyticsService(db, principal=user)

    if start_date and end_date:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date, end_of_day=True)
        if parsed_start and parsed_end:
            start_dt = parsed_start.date()
            end_dt = parsed_end.date()
        else:
            end_dt = datetime.now(timezone.utc).date()
            start_dt = (datetime.now(timezone.utc) - timedelta(days=months * 30)).date()
    else:
        end_dt = datetime.now(timezone.utc).date()
        start_dt = (datetime.now(timezone.utc) - timedelta(days=months * 30)).date()
    field_filters = AnalyticsFilters(start_date=start_dt, end_date=end_dt)
    field_metrics = field_service_service.get_dashboard_metrics(field_filters)
    order_breakdown = field_service_service.get_order_type_breakdown(field_filters)

    field_service = {
        "completion_rate": field_metrics.completion_rate,
        "avg_rating": float(field_metrics.avg_customer_rating or 0),
        "avg_response_time": float(field_metrics.avg_completion_time_hours or 0),
        "total_revenue": float(field_metrics.total_revenue or 0),
    }

    expenses = await analytics.get_expenses_by_category(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )
    cost_centers = await analytics.get_expenses_by_cost_center(
        months=months,
        start_date=start_date,
        end_date=end_date,
    )

    context = get_base_context(request, response, user, csrf_token)
    context["field_service"] = field_service
    context["order_breakdown"] = order_breakdown
    context["expenses"] = expenses
    context["cost_centers"] = cost_centers
    context["months"] = months
    context["start_date"] = start_date
    context["end_date"] = end_date

    comparison = None
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date, end_of_day=True)
    if parsed_start and parsed_end:
        prev_start, prev_end = _previous_period(parsed_start, parsed_end)
        current_total = analytics.get_expense_total(parsed_start, parsed_end)
        previous_total = analytics.get_expense_total(prev_start, prev_end)
        comparison = {
            "current": current_total,
            "previous": previous_total,
            "period": {
                "start": parsed_start.date().isoformat(),
                "end": parsed_end.date().isoformat(),
            },
        }
    context["comparison"] = comparison

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Operations Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Operations"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/operations.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Insights Analytics
# =============================================================================


@router.get("/insights", response_class=HTMLResponse, dependencies=[RequireAnalyticsRead])
async def insights_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Data quality and anomaly detection insights."""
    insights = InsightsService(db, principal=user)

    completeness_result = insights.get_data_completeness()
    anomalies_result = insights.detect_anomalies()
    availability_result = insights.get_data_availability()

    completeness = {
        "overall_completeness": completeness_result.summary.get("overall_completeness_score", 0),
        "grade": completeness_result.summary.get("grade"),
        "customer": {
            field: data.percent for field, data in completeness_result.customer_fields.items()
        },
        "recommendations": [
            f"{rec.issue} — {rec.action}" for rec in completeness_result.recommendations
        ],
    }

    anomalies: Dict[str, List[Dict[str, Any]]] = {}
    for anomaly in anomalies_result.anomalies:
        anomalies.setdefault(anomaly.type, []).append({
            "severity": anomaly.severity,
            "description": anomaly.description,
        })
    for pattern in anomalies_result.patterns:
        anomalies.setdefault("patterns", []).append({
            "severity": "low",
            "description": pattern.description,
        })

    context = get_base_context(request, response, user, csrf_token)
    context["completeness"] = completeness
    context["anomalies"] = anomalies
    context["availability"] = availability_result

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Insights"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Analytics", "href": "/analytics"},
        {"label": "Insights"},
    ])

    template = templates.get_template("modules/analytics/templates/pages/insights.html")
    return HTMLResponse(template.render(context))

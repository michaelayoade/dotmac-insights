"""
CRM Module - Customer Relationship Management.

Routes:
- /crm - Dashboard (landing page)
- /crm/leads - Lead management
- /crm/opportunities - Pipeline & opportunities
- /crm/activities - Activities (calls, meetings, tasks)
- /crm/campaigns - Marketing campaigns
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.web.module_types import ModuleConfig

# Import models
from app.models.crm import Activity
from app.services.crm.dashboard_service import CRMDashboardService
from app.services.crm.analytics import CRMAnalyticsService
from app.services.crm.analytics_types import AnalyticsFilters

from .routes import router as crm_routes_router

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="customer",
    name="Customer",
    description="CRM, sales, and support workflows",
    icon="users",
    prefix="/crm",
    group="Customer",
    order=10,
    scopes=["crm:read", "sales:read", "support:read"],
    prefixes=[
        "/crm",
        "/sales",
        "/support",
        "/inbox",
        "/parties",
        "/accounting/invoices",
        "/accounting/credit-notes",
    ],
)

NAVIGATION = [
    {
        "section": "CRM",
        "href": "/crm",
        "icon": "users",
        "scope": "crm:read",
        "order": 10,
        "links": [
            {"label": "Leads", "href": "/crm/leads", "icon": "user-plus", "scope": "crm:read"},
            {"label": "Accounts", "href": "/crm/accounts", "icon": "building", "scope": "crm:read"},
            {"label": "Contacts", "href": "/crm/contacts", "icon": "user", "scope": "crm:read"},
            {"label": "Opportunities", "href": "/crm/opportunities", "icon": "target", "scope": "crm:read"},
            {"label": "Activities", "href": "/crm/activities", "icon": "calendar", "scope": "crm:read"},
        ],
    },
    {
        "section": "Sales",
        "href": "/sales",
        "icon": "shopping-cart",
        "scope": "sales:read",
        "order": 20,
        "links": [
            {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text", "scope": "sales:read"},
            {"label": "Orders", "href": "/sales/orders", "icon": "shopping-bag", "scope": "sales:read"},
            {"label": "Invoices", "href": "/accounting/invoices", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Credit Notes", "href": "/accounting/credit-notes", "icon": "file-minus", "scope": "accounting:read"},
        ],
    },
    {
        "section": "Support",
        "href": "/support",
        "icon": "life-buoy",
        "scope": "support:read",
        "order": 30,
        "links": [
            {"label": "Tickets", "href": "/support/tickets", "icon": "life-buoy", "scope": "support:read"},
            {"label": "Inbox", "href": "/inbox", "icon": "inbox", "scope": "support:read"},
            {"label": "Teams", "href": "/support/teams", "icon": "users", "scope": "support:read"},
            {"label": "Agents", "href": "/support/agents", "icon": "user", "scope": "support:read"},
            {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open", "scope": "support:read"},
            {"label": "SLA", "href": "/support/sla", "icon": "clock", "scope": "support:read"},
            {"label": "CSAT", "href": "/support/csat/analytics", "icon": "bar-chart", "scope": "support:read"},
            {"label": "Tags", "href": "/support/tags", "icon": "tag", "scope": "support:read"},
        ],
    },
]

# =============================================================================
# Period Filter Options
# =============================================================================

PERIOD_OPTIONS = [
    {"value": "day", "label": "Today"},
    {"value": "week", "label": "This Week"},
    {"value": "month", "label": "This Month"},
    {"value": "quarter", "label": "This Quarter"},
    {"value": "year", "label": "This Year"},
]


def get_period_dates(period: str) -> tuple[date, date]:
    """Get start and end dates for a period filter."""
    today = date.today()
    end_date = today

    if period == "day":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "month":
        start_date = date(today.year, today.month, 1)
    elif period == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start_date = date(today.year, quarter_month, 1)
    else:  # year
        start_date = date(today.year, 1, 1)

    return start_date, end_date


# =============================================================================
# Router
# =============================================================================

templates = get_template_env()

# Main CRM router
router = APIRouter(tags=["crm"])


@router.get("/crm", response_class=HTMLResponse)
async def crm_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period: str = Query("month", description="Time period filter"),
):
    """CRM dashboard - landing page for CRM module."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CRM Dashboard"
    context["now"] = datetime.utcnow()

    # Period filter
    context["period"] = period
    context["period_options"] = PERIOD_OPTIONS
    start_date, end_date = get_period_dates(period)

    # Initialize services
    dashboard_service = CRMDashboardService(db)
    analytics_service = CRMAnalyticsService(db)
    filters = AnalyticsFilters(start_date=start_date, end_date=end_date)

    # Get comprehensive analytics
    try:
        lead_funnel = analytics_service.get_lead_funnel(filters)
    except Exception:
        lead_funnel = None

    try:
        pipeline = analytics_service.get_pipeline_forecast(filters)
    except Exception:
        pipeline = None

    try:
        velocity = analytics_service.get_pipeline_velocity(filters)
    except Exception:
        velocity = None

    try:
        top_reps = analytics_service.get_rep_performance(filters, limit=5)
    except Exception:
        top_reps = []

    try:
        lead_sources = analytics_service.get_lead_sources_breakdown(filters)
    except Exception:
        lead_sources = []

    # Build stats from analytics
    stats = []
    today = date.today()

    # Active Leads
    lead_count = lead_funnel.total_leads if lead_funnel else dashboard_service.get_active_lead_count()
    stats.append({
        "key": "leads",
        "label": "Active Leads",
        "value": f"{lead_count:,}",
        "subtext": "In pipeline",
        "icon": "user-plus",
        "icon_bg": "bg-blue-50",
        "icon_color": "text-blue-600",
        "href": "/crm/leads",
    })

    # Qualified Leads (Hot + Warm)
    qualified = 0
    if lead_funnel and lead_funnel.by_qualification:
        qualified = lead_funnel.by_qualification.get("Hot", 0) + lead_funnel.by_qualification.get("Warm", 0)
    stats.append({
        "key": "qualified",
        "label": "Qualified Leads",
        "value": f"{qualified:,}",
        "subtext": "Hot & Warm",
        "icon": "star",
        "icon_bg": "bg-yellow-50",
        "icon_color": "text-yellow-600",
        "href": "/crm/leads?qualification=hot,warm",
    })

    # Open Opportunities
    open_opps = dashboard_service.get_open_opportunity_count()
    stats.append({
        "key": "opportunities",
        "label": "Open Opps",
        "value": f"{open_opps:,}",
        "subtext": "Active deals",
        "icon": "target",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/crm/opportunities",
    })

    # Pipeline Value (weighted)
    if pipeline:
        pipeline_value = pipeline.weighted_pipeline_value
        total_pipeline = pipeline.total_pipeline_value
    else:
        pipeline_value = dashboard_service.get_pipeline_value()
        total_pipeline = pipeline_value
    stats.append({
        "key": "pipeline",
        "label": "Pipeline Value",
        "value": f"₦{pipeline_value:,.0f}",
        "subtext": f"₦{total_pipeline:,.0f} total",
        "icon": "trending-up",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/crm/opportunities",
    })

    # Won This Period
    month_start = date(today.year, today.month, 1)
    won_count, won_value = dashboard_service.get_won_stats(month_start)
    stats.append({
        "key": "won",
        "label": "Won This Month",
        "value": f"{won_count}",
        "subtext": f"₦{won_value:,.0f} revenue",
        "icon": "check-circle",
        "icon_bg": "bg-green-50",
        "icon_color": "text-green-600",
        "href": "/crm/opportunities?status=won",
    })

    # Win Rate / Conversion
    conversion_rate = lead_funnel.conversion_to_opportunity if lead_funnel else 0.0
    stats.append({
        "key": "conversion",
        "label": "Conversion Rate",
        "value": f"{conversion_rate:.1f}%",
        "subtext": "Lead → Opportunity",
        "icon": "percent",
        "icon_bg": "bg-indigo-50",
        "icon_color": "text-indigo-600",
        "href": "/crm/leads",
    })

    context["stats"] = stats

    # Lead Funnel Data
    if lead_funnel:
        context["lead_funnel"] = {
            "total": lead_funnel.total_leads,
            "by_qualification": lead_funnel.by_qualification,
            "by_status": lead_funnel.by_status,
            "conversion_rate": lead_funnel.conversion_to_opportunity,
        }
    else:
        context["lead_funnel"] = None

    # Pipeline by Stage
    if pipeline:
        context["pipeline_stages"] = sorted(pipeline.by_stage, key=lambda x: x.get("probability", 0), reverse=True)
        context["pipeline_total"] = pipeline.total_pipeline_value
        context["pipeline_weighted"] = pipeline.weighted_pipeline_value
        context["pipeline_at_risk"] = pipeline.at_risk_value
    else:
        context["pipeline_stages"] = []
        context["pipeline_total"] = Decimal("0")
        context["pipeline_weighted"] = Decimal("0")
        context["pipeline_at_risk"] = Decimal("0")

    # Velocity metrics
    if velocity:
        context["velocity"] = {
            "avg_cycle_days": velocity.avg_deal_cycle_days,
            "deals_stuck": velocity.deals_stuck,
        }
    else:
        context["velocity"] = None

    # Top Reps
    context["top_reps"] = [
        {
            "rank": rep.rank,
            "name": rep.rep_name,
            "won_count": rep.won_count,
            "won_value": f"₦{rep.won_value:,.0f}",
            "win_rate": f"{rep.win_rate:.1f}%",
            "opportunities": rep.opportunities_count,
        }
        for rep in top_reps
    ]

    # Lead Sources
    context["lead_sources"] = [
        {
            "source": s.source,
            "leads": s.lead_count,
            "opportunities": s.opportunity_count,
            "conversion_rate": f"{s.conversion_rate:.1f}%",
            "value": f"₦{s.total_value:,.0f}",
        }
        for s in lead_sources[:5]
    ]

    # Quick links
    context["quick_links"] = [
        {"label": "Leads", "href": "/crm/leads", "icon": "user-plus", "description": "Manage potential customers"},
        {"label": "Opportunities", "href": "/crm/opportunities", "icon": "target", "description": "Deal pipeline"},
        {"label": "Activities", "href": "/crm/activities", "icon": "calendar", "description": "Calls, meetings, tasks"},
        {"label": "Customer Health", "href": "/crm/health", "icon": "heart", "description": "Retention & health scores"},
    ]

    # Recent activities
    recent_activities = dashboard_service.list_recent_activities(limit=5)
    context["recent_activities"] = recent_activities

    # Upcoming activities
    upcoming = dashboard_service.list_upcoming_activities(
        since=datetime.utcnow(),
        limit=5,
    )
    context["upcoming_activities"] = upcoming

    template = templates.get_template("modules/crm/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/health", response_class=HTMLResponse)
async def customer_health(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    grade: Optional[str] = Query(None, description="Filter by health grade"),
    risk: Optional[str] = Query(None, description="Filter by churn risk level"),
):
    """Customer health dashboard - retention & health scoring."""
    from app.services.crm.health_web import CustomerHealthWebService
    from app.services.crm.health_web_types import HealthFilters, HealthGrade, ChurnRiskLevel

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Health"
    context["now"] = datetime.utcnow()
    context["grade_filter"] = grade
    context["risk_filter"] = risk

    # Build filters
    filters = HealthFilters()
    if grade:
        try:
            filters.grade = HealthGrade(grade)
        except ValueError:
            pass  # Invalid grade, ignore filter
    if risk:
        try:
            filters.risk = ChurnRiskLevel(risk)
        except ValueError:
            pass  # Invalid risk, ignore filter

    # Get dashboard data from service
    health_service = CustomerHealthWebService(db)
    dashboard = health_service.get_customer_health_dashboard(filters)

    # Format customers for template
    context["customers"] = [
        {
            "id": c.party_id,
            "name": c.party_name,
            "health_score": c.health_score,
            "health_grade": c.health_grade.value,
            "churn_risk": c.churn_risk.value,
            "total_opportunities": c.total_opportunities,
            "won_opportunities": c.won_opportunities,
            "lost_opportunities": c.lost_opportunities,
            "win_rate": f"{c.win_rate:.0f}%",
            "total_value": f"₦{c.total_value:,.0f}",
        }
        for c in dashboard.customers
    ]

    # Health stats
    context["health_stats"] = {
        "total": dashboard.health_distribution.total,
        "excellent": dashboard.health_distribution.excellent,
        "good": dashboard.health_distribution.good,
        "at_risk": dashboard.health_distribution.at_risk,
        "critical": dashboard.health_distribution.critical,
        "excellent_pct": dashboard.health_distribution.excellent_pct,
        "good_pct": dashboard.health_distribution.good_pct,
        "at_risk_pct": dashboard.health_distribution.at_risk_pct,
        "critical_pct": dashboard.health_distribution.critical_pct,
    }

    # Churn risk stats
    context["churn_stats"] = {
        "low": dashboard.churn_distribution.low,
        "medium": dashboard.churn_distribution.medium,
        "high": dashboard.churn_distribution.high,
        "critical": dashboard.churn_distribution.critical,
    }

    # Filter options
    context["grade_options"] = [
        {"value": "excellent", "label": "Excellent"},
        {"value": "good", "label": "Good"},
        {"value": "at_risk", "label": "At Risk"},
        {"value": "critical", "label": "Critical"},
    ]
    context["risk_options"] = [
        {"value": "low", "label": "Low"},
        {"value": "medium", "label": "Medium"},
        {"value": "high", "label": "High"},
        {"value": "critical", "label": "Critical"},
    ]

    template = templates.get_template("modules/crm/templates/pages/health.html")
    return HTMLResponse(template.render(context))


# Include the CRM routes (leads, opportunities, activities, campaigns)
router.include_router(crm_routes_router)

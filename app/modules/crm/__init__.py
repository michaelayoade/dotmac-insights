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

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func, and_, or_

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.web.module_types import ModuleConfig

# Import models
from app.models.party import Party, PartyRole
from app.models.crm import Opportunity, OpportunityStage, Activity

from .routes import router as crm_routes_router

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="crm",
    name="CRM",
    description="Manage leads, opportunities, and customer relationships",
    icon="users",
    prefix="/crm",
    group="Front Office",
    order=5,
    scopes=["crm:read"],
    prefixes=["/crm"],
)

NAVIGATION = [
    {
        "section": "CRM",
        "href": "/crm",
        "icon": "users",
        "scope": "crm:read",
        "order": 5,
        "links": [
            {"label": "Dashboard", "href": "/crm", "icon": "home"},
            {"label": "Leads", "href": "/crm/leads", "icon": "user-plus"},
            {"label": "Opportunities", "href": "/crm/opportunities", "icon": "target"},
            {"label": "Activities", "href": "/crm/activities", "icon": "calendar"},
            {"label": "Campaigns", "href": "/crm/campaigns", "icon": "megaphone"},
        ],
    },
]

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
):
    """CRM dashboard - landing page for CRM module."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CRM"
    context["now"] = datetime.utcnow()

    company_id = user.company_id

    # Gather stats
    stats = []

    # Active Leads
    lead_count = db.query(func.count(PartyRole.id)).filter(
        PartyRole.role == "lead",
        PartyRole.status == "active",
    ).scalar() or 0
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

    # Open Opportunities
    open_opps = db.query(func.count(Opportunity.id)).filter(
        Opportunity.company_id == company_id,
        Opportunity.status == "open",
    ).scalar() or 0
    stats.append({
        "key": "opportunities",
        "label": "Open Opportunities",
        "value": f"{open_opps:,}",
        "subtext": "Active deals",
        "icon": "target",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/crm/opportunities",
    })

    # Pipeline Value
    pipeline_value = db.query(func.sum(Opportunity.amount)).filter(
        Opportunity.company_id == company_id,
        Opportunity.status == "open",
    ).scalar() or Decimal("0")
    stats.append({
        "key": "pipeline",
        "label": "Pipeline Value",
        "value": f"${pipeline_value:,.0f}",
        "subtext": "Total potential",
        "icon": "trending-up",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/crm/opportunities",
    })

    # Today's Activities
    today = date.today()
    today_activities = db.query(func.count(Activity.id)).filter(
        Activity.company_id == company_id,
        func.date(Activity.scheduled_at) == today,
    ).scalar() or 0
    stats.append({
        "key": "activities",
        "label": "Today's Activities",
        "value": f"{today_activities:,}",
        "subtext": "Scheduled tasks",
        "icon": "calendar",
        "icon_bg": "bg-purple-50",
        "icon_color": "text-purple-600",
        "href": "/crm/activities",
    })

    # Won This Month
    month_start = date(today.year, today.month, 1)
    won_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.company_id == company_id,
        Opportunity.status == "won",
        Opportunity.closed_at >= month_start,
    ).scalar() or 0
    won_value = db.query(func.sum(Opportunity.amount)).filter(
        Opportunity.company_id == company_id,
        Opportunity.status == "won",
        Opportunity.closed_at >= month_start,
    ).scalar() or Decimal("0")
    stats.append({
        "key": "won",
        "label": "Won This Month",
        "value": f"{won_count}",
        "subtext": f"${won_value:,.0f} revenue",
        "icon": "check-circle",
        "icon_bg": "bg-green-50",
        "icon_color": "text-green-600",
        "href": "/crm/opportunities?status=won",
    })

    context["stats"] = stats

    # Quick links
    context["quick_links"] = [
        {"label": "Leads", "href": "/crm/leads", "icon": "user-plus", "description": "Manage potential customers"},
        {"label": "Opportunities", "href": "/crm/opportunities", "icon": "target", "description": "Deal pipeline"},
        {"label": "Activities", "href": "/crm/activities", "icon": "calendar", "description": "Calls, meetings, tasks"},
        {"label": "Campaigns", "href": "/crm/campaigns", "icon": "megaphone", "description": "Marketing campaigns"},
    ]

    # Recent activities
    recent_activities = db.query(Activity).filter(
        Activity.company_id == company_id,
    ).order_by(Activity.created_at.desc()).limit(5).all()
    context["recent_activities"] = recent_activities

    # Upcoming activities
    upcoming = db.query(Activity).filter(
        Activity.company_id == company_id,
        Activity.scheduled_at >= datetime.utcnow(),
        Activity.status.in_(["scheduled", "pending"]),
    ).order_by(Activity.scheduled_at).limit(5).all()
    context["upcoming_activities"] = upcoming

    template = templates.get_template("modules/crm/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# Include the CRM routes (leads, opportunities, activities, campaigns)
router.include_router(crm_routes_router)

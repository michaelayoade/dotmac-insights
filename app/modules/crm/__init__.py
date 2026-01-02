"""
CRM Module - Contact and Customer Management with SSR + HTMX.

Routes:
- /crm - Dashboard (landing page)
- /crm/contacts - Contacts management
- /crm/customers - Redirect to /customers (for nav consistency)
- /crm/opportunities - Sales opportunities
- /crm/pipeline - Pipeline kanban view
- /crm/leads - Lead management
- /crm/activities - Activity tracking
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Import models for dashboard stats
from app.models.contact import Contact, ContactStatus
from app.models.customer import Customer, CustomerStatus
from app.models.crm import Opportunity, OpportunityStatus

from .routes import router as contacts_router
from .leads_routes import router as leads_router
from .opportunities_routes import router as opportunities_router
from .activities_routes import router as activities_router

templates = get_template_env()

# Main CRM router - aggregates all CRM sub-routers
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

    # Gather stats
    stats = []

    # Total Contacts
    contact_count = db.query(func.count(Contact.id)).scalar() or 0
    stats.append({
        "key": "contacts",
        "label": "Total Contacts",
        "value": f"{contact_count:,}",
        "subtext": "Leads & prospects",
        "icon": "users",
        "icon_bg": "bg-primary-50",
        "icon_color": "text-primary-600",
        "href": "/crm/contacts",
    })

    # Active Customers
    customer_count = db.query(func.count(Customer.id)).filter(
        Customer.status == CustomerStatus.ACTIVE,
        Customer.is_deleted == False,
    ).scalar() or 0
    stats.append({
        "key": "customers",
        "label": "Active Customers",
        "value": f"{customer_count:,}",
        "subtext": "Paying accounts",
        "icon": "building",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/customers",
    })

    # Open Opportunities
    open_opps = db.query(func.count(Opportunity.id)).filter(
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0
    stats.append({
        "key": "opportunities",
        "label": "Open Opportunities",
        "value": f"{open_opps:,}",
        "subtext": "In pipeline",
        "icon": "trending-up",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/crm/opportunities",
    })

    # Pipeline Value
    pipeline_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or Decimal("0")
    stats.append({
        "key": "pipeline",
        "label": "Pipeline Value",
        "value": f"${pipeline_value:,.0f}",
        "subtext": "Total opportunity value",
        "icon": "dollar-sign",
        "icon_bg": "bg-blue-50",
        "icon_color": "text-blue-600",
        "href": "/crm/pipeline",
    })

    context["stats"] = stats

    # Quick links
    context["quick_links"] = [
        {"label": "Contacts", "href": "/crm/contacts", "icon": "users", "description": "Manage leads and prospects"},
        {"label": "Customers", "href": "/customers", "icon": "building", "description": "Customer accounts"},
        {"label": "Opportunities", "href": "/crm/opportunities", "icon": "trending-up", "description": "Sales pipeline"},
        {"label": "Pipeline", "href": "/crm/pipeline", "icon": "git-branch", "description": "Visual pipeline view"},
    ]

    template = templates.get_template("modules/crm/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# Redirect /crm/customers to /customers for navigation consistency
@router.get("/crm/customers")
async def crm_customers_redirect():
    """Redirect to customers module."""
    return RedirectResponse(url="/customers", status_code=302)


@router.get("/crm/customers/{path:path}")
async def crm_customers_path_redirect(path: str):
    """Redirect customer sub-paths."""
    return RedirectResponse(url=f"/customers/{path}", status_code=302)


# Include sub-routers (they already have /crm/* prefixes)
router.include_router(contacts_router)
router.include_router(leads_router)
router.include_router(opportunities_router)
router.include_router(activities_router)

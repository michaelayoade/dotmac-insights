"""
Module Dashboard Routes - Overview pages for each business module.

Each dashboard aggregates data from the API and displays key metrics,
recent items, quick links, and module-specific widgets.
"""
from __future__ import annotations

import httpx
from typing import Dict, Any, Optional, cast
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.config import settings

# Permission dependencies
RequireCRMRead = Depends(require_scope("crm:read"))
RequireSupportRead = Depends(require_scope("support:read"))
RequireAccountingRead = Depends(require_scope("accounting:read"))
RequireInventoryRead = Depends(require_scope("inventory:read"))

router = APIRouter(tags=["dashboards"])
templates = get_template_env()


async def fetch_dashboard_data(request: Request, endpoint: str) -> Dict[str, Any]:
    """Fetch dashboard data from internal API endpoint."""
    # Get auth cookie from request to forward to API
    auth_cookie = request.cookies.get("auth_token", "")

    # Build internal API URL
    base_url = str(request.base_url).rstrip("/")
    api_url = f"{base_url}/api/dashboards/{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                api_url,
                cookies={"auth_token": auth_cookie},
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
    except Exception as e:
        # Log error but don't fail the page
        print(f"Dashboard API error ({endpoint}): {e}")

    return {}


# =============================================================================
# CRM DASHBOARD
# =============================================================================

@router.get("/crm", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def crm_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """CRM Dashboard - Pipeline, contacts, leads overview."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CRM Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Dashboard", "href": "/"},
        {"label": "CRM"},
    ])

    # Fetch dashboard data from APIs
    pipeline_data = await fetch_dashboard_data(request, "crm-pipeline")
    contacts_data = await fetch_dashboard_data(request, "contacts")
    leads_data = await fetch_dashboard_data(request, "leads")

    context["pipeline"] = pipeline_data
    context["contacts"] = contacts_data
    context["leads"] = leads_data

    # Build stats for cards
    context["stats"] = [
        {
            "title": "Total Contacts",
            "value": contacts_data.get("total", 0),
            "icon": "users",
            "color": "primary",
            "href": "/crm/contacts",
        },
        {
            "title": "Active Leads",
            "value": leads_data.get("active_count", 0),
            "icon": "trending-up",
            "color": "blue",
            "href": "/crm/opportunities",
        },
        {
            "title": "Pipeline Value",
            "value": f"${pipeline_data.get('total_value', 0):,.0f}",
            "icon": "dollar-sign",
            "color": "emerald",
            "href": "/crm/pipeline",
        },
        {
            "title": "Won This Month",
            "value": pipeline_data.get("won_this_month", 0),
            "icon": "check-circle",
            "color": "green",
        },
    ]

    # Quick links
    context["quick_links"] = [
        {"label": "Contacts", "href": "/crm/contacts", "icon": "users", "count": contacts_data.get("total", 0)},
        {"label": "Opportunities", "href": "/crm/opportunities", "icon": "trending-up"},
        {"label": "Pipeline", "href": "/crm/pipeline", "icon": "git-branch"},
    ]

    # Recent items
    context["recent_contacts"] = contacts_data.get("recent", [])[:5]
    context["recent_leads"] = leads_data.get("recent", [])[:5]

    template = templates.get_template("modules/dashboards/templates/pages/crm.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SUPPORT DASHBOARD
# =============================================================================

@router.get("/support", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def support_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support Dashboard - Tickets, SLA, knowledge base overview."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Dashboard", "href": "/"},
        {"label": "Support"},
    ])

    # Fetch dashboard data
    support_data = await fetch_dashboard_data(request, "support")

    context["support"] = support_data

    # Build stats
    context["stats"] = [
        {
            "title": "Open Tickets",
            "value": support_data.get("open_count", 0),
            "icon": "life-buoy",
            "color": "amber",
            "href": "/support/tickets?status=open",
        },
        {
            "title": "Pending",
            "value": support_data.get("pending_count", 0),
            "icon": "clock",
            "color": "blue",
            "href": "/support/tickets?status=pending",
        },
        {
            "title": "Resolved Today",
            "value": support_data.get("resolved_today", 0),
            "icon": "check-circle",
            "color": "emerald",
        },
        {
            "title": "Avg Response Time",
            "value": support_data.get("avg_response_time", "N/A"),
            "icon": "zap",
            "color": "purple",
        },
    ]

    # Quick links
    context["quick_links"] = [
        {"label": "All Tickets", "href": "/support/tickets", "icon": "life-buoy", "count": support_data.get("total_count", 0)},
        {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open"},
        {"label": "New Ticket", "href": "/support/tickets/new", "icon": "plus"},
    ]

    # Recent tickets
    context["recent_tickets"] = support_data.get("recent_tickets", [])[:5]
    context["priority_breakdown"] = support_data.get("by_priority", {})

    template = templates.get_template("modules/dashboards/templates/pages/support.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# FINANCE DASHBOARD
# =============================================================================

@router.get("/finance", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def finance_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Finance Dashboard - Accounting, invoices, payments overview."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Finance Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Dashboard", "href": "/"},
        {"label": "Finance"},
    ])

    # Fetch dashboard data
    accounting_data = await fetch_dashboard_data(request, "accounting")
    sales_data = await fetch_dashboard_data(request, "sales")

    context["accounting"] = accounting_data
    context["sales"] = sales_data

    # Build stats
    context["stats"] = [
        {
            "title": "Total Revenue",
            "value": f"${sales_data.get('total_revenue', 0):,.0f}",
            "icon": "dollar-sign",
            "color": "emerald",
        },
        {
            "title": "Outstanding",
            "value": f"${accounting_data.get('outstanding', 0):,.0f}",
            "icon": "file-text",
            "color": "amber",
            "href": "/accounting/invoices?status=pending",
        },
        {
            "title": "Cash on Hand",
            "value": f"${accounting_data.get('cash_balance', 0):,.0f}",
            "icon": "credit-card",
            "color": "blue",
        },
        {
            "title": "Overdue",
            "value": f"${accounting_data.get('overdue', 0):,.0f}",
            "icon": "alert-circle",
            "color": "red",
            "href": "/accounting/invoices?status=overdue",
        },
    ]

    # Quick links
    context["quick_links"] = [
        {"label": "Invoices", "href": "/accounting/invoices", "icon": "file-text"},
        {"label": "Payments", "href": "/accounting/payments", "icon": "credit-card"},
        {"label": "Expenses", "href": "/expenses", "icon": "receipt"},
        {"label": "Reports", "href": "/reports", "icon": "chart-bar"},
    ]

    # Recent items
    context["recent_invoices"] = accounting_data.get("recent_invoices", [])[:5]
    context["recent_payments"] = accounting_data.get("recent_payments", [])[:5]
    context["ar_aging"] = sales_data.get("ar_aging", {})

    template = templates.get_template("modules/dashboards/templates/pages/finance.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# HR DASHBOARD - Already exists in app/modules/hr/routes/dashboard.py
# =============================================================================


# =============================================================================
# OPERATIONS DASHBOARD
# =============================================================================

@router.get("/operations", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def operations_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Operations Dashboard - Inventory, projects, field service overview."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Operations Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Dashboard", "href": "/"},
        {"label": "Operations"},
    ])

    # Fetch dashboard data
    inventory_data = await fetch_dashboard_data(request, "inventory")
    projects_data = await fetch_dashboard_data(request, "projects")
    field_service_data = await fetch_dashboard_data(request, "field-service")

    context["inventory"] = inventory_data
    context["projects"] = projects_data
    context["field_service"] = field_service_data

    # Build stats
    context["stats"] = [
        {
            "title": "Total SKUs",
            "value": inventory_data.get("total_skus", 0),
            "icon": "package",
            "color": "primary",
            "href": "/inventory",
        },
        {
            "title": "Low Stock Items",
            "value": inventory_data.get("low_stock_count", 0),
            "icon": "alert-triangle",
            "color": "amber" if inventory_data.get("low_stock_count", 0) > 0 else "emerald",
            "href": "/inventory?filter=low-stock",
        },
        {
            "title": "Active Projects",
            "value": projects_data.get("active_count", 0),
            "icon": "folder",
            "color": "blue",
            "href": "/projects?status=active",
        },
        {
            "title": "Service Orders",
            "value": field_service_data.get("open_orders", 0),
            "icon": "truck",
            "color": "purple",
            "href": "/field-service",
        },
    ]

    # Quick links
    context["quick_links"] = [
        {"label": "Inventory", "href": "/inventory", "icon": "package", "count": inventory_data.get("total_skus", 0)},
        {"label": "Projects", "href": "/projects", "icon": "folder", "count": projects_data.get("active_count", 0)},
        {"label": "Field Service", "href": "/field-service", "icon": "truck"},
    ]

    # Recent items
    context["low_stock_items"] = inventory_data.get("low_stock_items", [])[:5]
    context["recent_projects"] = projects_data.get("recent", [])[:5]
    context["upcoming_service"] = field_service_data.get("upcoming", [])[:5]

    template = templates.get_template("modules/dashboards/templates/pages/operations.html")
    return HTMLResponse(template.render(context))

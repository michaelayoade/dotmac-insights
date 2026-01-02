"""
Web router aggregation for SSR frontend.

Mounts all module routers and provides common endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import (
    SessionUser,
    OptionalUser,
    CSRFToken,
    DB,
    ensure_csrf_token,
)
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Web router - no /api prefix
web_router = APIRouter(tags=["web"])

# Template environment
templates = get_template_env()


@web_router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Dashboard / home page."""
    from datetime import datetime, date
    from sqlalchemy import func
    from app.models.contact import Contact
    from app.models.unified_ticket import UnifiedTicket, TicketStatus
    from app.models.invoice import Invoice, InvoiceStatus

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Dashboard"
    now = datetime.utcnow()
    context["now"] = now

    # Fetch dashboard stats
    stats = []

    # 1. Total Contacts
    contact_count = db.query(func.count(Contact.id)).scalar() or 0
    stats.append({
        "key": "contacts",
        "label": "Total Contacts",
        "value": f"{contact_count:,}",
        "subtext": "Leads & customers",
        "icon": "users",
        "icon_bg": "bg-primary-50",
        "icon_color": "text-primary-600",
        "accent_gradient": "from-primary-400 to-primary-600",
    })

    # 2. Open Tickets
    open_tickets = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.status.in_([
            "open",
            "in_progress",
            "waiting",
            "reopened",
        ])
    ).scalar() or 0
    stats.append({
        "key": "tickets",
        "label": "Open Tickets",
        "value": f"{open_tickets:,}",
        "subtext": "Awaiting response",
        "icon": "ticket",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "accent_gradient": "from-amber-400 to-amber-600",
    })

    # 3. Revenue MTD
    today = date.today()
    month_start = date(today.year, today.month, 1)
    revenue_mtd = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= month_start,
        Invoice.status.in_([
            InvoiceStatus.PAID,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PENDING,
            InvoiceStatus.OVERDUE,
        ])
    ).scalar() or 0
    stats.append({
        "key": "revenue",
        "label": "Revenue (MTD)",
        "value": f"${revenue_mtd:,.0f}",
        "subtext": "This month",
        "icon": "currency",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "accent_gradient": "from-emerald-400 to-emerald-600",
    })

    # 4. Pending Invoices
    pending_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status.in_([
            InvoiceStatus.PENDING,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        ])
    ).scalar() or 0
    stats.append({
        "key": "invoices",
        "label": "Pending Invoices",
        "value": f"{pending_invoices:,}",
        "subtext": "Awaiting payment",
        "icon": "invoice",
        "icon_bg": "bg-red-50",
        "icon_color": "text-red-600",
        "accent_gradient": "from-red-400 to-red-600",
    })

    context["stats"] = stats

    # Fetch recent activities (mix of invoices, tickets)
    activities = []

    # Recent invoices
    recent_invoices = db.query(Invoice).order_by(
        Invoice.created_at.desc()
    ).limit(3).all()
    for inv in recent_invoices:
        # Get customer name from contact or customer relationship
        cust_name = None
        if inv.contact:
            cust_name = inv.contact.name
        elif inv.customer:
            cust_name = inv.customer.name
        activities.append({
            "user_name": cust_name or "Customer",
            "user_initials": (cust_name or "C")[:2].upper(),
            "color_from": "from-emerald-100",
            "color_to": "to-emerald-200",
            "text_color": "text-emerald-600",
            "action": "was invoiced",
            "description": f"Invoice {inv.invoice_number} for ${inv.total_amount:,.2f}" if inv.total_amount else f"Invoice {inv.invoice_number}",
            "timestamp": inv.created_at,
            "badge": inv.status.value.replace("_", " ").title() if inv.status else None,
            "badge_color": "bg-emerald-100 text-emerald-600" if inv.status == InvoiceStatus.PAID else "bg-amber-100 text-amber-600",
        })

    # Recent tickets
    recent_tickets = db.query(UnifiedTicket).order_by(
        UnifiedTicket.created_at.desc()
    ).limit(3).all()
    for ticket in recent_tickets:
        activities.append({
            "user_name": ticket.contact_name or "Customer",
            "user_initials": (ticket.contact_name or "C")[:2].upper(),
            "color_from": "from-amber-100",
            "color_to": "to-amber-200",
            "text_color": "text-amber-600",
            "action": "opened a ticket",
            "description": f"#{ticket.ticket_number}: {ticket.subject[:50]}..." if len(ticket.subject or "") > 50 else f"#{ticket.ticket_number}: {ticket.subject}",
            "timestamp": ticket.created_at,
            "badge": ticket.priority.value.title() if ticket.priority else None,
            "badge_color": "bg-red-100 text-red-600" if ticket.priority and ticket.priority.value in ("urgent", "critical") else "bg-gray-100 text-gray-600",
        })

    # Sort by timestamp and take top 6
    activities.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    context["activities"] = activities[:6]

    template = templates.get_template("pages/dashboard.html")
    return HTMLResponse(template.render(context))


@web_router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    response: Response,
    user: OptionalUser,
    csrf_token: CSRFToken,
):
    """Login page - redirects to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)

    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Login"
    context["next_url"] = request.query_params.get("next", "/")

    template = templates.get_template("pages/login.html")
    return HTMLResponse(template.render(context))


@web_router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    response: Response,
    csrf_token: CSRFToken,
    db: DB,
):
    """Handle login form submission.

    Note: This endpoint is for direct login if supported.
    Most deployments use SSO via /auth/sso instead.
    """
    from app.core.security import set_flash, validate_csrf

    # Validate CSRF
    await validate_csrf(request)

    form = await request.form()
    raw_email = form.get("email", "")
    email = raw_email.strip() if isinstance(raw_email, str) else ""
    password = form.get("password", "")
    next_url = form.get("next", "/")

    # For now, direct login is not supported - redirect to SSO
    # In production, this would be handled by the external auth provider
    set_flash(response, "Please use SSO to sign in.", "info")

    context = get_base_context(request, response, None, csrf_token)
    context["page_title"] = "Login"
    context["next_url"] = next_url
    context["email"] = email

    template = templates.get_template("pages/login.html")
    return HTMLResponse(template.render(context))


@web_router.get("/auth/sso")
async def sso_redirect(request: Request):
    """Redirect to SSO provider for authentication.

    In production, this redirects to the configured OIDC provider.
    For development, this may redirect to a local auth server.
    """
    from app.config import settings

    # Get the 'next' URL to redirect back to after auth
    next_url = request.query_params.get("next", "/")

    # In a real implementation, this would:
    # 1. Generate a state token for CSRF protection
    # 2. Store the state and next_url in session/cookie
    # 3. Redirect to the OIDC authorization endpoint

    # For now, redirect to the auth provider's login page
    # The auth provider should be configured to redirect back with a JWT token
    auth_base = settings.jwt_issuer or "http://localhost:3000"
    auth_url = f"{auth_base}/login?redirect={request.url_for('auth_callback')}&next={next_url}"

    return RedirectResponse(url=auth_url, status_code=302)


@web_router.get("/auth/callback")
async def auth_callback(
    request: Request,
    response: Response,
):
    """Handle callback from SSO provider.

    The auth provider redirects here with a token after successful authentication.
    """
    from app.auth import AUTH_COOKIE_NAME
    from app.core.security import set_flash

    # Get token from query params or headers
    token = request.query_params.get("token")
    next_url = request.query_params.get("next", "/")

    if not token:
        set_flash(response, "Authentication failed. Please try again.", "error")
        return RedirectResponse(url="/login", status_code=303)

    # Set the auth cookie
    redirect = RedirectResponse(url=next_url, status_code=303)
    redirect.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=86400 * 7,  # 7 days
    )

    return redirect


@web_router.get("/logout")
async def logout(request: Request, response: Response):
    """Logout - clears session cookie and redirects to login."""
    from app.auth import AUTH_COOKIE_NAME
    from app.core.security import set_flash

    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(AUTH_COOKIE_NAME, path="/")
    set_flash(redirect, "You have been logged out.", "info")
    return redirect


@web_router.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "ok"}


# =============================================================================
# MODULE ROUTERS - Consolidated Structure
# =============================================================================

# CRM module (includes contacts, customers redirect, opportunities, pipeline)
from app.modules.crm import router as crm_router

# Sales module (includes quotations, orders, invoices/subscriptions redirects)
from app.modules.sales import router as sales_router

# Accounting module (includes all accounting sub-routes)
from app.modules.accounting.routes import router as accounting_router

# HR module (includes employees, leave, payroll, expenses/performance redirects)
from app.modules.hr.routes import router as hr_router

# Support module (includes tickets, agents, SLA, KB, etc.)
from app.modules.support.routes import (
    router as support_router,
    dashboard_router as support_dashboard_router,
    agents_router as support_agents_router,
    sla_router as support_sla_router,
    conversations_router as support_conversations_router,
    teams_router as support_teams_router,
    canned_router as support_canned_router,
    kb_router as support_kb_router,
    automation_router as support_automation_router,
    csat_router as support_csat_router,
    routing_router as support_routing_router,
    tags_router as support_tags_router,
)

# Operations module (NEW - aggregates projects, field_service, inventory, assets, vehicles)
from app.modules.operations.routes import router as operations_router

# Purchasing module (includes suppliers)
from app.modules.purchasing.routes import router as purchasing_router

# Network module
from app.modules.network.routes import router as network_router

# Analytics module
from app.modules.analytics.routes import router as analytics_router

# Settings module (includes workflow tasks redirect)
from app.modules.settings.routes import router as settings_router

# Standalone modules that are kept for direct access (linked via redirects from parent modules)
from app.modules.customers.routes import router as customers_router
from app.modules.invoices.routes import router as invoices_router
from app.modules.subscriptions.routes import router as subscriptions_router
from app.modules.subscriptions.tariff_routes import router as tariffs_router
from app.modules.subscriptions.payment_routes import router as payment_subscriptions_router
from app.modules.expenses.routes import router as expenses_router
from app.modules.performance.routes import router as performance_router
from app.modules.suppliers.routes import router as suppliers_router
from app.modules.reports.routes import router as reports_router
from app.modules.omnichannel.routes import router as omnichannel_router
from app.modules.workflow_tasks.routes import router as workflow_tasks_router
from app.modules.payments.routes import router as payments_router

# Legacy standalone modules (kept for backwards compatibility, accessed via parent modules)
from app.modules.inventory.routes import router as inventory_router
from app.modules.projects.routes import (
    router as projects_router,
    dashboard_router as projects_dashboard_router,
    tasks_router as projects_tasks_router,
    milestones_router as projects_milestones_router,
)
from app.modules.projects.gantt_routes import router as projects_gantt_router
from app.modules.field_service.routes import router as field_service_router
from app.modules.field_service.calendar_routes import router as field_service_calendar_router
from app.modules.assets.routes import router as assets_router
from app.modules.vehicles.routes import router as vehicles_router

# =============================================================================
# ROUTE REGISTRATION
# =============================================================================

# Core consolidated modules with landing pages
web_router.include_router(crm_router)
web_router.include_router(sales_router)
web_router.include_router(accounting_router)
web_router.include_router(hr_router)
web_router.include_router(purchasing_router)
web_router.include_router(operations_router)
web_router.include_router(network_router)
web_router.include_router(analytics_router)
web_router.include_router(settings_router)

# Support module with all sub-routers
web_router.include_router(support_router)
web_router.include_router(support_dashboard_router)
web_router.include_router(support_agents_router)
web_router.include_router(support_sla_router)
web_router.include_router(support_conversations_router)
web_router.include_router(support_teams_router)
web_router.include_router(support_canned_router)
web_router.include_router(support_kb_router)
web_router.include_router(support_automation_router)
web_router.include_router(support_csat_router)
web_router.include_router(support_routing_router)
web_router.include_router(support_tags_router)

# Standalone modules (linked from parent modules)
web_router.include_router(customers_router)
web_router.include_router(invoices_router)
web_router.include_router(subscriptions_router)
web_router.include_router(tariffs_router)
web_router.include_router(payment_subscriptions_router)
web_router.include_router(expenses_router)
web_router.include_router(performance_router)
web_router.include_router(suppliers_router)
web_router.include_router(reports_router)
web_router.include_router(omnichannel_router)
web_router.include_router(workflow_tasks_router)
web_router.include_router(payments_router)

# Legacy operations sub-modules (for backwards compatibility)
web_router.include_router(inventory_router)
web_router.include_router(projects_router)
web_router.include_router(projects_dashboard_router)
web_router.include_router(projects_tasks_router)
web_router.include_router(projects_milestones_router)
web_router.include_router(projects_gantt_router)
web_router.include_router(field_service_router)
web_router.include_router(field_service_calendar_router)
web_router.include_router(assets_router)
web_router.include_router(vehicles_router)

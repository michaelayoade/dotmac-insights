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
    from datetime import datetime

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Dashboard"
    context["now"] = datetime.utcnow()

    # TODO: Fetch actual dashboard stats from database
    context["stats"] = []
    context["activities"] = []

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


# Import and include module routers
from app.modules.crm.routes import router as crm_router
from app.modules.crm.opportunities_routes import router as crm_opportunities_router
from app.modules.support.routes import (
    router as support_router,
    kb_router as support_kb_router,
    dashboard_router as support_dashboard_router,
    agents_router as support_agents_router,
    canned_router as support_canned_router,
    sla_router as support_sla_router,
    automation_router as support_automation_router,
    csat_router as support_csat_router,
    routing_router as support_routing_router,
    conversations_router as support_conversations_router,
)

# Operations modules
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

# HR modules
from app.modules.hr.routes import router as hr_router

# Sales & Finance modules
from app.modules.accounting.routes import router as accounting_router
from app.modules.customers.routes import router as customers_router
from app.modules.sales.routes import router as sales_router

# Asset & Expense modules
from app.modules.assets.routes import router as assets_router
from app.modules.expenses.routes import router as expenses_router
from app.modules.purchasing.routes import router as purchasing_router

# Invoicing, Suppliers, Payments, Reports modules
from app.modules.invoices.routes import router as invoices_router
from app.modules.suppliers.routes import router as suppliers_router
from app.modules.payments.routes import router as payments_router
from app.modules.reports.routes import router as reports_router

# Performance & Fleet modules
from app.modules.performance.routes import router as performance_router
from app.modules.vehicles.routes import router as vehicles_router

# Omnichannel modules
from app.modules.omnichannel.routes import router as omnichannel_router

# Settings module
from app.modules.settings.routes import router as settings_router

# Workflow Tasks module
from app.modules.workflow_tasks.routes import router as workflow_tasks_router

# Analytics module
from app.modules.analytics.routes import router as analytics_router

# Network module
from app.modules.network.routes import router as network_router

# Subscriptions module
from app.modules.subscriptions.routes import router as subscriptions_router
from app.modules.subscriptions.tariff_routes import router as tariffs_router
from app.modules.subscriptions.payment_routes import router as payment_subscriptions_router

# Module dashboards
from app.modules.dashboards.routes import router as dashboards_router

web_router.include_router(dashboards_router)
web_router.include_router(crm_router)
web_router.include_router(crm_opportunities_router)
web_router.include_router(support_router)
web_router.include_router(support_kb_router)
web_router.include_router(support_dashboard_router)
web_router.include_router(support_agents_router)
web_router.include_router(support_canned_router)
web_router.include_router(support_sla_router)
web_router.include_router(support_automation_router)
web_router.include_router(support_csat_router)
web_router.include_router(support_routing_router)
web_router.include_router(support_conversations_router)

# Operations routes
web_router.include_router(inventory_router)
web_router.include_router(projects_router)
web_router.include_router(projects_dashboard_router)
web_router.include_router(projects_tasks_router)
web_router.include_router(projects_milestones_router)
web_router.include_router(projects_gantt_router)
web_router.include_router(field_service_router)
web_router.include_router(field_service_calendar_router)

# HR routes
web_router.include_router(hr_router)

# Sales & Finance routes
web_router.include_router(accounting_router)
web_router.include_router(customers_router)
web_router.include_router(sales_router)

# Asset & Expense routes
web_router.include_router(assets_router)
web_router.include_router(expenses_router)
web_router.include_router(purchasing_router)

# Invoicing, Suppliers, Payments, Reports routes
web_router.include_router(invoices_router)
web_router.include_router(suppliers_router)
web_router.include_router(payments_router)
web_router.include_router(reports_router)

# Performance & Fleet routes
web_router.include_router(performance_router)
web_router.include_router(vehicles_router)

# Omnichannel routes
web_router.include_router(omnichannel_router)

# Settings routes
web_router.include_router(settings_router)

# Workflow Tasks routes
web_router.include_router(workflow_tasks_router)

# Analytics routes
web_router.include_router(analytics_router)

# Network routes
web_router.include_router(network_router)

# Subscriptions routes
web_router.include_router(subscriptions_router)
web_router.include_router(tariffs_router)
web_router.include_router(payment_subscriptions_router)

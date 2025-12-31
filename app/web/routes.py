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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Dashboard"

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
    email = form.get("email", "").strip()
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
from app.modules.support.routes import router as support_router

web_router.include_router(crm_router)
web_router.include_router(support_router)

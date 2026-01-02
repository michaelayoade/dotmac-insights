"""Shared dependencies for web modules.

This module provides convenient re-exports and module-specific helpers
to simplify imports in module route files.

Usage in module routes:
    from app.web.deps import (
        SessionUser,
        CSRFToken,
        DB,
        get_module_context,
        render_page,
        render_partial,
    )
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.templates.environment import get_template_env
from app.auth import Principal

# Re-export common dependencies for convenience
from app.web.dependencies import (
    SessionUser,
    OptionalUser,
    CSRFToken,
    CSRFProtect,
    DB,
    require_scope,
    require_any_scope,
    require_all_scopes,
    require_scope_with_context,
)
from app.web.context import get_base_context, get_navigation_context

__all__ = [
    # Dependencies
    "SessionUser",
    "OptionalUser",
    "CSRFToken",
    "CSRFProtect",
    "DB",
    # Permission helpers
    "require_scope",
    "require_any_scope",
    "require_all_scopes",
    "require_scope_with_context",
    # Context helpers
    "get_base_context",
    "get_navigation_context",
    "get_module_context",
    # Rendering helpers
    "render_page",
    "render_partial",
    "is_htmx_request",
]


def is_htmx_request(request: Request) -> bool:
    """Check if this is an HTMX request."""
    return request.headers.get("HX-Request") == "true"


def get_module_context(
    request: Request,
    response: Response,
    user: Principal,
    csrf_token: str,
    *,
    page_title: str = "",
    page_description: str = "",
    breadcrumbs: Optional[list] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standard module page context.

    This is a convenience function that combines base context with
    module-specific settings.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.
        user: Authenticated user principal.
        csrf_token: CSRF token for forms.
        page_title: Page title for the header.
        page_description: Optional page description.
        breadcrumbs: Optional breadcrumb navigation.
        extra: Additional context variables.

    Returns:
        Complete context dict for template rendering.

    Example:
        @router.get("/")
        async def dashboard(
            request: Request,
            response: Response,
            user: SessionUser,
            csrf_token: CSRFToken,
            db: DB,
        ):
            context = get_module_context(
                request, response, user, csrf_token,
                page_title="Sales Dashboard",
                page_description="Overview of sales performance",
            )
            context["stats"] = get_sales_stats(db)
            return render_page("modules/sales/templates/pages/dashboard.html", context)
    """
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = page_title
    context["page_description"] = page_description

    if breadcrumbs:
        context["breadcrumbs"] = breadcrumbs

    if extra:
        context.update(extra)

    return context


def render_page(
    template_path: str,
    context: Dict[str, Any],
) -> HTMLResponse:
    """Render a full page template.

    Args:
        template_path: Path to the template (e.g., "modules/sales/templates/pages/dashboard.html").
        context: Template context dictionary.

    Returns:
        HTMLResponse with rendered template.

    Example:
        return render_page("modules/sales/templates/pages/list.html", context)
    """
    templates = get_template_env()
    template = templates.get_template(template_path)
    return HTMLResponse(template.render(context))


def render_partial(
    template_path: str,
    context: Dict[str, Any],
) -> HTMLResponse:
    """Render a partial template (for HTMX responses).

    Same as render_page but semantically indicates a partial update.

    Args:
        template_path: Path to the partial template.
        context: Template context dictionary.

    Returns:
        HTMLResponse with rendered partial.

    Example:
        if is_htmx_request(request):
            return render_partial("modules/sales/templates/partials/table.html", context)
        return render_page("modules/sales/templates/pages/list.html", context)
    """
    templates = get_template_env()
    template = templates.get_template(template_path)
    return HTMLResponse(template.render(context))


def render_or_partial(
    request: Request,
    page_template: str,
    partial_template: str,
    context: Dict[str, Any],
) -> HTMLResponse:
    """Render page or partial based on request type.

    Automatically chooses between full page and partial template
    based on whether this is an HTMX request.

    Args:
        request: FastAPI request object.
        page_template: Full page template path.
        partial_template: Partial template path for HTMX.
        context: Template context dictionary.

    Returns:
        HTMLResponse with appropriate template.

    Example:
        return render_or_partial(
            request,
            "modules/sales/templates/pages/list.html",
            "modules/sales/templates/partials/table.html",
            context,
        )
    """
    if is_htmx_request(request):
        return render_partial(partial_template, context)
    return render_page(page_template, context)

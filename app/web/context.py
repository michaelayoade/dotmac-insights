"""
Template context builders for SSR pages.

Provides consistent context for all templates including:
- User information
- CSRF token
- Branding
- Flash messages
- Navigation data
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List

from fastapi import Request, Response

from app.auth import Principal
from app.config import settings
from app.core.security import get_flash, FlashMessage


def get_base_context(
    request: Request,
    response: Response,
    user: Optional[Principal] = None,
    csrf_token: str = "",
) -> Dict[str, Any]:
    """Build base context for all templates.

    Includes user info, branding, CSRF token, and flash messages.
    """
    # Get and clear flash message
    flash = get_flash(request, response)

    return {
        # Request info
        "request": request,
        "current_path": request.url.path,

        # User info
        "user": user,
        "is_authenticated": user is not None,

        # Permission helpers
        "has_scope": user.has_scope if user else lambda s: False,

        # Security
        "csrf_token": csrf_token,

        # Flash message
        "flash": flash,

        # Branding (from settings)
        "company_name": settings.company_name,
        "product_name": settings.product_name,
        "support_email": settings.support_email,
        "base_currency": settings.base_currency,

        # Environment
        "is_production": settings.is_production,
        "environment": settings.environment,
    }


def build_breadcrumbs(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Build breadcrumb navigation items.

    Args:
        items: List of {"label": "Name", "href": "/path"} dicts
               Last item should not have href (current page)

    Returns:
        List with is_current flag added to last item
    """
    if not items:
        return []

    result = []
    for i, item in enumerate(items):
        is_current = i == len(items) - 1
        result.append({
            "label": item["label"],
            "href": item.get("href") if not is_current else None,
            "is_current": is_current,
        })
    return result


def build_pagination_context(
    page: int,
    per_page: int,
    total: int,
) -> Dict[str, Any]:
    """Build pagination context for templates.

    Args:
        page: Current page (1-indexed)
        per_page: Items per page
        total: Total item count

    Returns:
        Dict with pagination info for templates
    """
    total_pages = max(1, (total + per_page - 1) // per_page)

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
        "start_item": ((page - 1) * per_page) + 1 if total > 0 else 0,
        "end_item": min(page * per_page, total),
    }


# Navigation structure for sidebar
NAVIGATION_ITEMS = [
    {
        "section": "Main",
        "items": [
            {"label": "Dashboard", "href": "/", "icon": "home", "scope": None},
        ],
    },
    {
        "section": "CRM",
        "items": [
            {"label": "Contacts", "href": "/crm/contacts", "icon": "users", "scope": "crm:read"},
            {"label": "Opportunities", "href": "/crm/opportunities", "icon": "trending-up", "scope": "crm:read"},
            {"label": "Pipeline", "href": "/crm/pipeline", "icon": "git-branch", "scope": "crm:read"},
        ],
    },
    {
        "section": "Support",
        "items": [
            {"label": "Tickets", "href": "/support/tickets", "icon": "life-buoy", "scope": "support:read"},
            {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open", "scope": "support:read"},
        ],
    },
    {
        "section": "Finance",
        "items": [
            {"label": "Invoices", "href": "/accounting/invoices", "icon": "file-text", "scope": "accounting:read"},
            {"label": "Payments", "href": "/accounting/payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Expenses", "href": "/expenses", "icon": "receipt", "scope": "expenses:read"},
        ],
    },
    {
        "section": "Operations",
        "items": [
            {"label": "Inventory", "href": "/inventory", "icon": "package", "scope": "inventory:read"},
            {"label": "Projects", "href": "/projects", "icon": "folder", "scope": "projects:read"},
            {"label": "Field Service", "href": "/field-service", "icon": "truck", "scope": "field_service:read"},
        ],
    },
    {
        "section": "HR",
        "items": [
            {"label": "Employees", "href": "/hr/employees", "icon": "users", "scope": "hr:read"},
            {"label": "Leave", "href": "/hr/leave", "icon": "calendar", "scope": "hr:read"},
            {"label": "Payroll", "href": "/hr/payroll", "icon": "dollar-sign", "scope": "hr:read"},
        ],
    },
]


def get_navigation_context(user: Optional[Principal]) -> List[Dict[str, Any]]:
    """Get filtered navigation based on user permissions.

    Removes sections where user has no access to any items.
    """
    if not user:
        return []

    result = []
    for section in NAVIGATION_ITEMS:
        filtered_items = []
        for item in section["items"]:
            # No scope required or user has scope
            if item["scope"] is None or user.has_scope(item["scope"]):
                filtered_items.append(item)

        if filtered_items:
            result.append({
                "section": section["section"],
                "items": filtered_items,
            })

    return result

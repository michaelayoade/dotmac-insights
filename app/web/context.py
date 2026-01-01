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

from typing import Optional, Dict, Any, List, cast

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


def build_breadcrumbs(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
# Note: Using "links" instead of "items" to avoid conflict with dict.items()
# Section can have optional "href" for clickable module dashboards
NAVIGATION_ITEMS: List[Dict[str, Any]] = [
    {
        "section": "Main",
        "links": [
            {"label": "Dashboard", "href": "/", "icon": "home", "scope": None},
        ],
    },
    {
        "section": "CRM",
        "href": "/crm",
        "scope": "crm:read",
        "links": [
            {"label": "Contacts", "href": "/crm/contacts", "icon": "users", "scope": "crm:read"},
            {"label": "Opportunities", "href": "/crm/opportunities", "icon": "trending-up", "scope": "crm:read"},
            {"label": "Pipeline", "href": "/crm/pipeline", "icon": "git-branch", "scope": "crm:read"},
        ],
    },
    {
        "section": "Support",
        "href": "/support",
        "scope": "support:read",
        "links": [
            {"label": "Tickets", "href": "/support/tickets", "icon": "life-buoy", "scope": "support:read"},
            {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open", "scope": "support:read"},
        ],
    },
    {
        "section": "Finance",
        "href": "/finance",
        "scope": "accounting:read",
        "links": [
            {"label": "Invoices", "href": "/accounting/invoices", "icon": "file-text", "scope": "accounting:read"},
            {"label": "Payments", "href": "/accounting/payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Expenses", "href": "/expenses", "icon": "receipt", "scope": "expenses:read"},
        ],
    },
    {
        "section": "Operations",
        "href": "/operations",
        "scope": "inventory:read",
        "links": [
            {"label": "Inventory", "href": "/inventory", "icon": "package", "scope": "inventory:read"},
            {"label": "Projects", "href": "/projects", "icon": "folder", "scope": "projects:read"},
            {"label": "Field Service", "href": "/field-service", "icon": "truck", "scope": "field_service:read"},
        ],
    },
    {
        "section": "HR",
        "href": "/hr/",
        "scope": "hr:read",
        "links": [
            {"label": "Employees", "href": "/hr/employees", "icon": "users", "scope": "hr:read"},
            {"label": "Leave", "href": "/hr/leave", "icon": "calendar", "scope": "hr:read"},
            {"label": "Payroll", "href": "/hr/payroll", "icon": "dollar-sign", "scope": "hr:read"},
        ],
    },
    {
        "section": "Analytics",
        "href": "/analytics",
        "scope": "analytics:read",
        "links": [
            {"label": "Dashboard", "href": "/analytics", "icon": "chart-bar", "scope": "analytics:read"},
            {"label": "Revenue", "href": "/analytics/revenue", "icon": "dollar-sign", "scope": "analytics:read"},
            {"label": "Customers", "href": "/analytics/customers", "icon": "users", "scope": "analytics:read"},
            {"label": "Support", "href": "/analytics/support", "icon": "life-buoy", "scope": "analytics:read"},
            {"label": "Operations", "href": "/analytics/operations", "icon": "truck", "scope": "analytics:read"},
            {"label": "Insights", "href": "/analytics/insights", "icon": "trending-up", "scope": "analytics:read"},
        ],
    },
    {
        "section": "Settings",
        "links": [
            {"label": "Settings", "href": "/settings", "icon": "cog", "scope": "settings:read"},
        ],
    },
]


def get_navigation_context(user: Optional[Principal]) -> List[Dict[str, Any]]:
    """Get filtered navigation based on user permissions.

    Removes sections where user has no access to any links.
    Includes section href for clickable module dashboards.
    """
    if not user:
        return []

    result = []
    for section in NAVIGATION_ITEMS:
        filtered_links = []
        for link in section["links"]:
            # No scope required or user has scope
            link_scope = cast(Optional[str], link.get("scope"))
            if link_scope is None or user.has_scope(link_scope):
                filtered_links.append(link)

        if filtered_links:
            section_data = {
                "section": section["section"],
                "links": filtered_links,
            }
            # Include section href if user has permission
            if section.get("href"):
                section_scope = cast(Optional[str], section.get("scope"))
                if section_scope is None or user.has_scope(section_scope):
                    section_data["href"] = section["href"]
            result.append(section_data)

    return result

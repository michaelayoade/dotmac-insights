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
import logging

from fastapi import Request, Response

from app.auth import Principal
from app.config import settings
from app.core.security import get_flash, FlashMessage
from app.currency import get_currency_symbol

logger = logging.getLogger(__name__)


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

    module_registry = get_module_registry(user)
    active_module = resolve_active_module(request.url.path, module_registry)

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
        "currency_symbol": get_currency_symbol(settings.base_currency),

        # Environment
        "is_production": settings.is_production,
        "environment": settings.environment,

        # Modules
        "module_registry": module_registry,
        "active_module": active_module,
        "active_module_id": active_module["id"] if active_module else None,
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
    base_url: str = "",
    htmx_target: str = "",
) -> Dict[str, Any]:
    """Build pagination context for templates.

    Args:
        page: Current page (1-indexed)
        per_page: Items per page
        total: Total item count
        base_url: Base URL for pagination links (e.g., "/crm/contacts")
        htmx_target: HTMX target selector for partial updates (e.g., "#contacts-table")

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
        "base_url": base_url,
        "htmx_target": htmx_target,
    }


# Navigation structure for sidebar - Comprehensive navigation with all pages
# Note: Using "links" instead of "items" to avoid conflict with dict.items()
# Section can have optional "href" for clickable module landing pages
MODULE_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "customer",
        "label": "Customer",
        "href": "/crm",
        "icon": "users",
        "scopes": ["crm:read", "sales:read", "support:read"],
        "prefixes": [
            "/crm",
            "/sales",
            "/support",
            "/inbox",
            "/parties",
            "/accounting/invoices",
            "/accounting/credit-notes",
        ],
        "group": "Customer",
    },
    {
        "id": "finance",
        "label": "Finance",
        "href": "/accounting",
        "icon": "book",
        "scopes": ["accounting:read", "purchasing:read", "expenses:read", "assets:read", "reports:read"],
        "prefixes": [
            "/accounting",
            "/purchasing",
            "/expenses",
            "/assets",
            "/reports",
            "/suppliers",
        ],
        "group": "Finance",
    },
    {
        "id": "operations",
        "label": "Operations",
        "href": "/operations",
        "icon": "truck",
        "scopes": ["operations:read", "projects:read", "field_service:read", "inventory:read"],
        "prefixes": [
            "/operations",
            "/projects",
            "/field-service",
            "/inventory",
            "/vehicles",
        ],
        "group": "Operations",
    },
    {
        "id": "isp",
        "label": "ISP",
        "href": "/subscriptions",
        "icon": "globe",
        "scopes": ["subscriptions:read", "network:read", "noc:read"],
        "prefixes": [
            "/subscriptions",
            "/network",
        ],
        "group": "ISP",
    },
    {
        "id": "hr",
        "label": "Human Resources",
        "href": "/hr",
        "icon": "users",
        "scopes": ["hr:read", "performance:read"],
        "prefixes": [
            "/hr",
            "/performance",
        ],
        "group": "People Ops",
    },
]



def get_module_registry(user: Optional[Principal]) -> List[Dict[str, Any]]:
    """Filter modules based on user scopes.

    Combines:
    1. Hardcoded MODULE_REGISTRY (legacy modules)
    2. Auto-discovered modules from ModuleRegistry (new modular system)

    Auto-discovered modules take precedence if they have the same ID.
    """
    from app.web.modules import ModuleRegistry

    if not user:
        return []

    user_scopes = list(user.scopes) if user.scopes else []
    seen_ids = set()
    visible = []

    # First, add auto-discovered modules (they take precedence)
    for module_dict in ModuleRegistry.get_module_registry(user_scopes):
        module_id = module_dict.get("id")
        if module_id:
            seen_ids.add(module_id)
        visible.append(module_dict)

    # Then, add legacy hardcoded modules (if not already added)
    for module in MODULE_REGISTRY:
        module_id = module.get("id")
        if module_id and module_id in seen_ids:
            continue  # Already added from auto-discovery

        scopes = module.get("scopes") or []
        if not scopes or any(user.has_scope(scope) for scope in scopes):
            visible.append(module)

    return visible


def resolve_active_module(
    current_path: str,
    modules: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Pick the best matching module based on URL prefixes."""
    best_match = None
    best_len = 0

    for module in modules:
        for prefix in module.get("prefixes", []):
            if current_path == prefix or current_path.startswith(prefix.rstrip("/") + "/"):
                if len(prefix) > best_len:
                    best_match = module
                    best_len = len(prefix)

    if best_match:
        return best_match

    return modules[0] if modules else None


def get_navigation_context(user: Optional[Principal]) -> List[Dict[str, Any]]:
    """Get filtered navigation based on user permissions.

    Returns grouped navigation structure for sidebar:
    [
        {"label": "Customer", "sections": [...]},
        {"label": "Finance", "sections": [...]},
        ...
    ]
    """
    from app.web.modules import ModuleRegistry

    if not user:
        return []

    user_scopes = list(user.scopes) if user.scopes else []
    allow_all = user.is_superuser or "*" in user_scopes or not user_scopes

    ModuleRegistry.discover_modules()
    modules = ModuleRegistry.get_all()
    if not modules:
        logger.warning("Navigation build found no registered modules")

    # Group sections by module group
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for module in sorted(
        ModuleRegistry.get_all(),
        key=lambda m: (m.config.group, m.config.order, m.config.name),
    ):
        group_name = module.config.group

        for section in sorted(module.navigation, key=lambda s: s.order):
            if not allow_all and section.scope and not user.has_scope(section.scope):
                continue

            filtered_links = []
            for link in section.links:
                if not allow_all and link.scope and not user.has_scope(link.scope):
                    continue
                filtered_links.append({
                    "label": link.label,
                    "href": link.href,
                    "icon": link.icon,
                    "badge": link.badge,
                })

            if not filtered_links:
                continue

            section_data = {
                "section": section.section,
                "href": section.href,
                "icon": section.icon,
                "module": module.id,
                "links": filtered_links,
            }

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(section_data)

    # Convert to list format expected by template
    result = []
    for group_name, sections in groups.items():
        if sections:
            result.append({
                "label": group_name,
                "sections": sections,
            })

    if not result:
        logger.warning(
            "Navigation build produced no sections (modules=%s, scopes=%s, allow_all=%s)",
            len(modules),
            user_scopes,
            allow_all,
        )
    return result

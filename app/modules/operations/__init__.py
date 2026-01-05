"""
Operations Module - Operations Dashboard and Overview.

Consolidates projects, field service, inventory, assets, and vehicles
into a unified operations view.

Routes:
- /operations - Operations dashboard
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="operations",
    name="Operations",
    description="Inventory, projects, and field service operations",
    icon="truck",
    prefix="/operations",
    group="Operations",
    order=45,
    scopes=["operations:read", "inventory:read", "projects:read", "field_service:read"],
    prefixes=["/operations", "/inventory", "/projects", "/field-service", "/vehicles"],
)

NAVIGATION = [
    {
        "section": "Operations",
        "module": "operations",
        "href": "/operations",
        "icon": "truck",
        "scope": "operations:read",
        "order": 45,
        "links": [
            {"label": "Dashboard", "href": "/operations", "icon": "home"},
        ],
    },
    {
        "section": "Inventory",
        "module": "operations",
        "href": "/inventory",
        "icon": "package",
        "scope": "inventory:read",
        "order": 50,
        "links": [
            {"label": "Warehouses", "href": "/inventory", "icon": "package", "scope": "inventory:read"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries", "icon": "list", "scope": "inventory:read"},
        ],
    },
    {
        "section": "Projects",
        "module": "operations",
        "href": "/projects",
        "icon": "folder",
        "scope": "projects:read",
        "order": 60,
        "links": [
            {"label": "Projects", "href": "/projects", "icon": "folder", "scope": "projects:read"},
            {"label": "Tasks", "href": "/projects/tasks", "icon": "check-square", "scope": "projects:read"},
            {"label": "Milestones", "href": "/projects/milestones", "icon": "flag", "scope": "projects:read"},
        ],
    },
    {
        "section": "Field Services",
        "module": "operations",
        "href": "/field-service",
        "icon": "truck",
        "scope": "field_service:read",
        "order": 70,
        "links": [
            {"label": "Work Orders", "href": "/field-service", "icon": "truck", "scope": "field_service:read"},
            {"label": "Teams", "href": "/field-service/teams", "icon": "users", "scope": "field_service:read"},
            {"label": "Technicians", "href": "/field-service/technicians", "icon": "user", "scope": "field_service:read"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

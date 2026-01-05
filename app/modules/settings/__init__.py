"""
Settings Module - Centralized Settings Management UI.

Provides web interfaces for:
- General settings (email, payments, webhooks, SMS, notifications, branding, localization)
- Admin (users, roles, permissions, service tokens, audit log)
- Module settings (Books, HR, Support, Assets)
- Data sync and migration tools
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="settings",
    name="Settings",
    description="System configuration, admin, and module settings",
    icon="settings",
    prefix="/settings",
    group="System",
    order=100,
    scopes=["settings:read"],
    prefixes=["/settings"],
)

NAVIGATION = [
    {
        "section": "Settings",
        "module": "settings",
        "href": "/settings",
        "icon": "settings",
        "scope": "settings:read",
        "order": 100,
        "links": [
            {"label": "General", "href": "/settings", "icon": "settings"},
            {"label": "Accounting", "href": "/settings/books", "icon": "book"},
            {"label": "HR Settings", "href": "/settings/hr", "icon": "users"},
            {"label": "Support Settings", "href": "/settings/support", "icon": "life-buoy"},
            {"label": "Asset Settings", "href": "/settings/assets", "icon": "box"},
            {"label": "Data Sync", "href": "/settings/sync", "icon": "refresh-cw"},
            {"label": "Data Migration", "href": "/settings/migration", "icon": "upload"},
            {"label": "Data Cleanup", "href": "/settings/data-cleanup", "icon": "check-circle"},
            {"label": "Data Cleaner", "href": "/settings/data-cleaner", "icon": "edit-3"},
        ],
    },
    {
        "section": "Admin",
        "module": "settings",
        "href": "/settings/admin",
        "icon": "shield",
        "scope": "admin:read",
        "order": 110,
        "links": [
            {"label": "Users", "href": "/settings/admin/users", "icon": "users"},
            {"label": "Roles", "href": "/settings/admin/roles", "icon": "shield"},
            {"label": "Groups", "href": "/settings/admin/groups", "icon": "users"},
            {"label": "Permissions", "href": "/settings/admin/permissions", "icon": "lock"},
            {"label": "Sessions", "href": "/settings/admin/sessions", "icon": "clock"},
            {"label": "API Tokens", "href": "/settings/admin/tokens", "icon": "key"},
            {"label": "Webhooks", "href": "/settings/admin/webhooks", "icon": "link"},
            {"label": "Audit Log", "href": "/settings/admin/audit", "icon": "activity"},
            {"label": "Activity Log", "href": "/settings/admin/activity", "icon": "activity"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

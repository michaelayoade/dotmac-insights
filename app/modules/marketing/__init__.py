"""
Marketing Module - Journeys, Campaigns, Social, and Email.

Routes:
- /marketing - Dashboard
- /marketing/campaigns - Campaign management
- /marketing/journeys - Journey list
- /marketing/journeys/templates - Template gallery
- /marketing/social/* - Social calendar, compose, posts, accounts
- /marketing/email/* - Email campaigns, templates, analytics
- /marketing/audiences - Audience segments
- /marketing/integrations - Integrations
- /marketing/consent - Consent management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="marketing",
    name="Marketing",
    description="Journeys, campaigns, social media, and email marketing",
    icon="target",
    prefix="/marketing",
    group="Marketing",
    order=30,
    scopes=["marketing:read"],
    enabled=True,
    prefixes=["/marketing"],
)

NAVIGATION = [
    {
        "section": "Marketing",
        "module": "marketing",
        "href": "/marketing",
        "icon": "target",
        "scope": "marketing:read",
        "order": 30,
        "links": [
            {"label": "Dashboard", "href": "/marketing", "icon": "home"},
            {"label": "Campaigns", "href": "/marketing/campaigns", "icon": "list"},
            {"label": "Journeys", "href": "/marketing/journeys", "icon": "repeat"},
            {"label": "Journey Templates", "href": "/marketing/journeys/templates", "icon": "folder"},
        ],
    },
    {
        "section": "Social Media",
        "module": "marketing",
        "href": "/marketing/social",
        "icon": "globe",
        "scope": "marketing:read",
        "order": 31,
        "links": [
            {"label": "Calendar", "href": "/marketing/social/calendar", "icon": "calendar"},
            {"label": "Compose", "href": "/marketing/social/compose", "icon": "edit"},
            {"label": "Posts", "href": "/marketing/social/posts", "icon": "list"},
            {"label": "Accounts", "href": "/marketing/social/accounts", "icon": "users"},
        ],
    },
    {
        "section": "Email",
        "module": "marketing",
        "href": "/marketing/email",
        "icon": "inbox",
        "scope": "marketing:read",
        "order": 32,
        "links": [
            {"label": "Campaigns", "href": "/marketing/email/campaigns", "icon": "inbox"},
            {"label": "Templates", "href": "/marketing/email/templates", "icon": "file-text"},
            {"label": "Analytics", "href": "/marketing/email/analytics", "icon": "chart-bar"},
        ],
    },
    {
        "section": "Configuration",
        "module": "marketing",
        "href": "/marketing/settings",
        "icon": "settings",
        "scope": "marketing:read",
        "order": 33,
        "links": [
            {"label": "Audiences", "href": "/marketing/audiences", "icon": "users"},
            {"label": "Integrations", "href": "/marketing/integrations", "icon": "settings"},
            {"label": "Consent", "href": "/marketing/consent", "icon": "check-circle"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

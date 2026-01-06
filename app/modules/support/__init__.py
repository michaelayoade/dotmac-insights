"""
Support Module - Ticket Management and Customer Support.

Routes:
- /support/tickets - Ticket list and management
- /support/teams - Support team management
- /support/agents - Agent management
- /support/kb - Knowledge base articles
- /support/kb/categories - KB category management
- /support/canned-responses - Canned response templates
- /support/sla - SLA policy management
- /support/sla/calendars - Business calendar management
- /support/sla/breaches - SLA breach tracking
- /support/automation/logs - Automation log views
- /support/csat/analytics - Customer satisfaction analytics
- /support/tags - Tag management

Permission Requirements:
- support:read - View tickets and support data
- support:write - Create, update, delete support data
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="support",
    name="Support",
    description="Ticket management, knowledge base, and customer support",
    icon="life-buoy",
    prefix="/support",
    group="Customer",
    order=40,
    scopes=["support:read"],
    enabled=True,
    prefixes=["/support"],
)

NAVIGATION = [
    {
        "section": "Support Core",
        "module": "support",
        "href": "/support",
        "icon": "life-buoy",
        "scope": "support:read",
        "order": 40,
        "links": [
            {"label": "Dashboard", "href": "/support", "icon": "layout"},
            {"label": "Tickets", "href": "/support/tickets", "icon": "life-buoy"},
            {"label": "Conversations", "href": "/support/conversations", "icon": "message-circle"},
            {"label": "Queues", "href": "/support/queues", "icon": "list"},
            {"label": "Routing Rules", "href": "/support/routing", "icon": "shuffle"},
            {"label": "Teams", "href": "/support/teams", "icon": "users"},
            {"label": "Agents", "href": "/support/agents", "icon": "user"},
            {"label": "Escalations", "href": "/support/escalations", "icon": "arrow-up"},
            {"label": "Tags", "href": "/settings/support/tags", "icon": "tag"},
            {"label": "Channels", "href": "/support/channels", "icon": "wifi"},
        ],
    },
    {
        "section": "Knowledge Base",
        "module": "support",
        "href": "/support/kb",
        "icon": "book-open",
        "scope": "support:read",
        "order": 41,
        "links": [
            {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open"},
            {"label": "KB Categories", "href": "/support/kb/categories", "icon": "folder"},
            {"label": "Canned Responses", "href": "/support/canned-responses", "icon": "file-text"},
        ],
    },
    {
        "section": "Automation",
        "module": "support",
        "href": "/support/automation",
        "icon": "cpu",
        "scope": "support:read",
        "order": 42,
        "links": [
            {"label": "Automation Rules", "href": "/support/automation", "icon": "cpu"},
            {"label": "Automation Logs", "href": "/support/automation/logs", "icon": "activity"},
        ],
    },
    {
        "section": "Policies",
        "module": "support",
        "href": "/support/sla",
        "icon": "clock",
        "scope": "support:read",
        "order": 43,
        "links": [
            {"label": "SLA Policies", "href": "/support/sla", "icon": "clock"},
            {"label": "SLA Calendars", "href": "/support/sla/calendars", "icon": "calendar"},
            {"label": "SLA Breaches", "href": "/support/sla/breaches", "icon": "alert-circle"},
        ],
    },
    {
        "section": "Analytics",
        "module": "support",
        "href": "/support/csat/analytics",
        "icon": "bar-chart",
        "scope": "support:read",
        "order": 44,
        "links": [
            {"label": "CSAT Analytics", "href": "/support/csat/analytics", "icon": "bar-chart"},
        ],
    },
    {
        "section": "Administration",
        "module": "support",
        "href": "/support/webhooks",
        "icon": "settings",
        "scope": "support:read",
        "order": 45,
        "links": [
            {"label": "Webhooks", "href": "/support/webhooks", "icon": "rss"},
            {"label": "Support Settings", "href": "/settings/support", "icon": "settings"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

"""
Omnichannel Module - Unified Inbox & Conversations.

Routes:
- /inbox - Unified inbox
- /inbox/conversations - Conversation management
- /inbox/contacts - Contact management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="omnichannel",
    name="Inbox",
    description="Unified inbox and customer conversations",
    icon="inbox",
    prefix="/inbox",
    group="Operations",
    order=42,
    scopes=["support:read"],
    prefixes=["/inbox"],
)

NAVIGATION = [
    {
        "section": "Inbox",
        "module": "omnichannel",
        "href": "/inbox",
        "icon": "inbox",
        "scope": "support:read",
        "order": 42,
        "links": [
            {"label": "Inbox", "href": "/inbox", "icon": "inbox"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

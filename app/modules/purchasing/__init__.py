"""
Purchasing Module - Purchase Order Management.

Routes:
- /purchasing - Purchase order list
- /purchasing/{id} - Purchase order detail
- /purchasing/new - Create purchase order
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="purchasing",
    name="Purchasing",
    description="Purchase orders and procurement",
    icon="file-text",
    prefix="/purchasing",
    group="Back Office",
    order=24,
    scopes=["purchasing:read"],
    enabled=False,
    prefixes=["/purchasing"],
)

NAVIGATION = [
    {
        "section": "Purchasing",
        "module": "purchasing",
        "href": "/purchasing",
        "icon": "file-text",
        "scope": "purchasing:read",
        "order": 24,
        "links": [
            {"label": "Purchase Orders", "href": "/purchasing", "icon": "file-text"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

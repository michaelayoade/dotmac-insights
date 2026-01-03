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
    description="Operations dashboard and overview",
    icon="truck",
    prefix="/operations",
    group="Operations",
    order=45,
    scopes=["operations:read"],
    prefixes=["/operations"],
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
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

"""
Vehicles Module - Fleet Management.

Routes:
- /vehicles - Vehicle list
- /vehicles/{id} - Vehicle detail
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="vehicles",
    name="Vehicles",
    description="Fleet management and vehicle tracking",
    icon="truck",
    prefix="/vehicles",
    group="Facility",
    order=70,
    scopes=["vehicles:read"],
    prefixes=["/vehicles"],
)

NAVIGATION = [
    {
        "section": "Vehicles",
        "module": "vehicles",
        "href": "/vehicles",
        "icon": "truck",
        "scope": "vehicles:read",
        "order": 70,
        "links": [
            {"label": "All Vehicles", "href": "/vehicles", "icon": "truck"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

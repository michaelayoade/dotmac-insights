"""
Inventory Module - Warehouse and Stock Management.

Routes:
- /inventory - Warehouse list
- /inventory/stock-entries - Stock entry management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="inventory",
    name="Inventory",
    description="Warehouse and stock management",
    icon="package",
    prefix="/inventory",
    group="Operations",
    order=60,
    scopes=["inventory:read"],
    enabled=False,
    prefixes=["/inventory"],
)

NAVIGATION = [
    {
        "section": "Inventory",
        "module": "inventory",
        "href": "/inventory",
        "icon": "package",
        "scope": "inventory:read",
        "order": 60,
        "links": [
            {"label": "Warehouses", "href": "/inventory", "icon": "package"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries", "icon": "list"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

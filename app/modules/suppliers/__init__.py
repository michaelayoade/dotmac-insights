"""
Suppliers Module - Supplier Management.

Routes:
- /suppliers - Supplier list
- /suppliers/{id} - Supplier detail
- /suppliers/bills - Supplier bills
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="suppliers",
    name="Suppliers",
    description="Supplier management and bills",
    icon="truck",
    prefix="/suppliers",
    group="Procurement",
    order=23,
    scopes=["suppliers:read"],
    prefixes=["/suppliers"],
)

NAVIGATION = [
    {
        "section": "Suppliers",
        "module": "suppliers",
        "href": "/suppliers",
        "icon": "truck",
        "scope": "suppliers:read",
        "order": 23,
        "links": [
            {"label": "All Suppliers", "href": "/suppliers", "icon": "truck"},
            {"label": "Bills", "href": "/suppliers/bills", "icon": "receipt"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

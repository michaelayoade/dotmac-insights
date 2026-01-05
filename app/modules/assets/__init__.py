"""
Assets Module - Asset Management.

Routes:
- /assets - Asset list
- /assets/{id} - Asset detail
- /assets/categories - Asset category management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="assets",
    name="Assets",
    description="Fixed asset management and tracking",
    icon="box",
    prefix="/assets",
    group="Operations",
    order=65,
    scopes=["assets:read"],
    enabled=False,
    prefixes=["/assets"],
)

NAVIGATION = [
    {
        "section": "Assets",
        "module": "assets",
        "href": "/assets",
        "icon": "box",
        "scope": "assets:read",
        "order": 65,
        "links": [
            {"label": "All Assets", "href": "/assets", "icon": "box"},
            {"label": "Categories", "href": "/assets/categories", "icon": "folder"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

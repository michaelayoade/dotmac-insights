"""
Network Module - ISP Infrastructure Management.

Provides SSR pages for:
- Network Dashboard with health metrics
- POP (Point of Presence) management
- Router/NAS management
- IP Address management (IPv4/IPv6)
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="network",
    name="Network",
    description="ISP infrastructure, POPs, routers, and IP management",
    icon="globe",
    prefix="/network",
    group="Infrastructure",
    order=10,
    scopes=["network:read"],
    prefixes=["/network"],
)

NAVIGATION = [
    {
        "section": "Network",
        "module": "network",
        "href": "/network",
        "icon": "globe",
        "scope": "network:read",
        "order": 10,
        "links": [
            {"label": "Dashboard", "href": "/network", "icon": "home"},
            {"label": "POPs", "href": "/network/pops", "icon": "map-pin"},
            {"label": "Routers", "href": "/network/routers", "icon": "server"},
            {"label": "IP Management", "href": "/network/ip", "icon": "globe"},
            {"label": "Networks", "href": "/network/ip/networks", "icon": "globe"},
            {"label": "Addresses", "href": "/network/ip/addresses", "icon": "list"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

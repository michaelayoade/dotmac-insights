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
    id="isp",
    name="ISP",
    description="Subscriptions, network operations, and monitoring",
    icon="globe",
    prefix="/subscriptions",
    group="ISP",
    order=15,
    scopes=["subscriptions:read", "network:read", "noc:read"],
    prefixes=["/subscriptions", "/network"],
)

NAVIGATION = [
    {
        "section": "Subscriptions",
        "module": "isp",
        "href": "/subscriptions",
        "icon": "repeat",
        "scope": "subscriptions:read",
        "order": 10,
        "links": [
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat", "scope": "subscriptions:read"},
            {"label": "Tariffs", "href": "/subscriptions/tariffs", "icon": "list", "scope": "subscriptions:read"},
            {"label": "Payments", "href": "/subscriptions/payments", "icon": "credit-card", "scope": "subscriptions:read"},
        ],
    },
    {
        "section": "Network",
        "module": "isp",
        "href": "/network",
        "icon": "globe",
        "scope": "network:read",
        "order": 20,
        "links": [
            {"label": "POPs", "href": "/network/pops", "icon": "map-pin", "scope": "network:read"},
            {"label": "Routers", "href": "/network/routers", "icon": "server", "scope": "network:read"},
            {"label": "IP Management", "href": "/network/ip", "icon": "globe", "scope": "network:read"},
            {"label": "Networks", "href": "/network/ip/networks", "icon": "globe", "scope": "network:read"},
            {"label": "Addresses", "href": "/network/ip/addresses", "icon": "list", "scope": "network:read"},
        ],
    },
    {
        "section": "Monitoring",
        "module": "isp",
        "href": "/network/noc",
        "icon": "activity",
        "scope": "noc:read",
        "order": 30,
        "links": [
            {"label": "Alerts", "href": "/network/noc/alerts", "icon": "alert-circle", "scope": "noc:read"},
            {"label": "Uptime", "href": "/network/noc", "icon": "activity", "scope": "noc:read"},
            {"label": "Performance", "href": "/network/traffic", "icon": "bar-chart-2", "scope": "noc:read"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router
from .noc_routes import router as noc_router
from .traffic_routes import router as traffic_router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router", "noc_router", "traffic_router"]

"""
Subscriptions Module - Service and Payment Subscription Management.

Manages service subscriptions (internet, voice, bundles),
payment subscriptions, and tariff management.

Routes:
- /subscriptions - Subscription list and management
- /subscriptions/tariffs - Tariff plan management
- /subscriptions/payments - Subscription payment tracking
"""
from __future__ import annotations

from fastapi import APIRouter

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="subscriptions",
    name="Subscriptions",
    description="Service subscriptions, tariffs, and recurring billing",
    icon="repeat",
    prefix="/subscriptions",
    group="Infrastructure",
    order=15,
    scopes=["subscriptions:read"],
    prefixes=["/subscriptions"],
)

NAVIGATION = [
    {
        "section": "Subscriptions",
        "module": "subscriptions",
        "href": "/subscriptions",
        "icon": "repeat",
        "scope": "subscriptions:read",
        "order": 15,
        "links": [
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat"},
            {"label": "Tariffs", "href": "/subscriptions/tariffs", "icon": "list"},
            {"label": "Payments", "href": "/subscriptions/payments", "icon": "credit-card"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

# Import sub-routers
from .routes import router as subscriptions_router
from .tariff_routes import router as tariff_router
from .payment_routes import router as payment_router

# Create combined router
router = APIRouter(tags=["subscriptions"])
router.include_router(subscriptions_router)
router.include_router(tariff_router)
router.include_router(payment_router)

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

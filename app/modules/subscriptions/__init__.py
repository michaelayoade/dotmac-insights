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
    description="Service subscriptions, lifecycle, billing, and network operations",
    icon="repeat",
    prefix="/subscriptions",
    group="Infrastructure",
    order=15,
    scopes=["subscriptions:read"],
    enabled=True,
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
            {"label": "Dashboard", "href": "/subscriptions/dashboard", "icon": "bar-chart"},
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat"},
            {"label": "Usage", "href": "/subscriptions/usage", "icon": "activity"},
            {"label": "Sessions", "href": "/subscriptions/sessions", "icon": "globe"},
            {"label": "Provisioning", "href": "/subscriptions/provisioning", "icon": "server"},
            {"label": "Transactions", "href": "/subscriptions/transactions", "icon": "receipt"},
            {"label": "Billing", "href": "/subscriptions/billing", "icon": "credit-card"},
            {"label": "Finance", "href": "/subscriptions/finance", "icon": "dollar-sign"},
            {"label": "Tariffs", "href": "/subscriptions/tariffs", "icon": "list"},
            {"label": "Data Bundles", "href": "/subscriptions/bundles", "icon": "package"},
            {"label": "Payments", "href": "/subscriptions/payments", "icon": "credit-card"},
            {"label": "Settings", "href": "/subscriptions/settings", "icon": "settings"},
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
from .service_routes import router as service_router
from .bundle_routes import router as bundle_router

# Create combined router
router = APIRouter(tags=["subscriptions"])
router.include_router(subscriptions_router)
router.include_router(tariff_router)
router.include_router(payment_router)
router.include_router(service_router)
router.include_router(bundle_router)

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

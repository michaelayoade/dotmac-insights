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
    group="ISP",
    order=15,
    scopes=["subscriptions:read"],
    enabled=True,
    prefixes=["/subscriptions"],
)

NAVIGATION = [
    {
        "section": "Overview",
        "module": "subscriptions",
        "href": "/subscriptions",
        "icon": "repeat",
        "scope": "subscriptions:read",
        "order": 10,
        "links": [
            {"label": "Dashboard", "href": "/subscriptions/dashboard", "icon": "bar-chart"},
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat"},
        ],
    },
    {
        "section": "Usage & Sessions",
        "module": "subscriptions",
        "href": "/subscriptions/usage",
        "icon": "activity",
        "scope": "subscriptions:read",
        "order": 20,
        "links": [
            {"label": "Usage", "href": "/subscriptions/usage", "icon": "activity"},
            {"label": "Sessions", "href": "/subscriptions/sessions", "icon": "globe"},
        ],
    },
    {
        "section": "Billing",
        "module": "subscriptions",
        "href": "/subscriptions/billing",
        "icon": "credit-card",
        "scope": "subscriptions:read",
        "order": 30,
        "links": [
            {"label": "Transactions", "href": "/subscriptions/transactions", "icon": "receipt"},
            {"label": "Billing", "href": "/subscriptions/billing", "icon": "credit-card"},
            {"label": "Finance", "href": "/subscriptions/finance", "icon": "dollar-sign"},
            {"label": "Payments", "href": "/subscriptions/payments", "icon": "credit-card"},
        ],
    },
    {
        "section": "Products",
        "module": "subscriptions",
        "href": "/subscriptions/tariffs",
        "icon": "list",
        "scope": "subscriptions:read",
        "order": 40,
        "links": [
            {"label": "Tariffs", "href": "/subscriptions/tariffs", "icon": "list"},
            {"label": "Data Bundles", "href": "/subscriptions/bundles", "icon": "package"},
        ],
    },
    {
        "section": "Configuration",
        "module": "subscriptions",
        "href": "/subscriptions/provisioning",
        "icon": "settings",
        "scope": "subscriptions:read",
        "order": 50,
        "links": [
            {"label": "Provisioning", "href": "/subscriptions/provisioning", "icon": "server"},
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

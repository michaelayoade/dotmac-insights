"""
Payments Module - Payment Processing and Tracking.

Routes:
- /payments - Payment list and search
- /payments/{id} - Payment detail view
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="payments",
    name="Payments",
    description="Payment processing and tracking",
    icon="credit-card",
    prefix="/payments",
    group="Procurement",
    order=26,
    scopes=["payments:read"],
    prefixes=["/payments"],
)

NAVIGATION = [
    {
        "section": "Payments",
        "module": "payments",
        "href": "/payments",
        "icon": "credit-card",
        "scope": "payments:read",
        "order": 26,
        "links": [
            {"label": "All Payments", "href": "/payments", "icon": "credit-card"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

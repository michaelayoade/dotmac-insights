"""
Customers Module - Customer Account Management.

Routes:
- /customers - Customer list and search
- /customers/{id} - Customer detail view
- /customers/new - Create new customer
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="customers",
    name="Customers",
    description="Customer account management and profiles",
    icon="users",
    prefix="/customers",
    group="CRM",
    order=5,
    scopes=["customers:read"],
    prefixes=["/customers"],
)

NAVIGATION = [
    {
        "section": "Customers",
        "module": "customers",
        "href": "/customers",
        "icon": "users",
        "scope": "customers:read",
        "order": 5,
        "links": [
            {"label": "All Customers", "href": "/customers", "icon": "users"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

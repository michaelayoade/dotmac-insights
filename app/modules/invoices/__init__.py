"""
Invoices Module - Customer Invoice Management.

Routes:
- /invoices - Invoice list and search
- /invoices/{id} - Invoice detail view
- /invoices/new - Create new invoice
- /invoices/credit-notes - Credit notes management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="invoices",
    name="Invoices",
    description="Customer invoicing and credit notes",
    icon="credit-card",
    prefix="/invoices",
    group="Back Office",
    order=12,
    scopes=["accounting:read"],
    prefixes=["/invoices"],
)

NAVIGATION = [
    {
        "section": "Invoices",
        "module": "invoices",
        "href": "/invoices",
        "icon": "credit-card",
        "scope": "accounting:read",
        "order": 12,
        "links": [
            {"label": "All Invoices", "href": "/invoices", "icon": "credit-card"},
            {"label": "Credit Notes", "href": "/invoices/credit-notes", "icon": "file-minus"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

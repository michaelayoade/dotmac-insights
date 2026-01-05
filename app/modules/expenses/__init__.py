"""
Expenses Module - Expense Claims Management.

Routes:
- /expenses - Expense claim list
- /expenses/{id} - Expense detail view
- /expenses/categories - Expense category management
- /expenses/advances - Travel advances
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="expenses",
    name="Expenses",
    description="Expense claims, categories, and advances",
    icon="receipt",
    prefix="/expenses",
    group="Back Office",
    order=25,
    scopes=["expenses:read"],
    enabled=False,
    prefixes=["/expenses"],
)

NAVIGATION = [
    {
        "section": "Expenses",
        "module": "expenses",
        "href": "/expenses",
        "icon": "receipt",
        "scope": "expenses:read",
        "order": 25,
        "links": [
            {"label": "Expense Claims", "href": "/expenses", "icon": "receipt"},
            {"label": "Categories", "href": "/expenses/categories", "icon": "list"},
            {"label": "Advances", "href": "/expenses/advances", "icon": "dollar-sign"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

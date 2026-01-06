"""
Finance Module - Financial analytics, metrics, and reporting.

Routes:
- /finance - Dashboard (landing page with KPIs)
- /finance/analytics - Analytics overview
- /finance/analytics/collections - Collections metrics
- /finance/analytics/aging - Invoice aging report
- /finance/analytics/revenue - Revenue trends
- /finance/analytics/currency - Multi-currency breakdown
- /finance/insights - Insights overview
- /finance/insights/behavior - Payment behavior analysis
- /finance/insights/forecasts - Revenue forecasts
"""

from __future__ import annotations

from app.web.module_types import ModuleConfig

from .routes import router

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="finance",
    name="Finance",
    description="Financial analytics, revenue metrics, and reporting",
    icon="dollar-sign",
    prefix="/finance",
    group="Finance",
    order=25,
    scopes=["analytics:read"],
    prefixes=["/finance"],
)

NAVIGATION = [
    {
        "section": "Finance",
        "href": "/finance",
        "icon": "dollar-sign",
        "scope": "analytics:read",
        "order": 25,
        "links": [
            {"label": "Dashboard", "href": "/finance", "icon": "layout-dashboard", "scope": "analytics:read"},
            {"label": "Collections", "href": "/finance/analytics/collections", "icon": "credit-card", "scope": "analytics:read"},
            {"label": "Aging Report", "href": "/finance/analytics/aging", "icon": "clock", "scope": "analytics:read"},
            {"label": "Revenue Trends", "href": "/finance/analytics/revenue", "icon": "trending-up", "scope": "analytics:read"},
            {"label": "Payment Behavior", "href": "/finance/insights/behavior", "icon": "users", "scope": "analytics:read"},
            {"label": "Forecasts", "href": "/finance/insights/forecasts", "icon": "bar-chart", "scope": "analytics:read"},
        ],
    },
]

__all__ = ["router", "MODULE_CONFIG", "NAVIGATION"]

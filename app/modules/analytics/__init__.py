"""
Analytics Module - SSR Dashboard and Reports.

Provides comprehensive business analytics across all domains:
- Revenue metrics (MRR, DSO, Aging)
- Customer analytics (Segments, Health, Churn)
- Support analytics (SLA, Volume, Agent Performance)
- HR analytics (Leave, Payroll, Recruitment)
- Operations analytics (Field Service, Expenses)
- Data insights (Quality, Anomalies)
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="analytics",
    name="Analytics",
    description="Business intelligence and reporting dashboards",
    icon="activity",
    prefix="/analytics",
    group="Operations",
    order=80,
    scopes=["analytics:read"],
    enabled=False,
    prefixes=["/analytics"],
)

NAVIGATION = [
    {
        "section": "Analytics",
        "module": "analytics",
        "href": "/analytics",
        "icon": "activity",
        "scope": "analytics:read",
        "order": 80,
        "links": [
            {"label": "Insights", "href": "/analytics/insights", "icon": "activity"},
            {"label": "Revenue", "href": "/analytics/revenue", "icon": "dollar-sign"},
            {"label": "Customers", "href": "/analytics/customers", "icon": "users"},
            {"label": "Operations", "href": "/analytics/operations", "icon": "truck"},
            {"label": "HR Analytics", "href": "/analytics/hr", "icon": "users"},
            {"label": "Support Analytics", "href": "/analytics/support", "icon": "life-buoy"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

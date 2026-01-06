"""
Performance Module - Employee Performance Management.

Routes:
- /performance - Performance dashboard
- /performance/kpis - KPI management
- /performance/kras - KRA management
- /performance/scorecards - Performance scorecards
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="performance",
    name="Performance",
    description="KPIs, KRAs, and performance scorecards",
    icon="target",
    prefix="/performance",
    group="People",
    order=35,
    scopes=["performance:read"],
    prefixes=["/performance"],
)

NAVIGATION = [
    {
        "section": "Performance",
        "module": "performance",
        "href": "/performance",
        "icon": "target",
        "scope": "performance:read",
        "order": 35,
        "links": [
            {"label": "Dashboard", "href": "/performance", "icon": "target"},
            {"label": "KPIs", "href": "/performance/kpis", "icon": "activity"},
            {"label": "KRAs", "href": "/performance/kras", "icon": "target"},
            {"label": "Scorecards", "href": "/performance/scorecards", "icon": "bar-chart"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

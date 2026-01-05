"""
Field Service Module - Service Order and Technician Management.

Routes:
- /field-service - Service orders dashboard
- /field-service/teams - Field service team management
- /field-service/technicians - Technician management
- /field-service/calendar - Service calendar views
"""
from __future__ import annotations

from fastapi import APIRouter

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="field_service",
    name="Field Service",
    description="Service orders, technicians, and scheduling",
    icon="truck",
    prefix="/field-service",
    group="Operations",
    order=55,
    scopes=["field_service:read"],
    enabled=False,
    prefixes=["/field-service"],
)

NAVIGATION = [
    {
        "section": "Field Service",
        "module": "field_service",
        "href": "/field-service",
        "icon": "truck",
        "scope": "field_service:read",
        "order": 55,
        "links": [
            {"label": "Service Orders", "href": "/field-service", "icon": "truck"},
            {"label": "Teams", "href": "/field-service/teams", "icon": "users"},
            {"label": "Technicians", "href": "/field-service/technicians", "icon": "user"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

# Import sub-routers
from .routes import router as field_service_router
from .calendar_routes import router as calendar_router

# Create combined router
router = APIRouter(tags=["field_service"])
router.include_router(field_service_router)
router.include_router(calendar_router)

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]

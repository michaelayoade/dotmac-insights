"""Network API module.

This module provides a modular API structure for network infrastructure management,
with each sub-module handling a specific domain:

- pops: Points of Presence CRUD and statistics
- routers: Router/NAS CRUD and statistics
- ip_networks: IPv4/IPv6 network management
- ip_addresses: IP address management
- analytics: Network analytics and health insights

All endpoints delegate to services in app/services/network/.
Routes are thin wrappers that handle:
- Request validation
- Service invocation
- Transaction management (commit/rollback)
- Response formatting
"""
from fastapi import APIRouter

from .pops import router as pops_router
from .routers import router as routers_router
from .ip_networks import router as ip_networks_router
from .ip_addresses import router as ip_addresses_router
from .analytics import router as analytics_router

router = APIRouter(prefix="/network", tags=["network"])

# Include all sub-routers
router.include_router(pops_router)
router.include_router(routers_router)
router.include_router(ip_networks_router)
router.include_router(ip_addresses_router)
router.include_router(analytics_router)

__all__ = ["router"]

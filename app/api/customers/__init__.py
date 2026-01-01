"""
Customer API Package

Provides all customer-related endpoints:
- /dashboard - Key metrics and summary
- /360/{id} - Customer 360 view (all domains consolidated)
- / - List, search, filter customers
- /{id} - Customer detail with related data
- /{id}/usage - Bandwidth usage history
- /blocked - Blocked customers list
- /analytics/* - Signup trends, cohorts, distribution
- /insights/* - Segments, health, completeness
"""

from fastapi import APIRouter

from app.api.customers.dashboard import router as dashboard_router
from app.api.customers.customer_360 import router as customer_360_router
from app.api.customers.crud import router as crud_router
from app.api.customers.analytics import router as analytics_router
from app.api.customers.insights import router as insights_router

router = APIRouter()

# Include all module routers
router.include_router(dashboard_router)
router.include_router(customer_360_router)
router.include_router(crud_router)
router.include_router(analytics_router)
router.include_router(insights_router)

__all__ = ["router"]

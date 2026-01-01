"""
Dashboard API Package

Provides consolidated dashboard endpoints for improved frontend performance.
Each module contains related dashboard endpoints.
"""

from fastapi import APIRouter

from app.api.dashboards.sales import router as sales_router
from app.api.dashboards.finance import router as finance_router
from app.api.dashboards.hr import router as hr_router
from app.api.dashboards.operations import router as operations_router
from app.api.dashboards.support import router as support_router

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

# Include all module routers
router.include_router(sales_router)
router.include_router(finance_router)
router.include_router(hr_router)
router.include_router(operations_router)
router.include_router(support_router)

__all__ = ["router"]

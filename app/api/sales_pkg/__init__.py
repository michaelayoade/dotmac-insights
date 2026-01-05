"""
Sales API Package

Provides all sales-related endpoints:
- Dashboard, Invoices, Payments
- Orders, Quotations
- Customer Groups, Territories, Sales Persons
- Analytics, Insights
"""

from fastapi import APIRouter

from app.api.sales_pkg.dashboard import router as dashboard_router
from app.api.sales_pkg.invoices import router as invoices_router
from app.api.sales_pkg.payments import router as payments_router
from app.api.sales_pkg.orders import router as orders_router
from app.api.sales_pkg.masters import router as masters_router
from app.api.sales_pkg.analytics import router as analytics_router
from app.api.sales_pkg.insights import router as insights_router

router = APIRouter()

router.include_router(dashboard_router)
router.include_router(invoices_router)
router.include_router(payments_router)
router.include_router(orders_router)
router.include_router(masters_router)
router.include_router(analytics_router)
router.include_router(insights_router)

__all__ = ["router"]

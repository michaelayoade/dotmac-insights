"""Purchasing API module.

This module provides a modular API structure for purchasing/AP management:
- dashboard: Purchasing dashboard metrics
- bills: Purchase invoice CRUD
- suppliers: Supplier management
- payments: Vendor payments
- orders: Purchase orders
- debit_notes: Debit notes (returns)
- aging: AP aging reports
- analytics: Purchasing analytics
- expenses: GL expense entries

All endpoints delegate to services in app/services/purchasing/.
Routes are thin wrappers that handle request/response formatting.
"""
from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .bills import router as bills_router
from .suppliers import router as suppliers_router
from .payments import router as payments_router
from .debit_notes import router as debit_notes_router
from .aging import router as aging_router
from .analytics import router as analytics_router
from .expenses import router as expenses_router

router = APIRouter(prefix="/purchasing", tags=["purchasing"])

# Include all sub-routers
router.include_router(dashboard_router)
router.include_router(bills_router)
router.include_router(suppliers_router)
router.include_router(payments_router)
router.include_router(debit_notes_router)
router.include_router(aging_router)
router.include_router(analytics_router)
router.include_router(expenses_router)

__all__ = ["router"]

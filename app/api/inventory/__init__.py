"""Inventory API module.

This module provides a modular API structure for inventory management,
with each sub-module handling a specific domain:

- item_groups: Item group CRUD and hierarchy
- items: Item CRUD and stock queries
- warehouses: Warehouse CRUD and hierarchy
- stock_entries: Stock entries (material issue/receipt/transfer)
- stock_balance: Stock balance queries and valuation
- landed_costs: Landed cost voucher management
- transfers: Transfer request workflow
- batches: Batch tracking
- serials: Serial number tracking

All endpoints delegate to services in app/services/inventory/.
Routes are thin wrappers that handle:
- Request validation
- Service invocation
- Transaction management (commit/rollback)
- Response formatting
"""
from fastapi import APIRouter

from .item_groups import router as item_groups_router
from .items import router as items_router
from .warehouses import router as warehouses_router
from .stock_entries import router as stock_entries_router
from .stock_balance import router as stock_balance_router
from .landed_costs import router as landed_costs_router
from .transfers import router as transfers_router
from .batches import router as batches_router
from .serials import router as serials_router

router = APIRouter(prefix="/inventory", tags=["inventory"])

# Include all sub-routers
router.include_router(item_groups_router)
router.include_router(items_router)
router.include_router(warehouses_router)
router.include_router(stock_entries_router)
router.include_router(stock_balance_router)
router.include_router(landed_costs_router)
router.include_router(transfers_router)
router.include_router(batches_router)
router.include_router(serials_router)

__all__ = ["router"]

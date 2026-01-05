"""Inventory management services.

This package contains all inventory-related business logic:
- WarehouseService: Warehouse CRUD and hierarchy management
- StockEntryService: Stock entries (material issue/receipt/transfer)
- StockBalanceService: Stock balance queries and valuation
- TransferRequestService: Transfer request workflow
- ItemGroupService: Item group CRUD and hierarchy
- ItemService: Item CRUD and stock queries
- LandedCostService: Landed cost voucher management
- BatchService: Batch tracking and expiry management
- SerialService: Serial number tracking and lifecycle

Usage:
    from app.services.inventory import WarehouseService, StockEntryService

    def my_route(db: Session = Depends(get_db)):
        warehouse_service = WarehouseService(db, principal)
        warehouses = warehouse_service.list_warehouses(filters, pagination)
        db.commit()  # Routes control transaction
"""
from .warehouses import WarehouseService
from .stock_entries import StockEntryService
from .stock_balance import StockBalanceService
from .transfers import TransferRequestService
from .item_groups import ItemGroupService
from .items import ItemService
from .landed_costs import LandedCostService
from .batches import BatchService
from .serials import SerialService

from .types import (
    # Enums
    StockEntryType,
    TransferStatus,
    # Warehouse types
    WarehouseFilters,
    WarehouseCreateData,
    WarehouseUpdateData,
    # Stock entry types
    StockEntryFilters,
    StockEntryCreateData,
    StockEntryItemData,
    StockEntryUpdateData,
    # Stock balance types
    StockBalanceQuery,
    StockBalanceResult,
    WarehouseStock,
    ItemStock,
    # Transfer request types
    TransferFilters,
    TransferCreateData,
    TransferItemData,
    TransferApprovalData,
    # Item group types
    ItemGroupFilters,
    ItemGroupCreateData,
    ItemGroupUpdateData,
    # Item types
    ItemFilters,
    ItemCreateData,
    ItemUpdateData,
    # Landed cost types
    LandedCostFilters,
    LandedCostCreateData,
    LandedCostItemData,
    LandedCostTaxData,
    # Batch types
    BatchFilters,
    BatchCreateData,
    # Serial types
    SerialFilters,
    SerialCreateData,
)

__all__ = [
    # Services
    "WarehouseService",
    "StockEntryService",
    "StockBalanceService",
    "TransferRequestService",
    "ItemGroupService",
    "ItemService",
    "LandedCostService",
    "BatchService",
    "SerialService",
    # Enums
    "StockEntryType",
    "TransferStatus",
    # Warehouse types
    "WarehouseFilters",
    "WarehouseCreateData",
    "WarehouseUpdateData",
    # Stock entry types
    "StockEntryFilters",
    "StockEntryCreateData",
    "StockEntryItemData",
    "StockEntryUpdateData",
    # Stock balance types
    "StockBalanceQuery",
    "StockBalanceResult",
    "WarehouseStock",
    "ItemStock",
    # Transfer request types
    "TransferFilters",
    "TransferCreateData",
    "TransferItemData",
    "TransferApprovalData",
    # Item group types
    "ItemGroupFilters",
    "ItemGroupCreateData",
    "ItemGroupUpdateData",
    # Item types
    "ItemFilters",
    "ItemCreateData",
    "ItemUpdateData",
    # Landed cost types
    "LandedCostFilters",
    "LandedCostCreateData",
    "LandedCostItemData",
    "LandedCostTaxData",
    # Batch types
    "BatchFilters",
    "BatchCreateData",
    # Serial types
    "SerialFilters",
    "SerialCreateData",
]

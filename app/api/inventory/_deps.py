"""Shared dependencies for inventory API routes.

This module provides service dependency providers and common utilities
for inventory API endpoints.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.inventory import (
    WarehouseService,
    StockEntryService,
    StockBalanceService,
    TransferRequestService,
    ItemGroupService,
    ItemService,
    LandedCostService,
    BatchService,
    SerialService,
)
from app.services.errors import NotFoundError, ValidationError, ConflictError

__all__ = [
    # Dependency providers
    "get_item_group_service",
    "get_item_service",
    "get_warehouse_service",
    "get_stock_entry_service",
    "get_stock_balance_service",
    "get_transfer_service",
    "get_landed_cost_service",
    "get_batch_service",
    "get_serial_service",
    # Permission dependencies
    "RequireInventoryRead",
    "RequireInventoryWrite",
    # Error handler
    "handle_service_error",
]

# Permission dependencies
RequireInventoryRead = Depends(Require("inventory:read"))
RequireInventoryWrite = Depends(Require("inventory:write"))


# Service dependency providers
def get_item_group_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ItemGroupService:
    """Get item group service instance."""
    return ItemGroupService(db, principal)


def get_item_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ItemService:
    """Get item service instance."""
    return ItemService(db, principal)


def get_warehouse_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> WarehouseService:
    """Get warehouse service instance."""
    return WarehouseService(db, principal)


def get_stock_entry_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> StockEntryService:
    """Get stock entry service instance."""
    return StockEntryService(db, principal)


def get_stock_balance_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> StockBalanceService:
    """Get stock balance service instance."""
    return StockBalanceService(db, principal)


def get_transfer_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> TransferRequestService:
    """Get transfer request service instance."""
    return TransferRequestService(db, principal)


def get_landed_cost_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> LandedCostService:
    """Get landed cost service instance."""
    return LandedCostService(db, principal)


def get_batch_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> BatchService:
    """Get batch service instance."""
    return BatchService(db, principal)


def get_serial_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> SerialService:
    """Get serial service instance."""
    return SerialService(db, principal)


def handle_service_error(e: Exception) -> None:
    """Convert service exceptions to HTTP exceptions.

    Args:
        e: Service exception to convert.

    Raises:
        HTTPException: Converted HTTP exception.
    """
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=422, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail=str(e))

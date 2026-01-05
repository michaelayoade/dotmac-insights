"""Items API endpoints.

Thin wrapper around ItemService for item CRUD operations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import ItemService, ItemFilters, ItemCreateData, ItemUpdateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_item_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import ItemCreateRequest, ItemUpdateRequest

router = APIRouter(prefix="/items", tags=["inventory"])
logger = structlog.get_logger()


@router.get("", dependencies=[RequireInventoryRead])
async def list_items(
    search: str | None = None,
    item_group: str | None = None,
    status: str | None = None,
    is_stock_item: bool | None = None,
    sort_by: str = Query(default="item_name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: ItemService = Depends(get_item_service),
) -> Dict[str, Any]:
    """List items with optional filtering."""
    filters = ItemFilters(
        search=search,
        item_group=item_group,
        status=status,
        is_stock_item=is_stock_item,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_items(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "description": item.description,
                "uom": item.uom,
                "default_warehouse": item.default_warehouse,
                "valuation_rate": str(item.valuation_rate) if item.valuation_rate else None,
                "standard_selling_rate": str(item.standard_selling_rate) if item.standard_selling_rate else None,
                "is_stock_item": item.is_stock_item,
                "status": item.status,
            }
            for item in result.items
        ],
    }


@router.get("/stock-items", dependencies=[RequireInventoryRead])
async def list_stock_items(
    service: ItemService = Depends(get_item_service),
) -> Dict[str, Any]:
    """Get all active stock items."""
    items = service.get_stock_items()

    return {
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "uom": item.uom,
                "default_warehouse": item.default_warehouse,
            }
            for item in items
        ],
    }


@router.get("/{item_id}", dependencies=[RequireInventoryRead])
async def get_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
) -> Dict[str, Any]:
    """Get an item by ID."""
    try:
        item = service.get_item(item_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "description": item.description,
        "uom": item.uom,
        "default_warehouse": item.default_warehouse,
        "valuation_rate": str(item.valuation_rate) if item.valuation_rate else None,
        "standard_selling_rate": str(item.standard_selling_rate) if item.standard_selling_rate else None,
        "is_stock_item": item.is_stock_item,
        "status": item.status,
    }


@router.get("/{item_id}/stock", dependencies=[RequireInventoryRead])
async def get_item_stock(
    item_id: int,
    warehouse: str | None = None,
    service: ItemService = Depends(get_item_service),
) -> Dict[str, Any]:
    """Get current stock quantity for an item."""
    try:
        item = service.get_item(item_id)
        qty = service.get_item_stock_qty(item.item_code, warehouse)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "item_id": item_id,
        "item_code": item.item_code,
        "warehouse": warehouse,
        "qty": str(qty),
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_item(
    payload: ItemCreateRequest,
    service: ItemService = Depends(get_item_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new item."""
    try:
        data = ItemCreateData(
            item_code=payload.item_code,
            item_name=payload.item_name,
            description=payload.description,
            item_group=payload.item_group,
            uom=payload.uom,
            default_warehouse=payload.default_warehouse,
            valuation_rate=Decimal(str(payload.valuation_rate)) if payload.valuation_rate else None,
            standard_selling_rate=Decimal(str(payload.standard_selling_rate)) if payload.standard_selling_rate else None,
            is_stock_item=payload.is_stock_item,
            status=payload.status,
        )
        item = service.create_item(data)
        db.commit()

        logger.info(
            "inventory_item_created",
            item_id=item.id,
            item_code=item.item_code,
        )
    except (ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
    }


@router.patch("/{item_id}", dependencies=[RequireInventoryWrite])
async def update_item(
    item_id: int,
    payload: ItemUpdateRequest,
    service: ItemService = Depends(get_item_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing item."""
    try:
        data = ItemUpdateData(
            item_name=payload.item_name,
            description=payload.description,
            item_group=payload.item_group,
            uom=payload.uom,
            default_warehouse=payload.default_warehouse,
            valuation_rate=Decimal(str(payload.valuation_rate)) if payload.valuation_rate is not None else None,
            standard_selling_rate=Decimal(str(payload.standard_selling_rate)) if payload.standard_selling_rate is not None else None,
            is_stock_item=payload.is_stock_item,
            status=payload.status,
        )
        item = service.update_item(item_id, data)
        db.commit()

        logger.info(
            "inventory_item_updated",
            item_id=item.id,
            item_code=item.item_code,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
    }


@router.delete("/{item_id}", dependencies=[RequireInventoryWrite])
async def delete_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an item."""
    try:
        item = service.get_item(item_id)
        item_code = item.item_code
        service.delete_item(item_id)
        db.commit()

        logger.info(
            "inventory_item_deleted",
            item_id=item_id,
            item_code=item_code,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "item_id": item_id}


@router.post("/{item_id}/deactivate", dependencies=[RequireInventoryWrite])
async def deactivate_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivate an item."""
    try:
        item = service.deactivate_item(item_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": item.id, "status": item.status}


@router.post("/{item_id}/activate", dependencies=[RequireInventoryWrite])
async def activate_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Activate an item."""
    try:
        item = service.activate_item(item_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": item.id, "status": item.status}

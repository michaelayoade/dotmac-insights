"""Warehouses API endpoints.

Thin wrapper around WarehouseService for warehouse CRUD operations.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import WarehouseService, WarehouseFilters, WarehouseCreateData, WarehouseUpdateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_warehouse_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import WarehouseCreateRequest, WarehouseUpdateRequest

router = APIRouter(prefix="/warehouses", tags=["inventory"])
logger = structlog.get_logger()


@router.get("", dependencies=[RequireInventoryRead])
async def list_warehouses(
    search: str | None = None,
    warehouse_type: str | None = None,
    parent_warehouse: str | None = None,
    company: str | None = None,
    is_group: bool | None = None,
    include_disabled: bool = False,
    sort_by: str = Query(default="warehouse_name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: WarehouseService = Depends(get_warehouse_service),
) -> Dict[str, Any]:
    """List warehouses with optional filtering."""
    filters = WarehouseFilters(
        search=search,
        warehouse_type=warehouse_type,
        parent_warehouse=parent_warehouse,
        company=company,
        is_group=is_group,
        include_disabled=include_disabled,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_warehouses(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "warehouses": [
            {
                "id": w.id,
                "erpnext_id": w.erpnext_id,
                "warehouse_name": w.warehouse_name,
                "parent_warehouse": w.parent_warehouse,
                "warehouse_type": w.warehouse_type,
                "company": w.company,
                "account": w.account,
                "is_group": w.is_group,
                "disabled": w.disabled,
            }
            for w in result.items
        ],
    }


@router.get("/tree", dependencies=[RequireInventoryRead])
async def get_warehouse_tree(
    service: WarehouseService = Depends(get_warehouse_service),
) -> Dict[str, Any]:
    """Get warehouse hierarchy as a tree structure."""
    root_warehouses = service.get_root_warehouses()

    def build_tree(warehouses):
        """Recursively build tree structure."""
        tree = []
        for wh in warehouses:
            children = service.get_child_warehouses(wh.warehouse_name)
            node = {
                "id": wh.id,
                "warehouse_name": wh.warehouse_name,
                "warehouse_type": wh.warehouse_type,
                "is_group": wh.is_group,
                "children": build_tree(children) if children else [],
            }
            tree.append(node)
        return tree

    return {"tree": build_tree(root_warehouses)}


@router.get("/parents", dependencies=[RequireInventoryRead])
async def list_parent_warehouses(
    exclude_id: int | None = None,
    service: WarehouseService = Depends(get_warehouse_service),
) -> Dict[str, Any]:
    """Get warehouses that can be parents (is_group=True)."""
    if exclude_id:
        warehouses = service.get_parent_warehouses_excluding(exclude_id)
    else:
        warehouses = service.get_parent_warehouses()

    return {
        "warehouses": [
            {
                "id": w.id,
                "warehouse_name": w.warehouse_name,
            }
            for w in warehouses
        ],
    }


@router.get("/{warehouse_id}", dependencies=[RequireInventoryRead])
async def get_warehouse(
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
) -> Dict[str, Any]:
    """Get a warehouse by ID."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": warehouse.id,
        "erpnext_id": warehouse.erpnext_id,
        "warehouse_name": warehouse.warehouse_name,
        "parent_warehouse": warehouse.parent_warehouse,
        "warehouse_type": warehouse.warehouse_type,
        "company": warehouse.company,
        "account": warehouse.account,
        "is_group": warehouse.is_group,
        "disabled": warehouse.disabled,
        "lft": warehouse.lft,
        "rgt": warehouse.rgt,
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_warehouse(
    payload: WarehouseCreateRequest,
    service: WarehouseService = Depends(get_warehouse_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new warehouse."""
    try:
        data = WarehouseCreateData(
            warehouse_name=payload.name,
            warehouse_type=payload.warehouse_type,
            parent_warehouse=payload.parent_warehouse,
            company=payload.company,
            account=payload.account,
            is_group=payload.is_group,
        )
        warehouse = service.create_warehouse(data)
        db.commit()

        logger.info(
            "warehouse_created",
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.warehouse_name,
        )
    except (ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": warehouse.id,
        "warehouse_name": warehouse.warehouse_name,
    }


@router.patch("/{warehouse_id}", dependencies=[RequireInventoryWrite])
async def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdateRequest,
    service: WarehouseService = Depends(get_warehouse_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing warehouse."""
    try:
        data = WarehouseUpdateData(
            warehouse_name=payload.name,
            warehouse_type=payload.warehouse_type,
            parent_warehouse=payload.parent_warehouse,
            company=payload.company,
            account=payload.account,
            is_group=payload.is_group,
            disabled=payload.disabled,
        )
        warehouse = service.update_warehouse(warehouse_id, data)
        db.commit()

        logger.info(
            "warehouse_updated",
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.warehouse_name,
        )
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": warehouse.id,
        "warehouse_name": warehouse.warehouse_name,
    }


@router.delete("/{warehouse_id}", dependencies=[RequireInventoryWrite])
async def delete_warehouse(
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a warehouse (soft delete)."""
    try:
        service.delete_warehouse(warehouse_id)
        db.commit()

        logger.info(
            "warehouse_deleted",
            warehouse_id=warehouse_id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "warehouse_id": warehouse_id}


@router.post("/{warehouse_id}/disable", dependencies=[RequireInventoryWrite])
async def disable_warehouse(
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a warehouse."""
    try:
        warehouse = service.disable_warehouse(warehouse_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": warehouse.id, "disabled": warehouse.disabled}


@router.post("/{warehouse_id}/enable", dependencies=[RequireInventoryWrite])
async def enable_warehouse(
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Enable a warehouse."""
    try:
        warehouse = service.enable_warehouse(warehouse_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": warehouse.id, "disabled": warehouse.disabled}

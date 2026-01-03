"""Batches API endpoints.

Thin wrapper around BatchService for batch tracking operations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import BatchService, BatchFilters, BatchCreateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_batch_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import BatchCreateRequest, BatchUpdateRequest

router = APIRouter(prefix="/batches", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: str | None) -> datetime | None:
    """Parse date string to datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


@router.get("", dependencies=[RequireInventoryRead])
async def list_batches(
    search: str | None = None,
    item_code: str | None = None,
    has_expiry: bool | None = None,
    expired: bool | None = None,
    sort_by: str = Query(default="batch_id"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """List batches with optional filtering."""
    filters = BatchFilters(
        search=search,
        item_code=item_code,
        has_expiry=has_expiry,
        expired=expired,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_batches(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "batches": [
            {
                "id": batch.id,
                "batch_id": batch.batch_id,
                "item_code": batch.item_code,
                "item_name": batch.item_name,
                "manufacturing_date": batch.manufacturing_date.isoformat() if batch.manufacturing_date else None,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                "batch_qty": str(batch.batch_qty),
                "disabled": batch.disabled,
            }
            for batch in result.items
        ],
    }


@router.get("/expiring", dependencies=[RequireInventoryRead])
async def list_expiring_batches(
    days_ahead: int = Query(default=30, ge=1, le=365),
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """Get batches expiring within specified days."""
    batches = service.get_expiring_batches(days_ahead)

    return {
        "days_ahead": days_ahead,
        "batches": [
            {
                "id": batch.id,
                "batch_id": batch.batch_id,
                "item_code": batch.item_code,
                "item_name": batch.item_name,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                "batch_qty": str(batch.batch_qty),
            }
            for batch in batches
        ],
    }


@router.get("/expired", dependencies=[RequireInventoryRead])
async def list_expired_batches(
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """Get all expired batches."""
    batches = service.get_expired_batches()

    return {
        "batches": [
            {
                "id": batch.id,
                "batch_id": batch.batch_id,
                "item_code": batch.item_code,
                "item_name": batch.item_name,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                "batch_qty": str(batch.batch_qty),
            }
            for batch in batches
        ],
    }


@router.get("/by-item/{item_code}", dependencies=[RequireInventoryRead])
async def list_batches_for_item(
    item_code: str,
    include_expired: bool = False,
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """Get batches for a specific item."""
    batches = service.get_batches_for_item(item_code, include_expired)

    return {
        "item_code": item_code,
        "batches": [
            {
                "id": batch.id,
                "batch_id": batch.batch_id,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                "batch_qty": str(batch.batch_qty),
                "disabled": batch.disabled,
            }
            for batch in batches
        ],
    }


@router.get("/{batch_id}", dependencies=[RequireInventoryRead])
async def get_batch(
    batch_id: int,
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """Get a batch by ID."""
    try:
        batch = service.get_batch(batch_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "item_code": batch.item_code,
        "item_name": batch.item_name,
        "manufacturing_date": batch.manufacturing_date.isoformat() if batch.manufacturing_date else None,
        "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
        "batch_qty": str(batch.batch_qty),
        "supplier": batch.supplier,
        "reference_doctype": batch.reference_doctype,
        "reference_name": batch.reference_name,
        "disabled": batch.disabled,
        "description": batch.description,
    }


@router.get("/{batch_id}/stock", dependencies=[RequireInventoryRead])
async def get_batch_stock(
    batch_id: int,
    warehouse: str | None = None,
    service: BatchService = Depends(get_batch_service),
) -> Dict[str, Any]:
    """Get stock quantity for a batch."""
    try:
        batch = service.get_batch(batch_id)
        qty = service.get_batch_stock(batch.batch_id, warehouse)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "batch_id": batch.batch_id,
        "warehouse": warehouse,
        "qty": str(qty),
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_batch(
    payload: BatchCreateRequest,
    service: BatchService = Depends(get_batch_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new batch."""
    from decimal import Decimal

    try:
        data = BatchCreateData(
            batch_id=payload.batch_id,
            item_code=payload.item_code,
            expiry_date=_parse_date(payload.expiry_date),
            manufacturing_date=_parse_date(payload.manufacturing_date),
            batch_qty=Decimal(str(payload.batch_qty)),
            reference_doctype=payload.reference_doctype,
            reference_name=payload.reference_name,
        )
        batch = service.create_batch(data)
        db.commit()

        logger.info(
            "batch_created",
            batch_id=batch.batch_id,
            item_code=batch.item_code,
        )
    except ConflictError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
    }


@router.patch("/{batch_id}", dependencies=[RequireInventoryWrite])
async def update_batch(
    batch_id: int,
    payload: BatchUpdateRequest,
    service: BatchService = Depends(get_batch_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a batch."""
    try:
        batch = service.update_batch(
            batch_id,
            expiry_date=_parse_date(payload.expiry_date).date() if payload.expiry_date else None,
            manufacturing_date=_parse_date(payload.manufacturing_date).date() if payload.manufacturing_date else None,
            description=payload.description,
        )
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
    }


@router.post("/{batch_id}/disable", dependencies=[RequireInventoryWrite])
async def disable_batch(
    batch_id: int,
    service: BatchService = Depends(get_batch_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a batch."""
    try:
        batch = service.disable_batch(batch_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": batch.id, "disabled": batch.disabled}


@router.post("/{batch_id}/enable", dependencies=[RequireInventoryWrite])
async def enable_batch(
    batch_id: int,
    service: BatchService = Depends(get_batch_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Enable a batch."""
    try:
        batch = service.enable_batch(batch_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": batch.id, "disabled": batch.disabled}

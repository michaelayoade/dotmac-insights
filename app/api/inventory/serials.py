"""Serial Numbers API endpoints.

Thin wrapper around SerialService for serial number tracking operations.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import SerialService, SerialFilters, SerialCreateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_serial_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import (
    SerialCreateRequest,
    SerialBulkCreateRequest,
    SerialUpdateRequest,
    SerialDeliverRequest,
)

router = APIRouter(prefix="/serials", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: str | None) -> date | None:
    """Parse date string to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("", dependencies=[RequireInventoryRead])
async def list_serials(
    search: str | None = None,
    item_code: str | None = None,
    warehouse: str | None = None,
    status: str | None = None,
    sort_by: str = Query(default="serial_no"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """List serial numbers with optional filtering."""
    filters = SerialFilters(
        search=search,
        item_code=item_code,
        warehouse=warehouse,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_serials(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "serials": [
            {
                "id": serial.id,
                "serial_no": serial.serial_no,
                "item_code": serial.item_code,
                "item_name": serial.item_name,
                "warehouse": serial.warehouse,
                "batch_no": serial.batch_no,
                "status": serial.status.value,
                "customer": serial.customer,
            }
            for serial in result.items
        ],
    }


@router.get("/by-item/{item_code}", dependencies=[RequireInventoryRead])
async def list_serials_for_item(
    item_code: str,
    warehouse: str | None = None,
    status: str | None = None,
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """Get serial numbers for a specific item."""
    from app.models.inventory import SerialStatus

    status_enum = None
    if status:
        try:
            status_enum = SerialStatus(status.lower())
        except ValueError:
            pass

    serials = service.get_serials_for_item(item_code, warehouse, status_enum)

    return {
        "item_code": item_code,
        "serials": [
            {
                "id": serial.id,
                "serial_no": serial.serial_no,
                "warehouse": serial.warehouse,
                "batch_no": serial.batch_no,
                "status": serial.status.value,
            }
            for serial in serials
        ],
    }


@router.get("/available/{item_code}", dependencies=[RequireInventoryRead])
async def list_available_serials(
    item_code: str,
    warehouse: str | None = None,
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """Get available (active) serial numbers for an item."""
    serials = service.get_available_serials(item_code, warehouse)

    return {
        "item_code": item_code,
        "warehouse": warehouse,
        "serials": [
            {
                "id": serial.id,
                "serial_no": serial.serial_no,
                "batch_no": serial.batch_no,
            }
            for serial in serials
        ],
    }


@router.get("/by-customer/{customer}", dependencies=[RequireInventoryRead])
async def list_serials_by_customer(
    customer: str,
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """Get serial numbers assigned to a customer."""
    serials = service.get_serials_by_customer(customer)

    return {
        "customer": customer,
        "serials": [
            {
                "id": serial.id,
                "serial_no": serial.serial_no,
                "item_code": serial.item_code,
                "item_name": serial.item_name,
                "delivery_date": serial.delivery_date.isoformat() if serial.delivery_date else None,
                "warranty_expiry_date": serial.warranty_expiry_date.isoformat() if serial.warranty_expiry_date else None,
            }
            for serial in serials
        ],
    }


@router.get("/warranty-expiring", dependencies=[RequireInventoryRead])
async def list_warranty_expiring(
    days_ahead: int = Query(default=30, ge=1, le=365),
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """Get serial numbers with warranty expiring within specified days."""
    serials = service.get_serials_with_expiring_warranty(days_ahead)

    return {
        "days_ahead": days_ahead,
        "serials": [
            {
                "id": serial.id,
                "serial_no": serial.serial_no,
                "item_code": serial.item_code,
                "customer": serial.customer,
                "warranty_expiry_date": serial.warranty_expiry_date.isoformat() if serial.warranty_expiry_date else None,
            }
            for serial in serials
        ],
    }


@router.get("/{serial_id}", dependencies=[RequireInventoryRead])
async def get_serial(
    serial_id: int,
    service: SerialService = Depends(get_serial_service),
) -> Dict[str, Any]:
    """Get a serial number by ID."""
    try:
        serial = service.get_serial(serial_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": serial.id,
        "serial_no": serial.serial_no,
        "item_code": serial.item_code,
        "item_name": serial.item_name,
        "warehouse": serial.warehouse,
        "batch_no": serial.batch_no,
        "status": serial.status.value,
        "customer": serial.customer,
        "delivery_document_type": serial.delivery_document_type,
        "delivery_document_no": serial.delivery_document_no,
        "delivery_date": serial.delivery_date.isoformat() if serial.delivery_date else None,
        "purchase_document_type": serial.purchase_document_type,
        "purchase_document_no": serial.purchase_document_no,
        "purchase_date": serial.purchase_date.isoformat() if serial.purchase_date else None,
        "warranty_expiry_date": serial.warranty_expiry_date.isoformat() if serial.warranty_expiry_date else None,
        "amc_expiry_date": serial.amc_expiry_date.isoformat() if serial.amc_expiry_date else None,
        "description": serial.description,
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_serial(
    payload: SerialCreateRequest,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new serial number."""
    try:
        data = SerialCreateData(
            serial_no=payload.serial_no,
            item_code=payload.item_code,
            warehouse=payload.warehouse,
            batch_no=payload.batch_no,
            status=payload.status,
            purchase_document_type=payload.purchase_document_type,
            purchase_document_no=payload.purchase_document_no,
        )
        serial = service.create_serial(data)
        db.commit()

        logger.info(
            "serial_created",
            serial_no=serial.serial_no,
            item_code=serial.item_code,
        )
    except ConflictError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": serial.id,
        "serial_no": serial.serial_no,
    }


@router.post("/bulk", dependencies=[RequireInventoryWrite])
async def create_serials_bulk(
    payload: SerialBulkCreateRequest,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create multiple serial numbers at once."""
    try:
        serials = service.create_serials_bulk(
            item_code=payload.item_code,
            serial_nos=payload.serial_nos,
            warehouse=payload.warehouse,
            batch_no=payload.batch_no,
        )
        db.commit()

        logger.info(
            "serials_bulk_created",
            item_code=payload.item_code,
            count=len(serials),
        )
    except ConflictError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "created": len(serials),
        "serials": [{"id": s.id, "serial_no": s.serial_no} for s in serials],
    }


@router.patch("/{serial_id}", dependencies=[RequireInventoryWrite])
async def update_serial(
    serial_id: int,
    payload: SerialUpdateRequest,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a serial number."""
    try:
        serial = service.update_serial(
            serial_id,
            warehouse=payload.warehouse,
            batch_no=payload.batch_no,
            description=payload.description,
            warranty_expiry_date=_parse_date(payload.warranty_expiry_date),
            amc_expiry_date=_parse_date(payload.amc_expiry_date),
        )
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": serial.id,
        "serial_no": serial.serial_no,
    }


@router.post("/{serial_id}/deliver", dependencies=[RequireInventoryWrite])
async def deliver_serial(
    serial_id: int,
    payload: SerialDeliverRequest,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a serial number as delivered to a customer."""
    try:
        serial = service.deliver_serial(
            serial_id,
            customer=payload.customer,
            delivery_document_type=payload.delivery_document_type,
            delivery_document_no=payload.delivery_document_no,
            delivery_date=_parse_date(payload.delivery_date),
        )
        db.commit()

        logger.info(
            "serial_delivered",
            serial_no=serial.serial_no,
            customer=payload.customer,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": serial.id,
        "serial_no": serial.serial_no,
        "status": serial.status.value,
        "customer": serial.customer,
    }


@router.post("/{serial_id}/return", dependencies=[RequireInventoryWrite])
async def return_serial(
    serial_id: int,
    warehouse: str,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a delivered serial number as returned."""
    try:
        serial = service.return_serial(serial_id, warehouse)
        db.commit()

        logger.info(
            "serial_returned",
            serial_no=serial.serial_no,
            warehouse=warehouse,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": serial.id,
        "serial_no": serial.serial_no,
        "status": serial.status.value,
        "warehouse": serial.warehouse,
    }


@router.post("/{serial_id}/reactivate", dependencies=[RequireInventoryWrite])
async def reactivate_serial(
    serial_id: int,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reactivate a returned or inactive serial number."""
    try:
        serial = service.reactivate_serial(serial_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": serial.id, "status": serial.status.value}


@router.post("/{serial_id}/deactivate", dependencies=[RequireInventoryWrite])
async def deactivate_serial(
    serial_id: int,
    service: SerialService = Depends(get_serial_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivate a serial number."""
    try:
        serial = service.deactivate_serial(serial_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": serial.id, "status": serial.status.value}

"""Stock Entries API endpoints.

Thin wrapper around StockEntryService for stock entry operations.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import (
    StockEntryService,
    StockEntryFilters,
    StockEntryCreateData,
    StockEntryItemData,
    StockEntryUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_stock_entry_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import StockEntryCreateRequest, StockEntryUpdateRequest, StockEntryLineRequest

router = APIRouter(prefix="/stock-entries", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: str | None):
    """Parse date string to date."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _map_entry_type(entry_type: str) -> str:
    """Map compact entry type to ERPNext-style string."""
    mapping = {
        "material_receipt": "Material Receipt",
        "material_issue": "Material Issue",
        "material_transfer": "Material Transfer",
        "material_transfer_for_manufacture": "Material Transfer for Manufacture",
        "material_consumption_for_manufacture": "Material Consumption for Manufacture",
        "manufacture": "Manufacture",
        "repack": "Repack",
        "send_to_subcontractor": "Send to Subcontractor",
    }
    return mapping.get(entry_type.lower(), entry_type)


def _validate_stock_entry_request(entry_type_raw: str, lines: List[StockEntryLineRequest]) -> str:
    """Validate stock entry request and return mapped entry type."""
    allowed = {
        "material_receipt",
        "material_issue",
        "material_transfer",
        "material_transfer_for_manufacture",
        "material_consumption_for_manufacture",
        "manufacture",
        "repack",
        "send_to_subcontractor",
    }
    entry_key = entry_type_raw.lower()
    if entry_key not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type: {entry_type_raw}")

    if not lines:
        raise HTTPException(status_code=400, detail="At least one line is required")

    seen_serials: set[str] = set()
    for line in lines:
        if line.qty is None or line.qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        if line.rate is None or line.rate < 0:
            raise HTTPException(status_code=400, detail="Rate must be zero or positive")

        serials = line.serial_nos or []
        for s in serials:
            if s in seen_serials:
                raise HTTPException(status_code=400, detail=f"Duplicate serial number: {s}")
            seen_serials.add(s)

        if entry_key == "material_receipt":
            if not line.t_warehouse:
                raise HTTPException(status_code=400, detail="material_receipt requires t_warehouse")
        elif entry_key == "material_issue":
            if not line.s_warehouse:
                raise HTTPException(status_code=400, detail="material_issue requires s_warehouse")
        elif entry_key.startswith("material_transfer"):
            if not line.s_warehouse or not line.t_warehouse:
                raise HTTPException(status_code=400, detail="material_transfer requires both s_warehouse and t_warehouse")
            if line.s_warehouse == line.t_warehouse:
                raise HTTPException(status_code=400, detail="Source and target warehouse cannot match for transfer")

    return _map_entry_type(entry_key)


@router.get("", dependencies=[RequireInventoryRead])
async def list_stock_entries(
    search: str | None = None,
    stock_entry_type: str | None = None,
    from_warehouse: str | None = None,
    to_warehouse: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    company: str | None = None,
    docstatus: int | None = Query(None, ge=0, le=2),
    sort_by: str = Query(default="posting_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: StockEntryService = Depends(get_stock_entry_service),
) -> Dict[str, Any]:
    """List stock entries with optional filtering."""
    filters = StockEntryFilters(
        search=search,
        stock_entry_type=stock_entry_type,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        company=company,
        docstatus=docstatus,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_entries(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "stock_entries": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "stock_entry_type": e.stock_entry_type,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "from_warehouse": e.from_warehouse,
                "to_warehouse": e.to_warehouse,
                "company": e.company,
                "total_amount": str(e.total_amount),
                "docstatus": e.docstatus,
                "remarks": e.remarks,
            }
            for e in result.items
        ],
    }


@router.get("/{entry_id}", dependencies=[RequireInventoryRead])
async def get_stock_entry(
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
) -> Dict[str, Any]:
    """Get a stock entry by ID with line items."""
    try:
        entry = service.get_entry(entry_id, include_items=True)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "stock_entry_type": entry.stock_entry_type,
        "purpose": entry.purpose,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "posting_time": entry.posting_time,
        "from_warehouse": entry.from_warehouse,
        "to_warehouse": entry.to_warehouse,
        "company": entry.company,
        "total_incoming_value": str(entry.total_incoming_value),
        "total_outgoing_value": str(entry.total_outgoing_value),
        "value_difference": str(entry.value_difference),
        "total_amount": str(entry.total_amount),
        "docstatus": entry.docstatus,
        "remarks": entry.remarks,
        "work_order": entry.work_order,
        "purchase_order": entry.purchase_order,
        "sales_order": entry.sales_order,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "uom": item.uom,
                "qty": str(item.qty),
                "s_warehouse": item.s_warehouse,
                "t_warehouse": item.t_warehouse,
                "basic_rate": str(item.basic_rate),
                "basic_amount": str(item.basic_amount),
                "valuation_rate": str(item.valuation_rate),
                "amount": str(item.amount),
                "batch_no": item.batch_no,
                "serial_no": item.serial_no,
            }
            for item in entry.items
        ],
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_stock_entry(
    payload: StockEntryCreateRequest,
    service: StockEntryService = Depends(get_stock_entry_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new stock entry."""
    # Validate request
    entry_type = _validate_stock_entry_request(payload.entry_type, payload.lines)

    try:
        items = [
            StockEntryItemData(
                item_code=line.item_code,
                qty=Decimal(str(line.qty)),
                uom=line.uom,
                s_warehouse=line.s_warehouse,
                t_warehouse=line.t_warehouse,
                basic_rate=Decimal(str(line.rate)),
                batch_no=line.batch_no,
                serial_no=",".join(line.serial_nos) if line.serial_nos else None,
            )
            for line in payload.lines
        ]

        data = StockEntryCreateData(
            stock_entry_type=entry_type,
            posting_date=_parse_date(payload.posting_date) or datetime.now().date(),
            company=payload.company,
            remarks=payload.remarks,
            items=items,
        )

        entry = service.create_entry(data)
        db.commit()

        logger.info(
            "stock_entry_created",
            entry_id=entry.id,
            entry_type=entry.stock_entry_type,
        )
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": entry.id,
        "stock_entry_type": entry.stock_entry_type,
        "docstatus": entry.docstatus,
    }


@router.patch("/{entry_id}", dependencies=[RequireInventoryWrite])
async def update_stock_entry(
    entry_id: int,
    payload: StockEntryUpdateRequest,
    service: StockEntryService = Depends(get_stock_entry_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a stock entry (draft only)."""
    try:
        data = StockEntryUpdateData(
            posting_date=_parse_date(payload.posting_date),
            remarks=payload.remarks,
        )
        entry = service.update_entry(entry_id, data)
        db.commit()

        logger.info(
            "stock_entry_updated",
            entry_id=entry.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": entry.id,
        "docstatus": entry.docstatus,
    }


@router.post("/{entry_id}/submit", dependencies=[RequireInventoryWrite])
async def submit_stock_entry(
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a draft stock entry."""
    try:
        entry = service.submit_entry(entry_id)
        db.commit()

        logger.info(
            "stock_entry_submitted",
            entry_id=entry.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": entry.id,
        "docstatus": entry.docstatus,
    }


@router.post("/{entry_id}/cancel", dependencies=[RequireInventoryWrite])
async def cancel_stock_entry(
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel a submitted stock entry."""
    try:
        entry = service.cancel_entry(entry_id)
        db.commit()

        logger.info(
            "stock_entry_cancelled",
            entry_id=entry.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": entry.id,
        "docstatus": entry.docstatus,
    }


@router.delete("/{entry_id}", dependencies=[RequireInventoryWrite])
async def delete_stock_entry(
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a draft stock entry."""
    try:
        service.delete_entry(entry_id)
        db.commit()

        logger.info(
            "stock_entry_deleted",
            entry_id=entry_id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "entry_id": entry_id}

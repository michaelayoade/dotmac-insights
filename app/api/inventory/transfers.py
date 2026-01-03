"""Transfer Requests API endpoints.

Thin wrapper around TransferRequestService for transfer request operations.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.inventory import (
    TransferRequestService,
    TransferFilters,
    TransferCreateData,
    TransferItemData,
    TransferApprovalData,
    TransferStatus,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_transfer_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)

router = APIRouter(prefix="/transfers", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: str | None):
    """Parse date string to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# Request schemas (inline since they're specific to transfers)
from pydantic import BaseModel, Field
from typing import List, Optional


class TransferItemRequest(BaseModel):
    item_code: str
    qty: float
    item_name: Optional[str] = None
    description: Optional[str] = None
    uom: Optional[str] = None
    batch_no: Optional[str] = None
    serial_no: Optional[str] = None


class TransferCreateRequest(BaseModel):
    from_warehouse: str
    to_warehouse: str
    required_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    company: Optional[str] = None
    remarks: Optional[str] = None
    items: List[TransferItemRequest]


class TransferApprovalRequest(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None


@router.get("", dependencies=[RequireInventoryRead])
async def list_transfers(
    search: str | None = None,
    status: str | None = None,
    from_warehouse: str | None = None,
    to_warehouse: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    sort_by: str = Query(default="request_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: TransferRequestService = Depends(get_transfer_service),
) -> Dict[str, Any]:
    """List transfer requests with optional filtering."""
    status_enum = None
    if status:
        try:
            status_enum = TransferStatus(status.lower())
        except ValueError:
            pass

    filters = TransferFilters(
        search=search,
        status=status_enum,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_transfers(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "transfers": [
            {
                "id": t.id,
                "from_warehouse": t.from_warehouse,
                "to_warehouse": t.to_warehouse,
                "request_date": t.request_date.isoformat() if t.request_date else None,
                "required_date": t.required_date.isoformat() if t.required_date else None,
                "status": t.status.value,
                "total_qty": str(t.total_qty),
                "total_value": str(t.total_value),
                "company": t.company,
            }
            for t in result.items
        ],
    }


@router.get("/pending", dependencies=[RequireInventoryRead])
async def list_pending_transfers(
    service: TransferRequestService = Depends(get_transfer_service),
) -> Dict[str, Any]:
    """Get transfer requests pending approval."""
    transfers = service.get_pending_approvals()

    return {
        "transfers": [
            {
                "id": t.id,
                "from_warehouse": t.from_warehouse,
                "to_warehouse": t.to_warehouse,
                "request_date": t.request_date.isoformat() if t.request_date else None,
                "required_date": t.required_date.isoformat() if t.required_date else None,
                "total_qty": str(t.total_qty),
                "requested_by_id": t.requested_by_id,
            }
            for t in transfers
        ],
    }


@router.get("/{transfer_id}", dependencies=[RequireInventoryRead])
async def get_transfer(
    transfer_id: int,
    service: TransferRequestService = Depends(get_transfer_service),
) -> Dict[str, Any]:
    """Get a transfer request by ID with line items."""
    try:
        transfer = service.get_transfer(transfer_id, include_items=True)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": transfer.id,
        "from_warehouse": transfer.from_warehouse,
        "to_warehouse": transfer.to_warehouse,
        "company": transfer.company,
        "request_date": transfer.request_date.isoformat() if transfer.request_date else None,
        "required_date": transfer.required_date.isoformat() if transfer.required_date else None,
        "transfer_date": transfer.transfer_date.isoformat() if transfer.transfer_date else None,
        "status": transfer.status.value,
        "total_qty": str(transfer.total_qty),
        "total_value": str(transfer.total_value),
        "approved_by_id": transfer.approved_by_id,
        "approved_at": transfer.approved_at.isoformat() if transfer.approved_at else None,
        "rejection_reason": transfer.rejection_reason,
        "remarks": transfer.remarks,
        "requested_by_id": transfer.requested_by_id,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": str(item.qty),
                "uom": item.uom,
                "valuation_rate": str(item.valuation_rate),
                "amount": str(item.amount),
                "batch_no": item.batch_no,
                "serial_no": item.serial_no,
            }
            for item in transfer.items
        ],
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_transfer(
    payload: TransferCreateRequest,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new transfer request."""
    try:
        items = [
            TransferItemData(
                item_code=item.item_code,
                qty=Decimal(str(item.qty)),
                item_name=item.item_name,
                description=item.description,
                uom=item.uom,
                batch_no=item.batch_no,
                serial_no=item.serial_no,
            )
            for item in payload.items
        ]

        data = TransferCreateData(
            from_warehouse=payload.from_warehouse,
            to_warehouse=payload.to_warehouse,
            required_date=_parse_date(payload.required_date),
            company=payload.company,
            remarks=payload.remarks,
            items=items,
        )

        transfer = service.create_request(data)
        db.commit()

        logger.info(
            "transfer_created",
            transfer_id=transfer.id,
            from_warehouse=transfer.from_warehouse,
            to_warehouse=transfer.to_warehouse,
        )
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }


@router.post("/{transfer_id}/submit", dependencies=[RequireInventoryWrite])
async def submit_transfer(
    transfer_id: int,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a draft transfer request for approval."""
    try:
        transfer = service.submit_for_approval(transfer_id)
        db.commit()

        logger.info(
            "transfer_submitted",
            transfer_id=transfer.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }


@router.post("/{transfer_id}/approve", dependencies=[RequireInventoryWrite])
async def approve_transfer(
    transfer_id: int,
    payload: TransferApprovalRequest,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Approve or reject a transfer request."""
    try:
        data = TransferApprovalData(
            approved=payload.approved,
            rejection_reason=payload.rejection_reason,
            remarks=payload.remarks,
        )
        transfer = service.approve_transfer(transfer_id, data)
        db.commit()

        action = "approved" if payload.approved else "rejected"
        logger.info(
            f"transfer_{action}",
            transfer_id=transfer.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }


@router.post("/{transfer_id}/execute", dependencies=[RequireInventoryWrite])
async def execute_transfer(
    transfer_id: int,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute an approved transfer (create stock entries)."""
    try:
        transfer = service.execute_transfer(transfer_id)
        db.commit()

        logger.info(
            "transfer_executed",
            transfer_id=transfer.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }


@router.post("/{transfer_id}/complete", dependencies=[RequireInventoryWrite])
async def complete_transfer(
    transfer_id: int,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark an in-transit transfer as completed."""
    try:
        transfer = service.complete_transfer(transfer_id)
        db.commit()

        logger.info(
            "transfer_completed",
            transfer_id=transfer.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }


@router.post("/{transfer_id}/cancel", dependencies=[RequireInventoryWrite])
async def cancel_transfer(
    transfer_id: int,
    service: TransferRequestService = Depends(get_transfer_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel a transfer request."""
    try:
        transfer = service.cancel_transfer(transfer_id)
        db.commit()

        logger.info(
            "transfer_cancelled",
            transfer_id=transfer.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
    }

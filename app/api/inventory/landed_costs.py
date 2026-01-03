"""Landed Costs API endpoints.

Thin wrapper around LandedCostService for landed cost voucher operations.
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
    LandedCostService,
    LandedCostFilters,
    LandedCostCreateData,
    LandedCostItemData,
    LandedCostTaxData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_landed_cost_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import LandedCostCreateRequest

router = APIRouter(prefix="/landed-costs", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: str | None):
    """Parse date string to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("", dependencies=[RequireInventoryRead])
async def list_landed_costs(
    from_date: str | None = None,
    to_date: str | None = None,
    company: str | None = None,
    docstatus: int | None = Query(None, ge=0, le=2),
    sort_by: str = Query(default="posting_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: LandedCostService = Depends(get_landed_cost_service),
) -> Dict[str, Any]:
    """List landed cost vouchers with optional filtering."""
    filters = LandedCostFilters(
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        company=company,
        docstatus=docstatus,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_vouchers(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "vouchers": [
            {
                "id": v.id,
                "posting_date": v.posting_date.isoformat() if v.posting_date else None,
                "company": v.company,
                "distribute_charges_based_on": v.distribute_charges_based_on,
                "total_taxes_and_charges": str(v.total_taxes_and_charges),
                "docstatus": v.docstatus,
                "purchase_receipt": v.purchase_receipt,
            }
            for v in result.items
        ],
    }


@router.get("/by-receipt/{purchase_receipt}", dependencies=[RequireInventoryRead])
async def list_by_receipt(
    purchase_receipt: str,
    service: LandedCostService = Depends(get_landed_cost_service),
) -> Dict[str, Any]:
    """Get all landed cost vouchers for a purchase receipt."""
    vouchers = service.get_vouchers_for_receipt(purchase_receipt)

    return {
        "purchase_receipt": purchase_receipt,
        "vouchers": [
            {
                "id": v.id,
                "posting_date": v.posting_date.isoformat() if v.posting_date else None,
                "total_taxes_and_charges": str(v.total_taxes_and_charges),
                "docstatus": v.docstatus,
            }
            for v in vouchers
        ],
    }


@router.get("/{voucher_id}", dependencies=[RequireInventoryRead])
async def get_landed_cost(
    voucher_id: int,
    service: LandedCostService = Depends(get_landed_cost_service),
) -> Dict[str, Any]:
    """Get a landed cost voucher by ID with items and taxes."""
    try:
        voucher = service.get_voucher(voucher_id, include_details=True)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": voucher.id,
        "posting_date": voucher.posting_date.isoformat() if voucher.posting_date else None,
        "company": voucher.company,
        "distribute_charges_based_on": voucher.distribute_charges_based_on,
        "total_taxes_and_charges": str(voucher.total_taxes_and_charges),
        "purchase_receipt": voucher.purchase_receipt,
        "docstatus": voucher.docstatus,
        "remarks": voucher.remarks,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": str(item.qty),
                "rate": str(item.rate),
                "amount": str(item.amount),
                "applicable_charges": str(item.applicable_charges),
                "warehouse": item.warehouse,
            }
            for item in voucher.items
        ],
        "taxes": [
            {
                "id": tax.id,
                "expense_account": tax.expense_account,
                "description": tax.description,
                "amount": str(tax.amount),
            }
            for tax in voucher.taxes
        ],
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_landed_cost(
    payload: LandedCostCreateRequest,
    service: LandedCostService = Depends(get_landed_cost_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new landed cost voucher."""
    try:
        items = [
            LandedCostItemData(
                receipt_document_type=item.receipt_document_type,
                receipt_document=item.receipt_document,
                item_code=item.item_code,
                description=item.description,
                qty=Decimal(str(item.qty)),
                rate=Decimal(str(item.rate)),
                amount=Decimal(str(item.amount)),
            )
            for item in payload.items
        ]

        taxes = [
            LandedCostTaxData(
                expense_account=tax.expense_account,
                description=tax.description,
                amount=Decimal(str(tax.amount)),
            )
            for tax in payload.taxes
        ]

        data = LandedCostCreateData(
            posting_date=_parse_date(payload.posting_date),
            company=payload.company,
            distribute_charges_based_on=payload.distribute_charges_based_on,
            items=items,
            taxes=taxes,
        )

        voucher = service.create_voucher(data)
        db.commit()

        logger.info(
            "landed_cost_created",
            voucher_id=voucher.id,
            total_charges=str(voucher.total_taxes_and_charges),
        )
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": voucher.id,
        "total_taxes_and_charges": str(voucher.total_taxes_and_charges),
    }


@router.post("/{voucher_id}/submit", dependencies=[RequireInventoryWrite])
async def submit_landed_cost(
    voucher_id: int,
    service: LandedCostService = Depends(get_landed_cost_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a landed cost voucher."""
    try:
        voucher = service.submit_voucher(voucher_id)
        db.commit()

        logger.info(
            "landed_cost_submitted",
            voucher_id=voucher.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": voucher.id,
        "docstatus": voucher.docstatus,
    }


@router.post("/{voucher_id}/cancel", dependencies=[RequireInventoryWrite])
async def cancel_landed_cost(
    voucher_id: int,
    service: LandedCostService = Depends(get_landed_cost_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel a submitted landed cost voucher."""
    try:
        voucher = service.cancel_voucher(voucher_id)
        db.commit()

        logger.info(
            "landed_cost_cancelled",
            voucher_id=voucher.id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": voucher.id,
        "docstatus": voucher.docstatus,
    }


@router.delete("/{voucher_id}", dependencies=[RequireInventoryWrite])
async def delete_landed_cost(
    voucher_id: int,
    service: LandedCostService = Depends(get_landed_cost_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a draft landed cost voucher."""
    try:
        service.delete_voucher(voucher_id)
        db.commit()

        logger.info(
            "landed_cost_deleted",
            voucher_id=voucher_id,
        )
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "voucher_id": voucher_id}

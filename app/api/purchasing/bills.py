"""Bills (Purchase Invoices) API endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.purchasing import BillService, BillFilters, BillCreateData, BillUpdateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

from ._deps import (
    get_bill_service,
    RequireRead,
    RequireWrite,
    parse_date,
    handle_service_error,
)

router = APIRouter(prefix="/bills", tags=["purchasing"])


class BillCreateRequest(BaseModel):
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    company: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    posting_date: Optional[str] = None
    due_date: Optional[str] = None
    grand_total: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    currency: str = "NGN"
    status: Optional[str] = "draft"
    docstatus: int = 0
    is_return: bool = False

    @field_validator("grand_total", "outstanding_amount", "paid_amount", "tax_amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else Decimal("0")


class BillUpdateRequest(BaseModel):
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    grand_total: Optional[Decimal] = None
    outstanding_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None

    @field_validator("grand_total", "outstanding_amount", "paid_amount", "tax_amount", mode="before")
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


@router.get("", dependencies=[RequireRead])
async def get_bills(
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    overdue_only: bool = False,
    sort_by: str = Query(default="posting_date", pattern="^(posting_date|due_date|grand_total|supplier_name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: BillService = Depends(get_bill_service),
) -> Dict[str, Any]:
    """Get vendor bills with filtering and pagination."""
    filters = BillFilters(
        status=status,
        supplier=supplier,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        currency=currency,
        min_amount=Decimal(str(min_amount)) if min_amount else None,
        max_amount=Decimal(str(max_amount)) if max_amount else None,
        overdue_only=overdue_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    try:
        result = service.list_bills(filters, pagination)
    except ValidationError as e:
        handle_service_error(e)

    today = date.today()
    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "bills": [
            {
                "id": b.id,
                "erpnext_id": b.erpnext_id,
                "supplier": b.supplier,
                "supplier_name": b.supplier_name,
                "posting_date": b.posting_date.isoformat() if b.posting_date else None,
                "due_date": b.due_date.isoformat() if b.due_date else None,
                "grand_total": float(b.grand_total),
                "outstanding_amount": float(b.outstanding_amount),
                "status": b.status.value if b.status else None,
                "currency": b.currency,
                "is_overdue": b.due_date.date() < today if b.due_date else False,
                "days_overdue": (today - b.due_date.date()).days if b.due_date and b.due_date.date() < today else 0,
            }
            for b in result.data
        ],
    }


@router.get("/{bill_id}", dependencies=[RequireRead])
async def get_bill_detail(
    bill_id: int,
    service: BillService = Depends(get_bill_service),
) -> Dict[str, Any]:
    """Get detailed information for a specific bill."""
    try:
        detail = service.get_bill_detail(bill_id)
    except NotFoundError as e:
        handle_service_error(e)

    bill = detail["bill"]
    today = date.today()

    return {
        "id": bill.id,
        "erpnext_id": bill.erpnext_id,
        "supplier": bill.supplier,
        "supplier_name": bill.supplier_name,
        "posting_date": bill.posting_date.isoformat() if bill.posting_date else None,
        "due_date": bill.due_date.isoformat() if bill.due_date else None,
        "grand_total": float(bill.grand_total),
        "net_total": float(bill.grand_total - bill.tax_amount) if bill.tax_amount else float(bill.grand_total),
        "total_taxes_and_charges": float(bill.tax_amount or 0),
        "outstanding_amount": float(bill.outstanding_amount),
        "status": bill.status.value if bill.status else None,
        "currency": bill.currency,
        "company": bill.company,
        "is_overdue": bill.due_date.date() < today if bill.due_date else False,
        "items": [
            {
                "id": line.id,
                "idx": line.idx,
                "item_code": line.item_code,
                "item_name": line.item_name,
                "description": line.description,
                "quantity": float(line.quantity),
                "rate": float(line.rate),
                "uom": line.uom,
                "amount": float(line.amount),
                "account": line.account,
            }
            for line in detail["lines"]
        ],
        "gl_entries": [
            {
                "id": e.id,
                "account": e.account,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "cost_center": e.cost_center,
            }
            for e in detail["gl_entries"]
        ],
    }


@router.post("", dependencies=[RequireWrite])
async def create_bill(
    payload: BillCreateRequest,
    db: Session = Depends(get_db),
    service: BillService = Depends(get_bill_service),
) -> Dict[str, Any]:
    """Create a purchase invoice."""
    data = BillCreateData(
        bill_number=payload.bill_number,
        supplier_id=payload.supplier_id,
        supplier=payload.supplier,
        supplier_name=payload.supplier_name,
        company=payload.company,
        supplier_tax_id=payload.supplier_tax_id,
        supplier_address=payload.supplier_address,
        posting_date=parse_date(payload.posting_date, "posting_date") if payload.posting_date else None,
        due_date=parse_date(payload.due_date, "due_date") if payload.due_date else None,
        grand_total=payload.grand_total,
        outstanding_amount=payload.outstanding_amount,
        paid_amount=payload.paid_amount,
        tax_amount=payload.tax_amount,
        currency=payload.currency,
        status=payload.status,
        docstatus=payload.docstatus,
        is_return=payload.is_return,
    )

    try:
        bill = service.create_bill(data)
        db.commit()
    except ValidationError as e:
        db.rollback()
        handle_service_error(e)

    return {"id": bill.id}


@router.patch("/{bill_id}", dependencies=[RequireWrite])
async def update_bill(
    bill_id: int,
    payload: BillUpdateRequest,
    db: Session = Depends(get_db),
    service: BillService = Depends(get_bill_service),
) -> Dict[str, Any]:
    """Update a purchase invoice."""
    data = BillUpdateData(
        bill_number=payload.bill_number,
        supplier_id=payload.supplier_id,
        supplier=payload.supplier,
        supplier_name=payload.supplier_name,
        grand_total=payload.grand_total,
        outstanding_amount=payload.outstanding_amount,
        paid_amount=payload.paid_amount,
        tax_amount=payload.tax_amount,
        currency=payload.currency,
        status=payload.status,
    )

    try:
        bill = service.update_bill(bill_id, data)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": bill.id}


@router.delete("/{bill_id}", dependencies=[RequireWrite])
async def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    service: BillService = Depends(get_bill_service),
) -> Dict[str, Any]:
    """Delete a purchase invoice."""
    try:
        service.delete_bill(bill_id)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "bill_id": bill_id}

"""Suppliers API endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.purchasing import (
    SupplierService,
    SupplierFilters,
    SupplierCreateData,
    SupplierUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ConflictError

from ._deps import (
    get_supplier_service,
    RequireRead,
    RequireWrite,
    handle_service_error,
)

router = APIRouter(prefix="/suppliers", tags=["purchasing"])


class SupplierCreateRequest(BaseModel):
    supplier_name: str
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = "NGN"
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None


class SupplierUpdateRequest(BaseModel):
    supplier_name: Optional[str] = None
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None
    disabled: Optional[bool] = None


@router.get("", dependencies=[RequireRead])
async def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    country: Optional[str] = None,
    with_outstanding: bool = False,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Get suppliers list."""
    filters = SupplierFilters(
        search=search,
        supplier_group=supplier_group,
        country=country,
        with_outstanding=with_outstanding,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_suppliers(filters, pagination)
    outstanding_map = service.get_outstanding_by_supplier()

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "suppliers": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "name": s.supplier_name,
                "group": s.supplier_group,
                "type": s.supplier_type,
                "country": s.country,
                "currency": s.default_currency,
                "email": s.email_id,
                "mobile": s.mobile_no,
                "outstanding": float(outstanding_map.get(s.erpnext_id, 0)),
            }
            for s in result.data
        ],
    }


@router.get("/groups", dependencies=[RequireRead])
async def get_supplier_groups(
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Get supplier group breakdown."""
    groups = service.get_supplier_groups()
    return {
        "total_groups": len(groups),
        "groups": [
            {
                "name": g["name"],
                "count": g["count"],
                "outstanding": float(g["outstanding"]),
            }
            for g in groups
        ],
    }


@router.get("/{supplier_id}", dependencies=[RequireRead])
async def get_supplier_detail(
    supplier_id: int,
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Get supplier details with bills."""
    try:
        detail = service.get_supplier_detail(supplier_id)
    except NotFoundError as e:
        handle_service_error(e)

    supplier = detail["supplier"]
    return {
        "id": supplier.id,
        "erpnext_id": supplier.erpnext_id,
        "name": supplier.supplier_name,
        "group": supplier.supplier_group,
        "type": supplier.supplier_type,
        "country": supplier.country,
        "currency": supplier.default_currency,
        "email": supplier.email_id,
        "mobile": supplier.mobile_no,
        "tax_id": supplier.tax_id,
        "total_purchases": float(detail["total_purchases"]),
        "total_outstanding": float(detail["total_outstanding"]),
        "bill_count": detail["bill_count"],
        "recent_bills": [
            {
                "id": b.id,
                "bill_no": b.erpnext_id,
                "date": b.posting_date.isoformat() if b.posting_date else None,
                "amount": float(b.grand_total),
                "outstanding": float(b.outstanding_amount),
                "status": b.status.value if b.status else None,
            }
            for b in detail["bills"][:10]
        ],
    }


@router.post("", dependencies=[RequireWrite])
async def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Create a new supplier."""
    data = SupplierCreateData(
        supplier_name=payload.supplier_name,
        supplier_group=payload.supplier_group,
        supplier_type=payload.supplier_type,
        country=payload.country,
        default_currency=payload.default_currency or "NGN",
        email_id=payload.email_id,
        mobile_no=payload.mobile_no,
        tax_id=payload.tax_id,
        payment_terms=payload.payment_terms,
    )

    try:
        supplier = service.create_supplier(data)
        db.commit()
    except ConflictError as e:
        db.rollback()
        handle_service_error(e)

    return {
        "id": supplier.id,
        "name": supplier.supplier_name,
    }


@router.patch("/{supplier_id}", dependencies=[RequireWrite])
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Update a supplier."""
    data = SupplierUpdateData(
        supplier_name=payload.supplier_name,
        supplier_group=payload.supplier_group,
        supplier_type=payload.supplier_type,
        country=payload.country,
        default_currency=payload.default_currency,
        email_id=payload.email_id,
        mobile_no=payload.mobile_no,
        tax_id=payload.tax_id,
        payment_terms=payload.payment_terms,
        disabled=payload.disabled,
    )

    try:
        supplier = service.update_supplier(supplier_id, data)
        db.commit()
    except (NotFoundError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": supplier.id, "name": supplier.supplier_name}


@router.delete("/{supplier_id}", dependencies=[RequireWrite])
async def delete_supplier(
    supplier_id: int,
    soft: bool = Query(default=True),
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_supplier_service),
) -> Dict[str, Any]:
    """Delete a supplier."""
    try:
        service.delete_supplier(supplier_id, soft=soft)
        db.commit()
    except NotFoundError as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "soft_deleted" if soft else "deleted", "id": supplier_id}

"""Accounts Payable: AP aging, suppliers, outstanding payables."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.models.accounting import PurchaseInvoice
from app.services.accounting import AccountingSettingsService, PayablesService
from app.services.accounting.payables_types import (
    PayablesFilters,
    SupplierCreateData,
    SupplierFilters,
    SupplierUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

from .helpers import parse_date, resolve_currency_or_raise

router = APIRouter()


class SupplierCreateRequest(BaseModel):
    supplier_name: str
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    default_bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    tax_withholding_category: Optional[str] = None
    supplier_primary_contact: Optional[str] = None
    supplier_primary_address: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    default_price_list: Optional[str] = None
    payment_terms: Optional[str] = None
    is_transporter: bool = False
    is_internal_supplier: bool = False
    disabled: bool = False
    is_frozen: bool = False
    on_hold: bool = False


class SupplierUpdateRequest(BaseModel):
    supplier_name: Optional[str] = None
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    default_bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    tax_withholding_category: Optional[str] = None
    supplier_primary_contact: Optional[str] = None
    supplier_primary_address: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    default_price_list: Optional[str] = None
    payment_terms: Optional[str] = None
    is_transporter: Optional[bool] = None
    is_internal_supplier: Optional[bool] = None
    disabled: Optional[bool] = None
    is_frozen: Optional[bool] = None
    on_hold: Optional[bool] = None


def _get_payables_service(db: Session, principal: Optional[Principal] = None) -> PayablesService:
    """Factory to create PayablesService with dependencies."""
    settings_service = AccountingSettingsService(db, principal)
    return PayablesService(db, settings_service, principal)


# ACCOUNTS PAYABLE AGING


@router.get("/accounts-payable", dependencies=[Depends(Require("accounting:read"))])
def get_accounts_payable(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    supplier_account_id: Optional[int] = None,
    party_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get accounts payable aging report.

    Shows outstanding purchase invoices by age bucket.

    Args:
        as_of_date: Calculate aging as of this date (default: today)
        supplier: Filter by supplier name (legacy string filter)
        supplier_account_id: Filter by supplier account (party-based)
        party_id: Filter by party (person or organization)
        currency: Currency filter

    Returns:
        AP aging with buckets (current, 1-30, 31-60, 61-90, 90+)
    """
    cutoff = parse_date(as_of_date, "as_of_date")
    currency = resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    filters = PayablesFilters(
        as_of_date=cutoff,
        supplier=supplier,
        supplier_account_id=supplier_account_id,
        party_id=party_id,
        currency=currency,
    )

    try:
        service = _get_payables_service(db, principal)
        report = service.get_aging_report(filters)
        return report.to_dict()
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# SUPPLIERS


@router.get("/suppliers", dependencies=[Depends(Require("accounting:read"))])
def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get suppliers list.

    Args:
        search: Search by supplier name
        supplier_group: Filter by supplier group
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated list of suppliers
    """
    filters = SupplierFilters(
        search=search,
        supplier_group=supplier_group,
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    service = _get_payables_service(db, principal)
    total, suppliers = service.list_suppliers(filters, pagination)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "suppliers": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "name": s.name,
                "group": s.group,
                "type": s.type,
                "country": s.country,
                "currency": s.currency,
                "email": s.email,
                "mobile": s.mobile,
            }
            for s in suppliers
        ],
    }


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:read"))])
def get_supplier_detail(
    supplier_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get supplier detail."""
    try:
        service = _get_payables_service(db, principal)
        supplier = service.get_supplier(supplier_id)
        return supplier.to_dict()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/suppliers", dependencies=[Depends(Require("accounting:write"))])
def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a supplier locally."""
    data = SupplierCreateData(
        supplier_name=payload.supplier_name,
        supplier_group=payload.supplier_group,
        supplier_type=payload.supplier_type,
        country=payload.country,
        default_currency=payload.default_currency,
        default_bank_account=payload.default_bank_account,
        tax_id=payload.tax_id,
        tax_withholding_category=payload.tax_withholding_category,
        supplier_primary_contact=payload.supplier_primary_contact,
        supplier_primary_address=payload.supplier_primary_address,
        email_id=payload.email_id,
        mobile_no=payload.mobile_no,
        default_price_list=payload.default_price_list,
        payment_terms=payload.payment_terms,
        is_transporter=payload.is_transporter,
        is_internal_supplier=payload.is_internal_supplier,
        disabled=payload.disabled,
        is_frozen=payload.is_frozen,
        on_hold=payload.on_hold,
    )

    service = _get_payables_service(db, principal)
    supplier = service.create_supplier(data)
    db.commit()
    return {"id": supplier.id}


@router.patch("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:write"))])
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a supplier locally."""
    update_data = payload.model_dump(exclude_unset=True)
    data = SupplierUpdateData(**update_data)

    try:
        service = _get_payables_service(db, principal)
        supplier = service.update_supplier(supplier_id, data)
        db.commit()
        return {"id": supplier.id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Disable a supplier."""
    try:
        service = _get_payables_service(db, principal)
        service.disable_supplier(supplier_id)
        db.commit()
        return {"status": "disabled", "supplier_id": supplier_id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# OUTSTANDING PAYABLES


@router.get("/payables-outstanding", dependencies=[Depends(Require("accounting:read"))])
def get_payables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Outstanding payables with top suppliers.

    Args:
        currency: Currency filter
        top: Number of top suppliers to return

    Returns:
        Outstanding payables summary with top suppliers
    """
    currency = resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    service = _get_payables_service(db, principal)
    summary = service.get_outstanding_summary(currency=currency, top_n=top)

    return summary.to_dict()

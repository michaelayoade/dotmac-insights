"""Accounts Payable: AP aging, suppliers, outstanding payables."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional, List, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    GLEntry,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
)

from .helpers import parse_date, resolve_currency_or_raise, paginate

router = APIRouter()


class AgingBucket(TypedDict):
    count: int
    total: Decimal
    invoices: List[Dict[str, Any]]


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


# =============================================================================
# ACCOUNTS PAYABLE AGING
# =============================================================================

@router.get("/accounts-payable", dependencies=[Depends(Require("accounting:read"))])
def get_accounts_payable(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts payable aging report.

    Shows outstanding purchase invoices by age bucket.

    Args:
        as_of_date: Calculate aging as of this date (default: today)
        supplier: Filter by supplier name
        currency: Currency filter

    Returns:
        AP aging with buckets (current, 1-30, 31-60, 61-90, 90+)
    """
    cutoff = parse_date(as_of_date, "as_of_date") or date.today()
    currency = resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )

    if supplier:
        query = query.filter(PurchaseInvoice.supplier.ilike(f"%{supplier}%"))

    if currency:
        query = query.filter(PurchaseInvoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets: Dict[str, AgingBucket] = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else cutoff)
        days_overdue = (cutoff - due).days if cutoff > due else 0

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += inv.outstanding_amount
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.erpnext_id,
            "supplier": inv.supplier_name or inv.supplier,
            "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "grand_total": float(inv.grand_total),
            "outstanding": float(inv.outstanding_amount),
            "days_overdue": days_overdue,
        })

    buckets_response: Dict[str, Dict[str, Any]] = {
        key: {**value, "total": float(value["total"])} for key, value in buckets.items()
    }
    total_payable = sum(b["total"] for b in buckets_response.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_payable": total_payable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets_response,
    }


# Alias
@router.get("/payables-aging", dependencies=[Depends(Require("accounting:read"))])
def get_payables_aging(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Alias for /accounts-payable - AP aging report."""
    return get_accounts_payable(as_of_date, supplier, currency, db)


# =============================================================================
# SUPPLIERS
# =============================================================================

@router.get("/suppliers", dependencies=[Depends(Require("accounting:read"))])
def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
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
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if search:
        query = query.filter(Supplier.supplier_name.ilike(f"%{search}%"))

    if supplier_group:
        query = query.filter(Supplier.supplier_group == supplier_group)

    query = query.order_by(Supplier.supplier_name)
    total, suppliers = paginate(query, offset, limit)

    return {
        "total": total,
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
            }
            for s in suppliers
        ],
    }


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:read"))])
def get_supplier_detail(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get supplier detail."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return {
        "id": supplier.id,
        "erpnext_id": supplier.erpnext_id,
        "supplier_name": supplier.supplier_name,
        "supplier_group": supplier.supplier_group,
        "supplier_type": supplier.supplier_type,
        "country": supplier.country,
        "default_currency": supplier.default_currency,
        "default_bank_account": supplier.default_bank_account,
        "tax_id": supplier.tax_id,
        "tax_withholding_category": supplier.tax_withholding_category,
        "supplier_primary_contact": supplier.supplier_primary_contact,
        "supplier_primary_address": supplier.supplier_primary_address,
        "email_id": supplier.email_id,
        "mobile_no": supplier.mobile_no,
        "default_price_list": supplier.default_price_list,
        "payment_terms": supplier.payment_terms,
        "is_transporter": supplier.is_transporter,
        "is_internal_supplier": supplier.is_internal_supplier,
        "disabled": supplier.disabled,
        "is_frozen": supplier.is_frozen,
        "on_hold": supplier.on_hold,
    }


@router.post("/suppliers", dependencies=[Depends(Require("accounting:write"))])
def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a supplier locally."""
    supplier = Supplier(
        supplier_name=payload.supplier_name,
        supplier_group=payload.supplier_group,
        supplier_type=payload.supplier_type,
        country=payload.country,
        default_currency=payload.default_currency or "NGN",
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
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return {"id": supplier.id}


@router.patch("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:write"))])
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a supplier locally."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(supplier, key, value)

    db.commit()
    db.refresh(supplier)
    return {"id": supplier.id}


@router.delete("/suppliers/{supplier_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a supplier."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier.disabled = True
    db.commit()
    return {"status": "disabled", "supplier_id": supplier_id}


# =============================================================================
# OUTSTANDING PAYABLES
# =============================================================================

@router.get("/payables-outstanding", dependencies=[Depends(Require("accounting:read"))])
def get_payables_outstanding(
    currency: Optional[str] = None,
    top: int = Query(default=5, le=25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Outstanding payables with top suppliers.

    Args:
        currency: Currency filter
        top: Number of top suppliers to return

    Returns:
        Outstanding payables summary with top suppliers
    """
    as_of = date.today()
    currency = resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    pi_query = db.query(
        func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        func.count(PurchaseInvoice.id).label("invoice_count"),
    ).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )
    if currency:
        pi_query = pi_query.filter(PurchaseInvoice.currency == currency)
    pi_totals = pi_query.first()
    total_outstanding = float(pi_totals.outstanding or 0) if pi_totals else 0.0
    total_invoices = int(pi_totals.invoice_count or 0) if pi_totals else 0

    # Top suppliers by outstanding
    by_supplier_query = (
        db.query(
            PurchaseInvoice.supplier,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        )
        .filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ]),
        )
    )
    if currency:
        by_supplier_query = by_supplier_query.filter(PurchaseInvoice.currency == currency)

    by_supplier = (
        by_supplier_query.group_by(PurchaseInvoice.supplier)
        .order_by(func.sum(PurchaseInvoice.outstanding_amount).desc())
        .limit(top)
        .all()
    )

    return {
        "as_of_date": as_of.isoformat(),
        "currency": currency,
        "total_outstanding": total_outstanding,
        "total_invoices": total_invoices,
        "top_suppliers": [
            {
                "supplier": row.supplier,
                "outstanding": float(row.outstanding),
            }
            for row in by_supplier
        ],
    }

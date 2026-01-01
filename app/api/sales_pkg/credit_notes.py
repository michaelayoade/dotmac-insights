"""
Credit Notes Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.credit_note import CreditNote
from app.models.customer import Customer, CustomerStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.sales import (
    ERPNextLead, SalesOrder, Quotation, CustomerGroup, 
    Territory, SalesPerson
)
from app.api.sales_pkg.common import (
    Principal,
    CreditNoteRequest,
    CreditNoteUpdateRequest,
    CustomerRequest,
    CustomerUpdateRequest,
    CreditNoteStatus,
    CustomerStatus,
    CustomerType,
    BillingType,
    _ensure_utc,
    _generate_local_external_id,
    _parse_credit_note_status,
    _parse_customer_status,
    _parse_customer_type,
    _parse_billing_type,
    _serialize_credit_note,
    _serialize_customer,
    get_company_context,
    get_current_principal,
)

router = APIRouter()

@router.post("/credit-notes", dependencies=[Depends(Require("sales:write"))])
async def create_credit_note(
    payload: CreditNoteRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a credit note locally."""
    if payload.customer_id:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
    if payload.invoice_id:
        if not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")

    note = CreditNote(
        splynx_id=_generate_local_external_id(),
        credit_number=payload.credit_number,
        customer_id=payload.customer_id,
        invoice_id=payload.invoice_id,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        status=_parse_credit_note_status(payload.status) or CreditNoteStatus.ISSUED,
        issue_date=_ensure_utc(payload.issue_date),
        applied_date=_ensure_utc(payload.applied_date),
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
        updated_by_id=principal.id,
        company=get_company_context(allow_null=True),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize_credit_note(note)


@router.patch("/credit-notes/{credit_note_id}", dependencies=[Depends(Require("sales:write"))])
async def update_credit_note(
    credit_note_id: int,
    payload: CreditNoteUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a credit note locally."""
    note = db.query(CreditNote).filter(CreditNote.id == credit_note_id, CreditNote.is_deleted == False).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if payload.customer_id is not None:
        if payload.customer_id and not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        note.customer_id = payload.customer_id
    if payload.invoice_id is not None:
        if payload.invoice_id and not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")
        note.invoice_id = payload.invoice_id
    if payload.credit_number is not None:
        note.credit_number = payload.credit_number
    if payload.description is not None:
        note.description = payload.description
    if payload.amount is not None:
        note.amount = payload.amount
    if payload.currency is not None:
        note.currency = payload.currency
    if payload.status is not None:
        note.status = _parse_credit_note_status(payload.status) or note.status
    if payload.issue_date is not None:
        note.issue_date = _ensure_utc(payload.issue_date)
    if payload.applied_date is not None:
        note.applied_date = _ensure_utc(payload.applied_date)

    if hasattr(note, "updated_by_id"):
        setattr(note, "updated_by_id", principal.id)
    if hasattr(note, "write_back_status"):
        setattr(note, "write_back_status", "pending")
    db.commit()
    db.refresh(note)
    return _serialize_credit_note(note)


@router.delete("/credit-notes/{credit_note_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_credit_note(
    credit_note_id: int,
    soft: bool = Query(default=True, description="Soft delete by marking is_deleted"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a credit note."""
    note = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    note.is_deleted = True
    note.deleted_at = datetime.now(timezone.utc)
    note.deleted_by_id = principal.id
    if hasattr(note, "write_back_status"):
        setattr(note, "write_back_status", "pending")
    db.commit()
    return {"status": "disabled", "credit_note_id": credit_note_id}


@router.post("/customers", dependencies=[Depends(Require("sales:write"))])
async def create_sales_customer(
    payload: CustomerRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a customer locally (sales context)."""
    customer = Customer(
        name=payload.name,
        email=payload.email,
        billing_email=payload.billing_email,
        phone=payload.phone,
        phone_secondary=payload.phone_secondary,
        address=payload.address,
        address_2=payload.address_2,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        country=payload.country,
        customer_type=_parse_customer_type(payload.customer_type) or CustomerType.RESIDENTIAL,
        status=_parse_customer_status(payload.status) or CustomerStatus.ACTIVE,
        billing_type=_parse_billing_type(payload.billing_type) if payload.billing_type else None,
        gps=payload.gps,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _serialize_customer(customer)


@router.patch("/customers/{customer_id}", dependencies=[Depends(Require("sales:write"))])
async def update_sales_customer(
    customer_id: int,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a customer locally (sales context)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "customer_type" and value is not None:
            customer.customer_type = _parse_customer_type(value) or customer.customer_type
        elif field == "status" and value is not None:
            customer.status = _parse_customer_status(value) or customer.status
        elif field == "billing_type" and value is not None:
            customer.billing_type = _parse_billing_type(value)
        else:
            setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return _serialize_customer(customer)


@router.delete("/customers/{customer_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_sales_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.is_deleted = True
    customer.deleted_at = datetime.now(timezone.utc)
    customer.deleted_by_id = principal.id
    db.commit()
    return {"status": "disabled", "customer_id": customer_id}


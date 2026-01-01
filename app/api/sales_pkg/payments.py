"""
Payments Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import Dict, Any, Optional, List, cast
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
    PaymentRequest,
    PaymentUpdateRequest,
    PaymentSource,
    PaymentMethod,
    Principal,
    get_current_principal,
    NotificationEventType,
    NotificationService,
    _ensure_utc,
    _parse_payment_method,
    _parse_payment_status,
    _serialize_payment,
)

router = APIRouter()

@router.post("/payments", dependencies=[Depends(Require("sales:write"))])
async def create_payment(
    payload: PaymentRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a payment in the local database."""
    if payload.customer_id:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
    if payload.invoice_id:
        if not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")

    payment = Payment(
        source=PaymentSource.ERPNEXT,
        receipt_number=payload.receipt_number,
        customer_id=payload.customer_id,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=_parse_payment_method(payload.payment_method) or PaymentMethod.BANK_TRANSFER,
        status=_parse_payment_status(payload.status) or PaymentStatus.COMPLETED,
        payment_date=_ensure_utc(payload.payment_date),
        transaction_reference=payload.transaction_reference,
        gateway_reference=payload.gateway_reference,
        notes=payload.notes,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    # Emit payment received notification
    if payment.status in {PaymentStatus.COMPLETED, PaymentStatus.POSTED}:
        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first() if payment.customer_id else None
        invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first() if payment.invoice_id else None
        NotificationService(db).emit_event(
            event_type=NotificationEventType.PAYMENT_RECEIVED,
            payload={
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "amount": float(payment.amount) if payment.amount else 0,
                "currency": payment.currency,
                "customer_id": payment.customer_id,
                "customer_name": customer.name if customer else None,
                "invoice_id": payment.invoice_id,
                "invoice_number": invoice.invoice_number if invoice else None,
            },
            entity_type="payment",
            entity_id=payment.id,
        )

    return _serialize_payment(payment)


@router.patch("/payments/{payment_id}", dependencies=[Depends(Require("sales:write"))])
async def update_payment(
    payment_id: int,
    payload: PaymentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a payment in the local database."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payload.customer_id is not None:
        if not db.query(Customer.id).filter(Customer.id == payload.customer_id).first():
            raise HTTPException(status_code=400, detail=f"Customer {payload.customer_id} not found")
        payment.customer_id = payload.customer_id
    if payload.invoice_id is not None:
        if payload.invoice_id and not db.query(Invoice.id).filter(Invoice.id == payload.invoice_id).first():
            raise HTTPException(status_code=400, detail=f"Invoice {payload.invoice_id} not found")
        payment.invoice_id = payload.invoice_id
    if payload.receipt_number is not None:
        payment.receipt_number = payload.receipt_number
    if payload.amount is not None:
        payment.amount = payload.amount
    if payload.currency is not None:
        payment.currency = payload.currency
    if payload.payment_method is not None:
        payment.payment_method = _parse_payment_method(payload.payment_method) or payment.payment_method
    if payload.status is not None:
        payment.status = _parse_payment_status(payload.status) or payment.status
    if payload.payment_date is not None:
        payment.payment_date = cast(datetime, _ensure_utc(payload.payment_date))
    if payload.transaction_reference is not None:
        payment.transaction_reference = payload.transaction_reference
    if payload.gateway_reference is not None:
        payment.gateway_reference = payload.gateway_reference
    if payload.notes is not None:
        payment.notes = payload.notes

    db.commit()
    db.refresh(payment)
    return _serialize_payment(payment)


@router.delete("/payments/{payment_id}", dependencies=[Depends(Require("sales:write"))])
async def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete a payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.is_deleted = True
    payment.deleted_at = datetime.now(timezone.utc)
    payment.deleted_by_id = principal.id
    db.commit()
    return {"status": "disabled", "payment_id": payment_id}


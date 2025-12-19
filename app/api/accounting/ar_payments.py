"""AR Payments: Customer payment CRUD and workflow."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource
from app.models.payment_allocation import PaymentAllocation
from app.services.payment_allocation_service import (
    PaymentAllocationService,
    AllocationRequest,
    PaymentAllocationError,
)

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class AllocationCreate(BaseModel):
    """Schema for creating a payment allocation."""
    document_type: str  # invoice, credit_note
    document_id: int
    allocated_amount: float
    discount_amount: float = 0
    write_off_amount: float = 0
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None


class CustomerPaymentCreate(BaseModel):
    """Schema for creating a customer payment."""
    customer_id: int
    payment_date: str
    amount: float
    currency: str = "NGN"
    payment_method: str = "bank_transfer"
    receipt_number: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: float = 1
    bank_account_id: Optional[int] = None
    allocations: List[AllocationCreate] = []


class CustomerPaymentUpdate(BaseModel):
    """Schema for updating a customer payment."""
    payment_date: Optional[str] = None
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: Optional[float] = None


# =============================================================================
# AR PAYMENTS LIST & DETAIL
# =============================================================================

@router.get("/ar-payments", dependencies=[Depends(Require("accounting:read"))])
def list_ar_payments(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List customer payments with filters."""
    query = db.query(Payment)

    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)

    if status:
        try:
            status_enum = PaymentStatus(status.lower())
            query = query.filter(Payment.status == status_enum)
        except ValueError:
            pass

    if start_date:
        query = query.filter(Payment.payment_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(Payment.payment_date <= parse_date(end_date, "end_date"))

    query = query.order_by(Payment.payment_date.desc(), Payment.id.desc())
    total, payments = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "payments": [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "customer_id": p.customer_id,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method.value if p.payment_method else None,
                "status": p.status.value if p.status else None,
                "total_allocated": float(p.total_allocated) if p.total_allocated else 0,
                "unallocated_amount": float(p.unallocated_amount) if p.unallocated_amount else 0,
            }
            for p in payments
        ],
    }


@router.get("/ar-payments/{payment_id}", dependencies=[Depends(Require("accounting:read"))])
def get_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get customer payment detail with allocations."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    allocations = db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_id == payment_id
    ).all()

    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "customer_id": payment.customer_id,
        "invoice_id": payment.invoice_id,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "base_currency": payment.base_currency,
        "conversion_rate": float(payment.conversion_rate) if payment.conversion_rate else 1,
        "base_amount": float(payment.base_amount) if payment.base_amount else 0,
        "payment_method": payment.payment_method.value if payment.payment_method else None,
        "status": payment.status.value if payment.status else None,
        "workflow_status": payment.workflow_status,
        "docstatus": payment.docstatus,
        "transaction_reference": payment.transaction_reference,
        "gateway_reference": payment.gateway_reference,
        "notes": payment.notes,
        "total_allocated": float(payment.total_allocated) if payment.total_allocated else 0,
        "unallocated_amount": float(payment.unallocated_amount) if payment.unallocated_amount else 0,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "allocations": [
            {
                "id": a.id,
                "document_type": a.allocation_type.value,
                "document_id": a.document_id,
                "allocated_amount": float(a.allocated_amount),
                "discount_amount": float(a.discount_amount) if a.discount_amount else 0,
                "write_off_amount": float(a.write_off_amount) if a.write_off_amount else 0,
                "exchange_gain_loss": float(a.exchange_gain_loss) if a.exchange_gain_loss else 0,
            }
            for a in allocations
        ],
    }


# =============================================================================
# AR PAYMENTS CRUD
# =============================================================================

@router.post("/ar-payments", dependencies=[Depends(Require("books:write"))])
def create_ar_payment(
    data: CustomerPaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new customer payment."""
    # Parse payment method
    try:
        method_enum = PaymentMethod(data.payment_method.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid payment method: {data.payment_method}")

    # Parse date
    try:
        payment_date = datetime.fromisoformat(data.payment_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    payment = Payment(
        customer_id=data.customer_id,
        payment_date=payment_date,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        payment_method=method_enum,
        receipt_number=data.receipt_number,
        transaction_reference=data.transaction_reference,
        notes=data.notes,
        conversion_rate=Decimal(str(data.conversion_rate)),
        bank_account_id=data.bank_account_id,
        source=PaymentSource.INTERNAL,
        status=PaymentStatus.PENDING,
        created_by_id=user.id,
    )

    # Calculate base amount
    payment.base_amount = payment.amount * payment.conversion_rate
    payment.base_currency = "NGN"  # TODO: Get from company settings
    payment.unallocated_amount = payment.amount
    payment.total_allocated = Decimal("0")

    db.add(payment)
    db.flush()

    # Process allocations if provided
    if data.allocations:
        alloc_service = PaymentAllocationService(db)
        alloc_requests = [
            AllocationRequest(
                document_type=a.document_type,
                document_id=a.document_id,
                allocated_amount=Decimal(str(a.allocated_amount)),
                discount_amount=Decimal(str(a.discount_amount)),
                write_off_amount=Decimal(str(a.write_off_amount)),
                discount_type=a.discount_type,
                discount_account=a.discount_account,
                write_off_account=a.write_off_account,
                write_off_reason=a.write_off_reason,
            )
            for a in data.allocations
        ]
        try:
            alloc_service.allocate_payment(
                payment_id=payment.id,
                allocations=alloc_requests,
                user_id=user.id,
                is_supplier_payment=False,
            )
        except PaymentAllocationError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(payment)

    return {
        "message": "Customer payment created",
        "id": payment.id,
        "receipt_number": payment.receipt_number,
    }


@router.patch("/ar-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def update_ar_payment(
    payment_id: int,
    data: CustomerPaymentUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a customer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only update draft payments")

    if data.payment_date:
        try:
            payment.payment_date = datetime.fromisoformat(data.payment_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    if data.amount is not None:
        payment.amount = Decimal(str(data.amount))
        payment.base_amount = payment.amount * payment.conversion_rate
        payment.unallocated_amount = payment.amount - payment.total_allocated

    if data.payment_method:
        try:
            payment.payment_method = PaymentMethod(data.payment_method.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid payment method: {data.payment_method}")

    if data.transaction_reference is not None:
        payment.transaction_reference = data.transaction_reference

    if data.notes is not None:
        payment.notes = data.notes

    if data.conversion_rate is not None:
        payment.conversion_rate = Decimal(str(data.conversion_rate))
        payment.base_amount = payment.amount * payment.conversion_rate

    db.commit()

    return {
        "message": "Payment updated",
        "id": payment.id,
    }


@router.delete("/ar-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def delete_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a draft customer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only delete draft payments")

    # Remove allocations first
    db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_id == payment_id
    ).delete()

    payment.is_deleted = True
    payment.deleted_at = datetime.utcnow()
    payment.deleted_by_id = principal.id
    db.commit()

    return {"message": "Payment deleted"}


# =============================================================================
# ALLOCATIONS
# =============================================================================

@router.post("/ar-payments/{payment_id}/allocations", dependencies=[Depends(Require("books:write"))])
def add_payment_allocations(
    payment_id: int,
    allocations: List[AllocationCreate],
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Add allocations to a customer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    alloc_service = PaymentAllocationService(db)
    alloc_requests = [
        AllocationRequest(
            document_type=a.document_type,
            document_id=a.document_id,
            allocated_amount=Decimal(str(a.allocated_amount)),
            discount_amount=Decimal(str(a.discount_amount)),
            write_off_amount=Decimal(str(a.write_off_amount)),
            discount_type=a.discount_type,
            discount_account=a.discount_account,
            write_off_account=a.write_off_account,
            write_off_reason=a.write_off_reason,
        )
        for a in allocations
    ]

    try:
        created = alloc_service.allocate_payment(
            payment_id=payment_id,
            allocations=alloc_requests,
            user_id=user.id,
            is_supplier_payment=False,
        )
        db.commit()
        return {
            "message": f"Added {len(created)} allocations",
            "allocation_ids": [a.id for a in created],
        }
    except PaymentAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/ar-payments/{payment_id}/allocations/{allocation_id}", dependencies=[Depends(Require("books:write"))])
def remove_payment_allocation(
    payment_id: int,
    allocation_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Remove an allocation from a customer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.docstatus != 0:
        raise HTTPException(status_code=400, detail="Cannot modify allocations on posted payment")

    alloc_service = PaymentAllocationService(db)
    try:
        alloc_service.remove_allocation(allocation_id, user.id)
        db.commit()
        return {"message": "Allocation removed"}
    except PaymentAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# POSTING
# =============================================================================

@router.post("/ar-payments/{payment_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Post AR payment to GL - creates bank debit, AR credit."""
    from app.services.document_posting import DocumentPostingService, PostingError
    from app.services.billing_outbound_sync import BillingOutboundSyncService
    from .helpers import invalidate_report_cache

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Check workflow status (mirror AP pattern)
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Can only post approved payments")

    posting_service = DocumentPostingService(db)
    try:
        # post_payment requires (payment_id, user_id, posting_date=None)
        je = posting_service.post_payment(payment_id, user.id)
        payment.status = PaymentStatus.POSTED
        payment.workflow_status = "posted"
        db.commit()
        db.refresh(payment)  # ensure returned data reflects DB state
    except PostingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise  # let FastAPI handle unexpected errors

    await invalidate_report_cache()

    # Trigger outbound sync to ERPNext (if enabled via feature flag)
    sync_service = BillingOutboundSyncService(db)
    sync_service.sync_payment_to_erpnext(payment)
    db.commit()  # persist sync log

    return {
        "message": "Payment posted",
        "journal_entry_id": je.id,
        "status": payment.status.value,
    }


@router.post("/ar-payments/{payment_id}/approve", dependencies=[Depends(Require("books:approve"))])
def approve_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Approve a pending AR payment for posting."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only approve pending payments")

    payment.status = PaymentStatus.APPROVED
    payment.workflow_status = "approved"
    db.commit()

    return {
        "message": "Payment approved",
        "id": payment.id,
        "status": payment.status.value,
    }


# =============================================================================
# OUTSTANDING INVOICES
# =============================================================================

@router.get("/ar-payments/outstanding-invoices", dependencies=[Depends(Require("accounting:read"))])
def get_outstanding_invoices(
    customer_id: int,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get outstanding invoices available for payment."""
    alloc_service = PaymentAllocationService(db)
    docs = alloc_service.get_outstanding_documents("customer", customer_id, currency)

    return {
        "total": len(docs),
        "documents": [
            {
                "document_type": d.document_type,
                "document_id": d.document_id,
                "document_number": d.document_number,
                "document_date": d.document_date,
                "due_date": d.due_date,
                "currency": d.currency,
                "total_amount": float(d.total_amount),
                "outstanding_amount": float(d.outstanding_amount),
            }
            for d in docs
        ],
    }

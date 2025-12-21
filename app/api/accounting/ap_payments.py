"""AP Payments: Supplier payment CRUD and workflow."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.supplier_payment import SupplierPayment, SupplierPaymentStatus
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
    document_type: str  # bill, debit_note
    document_id: int
    allocated_amount: float
    discount_amount: float = 0
    write_off_amount: float = 0
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None


class SupplierPaymentCreate(BaseModel):
    """Schema for creating a supplier payment."""
    supplier_id: int
    supplier_name: Optional[str] = None
    payment_date: str
    posting_date: Optional[str] = None
    mode_of_payment: Optional[str] = None
    bank_account_id: Optional[int] = None
    currency: str = "NGN"
    paid_amount: float
    conversion_rate: float = 1
    reference_number: Optional[str] = None
    reference_date: Optional[str] = None
    remarks: Optional[str] = None
    company: Optional[str] = None
    allocations: List[AllocationCreate] = []


class SupplierPaymentUpdate(BaseModel):
    """Schema for updating a supplier payment."""
    payment_date: Optional[str] = None
    posting_date: Optional[str] = None
    mode_of_payment: Optional[str] = None
    bank_account_id: Optional[int] = None
    paid_amount: Optional[float] = None
    conversion_rate: Optional[float] = None
    reference_number: Optional[str] = None
    reference_date: Optional[str] = None
    remarks: Optional[str] = None


# =============================================================================
# AP PAYMENTS LIST & DETAIL
# =============================================================================

@router.get("/ap-payments", dependencies=[Depends(Require("accounting:read"))])
def list_ap_payments(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List supplier payments with filters."""
    query = db.query(SupplierPayment)

    if supplier_id:
        query = query.filter(SupplierPayment.supplier_id == supplier_id)

    if status:
        try:
            status_enum = SupplierPaymentStatus(status.lower())
            query = query.filter(SupplierPayment.status == status_enum)
        except ValueError:
            pass

    if start_date:
        query = query.filter(SupplierPayment.payment_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(SupplierPayment.payment_date <= parse_date(end_date, "end_date"))

    query = query.order_by(SupplierPayment.payment_date.desc(), SupplierPayment.id.desc())
    total, payments = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "payments": [
            {
                "id": p.id,
                "payment_number": p.payment_number,
                "supplier_id": p.supplier_id,
                "supplier_name": p.supplier_name,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "paid_amount": float(p.paid_amount),
                "currency": p.currency,
                "status": p.status.value,
                "total_allocated": float(p.total_allocated) if p.total_allocated else 0,
                "unallocated_amount": float(p.unallocated_amount) if p.unallocated_amount else 0,
            }
            for p in payments
        ],
    }


@router.get("/ap-payments/{payment_id}", dependencies=[Depends(Require("accounting:read"))])
def get_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get supplier payment detail with allocations."""
    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    allocations = db.query(PaymentAllocation).filter(
        PaymentAllocation.supplier_payment_id == payment_id
    ).all()

    return {
        "id": payment.id,
        "payment_number": payment.payment_number,
        "supplier_id": payment.supplier_id,
        "supplier_name": payment.supplier_name,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "posting_date": payment.posting_date.isoformat() if payment.posting_date else None,
        "mode_of_payment": payment.mode_of_payment,
        "bank_account_id": payment.bank_account_id,
        "currency": payment.currency,
        "paid_amount": float(payment.paid_amount),
        "conversion_rate": float(payment.conversion_rate) if payment.conversion_rate else 1,
        "base_paid_amount": float(payment.base_paid_amount) if payment.base_paid_amount else 0,
        "total_allocated": float(payment.total_allocated) if payment.total_allocated else 0,
        "unallocated_amount": float(payment.unallocated_amount) if payment.unallocated_amount else 0,
        "total_discount": float(payment.total_discount) if payment.total_discount else 0,
        "total_write_off": float(payment.total_write_off) if payment.total_write_off else 0,
        "total_withholding_tax": float(payment.total_withholding_tax) if payment.total_withholding_tax else 0,
        "reference_number": payment.reference_number,
        "reference_date": payment.reference_date.isoformat() if payment.reference_date else None,
        "remarks": payment.remarks,
        "status": payment.status.value,
        "workflow_status": payment.workflow_status,
        "docstatus": payment.docstatus,
        "company": payment.company,
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
# AP PAYMENTS CRUD
# =============================================================================

@router.post("/ap-payments", dependencies=[Depends(Require("books:write"))])
def create_ap_payment(
    data: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new supplier payment."""
    # Generate payment number
    from app.services.number_generator import generate_voucher_number
    payment_number = generate_voucher_number(db, "supplier_payment")

    # Parse dates
    payment_date = date.fromisoformat(data.payment_date)
    posting_date = date.fromisoformat(data.posting_date) if data.posting_date else payment_date
    reference_date = date.fromisoformat(data.reference_date) if data.reference_date else None

    payment = SupplierPayment(
        payment_number=payment_number,
        supplier_id=data.supplier_id,
        supplier_name=data.supplier_name,
        payment_date=payment_date,
        posting_date=posting_date,
        mode_of_payment=data.mode_of_payment,
        bank_account_id=data.bank_account_id,
        currency=data.currency,
        paid_amount=Decimal(str(data.paid_amount)),
        conversion_rate=Decimal(str(data.conversion_rate)),
        reference_number=data.reference_number,
        reference_date=reference_date,
        remarks=data.remarks,
        company=data.company,
        status=SupplierPaymentStatus.DRAFT,
        created_by_id=user.id,
    )

    # Calculate base amount
    payment.base_paid_amount = payment.paid_amount * payment.conversion_rate
    payment.unallocated_amount = payment.paid_amount
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
                is_supplier_payment=True,
            )
        except PaymentAllocationError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(payment)

    return {
        "message": "Supplier payment created",
        "id": payment.id,
        "payment_number": payment.payment_number,
    }


@router.patch("/ap-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def update_ap_payment(
    payment_id: int,
    data: SupplierPaymentUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a draft supplier payment."""
    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != SupplierPaymentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only update draft payments")

    if data.payment_date:
        payment.payment_date = date.fromisoformat(data.payment_date)
    if data.posting_date:
        payment.posting_date = date.fromisoformat(data.posting_date)
    if data.mode_of_payment is not None:
        payment.mode_of_payment = data.mode_of_payment
    if data.bank_account_id is not None:
        payment.bank_account_id = data.bank_account_id
    if data.paid_amount is not None:
        payment.paid_amount = Decimal(str(data.paid_amount))
        payment.unallocated_amount = payment.paid_amount - payment.total_allocated
    if data.conversion_rate is not None:
        payment.conversion_rate = Decimal(str(data.conversion_rate))
        payment.base_paid_amount = payment.paid_amount * payment.conversion_rate
    if data.reference_number is not None:
        payment.reference_number = data.reference_number
    if data.reference_date is not None:
        payment.reference_date = date.fromisoformat(data.reference_date) if data.reference_date else None
    if data.remarks is not None:
        payment.remarks = data.remarks

    db.commit()

    return {
        "message": "Payment updated",
        "id": payment.id,
    }


@router.delete("/ap-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def delete_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a draft supplier payment."""
    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != SupplierPaymentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only delete draft payments")

    # Remove allocations first
    db.query(PaymentAllocation).filter(
        PaymentAllocation.supplier_payment_id == payment_id
    ).delete()

    payment.is_deleted = True
    payment.deleted_at = datetime.utcnow()
    payment.deleted_by_id = principal.id
    db.commit()

    return {"message": "Payment deleted"}


# =============================================================================
# ALLOCATIONS
# =============================================================================

@router.post("/ap-payments/{payment_id}/allocations", dependencies=[Depends(Require("books:write"))])
def add_payment_allocations(
    payment_id: int,
    allocations: List[AllocationCreate],
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Add allocations to a supplier payment."""
    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status not in [SupplierPaymentStatus.DRAFT, SupplierPaymentStatus.SUBMITTED]:
        raise HTTPException(status_code=400, detail="Cannot allocate on this payment status")

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
            is_supplier_payment=True,
        )
        db.commit()
        return {
            "message": f"Added {len(created)} allocations",
            "allocation_ids": [a.id for a in created],
        }
    except PaymentAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/ap-payments/{payment_id}/allocations/{allocation_id}", dependencies=[Depends(Require("books:write"))])
def remove_payment_allocation(
    payment_id: int,
    allocation_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Remove an allocation from a supplier payment."""
    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status not in [SupplierPaymentStatus.DRAFT, SupplierPaymentStatus.SUBMITTED]:
        raise HTTPException(status_code=400, detail="Cannot modify allocations on this payment status")

    alloc_service = PaymentAllocationService(db)
    try:
        alloc_service.remove_allocation(allocation_id, user.id)
        db.commit()
        return {"message": "Allocation removed"}
    except PaymentAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# WORKFLOW
# =============================================================================

@router.post("/ap-payments/{payment_id}/submit", dependencies=[Depends(Require("books:write"))])
def submit_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Submit a supplier payment for approval."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != SupplierPaymentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only submit draft payments")

    engine = ApprovalEngine(db)
    try:
        approval = engine.submit_document(
            doctype="supplier_payment",
            document_id=payment_id,
            user_id=user.id,
            amount=payment.paid_amount,
            document_name=payment.payment_number,
        )
        payment.status = SupplierPaymentStatus.SUBMITTED
        payment.workflow_status = "pending_approval"
        db.commit()
        return {
            "message": "Payment submitted for approval",
            "approval_id": approval.id,
            "status": payment.status.value,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ap-payments/{payment_id}/approve", dependencies=[Depends(Require("books:approve"))])
def approve_ap_payment(
    payment_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Approve a supplier payment."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    engine = ApprovalEngine(db)
    try:
        approval = engine.approve_document(
            doctype="supplier_payment",
            document_id=payment_id,
            user_id=user.id,
            remarks=remarks,
        )
        payment.status = SupplierPaymentStatus.APPROVED
        payment.workflow_status = "approved"
        db.commit()
        return {
            "message": "Payment approved",
            "approval_id": approval.id,
            "status": payment.status.value,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ap-payments/{payment_id}/reject", dependencies=[Depends(Require("books:approve"))])
def reject_ap_payment(
    payment_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Reject a supplier payment."""
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    engine = ApprovalEngine(db)
    try:
        approval = engine.reject_document(
            doctype="supplier_payment",
            document_id=payment_id,
            user_id=user.id,
            reason=reason,
        )
        payment.status = SupplierPaymentStatus.DRAFT
        payment.workflow_status = "rejected"
        db.commit()
        return {
            "message": "Payment rejected",
            "approval_id": approval.id,
            "status": payment.status.value,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ap-payments/{payment_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_ap_payment(
    payment_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Post an approved supplier payment to the GL."""
    from app.services.document_posting import DocumentPostingService, PostingError
    from .helpers import invalidate_report_cache

    payment = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != SupplierPaymentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Can only post approved payments")

    posting_service = DocumentPostingService(db)
    try:
        je = posting_service.post_supplier_payment(payment_id, user.id)
        payment.status = SupplierPaymentStatus.POSTED
        payment.workflow_status = "posted"
        db.commit()

        await invalidate_report_cache()

        return {
            "message": "Payment posted",
            "journal_entry_id": je.id,
            "status": payment.status.value,
        }
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# OUTSTANDING BILLS
# =============================================================================

@router.get("/ap-payments/outstanding-bills", dependencies=[Depends(Require("accounting:read"))])
def get_outstanding_bills(
    supplier_id: int,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get outstanding bills available for payment."""
    alloc_service = PaymentAllocationService(db)
    docs = alloc_service.get_outstanding_documents("supplier", supplier_id, currency)

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

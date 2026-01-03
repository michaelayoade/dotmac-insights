"""AR Payments: Customer payment CRUD and workflow.

Uses ARPaymentService for business logic.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.services.accounting.ar_payment_types import (
    AllocationData,
    PaymentCreateData,
    PaymentFilters,
    PaymentUpdateData,
)
from app.services.accounting.ar_payments import ARPaymentService
from app.services.errors import NotFoundError, ServiceError, ValidationError
from app.services.payment_allocation_service import (
    AllocationRequest,
    PaymentAllocationError,
    PaymentAllocationService,
)
from app.services.types import PaginationParams

from .helpers import parse_date
from .schemas.allocation import AllocationCreate

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------


def get_ar_payment_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ARPaymentService:
    """Dependency to get an ARPaymentService instance."""
    return ARPaymentService(db, principal)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class CustomerPaymentCreate(BaseModel):
    """Schema for creating a customer payment."""

    customer_account_id: Optional[int] = None
    payment_date: str
    amount: float = Field(..., gt=0, description="Payment amount must be positive")
    currency: str = "NGN"
    payment_method: str = "bank_transfer"
    receipt_number: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: float = Field(
        default=1, gt=0, description="Conversion rate must be positive"
    )
    bank_account_id: Optional[int] = None
    allocations: List[AllocationCreate] = []


class CustomerPaymentUpdate(BaseModel):
    """Schema for updating a customer payment."""

    payment_date: Optional[str] = None
    amount: Optional[float] = Field(
        default=None, gt=0, description="Payment amount must be positive"
    )
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    conversion_rate: Optional[float] = Field(
        default=None, gt=0, description="Conversion rate must be positive"
    )


# ---------------------------------------------------------------------------
# Helper: Convert Pydantic schema to service dataclass
# ---------------------------------------------------------------------------


def _to_create_data(schema: CustomerPaymentCreate) -> PaymentCreateData:
    """Convert Pydantic schema to service PaymentCreateData."""
    # Parse payment method
    try:
        method_enum = PaymentMethod(schema.payment_method.lower())
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid payment method: {schema.payment_method}"
        ) from e

    # Parse date
    try:
        payment_date = datetime.fromisoformat(schema.payment_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format") from e

    allocations = [
        AllocationData(
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
        for a in schema.allocations
    ]

    return PaymentCreateData(
        customer_account_id=schema.customer_account_id,
        payment_date=payment_date,
        amount=Decimal(str(schema.amount)),
        currency=schema.currency,
        payment_method=method_enum,
        receipt_number=schema.receipt_number,
        transaction_reference=schema.transaction_reference,
        notes=schema.notes,
        conversion_rate=Decimal(str(schema.conversion_rate)),
        bank_account_id=schema.bank_account_id,
        allocations=allocations,
    )


def _to_update_data(schema: CustomerPaymentUpdate) -> PaymentUpdateData:
    """Convert Pydantic schema to service PaymentUpdateData."""
    payment_date = None
    if schema.payment_date is not None:
        try:
            payment_date = datetime.fromisoformat(schema.payment_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date format") from e

    payment_method = None
    if schema.payment_method is not None:
        try:
            payment_method = PaymentMethod(schema.payment_method.lower())
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid payment method: {schema.payment_method}"
            ) from e

    amount = Decimal(str(schema.amount)) if schema.amount is not None else None
    conversion_rate = (
        Decimal(str(schema.conversion_rate))
        if schema.conversion_rate is not None
        else None
    )

    return PaymentUpdateData(
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        transaction_reference=schema.transaction_reference,
        notes=schema.notes,
        conversion_rate=conversion_rate,
    )


# ---------------------------------------------------------------------------
# Helper: Serialize payment to response dict
# ---------------------------------------------------------------------------


def _serialize_payment_list_item(p: Payment) -> Dict[str, Any]:
    """Serialize payment for list response."""
    return {
        "id": p.id,
        "receipt_number": p.receipt_number,
        "customer_account_id": p.customer_account_id,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "amount": float(p.amount),
        "currency": p.currency,
        "payment_method": p.payment_method.value if p.payment_method else None,
        "status": p.status.value if p.status else None,
        "total_allocated": float(p.total_allocated) if p.total_allocated else 0,
        "unallocated_amount": float(p.unallocated_amount) if p.unallocated_amount else 0,
    }


def _serialize_payment_detail(
    payment: Payment, allocations: list
) -> Dict[str, Any]:
    """Serialize payment for detail response."""
    return {
        "id": payment.id,
        "receipt_number": payment.receipt_number,
        "customer_account_id": payment.customer_account_id,
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


# ---------------------------------------------------------------------------
# AR Payments List & Detail
# ---------------------------------------------------------------------------


@router.get("/ar-payments", dependencies=[Depends(Require("accounting:read"))])
def list_ar_payments(
    customer_account_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """List customer payments with filters."""
    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = PaymentStatus(status.lower())
        except ValueError:
            valid_statuses = [s.value for s in PaymentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_statuses}",
            )

    filters = PaymentFilters(
        customer_account_id=customer_account_id,
        status=status_enum,
        start_date=parse_date(start_date, "start_date") if start_date else None,
        end_date=parse_date(end_date, "end_date") if end_date else None,
    )

    pagination = PaginationParams(offset=offset, limit=limit)
    result = service.list_payments(filters, pagination)

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "payments": [_serialize_payment_list_item(p) for p in result.items],
    }


@router.get("/ar-payments/{payment_id}", dependencies=[Depends(Require("accounting:read"))])
def get_ar_payment(
    payment_id: int,
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """Get customer payment detail with allocations."""
    try:
        payment = service.get_payment(payment_id)
        allocations = service.get_payment_allocations(payment_id)
        return _serialize_payment_detail(payment, allocations)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ---------------------------------------------------------------------------
# AR Payments CRUD
# ---------------------------------------------------------------------------


@router.post("/ar-payments", dependencies=[Depends(Require("books:write"))])
def create_ar_payment(
    data: CustomerPaymentCreate,
    db: Session = Depends(get_db),
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """Create a new customer payment."""
    try:
        create_data = _to_create_data(data)
        payment = service.create_payment(create_data)
        db.commit()
        db.refresh(payment)
        return {
            "message": "Customer payment created",
            "id": payment.id,
            "receipt_number": payment.receipt_number,
        }
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/ar-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def update_ar_payment(
    payment_id: int,
    data: CustomerPaymentUpdate,
    db: Session = Depends(get_db),
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """Update a customer payment."""
    try:
        update_data = _to_update_data(data)
        payment = service.update_payment(payment_id, update_data)
        db.commit()
        return {
            "message": "Payment updated",
            "id": payment.id,
        }
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/ar-payments/{payment_id}", dependencies=[Depends(Require("books:write"))])
def delete_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """Delete a draft customer payment."""
    try:
        service.delete_payment(payment_id)
        db.commit()
        return {"message": "Payment deleted"}
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------


@router.post("/ar-payments/{payment_id}/allocations", dependencies=[Depends(Require("books:write"))])
def add_payment_allocations(
    payment_id: int,
    allocations: List[AllocationCreate],
    db: Session = Depends(get_db),
    service: ARPaymentService = Depends(get_ar_payment_service),
) -> Dict[str, Any]:
    """Add allocations to a customer payment."""
    try:
        alloc_data = [
            AllocationData(
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
        service.add_allocations(payment_id, alloc_data)
        db.commit()
        return {
            "message": f"Added {len(allocations)} allocations",
        }
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete("/ar-payments/{payment_id}/allocations/{allocation_id}", dependencies=[Depends(Require("books:write"))])
def remove_payment_allocation(
    payment_id: int,
    allocation_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Remove an allocation from a customer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.docstatus != 0:
        raise HTTPException(
            status_code=400, detail="Cannot modify allocations on posted payment"
        )

    alloc_service = PaymentAllocationService(db)
    try:
        alloc_service.remove_allocation(allocation_id, principal.id)
        db.commit()
        return {"message": "Allocation removed"}
    except PaymentAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Posting (keeps existing logic - workflow dependent)
# ---------------------------------------------------------------------------


@router.post("/ar-payments/{payment_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_ar_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Post AR payment to GL - creates bank debit, AR credit."""
    from app.services.billing_outbound_sync import BillingOutboundSyncService
    from app.services.document_posting import DocumentPostingService, PostingError

    from .helpers import invalidate_report_cache

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Can only post approved payments")

    posting_service = DocumentPostingService(db)
    try:
        je = posting_service.post_payment(payment_id, principal.id)
        payment.status = PaymentStatus.POSTED
        payment.workflow_status = "posted"
        db.commit()
        db.refresh(payment)
    except PostingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await invalidate_report_cache()

    # Trigger outbound sync to ERPNext (if enabled)
    sync_service = BillingOutboundSyncService(db)
    sync_service.sync_payment_to_erpnext(payment)
    db.commit()

    return {
        "message": "Payment posted",
        "id": payment.id,
        "journal_entry_id": je.id,
        "status": payment.status.value,
    }

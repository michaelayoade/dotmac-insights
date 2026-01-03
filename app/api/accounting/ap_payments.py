"""AP Payments: Supplier payment API endpoints.

This module provides the REST API for supplier payment management.
Business logic is delegated to APPaymentService.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.services.accounting import APPaymentService
from app.services.accounting.ap_payment_types import (
    APAllocationData,
    APPaymentCreateData,
    APPaymentFilters,
    APPaymentUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

from .helpers import parse_date
from .schemas.allocation import AllocationCreate

router = APIRouter()


# ============= SERVICE DEPENDENCY =============

def get_ap_payment_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> APPaymentService:
    """Create an APPaymentService instance for dependency injection."""
    return APPaymentService(db, principal)


# ============= PYDANTIC SCHEMAS =============

class SupplierPaymentCreate(BaseModel):
    """Schema for creating a supplier payment."""

    supplier_id: int
    supplier_name: Optional[str] = None
    payment_date: str
    posting_date: Optional[str] = None
    mode_of_payment: Optional[str] = None
    bank_account_id: Optional[int] = None
    currency: str = "NGN"
    paid_amount: float = Field(..., gt=0, description="Payment amount must be positive")
    conversion_rate: float = Field(
        default=1, gt=0, description="Conversion rate must be positive"
    )
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
    paid_amount: Optional[float] = Field(
        default=None, gt=0, description="Payment amount must be positive"
    )
    conversion_rate: Optional[float] = Field(
        default=None, gt=0, description="Conversion rate must be positive"
    )
    reference_number: Optional[str] = None
    reference_date: Optional[str] = None
    remarks: Optional[str] = None


# ============= HELPER FUNCTIONS =============

def _payment_to_dict(p) -> Dict[str, Any]:
    """Convert SupplierPayment to response dict."""
    return {
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


def _payment_detail_to_dict(p, allocations) -> Dict[str, Any]:
    """Convert SupplierPayment with allocations to detailed response dict."""
    return {
        "id": p.id,
        "payment_number": p.payment_number,
        "supplier_id": p.supplier_id,
        "supplier_name": p.supplier_name,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "posting_date": p.posting_date.isoformat() if p.posting_date else None,
        "mode_of_payment": p.mode_of_payment,
        "bank_account_id": p.bank_account_id,
        "currency": p.currency,
        "paid_amount": float(p.paid_amount),
        "conversion_rate": float(p.conversion_rate) if p.conversion_rate else 1,
        "base_paid_amount": float(p.base_paid_amount) if p.base_paid_amount else 0,
        "total_allocated": float(p.total_allocated) if p.total_allocated else 0,
        "unallocated_amount": float(p.unallocated_amount) if p.unallocated_amount else 0,
        "total_discount": float(p.total_discount) if p.total_discount else 0,
        "total_write_off": float(p.total_write_off) if p.total_write_off else 0,
        "total_withholding_tax": (
            float(p.total_withholding_tax) if p.total_withholding_tax else 0
        ),
        "reference_number": p.reference_number,
        "reference_date": p.reference_date.isoformat() if p.reference_date else None,
        "remarks": p.remarks,
        "status": p.status.value,
        "workflow_status": p.workflow_status,
        "docstatus": p.docstatus,
        "company": p.company,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "allocations": [
            {
                "id": a.id,
                "document_type": a.allocation_type.value,
                "document_id": a.document_id,
                "allocated_amount": float(a.allocated_amount),
                "discount_amount": float(a.discount_amount) if a.discount_amount else 0,
                "write_off_amount": (
                    float(a.write_off_amount) if a.write_off_amount else 0
                ),
                "exchange_gain_loss": (
                    float(a.exchange_gain_loss) if a.exchange_gain_loss else 0
                ),
            }
            for a in allocations
        ],
    }


# ============= LIST & DETAIL ENDPOINTS =============

@router.get("/ap-payments", dependencies=[Depends(Require("accounting:read"))])
def list_ap_payments(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """List supplier payments with filters."""
    from app.models.supplier_payment import SupplierPaymentStatus

    # Build filters
    status_enum = None
    if status:
        try:
            status_enum = SupplierPaymentStatus(status.lower())
        except ValueError:
            valid_statuses = [s.value for s in SupplierPaymentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_statuses}",
            )

    filters = APPaymentFilters(
        supplier_id=supplier_id,
        status=status_enum,
        start_date=parse_date(start_date, "start_date") if start_date else None,
        end_date=parse_date(end_date, "end_date") if end_date else None,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_payments(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "payments": [_payment_to_dict(p) for p in result.items],
    }


@router.get(
    "/ap-payments/{payment_id}", dependencies=[Depends(Require("accounting:read"))]
)
def get_ap_payment(
    payment_id: int,
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Get supplier payment detail with allocations."""
    try:
        payment = service.get_payment(payment_id)
        allocations = service.get_payment_allocations(payment_id)
        return _payment_detail_to_dict(payment, allocations)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= CRUD ENDPOINTS =============

@router.post("/ap-payments", dependencies=[Depends(Require("books:write"))])
def create_ap_payment(
    data: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Create a new supplier payment."""
    try:
        # Convert Pydantic to service data type
        create_data = APPaymentCreateData(
            supplier_id=data.supplier_id,
            supplier_name=data.supplier_name,
            payment_date=date.fromisoformat(data.payment_date),
            posting_date=(
                date.fromisoformat(data.posting_date) if data.posting_date else None
            ),
            mode_of_payment=data.mode_of_payment,
            bank_account_id=data.bank_account_id,
            currency=data.currency,
            paid_amount=Decimal(str(data.paid_amount)),
            conversion_rate=Decimal(str(data.conversion_rate)),
            reference_number=data.reference_number,
            reference_date=(
                date.fromisoformat(data.reference_date) if data.reference_date else None
            ),
            remarks=data.remarks,
            company=data.company,
            allocations=[
                APAllocationData(
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
            ],
        )

        payment = service.create_payment(create_data)
        db.commit()
        db.refresh(payment)

        return {
            "message": "Supplier payment created",
            "id": payment.id,
            "payment_number": payment.payment_number,
        }
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/ap-payments/{payment_id}", dependencies=[Depends(Require("books:write"))]
)
def update_ap_payment(
    payment_id: int,
    data: SupplierPaymentUpdate,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Update a draft supplier payment."""
    try:
        update_data = APPaymentUpdateData(
            payment_date=(
                date.fromisoformat(data.payment_date) if data.payment_date else None
            ),
            posting_date=(
                date.fromisoformat(data.posting_date) if data.posting_date else None
            ),
            mode_of_payment=data.mode_of_payment,
            bank_account_id=data.bank_account_id,
            paid_amount=(
                Decimal(str(data.paid_amount)) if data.paid_amount is not None else None
            ),
            conversion_rate=(
                Decimal(str(data.conversion_rate))
                if data.conversion_rate is not None
                else None
            ),
            reference_number=data.reference_number,
            reference_date=(
                date.fromisoformat(data.reference_date)
                if data.reference_date
                else None
            ),
            remarks=data.remarks,
        )

        service.update_payment(payment_id, update_data)
        db.commit()

        return {"message": "Payment updated", "id": payment_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/ap-payments/{payment_id}", dependencies=[Depends(Require("books:write"))]
)
def delete_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Delete a draft supplier payment."""
    try:
        service.delete_payment(payment_id)
        db.commit()
        return {"message": "Payment deleted"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= ALLOCATION ENDPOINTS =============

@router.post(
    "/ap-payments/{payment_id}/allocations",
    dependencies=[Depends(Require("books:write"))],
)
def add_payment_allocations(
    payment_id: int,
    allocations: List[AllocationCreate],
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Add allocations to a supplier payment."""
    try:
        alloc_data = [
            APAllocationData(
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

        return {"message": f"Added {len(allocations)} allocations"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/ap-payments/{payment_id}/allocations/{allocation_id}",
    dependencies=[Depends(Require("books:write"))],
)
def remove_payment_allocation(
    payment_id: int,
    allocation_id: int,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Remove an allocation from a supplier payment."""
    try:
        service.remove_allocation(payment_id, allocation_id)
        db.commit()
        return {"message": "Allocation removed"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= WORKFLOW ENDPOINTS =============

@router.post(
    "/ap-payments/{payment_id}/submit", dependencies=[Depends(Require("books:write"))]
)
def submit_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Submit a supplier payment for approval."""
    try:
        payment = service.submit_payment(payment_id)
        db.commit()
        return {
            "message": "Payment submitted for approval",
            "status": payment.status.value,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/ap-payments/{payment_id}/approve",
    dependencies=[Depends(Require("books:approve"))],
)
def approve_ap_payment(
    payment_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Approve a supplier payment."""
    try:
        payment = service.approve_payment(payment_id, remarks)
        db.commit()
        return {
            "message": "Payment approved",
            "status": payment.status.value,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/ap-payments/{payment_id}/reject",
    dependencies=[Depends(Require("books:approve"))],
)
def reject_ap_payment(
    payment_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Reject a supplier payment."""
    try:
        payment = service.reject_payment(payment_id, reason)
        db.commit()
        return {
            "message": "Payment rejected",
            "status": payment.status.value,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/ap-payments/{payment_id}/post", dependencies=[Depends(Require("books:approve"))]
)
async def post_ap_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Post an approved supplier payment to the GL."""
    from .helpers import invalidate_report_cache

    try:
        payment = service.post_payment(payment_id)
        db.commit()

        await invalidate_report_cache()

        return {
            "message": "Payment posted",
            "journal_entry_id": payment.journal_entry_id,
            "status": payment.status.value,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= OUTSTANDING BILLS =============

@router.get(
    "/ap-payments/outstanding-bills", dependencies=[Depends(Require("accounting:read"))]
)
def get_outstanding_bills(
    supplier_id: int,
    currency: Optional[str] = None,
    service: APPaymentService = Depends(get_ap_payment_service),
) -> Dict[str, Any]:
    """Get outstanding bills available for payment."""
    docs = service.get_outstanding_bills(supplier_id, currency)

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

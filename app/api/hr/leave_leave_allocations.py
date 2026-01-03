"""
Leave Allocations Endpoints

Uses LeaveService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timezone
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_leave import LeaveAllocationStatus
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import (
    AllocationFilters,
    AllocationCreateData,
    AllocationUpdateData,
    BulkAllocationData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import (
    LeaveAllocationNotFoundError,
    ValidationError as HRValidationError,
)
from .helpers import csv_response

router = APIRouter()

# =============================================================================
# LEAVE ALLOCATION
# =============================================================================

class LeaveAllocationCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leave_type: str
    leave_type_id: Optional[int] = None
    from_date: date
    to_date: date
    new_leaves_allocated: Optional[Decimal] = Decimal("0")
    total_leaves_allocated: Optional[Decimal] = Decimal("0")
    unused_leaves: Optional[Decimal] = Decimal("0")
    carry_forwarded_leaves: Optional[Decimal] = Decimal("0")
    carry_forwarded_leaves_count: Optional[Decimal] = Decimal("0")
    leave_policy: Optional[str] = None
    status: Optional[LeaveAllocationStatus] = LeaveAllocationStatus.DRAFT
    docstatus: Optional[int] = 0
    company: Optional[str] = None


class LeaveAllocationUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leave_type: Optional[str] = None
    leave_type_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    new_leaves_allocated: Optional[Decimal] = None
    total_leaves_allocated: Optional[Decimal] = None
    unused_leaves: Optional[Decimal] = None
    carry_forwarded_leaves: Optional[Decimal] = None
    carry_forwarded_leaves_count: Optional[Decimal] = None
    leave_policy: Optional[str] = None
    status: Optional[LeaveAllocationStatus] = None
    docstatus: Optional[int] = None
    company: Optional[str] = None


class BulkLeaveAllocationCreate(BaseModel):
    """Payload for bulk creating leave allocations based on a leave policy."""
    employee_ids: List[int]
    leave_policy_id: int
    from_date: date
    to_date: date
    company: Optional[str] = None


def _serialize_allocation(a, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a LeaveAllocation model to dict."""
    result = {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "leave_type": a.leave_type,
        "leave_type_id": a.leave_type_id,
        "from_date": a.from_date.isoformat() if a.from_date else None,
        "to_date": a.to_date.isoformat() if a.to_date else None,
        "new_leaves_allocated": float(a.new_leaves_allocated) if a.new_leaves_allocated else 0,
        "total_leaves_allocated": float(a.total_leaves_allocated) if a.total_leaves_allocated else 0,
        "unused_leaves": float(a.unused_leaves) if a.unused_leaves else 0,
        "used_days": float((a.total_leaves_allocated or 0) - (a.unused_leaves or 0)),
        "status": a.status.value if a.status else None,
        "company": a.company,
    }
    if include_timestamps:
        result["carry_forwarded_leaves"] = float(a.carry_forwarded_leaves) if a.carry_forwarded_leaves else 0
        result["carry_forwarded_leaves_count"] = float(a.carry_forwarded_leaves_count) if a.carry_forwarded_leaves_count else 0
        result["leave_policy"] = a.leave_policy
        result["docstatus"] = a.docstatus
        result["created_at"] = a.created_at.isoformat() if a.created_at else None
        result["updated_at"] = a.updated_at.isoformat() if a.updated_at else None
    return result


@router.get("/leave-allocations", dependencies=[Depends(Require("hr:read"))])
def list_leave_allocations(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave allocations with filtering."""
    service = LeaveService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = LeaveAllocationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = AllocationFilters(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_allocations(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_allocation(a) for a in result.items],
    }


@router.get("/leave-allocations/export", dependencies=[Depends(Require("hr:read"))])
def export_leave_allocations(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export leave allocations to CSV."""
    service = LeaveService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = LeaveAllocationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = AllocationFilters(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    # Get all for export (no pagination limit)
    pagination = PaginationParams(offset=0, limit=10000)
    result = service.list_allocations(filters, pagination)

    rows = [["id", "employee", "employee_id", "leave_type", "from_date", "to_date", "total_leaves_allocated", "unused_leaves", "status", "company"]]
    for a in result.items:
        rows.append([
            str(a.id),
            a.employee,
            str(a.employee_id) if a.employee_id is not None else "",
            a.leave_type,
            a.from_date.isoformat() if a.from_date else "",
            a.to_date.isoformat() if a.to_date else "",
            str(float(a.total_leaves_allocated or 0)),
            str(float(a.unused_leaves or 0)),
            a.status.value if a.status else "",
            a.company or "",
        ])
    return csv_response(rows, "leave_allocations.csv")


@router.get("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave allocation detail."""
    service = LeaveService(db)
    try:
        a = service.get_allocation(allocation_id)
    except LeaveAllocationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave allocation not found")

    return _serialize_allocation(a, include_timestamps=True)


@router.post("/leave-allocations", dependencies=[Depends(Require("hr:write"))])
def create_leave_allocation(
    payload: LeaveAllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new leave allocation."""
    service = LeaveService(db, current_user)

    # Validate date order
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")

    create_data = AllocationCreateData(
        employee_id=payload.employee_id or 0,
        employee=payload.employee,
        employee_name=payload.employee_name,
        leave_type_id=payload.leave_type_id or 0,
        leave_type=payload.leave_type,
        from_date=payload.from_date,
        to_date=payload.to_date,
        new_leaves_allocated=payload.new_leaves_allocated or Decimal("0"),
        carry_forwarded_leaves=payload.carry_forwarded_leaves or Decimal("0"),
        leave_policy=payload.leave_policy,
        company=payload.company,
    )

    try:
        allocation = service.create_allocation(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_allocation(allocation.id, db)


@router.patch("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_allocation(
    allocation_id: int,
    payload: LeaveAllocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a leave allocation."""
    service = LeaveService(db, current_user)

    update_data = AllocationUpdateData(
        new_leaves_allocated=payload.new_leaves_allocated,
        carry_forwarded_leaves=payload.carry_forwarded_leaves,
        unused_leaves=payload.unused_leaves,
        status=payload.status,
    )

    try:
        service.update_allocation(allocation_id, update_data)
        db.commit()
    except LeaveAllocationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave allocation not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_allocation(allocation_id, db)


@router.delete("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a leave allocation."""
    service = LeaveService(db, current_user)

    try:
        allocation = service.get_allocation(allocation_id)
        db.delete(allocation)
        db.commit()
    except LeaveAllocationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave allocation not found")

    return {"message": "Leave allocation deleted", "id": allocation_id}


@router.post("/leave-allocations/bulk", dependencies=[Depends(Require("hr:write"))])
def bulk_create_leave_allocations(
    payload: BulkLeaveAllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Bulk create leave allocations for multiple employees based on a leave policy.

    Creates allocations for each leave type defined in the policy for each employee.
    Skips employees who already have allocations for the same leave type and overlapping period.
    """
    service = LeaveService(db, current_user)

    # Validate date order
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")

    # Load the leave policy with its details
    try:
        policy = service.get_leave_policy(payload.leave_policy_id)
    except HRValidationError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    if not policy.details:
        raise HTTPException(status_code=400, detail="Leave policy has no leave type details defined")

    created = []
    skipped = []

    for employee_id in payload.employee_ids:
        for detail in policy.details:
            if detail.leave_type_id is None:
                skipped.append({
                    "employee_id": employee_id,
                    "leave_type": detail.leave_type,
                    "reason": "Missing leave_type_id in policy detail",
                })
                continue

            # Use service bulk_allocate for each leave type
            bulk_data = BulkAllocationData(
                employee_ids=[employee_id],
                leave_type_id=detail.leave_type_id,
                leave_type=detail.leave_type,
                from_date=payload.from_date,
                to_date=payload.to_date,
                new_leaves_allocated=detail.annual_allocation or Decimal("0"),
                company=payload.company,
            )

            result = service.bulk_allocate(bulk_data)

            if result.created_count > 0:
                created.append({
                    "employee_id": employee_id,
                    "leave_type": detail.leave_type,
                    "total_allocated": float(detail.annual_allocation or 0),
                })
            if result.skipped_count > 0:
                skipped.append({
                    "employee_id": employee_id,
                    "leave_type": detail.leave_type,
                    "reason": result.errors[0] if result.errors else "Skipped",
                })

    db.commit()
    return {
        "created": len(created),
        "skipped": len(skipped),
        "total_employees": len(payload.employee_ids),
        "total_leave_types": len(policy.details),
        "created_details": created,
        "skipped_details": skipped,
    }


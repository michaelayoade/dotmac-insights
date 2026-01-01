"""
Leave Allocations Endpoints
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
from app.models.hr_leave import LeaveType, LeaveAllocation, LeaveAllocationStatus, LeavePolicy
from app.models.employee import Employee
from .helpers import (
    decimal_or_default,
    check_allocation_overlap,
    csv_response,
    validate_date_order,
    get_leave_type_constraints,
)
from app.services.audit_logger import AuditLogger, serialize_for_audit

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
    query = db.query(LeaveAllocation)

    if employee_id:
        query = query.filter(LeaveAllocation.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveAllocation.leave_type_id == leave_type_id)
    if status:
        try:
            status_enum = LeaveAllocationStatus(status)
            query = query.filter(LeaveAllocation.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(LeaveAllocation.from_date >= from_date)
    if to_date:
        query = query.filter(LeaveAllocation.to_date <= to_date)
    if company:
        query = query.filter(LeaveAllocation.company.ilike(f"%{company}%"))

    total = query.count()
    allocations = query.order_by(LeaveAllocation.from_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
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
            for a in allocations
        ],
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
    query = db.query(LeaveAllocation)
    if employee_id:
        query = query.filter(LeaveAllocation.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveAllocation.leave_type_id == leave_type_id)
    if status:
        try:
            status_enum = LeaveAllocationStatus(status)
            query = query.filter(LeaveAllocation.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(LeaveAllocation.from_date >= from_date)
    if to_date:
        query = query.filter(LeaveAllocation.to_date <= to_date)
    if company:
        query = query.filter(LeaveAllocation.company.ilike(f"%{company}%"))

    rows = [["id", "employee", "employee_id", "leave_type", "from_date", "to_date", "total_leaves_allocated", "unused_leaves", "status", "company"]]
    for a in query.order_by(LeaveAllocation.from_date.desc()).all():
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
    a = db.query(LeaveAllocation).filter(LeaveAllocation.id == allocation_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Leave allocation not found")

    return {
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
        "carry_forwarded_leaves": float(a.carry_forwarded_leaves) if a.carry_forwarded_leaves else 0,
        "carry_forwarded_leaves_count": float(a.carry_forwarded_leaves_count) if a.carry_forwarded_leaves_count else 0,
        "leave_policy": a.leave_policy,
        "status": a.status.value if a.status else None,
        "docstatus": a.docstatus,
        "company": a.company,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/leave-allocations", dependencies=[Depends(Require("hr:write"))])
def create_leave_allocation(
    payload: LeaveAllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new leave allocation."""
    # Validate date order
    validate_date_order(payload.from_date, payload.to_date, "from_date/to_date")

    # Validate no overlapping allocations for same employee + leave type
    if payload.employee_id and payload.leave_type_id:
        overlap = check_allocation_overlap(
            db,
            payload.employee_id,
            payload.leave_type_id,
            payload.from_date,
            payload.to_date,
        )
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"Overlapping allocation exists (ID: {overlap['id']}, {overlap['from_date']} to {overlap['to_date']})"
            )

        # Validate carry-forward rules
        carry_fwd = decimal_or_default(payload.carry_forwarded_leaves)
        if carry_fwd > 0 and payload.leave_type_id:
            leave_type_info = get_leave_type_constraints(db, payload.leave_type_id)
            if leave_type_info:
                # Check if leave type allows carry-forward
                if not leave_type_info["is_carry_forward"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Leave type '{leave_type_info['leave_type_name']}' does not allow carry-forward"
                    )
                # Check carry-forward cap (max_leaves_allowed as cap if set)
                if leave_type_info["max_leaves_allowed"] > 0 and carry_fwd > leave_type_info["max_leaves_allowed"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Carry-forward amount ({float(carry_fwd)}) exceeds maximum allowed ({leave_type_info['max_leaves_allowed']})"
                    )

    allocation = LeaveAllocation(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        leave_type=payload.leave_type,
        leave_type_id=payload.leave_type_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        new_leaves_allocated=decimal_or_default(payload.new_leaves_allocated),
        total_leaves_allocated=decimal_or_default(payload.total_leaves_allocated),
        unused_leaves=decimal_or_default(payload.unused_leaves),
        carry_forwarded_leaves=decimal_or_default(payload.carry_forwarded_leaves),
        carry_forwarded_leaves_count=decimal_or_default(payload.carry_forwarded_leaves_count),
        leave_policy=payload.leave_policy,
        status=payload.status or LeaveAllocationStatus.DRAFT,
        docstatus=payload.docstatus or 0,
        company=payload.company,
        created_by_id=current_user.id if current_user else None,
        updated_by_id=current_user.id if current_user else None,
    )
    db.add(allocation)
    db.flush()

    # Log audit event
    audit = AuditLogger(db)
    audit.log_create(
        doctype="leave_allocation",
        document_id=allocation.id,
        new_values=serialize_for_audit(allocation),
        user_id=current_user.id if current_user else None,
        document_name=f"{allocation.employee} - {allocation.leave_type}",
    )

    db.commit()
    return get_leave_allocation(allocation.id, db)


@router.patch("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_allocation(
    allocation_id: int,
    payload: LeaveAllocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a leave allocation."""
    allocation = db.query(LeaveAllocation).filter(LeaveAllocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Leave allocation not found")

    old_values = serialize_for_audit(allocation)
    old_status = allocation.status

    update_data = payload.model_dump(exclude_unset=True)
    decimal_fields = ["new_leaves_allocated", "total_leaves_allocated", "unused_leaves",
                      "carry_forwarded_leaves", "carry_forwarded_leaves_count"]

    for field, value in update_data.items():
        if value is not None:
            if field in decimal_fields:
                setattr(allocation, field, decimal_or_default(value))
            else:
                setattr(allocation, field, value)

    allocation.updated_by_id = current_user.id if current_user else None

    # Track status change
    if allocation.status != old_status:
        allocation.status_changed_by_id = current_user.id if current_user else None
        allocation.status_changed_at = datetime.now(timezone.utc)

    # Log audit event
    audit = AuditLogger(db)
    audit.log_update(
        doctype="leave_allocation",
        document_id=allocation.id,
        old_values=old_values,
        new_values=serialize_for_audit(allocation),
        user_id=current_user.id if current_user else None,
        document_name=f"{allocation.employee} - {allocation.leave_type}",
    )

    db.commit()
    return get_leave_allocation(allocation.id, db)


@router.delete("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a leave allocation."""
    allocation = db.query(LeaveAllocation).filter(LeaveAllocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Leave allocation not found")

    old_values = serialize_for_audit(allocation)

    # Log audit event before deletion
    audit = AuditLogger(db)
    audit.log_delete(
        doctype="leave_allocation",
        document_id=allocation.id,
        old_values=old_values,
        user_id=current_user.id if current_user else None,
        document_name=f"{allocation.employee} - {allocation.leave_type}",
    )

    db.delete(allocation)
    db.commit()
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
    # Validate date order
    validate_date_order(payload.from_date, payload.to_date, "from_date/to_date")

    # Load the leave policy with its details
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == payload.leave_policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    if not policy.details:
        raise HTTPException(status_code=400, detail="Leave policy has no leave type details defined")

    created = []
    skipped = []
    audit = AuditLogger(db)

    for employee_id in payload.employee_ids:
        for detail in policy.details:
            # Check for existing allocation
            if detail.leave_type_id is None:
                skipped.append({
                    "employee_id": employee_id,
                    "leave_type": detail.leave_type,
                    "reason": "Missing leave_type_id in policy detail",
                })
                continue
            overlap = check_allocation_overlap(
                db,
                employee_id,
                detail.leave_type_id,
                payload.from_date,
                payload.to_date,
            )
            if overlap:
                skipped.append({
                    "employee_id": employee_id,
                    "leave_type": detail.leave_type,
                    "reason": "Overlapping allocation exists",
                })
                continue

            # Create allocation based on policy detail
            allocation = LeaveAllocation(
                employee=f"EMP-{employee_id}",  # Placeholder, could be enhanced to lookup
                employee_id=employee_id,
                leave_type=detail.leave_type,
                leave_type_id=detail.leave_type_id,
                from_date=payload.from_date,
                to_date=payload.to_date,
                new_leaves_allocated=detail.annual_allocation or Decimal("0"),
                total_leaves_allocated=detail.annual_allocation or Decimal("0"),
                unused_leaves=detail.annual_allocation or Decimal("0"),
                leave_policy=policy.leave_policy_name,
                status=LeaveAllocationStatus.DRAFT,
                company=payload.company,
                created_by_id=current_user.id if current_user else None,
                updated_by_id=current_user.id if current_user else None,
            )
            db.add(allocation)
            db.flush()

            # Log audit event
            audit.log_create(
                doctype="leave_allocation",
                document_id=allocation.id,
                new_values=serialize_for_audit(allocation),
                user_id=current_user.id if current_user else None,
                document_name=f"EMP-{employee_id} - {detail.leave_type}",
                remarks=f"Bulk created from policy: {policy.leave_policy_name}",
            )

            created.append({
                "id": allocation.id,
                "employee_id": employee_id,
                "leave_type": detail.leave_type,
                "total_allocated": float(detail.annual_allocation or 0),
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


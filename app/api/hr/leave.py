"""
Leave Management Router

Endpoints for LeaveType, LeaveAllocation, LeaveApplication, HolidayList, LeavePolicy.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_leave import (
    LeaveType,
    HolidayList,
    Holiday,
    LeavePolicy,
    LeavePolicyDetail,
    LeaveAllocation,
    LeaveAllocationStatus,
    LeaveApplication,
    LeaveApplicationStatus,
)
from app.services.audit_logger import AuditLogger, serialize_for_audit
from .helpers import (
    decimal_or_default,
    csv_response,
    get_leave_balance,
    check_leave_overlap,
    check_allocation_overlap,
    get_leave_type_constraints,
    update_allocation_balance,
    validate_date_order,
)

router = APIRouter()


# =============================================================================
# LEAVE TYPE
# =============================================================================

class LeaveTypeCreate(BaseModel):
    leave_type_name: str
    max_leaves_allowed: Optional[int] = 0
    max_continuous_days_allowed: Optional[int] = 0
    is_carry_forward: Optional[bool] = False
    is_lwp: Optional[bool] = False
    is_optional_leave: Optional[bool] = False
    is_compensatory: Optional[bool] = False
    allow_encashment: Optional[bool] = False
    include_holiday: Optional[bool] = False
    is_earned_leave: Optional[bool] = False
    earned_leave_frequency: Optional[str] = None
    rounding: Optional[Decimal] = None


class LeaveTypeUpdate(BaseModel):
    leave_type_name: Optional[str] = None
    max_leaves_allowed: Optional[int] = None
    max_continuous_days_allowed: Optional[int] = None
    is_carry_forward: Optional[bool] = None
    is_lwp: Optional[bool] = None
    is_optional_leave: Optional[bool] = None
    is_compensatory: Optional[bool] = None
    allow_encashment: Optional[bool] = None
    include_holiday: Optional[bool] = None
    is_earned_leave: Optional[bool] = None
    earned_leave_frequency: Optional[str] = None
    rounding: Optional[Decimal] = None


@router.get("/leave-types", dependencies=[Depends(Require("hr:read"))])
async def list_leave_types(
    search: Optional[str] = None,
    is_lwp: Optional[bool] = None,
    is_carry_forward: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave types."""
    query = db.query(LeaveType)

    if search:
        query = query.filter(LeaveType.leave_type_name.ilike(f"%{search}%"))
    if is_lwp is not None:
        query = query.filter(LeaveType.is_lwp == is_lwp)
    if is_carry_forward is not None:
        query = query.filter(LeaveType.is_carry_forward == is_carry_forward)

    total = query.count()
    leave_types = query.order_by(LeaveType.leave_type_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": lt.id,
                "erpnext_id": lt.erpnext_id,
                "leave_type_name": lt.leave_type_name,
                "max_leaves_allowed": lt.max_leaves_allowed,
                "max_continuous_days_allowed": lt.max_continuous_days_allowed,
                "is_carry_forward": lt.is_carry_forward,
                "is_lwp": lt.is_lwp,
                "is_optional_leave": lt.is_optional_leave,
                "is_compensatory": lt.is_compensatory,
                "allow_encashment": lt.allow_encashment,
                "include_holiday": lt.include_holiday,
                "is_earned_leave": lt.is_earned_leave,
                "earned_leave_frequency": lt.earned_leave_frequency,
                "rounding": float(lt.rounding) if lt.rounding else 0.5,
            }
            for lt in leave_types
        ],
    }


@router.get("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:read"))])
async def get_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave type detail."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    return {
        "id": lt.id,
        "erpnext_id": lt.erpnext_id,
        "leave_type_name": lt.leave_type_name,
        "max_leaves_allowed": lt.max_leaves_allowed,
        "max_continuous_days_allowed": lt.max_continuous_days_allowed,
        "is_carry_forward": lt.is_carry_forward,
        "is_lwp": lt.is_lwp,
        "is_optional_leave": lt.is_optional_leave,
        "is_compensatory": lt.is_compensatory,
        "allow_encashment": lt.allow_encashment,
        "include_holiday": lt.include_holiday,
        "is_earned_leave": lt.is_earned_leave,
        "earned_leave_frequency": lt.earned_leave_frequency,
        "rounding": float(lt.rounding) if lt.rounding else 0.5,
        "created_at": lt.created_at.isoformat() if lt.created_at else None,
        "updated_at": lt.updated_at.isoformat() if lt.updated_at else None,
    }


@router.post("/leave-types", dependencies=[Depends(Require("hr:write"))])
async def create_leave_type(
    payload: LeaveTypeCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave type."""
    lt = LeaveType(
        leave_type_name=payload.leave_type_name,
        max_leaves_allowed=payload.max_leaves_allowed or 0,
        max_continuous_days_allowed=payload.max_continuous_days_allowed or 0,
        is_carry_forward=payload.is_carry_forward or False,
        is_lwp=payload.is_lwp or False,
        is_optional_leave=payload.is_optional_leave or False,
        is_compensatory=payload.is_compensatory or False,
        allow_encashment=payload.allow_encashment or False,
        include_holiday=payload.include_holiday or False,
        is_earned_leave=payload.is_earned_leave or False,
        earned_leave_frequency=payload.earned_leave_frequency,
        rounding=decimal_or_default(payload.rounding, Decimal("0.5")),
    )
    db.add(lt)
    db.commit()
    return await get_leave_type(lt.id, db)


@router.patch("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
async def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave type."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "rounding" and value is not None:
            setattr(lt, field, decimal_or_default(value))
        elif value is not None:
            setattr(lt, field, value)

    db.commit()
    return await get_leave_type(leave_type_id, db)


@router.delete("/leave-types/{leave_type_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_leave_type(
    leave_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave type."""
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")
    db.delete(lt)
    db.commit()
    return {"message": "Leave type deleted", "id": leave_type_id}


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
async def list_leave_allocations(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
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
                "status": a.status.value if a.status else None,
                "company": a.company,
            }
            for a in allocations
        ],
    }


@router.get("/leave-allocations/export", dependencies=[Depends(Require("hr:read"))])
async def export_leave_allocations(
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
            a.id,
            a.employee,
            a.employee_id,
            a.leave_type,
            a.from_date.isoformat() if a.from_date else "",
            a.to_date.isoformat() if a.to_date else "",
            float(a.total_leaves_allocated or 0),
            float(a.unused_leaves or 0),
            a.status.value if a.status else "",
            a.company or "",
        ])
    return csv_response(rows, "leave_allocations.csv")


@router.get("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:read"))])
async def get_leave_allocation(
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
async def create_leave_allocation(
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
    return await get_leave_allocation(allocation.id, db)


@router.patch("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
async def update_leave_allocation(
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
        allocation.status_changed_at = datetime.utcnow()

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
    return await get_leave_allocation(allocation.id, db)


@router.delete("/leave-allocations/{allocation_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_leave_allocation(
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
async def bulk_create_leave_allocations(
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


# =============================================================================
# LEAVE APPLICATION
# =============================================================================

class LeaveApplicationCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leave_type: str
    leave_type_id: Optional[int] = None
    from_date: date
    to_date: date
    posting_date: date
    half_day: Optional[bool] = False
    half_day_date: Optional[date] = None
    total_leave_days: Optional[Decimal] = Decimal("0")
    description: Optional[str] = None
    leave_approver: Optional[str] = None
    leave_approver_name: Optional[str] = None
    status: Optional[LeaveApplicationStatus] = LeaveApplicationStatus.OPEN
    docstatus: Optional[int] = 0
    company: Optional[str] = None


class LeaveApplicationUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leave_type: Optional[str] = None
    leave_type_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    posting_date: Optional[date] = None
    half_day: Optional[bool] = None
    half_day_date: Optional[date] = None
    total_leave_days: Optional[Decimal] = None
    description: Optional[str] = None
    leave_approver: Optional[str] = None
    leave_approver_name: Optional[str] = None
    status: Optional[LeaveApplicationStatus] = None
    docstatus: Optional[int] = None
    company: Optional[str] = None


class LeaveApplicationBulkAction(BaseModel):
    application_ids: List[int]


def _require_leave_status(application: LeaveApplication, allowed: List[LeaveApplicationStatus]):
    if application.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {application.status.value if application.status else None}",
        )


def _load_application(db: Session, application_id: int) -> LeaveApplication:
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")
    return application


@router.get("/leave-applications", dependencies=[Depends(Require("hr:read"))])
async def list_leave_applications(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave applications with filtering."""
    query = db.query(LeaveApplication)

    if employee_id:
        query = query.filter(LeaveApplication.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveApplication.leave_type_id == leave_type_id)
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
            query = query.filter(LeaveApplication.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(LeaveApplication.from_date >= from_date)
    if to_date:
        query = query.filter(LeaveApplication.to_date <= to_date)
    if company:
        query = query.filter(LeaveApplication.company.ilike(f"%{company}%"))

    total = query.count()
    applications = query.order_by(LeaveApplication.from_date.desc()).offset(offset).limit(limit).all()

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
                "total_leave_days": float(a.total_leave_days) if a.total_leave_days else 0,
                "half_day": a.half_day,
                "status": a.status.value if a.status else None,
                "leave_approver_name": a.leave_approver_name,
                "company": a.company,
            }
            for a in applications
        ],
    }


@router.get("/leave-applications/export", dependencies=[Depends(Require("hr:read"))])
async def export_leave_applications(
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export leave applications to CSV."""
    query = db.query(LeaveApplication)
    if employee_id:
        query = query.filter(LeaveApplication.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveApplication.leave_type_id == leave_type_id)
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
            query = query.filter(LeaveApplication.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(LeaveApplication.from_date >= from_date)
    if to_date:
        query = query.filter(LeaveApplication.to_date <= to_date)
    if company:
        query = query.filter(LeaveApplication.company.ilike(f"%{company}%"))

    rows = [["id", "employee", "employee_id", "leave_type", "from_date", "to_date", "total_leave_days", "status", "company"]]
    for a in query.order_by(LeaveApplication.from_date.desc()).all():
        rows.append([
            a.id,
            a.employee,
            a.employee_id,
            a.leave_type,
            a.from_date.isoformat() if a.from_date else "",
            a.to_date.isoformat() if a.to_date else "",
            float(a.total_leave_days or 0),
            a.status.value if a.status else "",
            a.company or "",
        ])
    return csv_response(rows, "leave_applications.csv")


@router.get("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:read"))])
async def get_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave application detail."""
    a = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Leave application not found")

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
        "posting_date": a.posting_date.isoformat() if a.posting_date else None,
        "half_day": a.half_day,
        "half_day_date": a.half_day_date.isoformat() if a.half_day_date else None,
        "total_leave_days": float(a.total_leave_days) if a.total_leave_days else 0,
        "description": a.description,
        "leave_approver": a.leave_approver,
        "leave_approver_name": a.leave_approver_name,
        "status": a.status.value if a.status else None,
        "docstatus": a.docstatus,
        "company": a.company,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/leave-applications", dependencies=[Depends(Require("hr:write"))])
async def create_leave_application(
    payload: LeaveApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new leave application."""
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")
    if payload.total_leave_days is not None and payload.total_leave_days < 0:
        raise HTTPException(status_code=400, detail="total_leave_days must be non-negative")

    # Validate leave type constraints if leave_type_id is provided
    if payload.leave_type_id and payload.employee_id:
        leave_type_info = get_leave_type_constraints(db, payload.leave_type_id)
        if leave_type_info:
            # Check max continuous days
            if leave_type_info["max_continuous_days_allowed"] > 0:
                requested_days = (payload.to_date - payload.from_date).days + 1
                if requested_days > leave_type_info["max_continuous_days_allowed"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Leave request exceeds maximum continuous days allowed ({leave_type_info['max_continuous_days_allowed']})"
                    )

            # Check available balance (skip for LWP - leave without pay)
            if not leave_type_info["is_lwp"]:
                available_balance = get_leave_balance(
                    db, payload.employee_id, payload.leave_type_id, payload.from_date
                )
                requested = payload.total_leave_days or Decimal("0")
                if requested > available_balance:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient leave balance. Available: {float(available_balance)}, Requested: {float(requested)}"
                    )

    # Check for overlapping leave applications
    if payload.employee_id:
        overlap = check_leave_overlap(
            db, payload.employee_id, payload.from_date, payload.to_date
        )
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"Overlapping leave application exists (ID: {overlap['id']}, {overlap['from_date']} to {overlap['to_date']})"
            )

    application = LeaveApplication(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        leave_type=payload.leave_type,
        leave_type_id=payload.leave_type_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        posting_date=payload.posting_date,
        half_day=payload.half_day or False,
        half_day_date=payload.half_day_date,
        total_leave_days=decimal_or_default(payload.total_leave_days),
        description=payload.description,
        leave_approver=payload.leave_approver,
        leave_approver_name=payload.leave_approver_name,
        status=payload.status or LeaveApplicationStatus.OPEN,
        docstatus=payload.docstatus or 0,
        company=payload.company,
        created_by_id=current_user.id if current_user else None,
        updated_by_id=current_user.id if current_user else None,
    )
    db.add(application)
    db.flush()

    # Log audit event
    audit = AuditLogger(db)
    audit.log_create(
        doctype="leave_application",
        document_id=application.id,
        new_values=serialize_for_audit(application),
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
    )

    db.commit()
    return await get_leave_application(application.id, db)


@router.patch("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
async def update_leave_application(
    application_id: int,
    payload: LeaveApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a leave application."""
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    old_values = serialize_for_audit(application)
    old_status = application.status

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            if field == "total_leave_days":
                if value < 0:
                    raise HTTPException(status_code=400, detail="total_leave_days must be non-negative")
                setattr(application, field, decimal_or_default(value))
            else:
                setattr(application, field, value)

    if application.from_date and application.to_date and application.from_date > application.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")

    # Prevent overlaps after updates
    if application.employee_id and application.from_date and application.to_date:
        overlap = check_leave_overlap(
            db,
            application.employee_id,
            application.from_date,
            application.to_date,
            exclude_id=application.id,
        )
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"Overlapping leave application exists (ID: {overlap['id']}, {overlap['from_date']} to {overlap['to_date']})"
            )

    application.updated_by_id = current_user.id if current_user else None

    # Track status change
    if application.status != old_status:
        application.status_changed_by_id = current_user.id if current_user else None
        application.status_changed_at = datetime.utcnow()

    # Log audit event
    audit = AuditLogger(db)
    audit.log_update(
        doctype="leave_application",
        document_id=application.id,
        old_values=old_values,
        new_values=serialize_for_audit(application),
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
    )

    db.commit()
    return await get_leave_application(application.id, db)


@router.delete("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a leave application."""
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    old_values = serialize_for_audit(application)

    # Log audit event before deletion
    audit = AuditLogger(db)
    audit.log_delete(
        doctype="leave_application",
        document_id=application.id,
        old_values=old_values,
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
    )

    db.delete(application)
    db.commit()
    return {"message": "Leave application deleted", "id": application_id}


@router.post("/leave-applications/{application_id}/approve", dependencies=[Depends(Require("hr:write"))])
async def approve_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve a leave application."""
    application = _load_application(db, application_id)
    _require_leave_status(application, [LeaveApplicationStatus.OPEN])

    # Re-validate balance before approval to prevent race conditions
    if application.leave_type_id and application.employee_id:
        leave_type_info = get_leave_type_constraints(db, application.leave_type_id)
        if leave_type_info and not leave_type_info["is_lwp"]:
            available_balance = get_leave_balance(
                db, application.employee_id, application.leave_type_id, application.from_date
            )
            requested = application.total_leave_days or Decimal("0")
            if requested > available_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient leave balance. Available: {float(available_balance)}, Requested: {float(requested)}"
                )

    old_status = application.status
    application.status = LeaveApplicationStatus.APPROVED
    application.status_changed_by_id = current_user.id if current_user else None
    application.status_changed_at = datetime.utcnow()
    application.updated_by_id = current_user.id if current_user else None

    # Deduct leave days from allocation balance
    if application.employee_id and application.leave_type_id:
        leave_type_info = get_leave_type_constraints(db, application.leave_type_id) if not locals().get('leave_type_info') else leave_type_info
        # Only require allocation update for non-LWP leave types
        if not leave_type_info or not leave_type_info.get("is_lwp"):
            days_to_deduct = -(application.total_leave_days or Decimal("0"))
            balance_updated = update_allocation_balance(
                db,
                application.employee_id,
                application.leave_type_id,
                application.from_date,
                days_to_deduct,
            )
            if not balance_updated:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot approve: no active leave allocation found for this employee and leave type covering the application period"
                )

    # Log audit event
    audit = AuditLogger(db)
    audit.log_approve(
        doctype="leave_application",
        document_id=application.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
        remarks=f"Status changed from {old_status.value} to approved",
    )

    db.commit()
    return await get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject a leave application."""
    application = _load_application(db, application_id)
    _require_leave_status(application, [LeaveApplicationStatus.OPEN])

    old_status = application.status
    application.status = LeaveApplicationStatus.REJECTED
    application.status_changed_by_id = current_user.id if current_user else None
    application.status_changed_at = datetime.utcnow()
    application.updated_by_id = current_user.id if current_user else None

    # Log audit event
    audit = AuditLogger(db)
    audit.log_reject(
        doctype="leave_application",
        document_id=application.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
        remarks=f"Status changed from {old_status.value} to rejected",
    )

    db.commit()
    return await get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a leave application."""
    application = _load_application(db, application_id)
    _require_leave_status(application, [LeaveApplicationStatus.OPEN, LeaveApplicationStatus.APPROVED])

    old_status = application.status

    # If application was approved, restore the leave balance
    balance_restore_warning = None
    if old_status == LeaveApplicationStatus.APPROVED and application.employee_id and application.leave_type_id:
        leave_type_info = get_leave_type_constraints(db, application.leave_type_id)
        # Only restore for non-LWP leave types
        if not leave_type_info or not leave_type_info.get("is_lwp"):
            days_to_restore = application.total_leave_days or Decimal("0")
            balance_restored = update_allocation_balance(
                db,
                application.employee_id,
                application.leave_type_id,
                application.from_date,
                days_to_restore,  # Positive to restore
            )
            if not balance_restored:
                balance_restore_warning = "Leave balance could not be restored: no active allocation found for this period"

    application.status = LeaveApplicationStatus.CANCELLED
    application.status_changed_by_id = current_user.id if current_user else None
    application.status_changed_at = datetime.utcnow()
    application.updated_by_id = current_user.id if current_user else None

    # Log audit event
    audit = AuditLogger(db)
    cancel_remarks = f"Status changed from {old_status.value} to cancelled"
    if old_status == LeaveApplicationStatus.APPROVED:
        if balance_restore_warning:
            cancel_remarks += f". WARNING: {balance_restore_warning}"
        else:
            cancel_remarks += f", restored {float(application.total_leave_days or 0)} days to allocation"
    audit.log_cancel(
        doctype="leave_application",
        document_id=application.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{application.employee} - {application.leave_type}",
        remarks=cancel_remarks,
    )

    db.commit()
    result = await get_leave_application(application_id, db)
    if balance_restore_warning:
        result["warning"] = balance_restore_warning
    return result


@router.post("/leave-applications/bulk/approve", dependencies=[Depends(Require("hr:write"))])
async def bulk_approve_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk approve leave applications."""
    updated = 0
    skipped: List[Dict[str, Any]] = []
    audit = AuditLogger(db)
    now = datetime.utcnow()

    for app_id in payload.application_ids:
        application = db.query(LeaveApplication).filter(LeaveApplication.id == app_id).first()
        if not application or application.status != LeaveApplicationStatus.OPEN:
            skipped.append({"application_id": app_id, "reason": "Not open or not found"})
            continue

        # Get leave type constraints once per iteration
        lt_info = None
        is_lwp = False
        if application.leave_type_id:
            lt_info = get_leave_type_constraints(db, application.leave_type_id)
            is_lwp = lt_info.get("is_lwp", False) if lt_info else False

        # Re-validate balance (skip for LWP)
        if application.leave_type_id and application.employee_id and not is_lwp:
            available_balance = get_leave_balance(
                db, application.employee_id, application.leave_type_id, application.from_date
            )
            requested = application.total_leave_days or Decimal("0")
            if requested > available_balance:
                skipped.append({
                    "application_id": app_id,
                    "reason": "Insufficient balance",
                    "available": float(available_balance),
                    "requested": float(requested),
                })
                continue

        # Deduct balance first (before status change) for non-LWP types
        if application.employee_id and application.leave_type_id and not is_lwp:
            days_to_deduct = -(application.total_leave_days or Decimal("0"))
            allocation_updated = update_allocation_balance(
                db,
                application.employee_id,
                application.leave_type_id,
                application.from_date,
                days_to_deduct,
            )
            if not allocation_updated:
                skipped.append({
                    "application_id": app_id,
                    "reason": "No allocation covering dates",
                })
                continue

        # Only update status after successful allocation deduction
        application.status = LeaveApplicationStatus.APPROVED
        application.status_changed_by_id = current_user.id if current_user else None
        application.status_changed_at = now
        application.updated_by_id = current_user.id if current_user else None

        audit.log_approve(
            doctype="leave_application",
            document_id=application.id,
            user_id=current_user.id if current_user else None,
            document_name=f"{application.employee} - {application.leave_type}",
            remarks="Bulk approval: open to approved",
        )
        updated += 1
    db.commit()
    return {
        "updated": updated,
        "requested": len(payload.application_ids),
        "skipped": skipped,
    }


@router.post("/leave-applications/bulk/reject", dependencies=[Depends(Require("hr:write"))])
async def bulk_reject_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reject leave applications."""
    updated = 0
    audit = AuditLogger(db)
    now = datetime.utcnow()

    for app_id in payload.application_ids:
        application = db.query(LeaveApplication).filter(LeaveApplication.id == app_id).first()
        if application and application.status == LeaveApplicationStatus.OPEN:
            old_status = application.status
            application.status = LeaveApplicationStatus.REJECTED
            application.status_changed_by_id = current_user.id if current_user else None
            application.status_changed_at = now
            application.updated_by_id = current_user.id if current_user else None

            audit.log_reject(
                doctype="leave_application",
                document_id=application.id,
                user_id=current_user.id if current_user else None,
                document_name=f"{application.employee} - {application.leave_type}",
                remarks=f"Bulk rejection: {old_status.value} to rejected",
            )
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.application_ids)}


# =============================================================================
# HOLIDAY LIST
# =============================================================================

class HolidayPayload(BaseModel):
    holiday_date: date
    description: Optional[str] = None
    weekly_off: Optional[bool] = False
    idx: Optional[int] = 0


class HolidayListCreate(BaseModel):
    holiday_list_name: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    weekly_off: Optional[str] = None
    holidays: Optional[List[HolidayPayload]] = Field(default=None)


class HolidayListUpdate(BaseModel):
    holiday_list_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    weekly_off: Optional[str] = None
    holidays: Optional[List[HolidayPayload]] = Field(default=None)


@router.get("/holiday-lists", dependencies=[Depends(Require("hr:read"))])
async def list_holiday_lists(
    company: Optional[str] = None,
    year: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List holiday lists with filtering."""
    query = db.query(HolidayList)

    if company:
        query = query.filter(HolidayList.company.ilike(f"%{company}%"))
    if year:
        query = query.filter(func.extract("year", HolidayList.from_date) == year)
    if search:
        query = query.filter(HolidayList.holiday_list_name.ilike(f"%{search}%"))

    total = query.count()
    lists = query.order_by(HolidayList.from_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": h.id,
                "erpnext_id": h.erpnext_id,
                "holiday_list_name": h.holiday_list_name,
                "from_date": h.from_date.isoformat() if h.from_date else None,
                "to_date": h.to_date.isoformat() if h.to_date else None,
                "total_holidays": h.total_holidays,
                "company": h.company,
                "weekly_off": h.weekly_off,
                "holiday_count": len(h.holidays),
            }
            for h in lists
        ],
    }


@router.get("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:read"))])
async def get_holiday_list(
    list_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get holiday list detail with holidays."""
    h = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    holidays = [
        {
            "id": hd.id,
            "holiday_date": hd.holiday_date.isoformat() if hd.holiday_date else None,
            "description": hd.description,
            "weekly_off": hd.weekly_off,
            "idx": hd.idx,
        }
        for hd in sorted(h.holidays, key=lambda x: x.idx)
    ]

    return {
        "id": h.id,
        "erpnext_id": h.erpnext_id,
        "holiday_list_name": h.holiday_list_name,
        "from_date": h.from_date.isoformat() if h.from_date else None,
        "to_date": h.to_date.isoformat() if h.to_date else None,
        "total_holidays": h.total_holidays,
        "company": h.company,
        "weekly_off": h.weekly_off,
        "holidays": holidays,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


@router.post("/holiday-lists", dependencies=[Depends(Require("hr:write"))])
async def create_holiday_list(
    payload: HolidayListCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new holiday list with holidays."""
    holiday_list = HolidayList(
        holiday_list_name=payload.holiday_list_name,
        from_date=payload.from_date,
        to_date=payload.to_date,
        company=payload.company,
        weekly_off=payload.weekly_off,
        total_holidays=len(payload.holidays) if payload.holidays else 0,
    )
    db.add(holiday_list)
    db.flush()

    if payload.holidays:
        for idx, h in enumerate(payload.holidays):
            holiday = Holiday(
                holiday_list_id=holiday_list.id,
                holiday_date=h.holiday_date,
                description=h.description,
                weekly_off=h.weekly_off or False,
                idx=h.idx if h.idx is not None else idx,
            )
            db.add(holiday)

    db.commit()
    return await get_holiday_list(holiday_list.id, db)


@router.patch("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:write"))])
async def update_holiday_list(
    list_id: int,
    payload: HolidayListUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a holiday list and optionally replace holidays."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    if payload.holiday_list_name is not None:
        holiday_list.holiday_list_name = payload.holiday_list_name
    if payload.from_date is not None:
        holiday_list.from_date = payload.from_date
    if payload.to_date is not None:
        holiday_list.to_date = payload.to_date
    if payload.company is not None:
        holiday_list.company = payload.company
    if payload.weekly_off is not None:
        holiday_list.weekly_off = payload.weekly_off

    if payload.holidays is not None:
        db.query(Holiday).filter(Holiday.holiday_list_id == holiday_list.id).delete(synchronize_session=False)
        for idx, h in enumerate(payload.holidays):
            holiday = Holiday(
                holiday_list_id=holiday_list.id,
                holiday_date=h.holiday_date,
                description=h.description,
                weekly_off=h.weekly_off or False,
                idx=h.idx if h.idx is not None else idx,
            )
            db.add(holiday)
        holiday_list.total_holidays = len(payload.holidays)

    db.commit()
    return await get_holiday_list(holiday_list.id, db)


@router.delete("/holiday-lists/{list_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_holiday_list(
    list_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a holiday list and its holidays."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()
    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    db.delete(holiday_list)
    db.commit()
    return {"message": "Holiday list deleted", "id": list_id}


# =============================================================================
# LEAVE POLICY
# =============================================================================

class LeavePolicyDetailPayload(BaseModel):
    leave_type: str
    leave_type_id: Optional[int] = None
    annual_allocation: Optional[Decimal] = Decimal("0")
    idx: Optional[int] = 0


class LeavePolicyCreate(BaseModel):
    leave_policy_name: str
    details: Optional[List[LeavePolicyDetailPayload]] = Field(default=None)


class LeavePolicyUpdate(BaseModel):
    leave_policy_name: Optional[str] = None
    details: Optional[List[LeavePolicyDetailPayload]] = Field(default=None)


@router.get("/leave-policies", dependencies=[Depends(Require("hr:read"))])
async def list_leave_policies(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List leave policies with filtering."""
    query = db.query(LeavePolicy)

    if search:
        query = query.filter(LeavePolicy.leave_policy_name.ilike(f"%{search}%"))

    total = query.count()
    policies = query.order_by(LeavePolicy.leave_policy_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "leave_policy_name": p.leave_policy_name,
                "detail_count": len(p.details),
            }
            for p in policies
        ],
    }


@router.get("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:read"))])
async def get_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get leave policy detail with details."""
    p = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    details = [
        {
            "id": d.id,
            "leave_type": d.leave_type,
            "leave_type_id": d.leave_type_id,
            "annual_allocation": float(d.annual_allocation) if d.annual_allocation else 0,
            "idx": d.idx,
        }
        for d in sorted(p.details, key=lambda x: x.idx)
    ]

    return {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "leave_policy_name": p.leave_policy_name,
        "details": details,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/leave-policies", dependencies=[Depends(Require("hr:write"))])
async def create_leave_policy(
    payload: LeavePolicyCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new leave policy with details."""
    policy = LeavePolicy(
        leave_policy_name=payload.leave_policy_name,
    )
    db.add(policy)
    db.flush()

    if payload.details:
        for idx, d in enumerate(payload.details):
            detail = LeavePolicyDetail(
                leave_policy_id=policy.id,
                leave_type=d.leave_type,
                leave_type_id=d.leave_type_id,
                annual_allocation=decimal_or_default(d.annual_allocation),
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_leave_policy(policy.id, db)


@router.patch("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
async def update_leave_policy(
    policy_id: int,
    payload: LeavePolicyUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a leave policy and optionally replace details."""
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    if payload.leave_policy_name is not None:
        policy.leave_policy_name = payload.leave_policy_name

    if payload.details is not None:
        db.query(LeavePolicyDetail).filter(LeavePolicyDetail.leave_policy_id == policy.id).delete(synchronize_session=False)
        for idx, d in enumerate(payload.details):
            detail = LeavePolicyDetail(
                leave_policy_id=policy.id,
                leave_type=d.leave_type,
                leave_type_id=d.leave_type_id,
                annual_allocation=decimal_or_default(d.annual_allocation),
                idx=d.idx if d.idx is not None else idx,
            )
            db.add(detail)

    db.commit()
    return await get_leave_policy(policy.id, db)


@router.delete("/leave-policies/{policy_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_leave_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a leave policy and its details."""
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    db.delete(policy)
    db.commit()
    return {"message": "Leave policy deleted", "id": policy_id}

"""
Leave Applications Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_leave import (
    LeaveType,
    LeaveAllocation,
    LeaveApplication,
    LeaveApplicationStatus,
)
from app.models.employee import Employee
from app.services.audit_logger import AuditLogger, serialize_for_audit
from .helpers import (
    decimal_or_default,
    csv_response,
    get_leave_balance,
    check_leave_overlap,
    get_leave_type_constraints,
    update_allocation_balance,
    validate_date_order,
)

router = APIRouter()

# =============================================================================
# LEAVE APPLICATION
# =============================================================================

class LeaveApplicationCreate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leave_type: Optional[str] = None
    leave_type_id: Optional[int] = None
    from_date: date
    to_date: date
    posting_date: Optional[date] = None
    half_day: Optional[bool] = False
    half_day_date: Optional[date] = None
    total_leave_days: Optional[Decimal] = Decimal("0")
    description: Optional[str] = None
    reason: Optional[str] = None
    leave_approver: Optional[str] = None
    leave_approver_name: Optional[str] = None
    status: Optional[LeaveApplicationStatus] = LeaveApplicationStatus.OPEN
    docstatus: Optional[int] = 0
    company: Optional[str] = None

    @field_validator("status", mode="before")
    def _normalize_status(cls, value):
        if isinstance(value, str) and value.lower() == "pending":
            return "open"
        return value


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

    @field_validator("status", mode="before")
    def _normalize_status(cls, value):
        if isinstance(value, str) and value.lower() == "pending":
            return "open"
        return value


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
def list_leave_applications(
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
    """List leave applications with filtering."""
    query = db.query(LeaveApplication)

    if employee_id:
        query = query.filter(LeaveApplication.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveApplication.leave_type_id == leave_type_id)
    if status:
        try:
            normalized_status = "open" if status == "pending" else status
            status_enum = LeaveApplicationStatus(normalized_status)
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
def export_leave_applications(
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
            str(a.id),
            a.employee,
            str(a.employee_id) if a.employee_id is not None else "",
            a.leave_type,
            a.from_date.isoformat() if a.from_date else "",
            a.to_date.isoformat() if a.to_date else "",
            str(float(a.total_leave_days or 0)),
            a.status.value if a.status else "",
            a.company or "",
        ])
    return csv_response(rows, "leave_applications.csv")


@router.get("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:read"))])
def get_leave_application(
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
def create_leave_application(
    payload: LeaveApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new leave application."""
    if not payload.employee and not payload.employee_id:
        raise HTTPException(status_code=400, detail="employee or employee_id is required")

    if not payload.leave_type and not payload.leave_type_id:
        raise HTTPException(status_code=400, detail="leave_type or leave_type_id is required")

    if payload.description is None and payload.reason:
        payload.description = payload.reason

    if payload.posting_date is None:
        payload.posting_date = date.today()

    if payload.employee_id and not payload.employee:
        employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if employee:
            payload.employee = employee.employee_number or f"EMP-{employee.id}"
            if payload.employee_name is None:
                payload.employee_name = employee.name
    if payload.leave_type_id and not payload.leave_type:
        leave_type = db.query(LeaveType).filter(LeaveType.id == payload.leave_type_id).first()
        if leave_type:
            payload.leave_type = leave_type.leave_type_name
        else:
            raise HTTPException(status_code=400, detail=f"Leave type {payload.leave_type_id} not found")

    if payload.employee is None:
        raise HTTPException(status_code=400, detail="employee is required")
    if payload.leave_type is None:
        raise HTTPException(status_code=400, detail="leave_type is required")

    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")
    if payload.total_leave_days is not None and payload.total_leave_days < 0:
        raise HTTPException(status_code=400, detail="total_leave_days must be non-negative")
    if payload.total_leave_days is None or payload.total_leave_days == 0:
        payload.total_leave_days = Decimal((payload.to_date - payload.from_date).days + 1)

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
    return get_leave_application(application.id, db)


@router.patch("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_application(
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
        application.status_changed_at = datetime.now(timezone.utc)

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
    return get_leave_application(application.id, db)


@router.delete("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_application(
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
def approve_leave_application(
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
    application.status_changed_at = datetime.now(timezone.utc)
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
    return get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/reject", dependencies=[Depends(Require("hr:write"))])
def reject_leave_application(
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
    application.status_changed_at = datetime.now(timezone.utc)
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
    return get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/cancel", dependencies=[Depends(Require("hr:write"))])
def cancel_leave_application(
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
    application.status_changed_at = datetime.now(timezone.utc)
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
    result = get_leave_application(application_id, db)
    if balance_restore_warning:
        result["warning"] = balance_restore_warning
    return result


@router.post("/leave-applications/bulk/approve", dependencies=[Depends(Require("hr:write"))])
def bulk_approve_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk approve leave applications."""
    updated = 0
    skipped: List[Dict[str, Any]] = []
    audit = AuditLogger(db)
    now = datetime.now(timezone.utc)

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
def bulk_reject_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reject leave applications."""
    updated = 0
    audit = AuditLogger(db)
    now = datetime.now(timezone.utc)

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



"""
Leave Applications Endpoints

Uses LeaveService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_leave import LeaveApplicationStatus
from app.models.employee import Employee
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import (
    ApplicationFilters,
    ApplicationCreateData,
    ApplicationUpdateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import (
    LeaveApplicationNotFoundError,
    LeaveStatusTransitionError,
    InsufficientLeaveBalanceError,
    LeaveOverlapError,
    LeavePolicyViolationError,
    ValidationError as HRValidationError,
)
from .helpers import csv_response

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


def _serialize_application(a, include_timestamps: bool = False) -> Dict[str, Any]:
    """Serialize a LeaveApplication model to dict."""
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
        "total_leave_days": float(a.total_leave_days) if a.total_leave_days else 0,
        "half_day": a.half_day,
        "status": a.status.value if a.status else None,
        "leave_approver_name": a.leave_approver_name,
        "company": a.company,
    }
    if include_timestamps:
        result["posting_date"] = a.posting_date.isoformat() if a.posting_date else None
        result["half_day_date"] = a.half_day_date.isoformat() if a.half_day_date else None
        result["description"] = a.description
        result["leave_approver"] = a.leave_approver
        result["docstatus"] = a.docstatus
        result["created_at"] = a.created_at.isoformat() if a.created_at else None
        result["updated_at"] = a.updated_at.isoformat() if a.updated_at else None
    return result


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
    service = LeaveService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            normalized_status = "open" if status == "pending" else status
            status_enum = LeaveApplicationStatus(normalized_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = ApplicationFilters(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_applications(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_application(a) for a in result.items],
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
    service = LeaveService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = ApplicationFilters(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    # Get all for export (no pagination limit)
    pagination = PaginationParams(offset=0, limit=10000)
    result = service.list_applications(filters, pagination)

    rows = [["id", "employee", "employee_id", "leave_type", "from_date", "to_date", "total_leave_days", "status", "company"]]
    for a in result.items:
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
    service = LeaveService(db)
    try:
        a = service.get_application(application_id)
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")

    return _serialize_application(a, include_timestamps=True)


@router.post("/leave-applications", dependencies=[Depends(Require("hr:write"))])
def create_leave_application(
    payload: LeaveApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new leave application."""
    service = LeaveService(db, current_user)

    if not payload.employee and not payload.employee_id:
        raise HTTPException(status_code=400, detail="employee or employee_id is required")

    if not payload.leave_type and not payload.leave_type_id:
        raise HTTPException(status_code=400, detail="leave_type or leave_type_id is required")

    # Resolve employee info if needed
    employee = payload.employee
    employee_name = payload.employee_name
    if payload.employee_id and not payload.employee:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if emp:
            employee = emp.employee_number or f"EMP-{emp.id}"
            if employee_name is None:
                employee_name = emp.name

    # Resolve leave type if needed
    leave_type = payload.leave_type
    if payload.leave_type_id and not payload.leave_type:
        try:
            lt = service.get_leave_type(payload.leave_type_id)
            leave_type = lt.leave_type_name
        except HRValidationError:
            raise HTTPException(status_code=400, detail=f"Leave type {payload.leave_type_id} not found")

    create_data = ApplicationCreateData(
        employee_id=payload.employee_id or 0,
        employee=employee or "",
        employee_name=employee_name,
        leave_type_id=payload.leave_type_id or 0,
        leave_type=leave_type or "",
        from_date=payload.from_date,
        to_date=payload.to_date,
        half_day=payload.half_day or False,
        half_day_date=payload.half_day_date,
        description=payload.description or payload.reason,
        leave_approver=payload.leave_approver,
        leave_approver_name=payload.leave_approver_name,
        company=payload.company,
    )

    try:
        application = service.create_application(create_data)
        db.commit()
    except InsufficientLeaveBalanceError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except LeaveOverlapError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except LeavePolicyViolationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_application(application.id, db)


@router.patch("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
def update_leave_application(
    application_id: int,
    payload: LeaveApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a leave application."""
    service = LeaveService(db, current_user)

    update_data = ApplicationUpdateData(
        from_date=payload.from_date,
        to_date=payload.to_date,
        half_day=payload.half_day,
        half_day_date=payload.half_day_date,
        description=payload.description,
        leave_approver=payload.leave_approver,
        leave_approver_name=payload.leave_approver_name,
    )

    try:
        service.update_application(application_id, update_data)
        db.commit()
    except LeaveApplicationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave application not found")
    except LeaveOverlapError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_application(application_id, db)


@router.delete("/leave-applications/{application_id}", dependencies=[Depends(Require("hr:write"))])
def delete_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a leave application."""
    service = LeaveService(db, current_user)

    try:
        application = service.get_application(application_id)
        db.delete(application)
        db.commit()
    except LeaveApplicationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave application not found")

    return {"message": "Leave application deleted", "id": application_id}


@router.post("/leave-applications/{application_id}/approve", dependencies=[Depends(Require("hr:write"))])
def approve_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve a leave application."""
    service = LeaveService(db, current_user)

    try:
        service.approve_application(application_id)
        db.commit()
    except LeaveApplicationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave application not found")
    except LeaveStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientLeaveBalanceError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/reject", dependencies=[Depends(Require("hr:write"))])
def reject_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject a leave application."""
    service = LeaveService(db, current_user)

    try:
        service.reject_application(application_id)
        db.commit()
    except LeaveApplicationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave application not found")
    except LeaveStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_application(application_id, db)


@router.post("/leave-applications/{application_id}/cancel", dependencies=[Depends(Require("hr:write"))])
def cancel_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a leave application."""
    service = LeaveService(db, current_user)

    try:
        service.cancel_application(application_id)
        db.commit()
    except LeaveApplicationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Leave application not found")
    except LeaveStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return get_leave_application(application_id, db)


@router.post("/leave-applications/bulk/approve", dependencies=[Depends(Require("hr:write"))])
def bulk_approve_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk approve leave applications."""
    service = LeaveService(db, current_user)

    result = service.bulk_approve(payload.application_ids)
    db.commit()

    return {
        "updated": result.approved_count,
        "requested": len(payload.application_ids),
        "skipped": [
            {"application_id": s.application_id, "reason": s.reason}
            for s in result.skipped
        ],
    }


@router.post("/leave-applications/bulk/reject", dependencies=[Depends(Require("hr:write"))])
def bulk_reject_leave_applications(
    payload: LeaveApplicationBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reject leave applications."""
    service = LeaveService(db, current_user)

    result = service.bulk_reject(payload.application_ids)
    db.commit()

    return {"updated": result.rejected_count, "requested": len(payload.application_ids)}



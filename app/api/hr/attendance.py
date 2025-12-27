"""
Attendance Management Router

Endpoints for ShiftType, ShiftAssignment, Attendance, AttendanceRequest.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date, time, datetime
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_attendance import (
    ShiftType,
    ShiftAssignment,
    Attendance,
    AttendanceStatus,
    AttendanceRequest,
    AttendanceRequestStatus,
)
from .helpers import decimal_or_default, csv_response, validate_date_order, now

router = APIRouter()


# =============================================================================
# SHIFT TYPE
# =============================================================================

@router.get("/shift-types", dependencies=[Depends(Require("hr:read"))])
async def list_shift_types(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List shift types."""
    query = db.query(ShiftType)

    if search:
        query = query.filter(ShiftType.shift_type_name.ilike(f"%{search}%"))

    total = query.count()
    shift_types = query.order_by(ShiftType.shift_type_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": st.id,
                "erpnext_id": st.erpnext_id,
                "shift_type_name": st.shift_type_name,
                "start_time": st.start_time.isoformat() if st.start_time else None,
                "end_time": st.end_time.isoformat() if st.end_time else None,
                "enable_auto_attendance": st.enable_auto_attendance,
                "holiday_list": st.holiday_list,
            }
            for st in shift_types
        ],
    }


@router.get("/shift-types/{shift_type_id}", dependencies=[Depends(Require("hr:read"))])
async def get_shift_type(
    shift_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get shift type detail."""
    st = db.query(ShiftType).filter(ShiftType.id == shift_type_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Shift type not found")

    return {
        "id": st.id,
        "erpnext_id": st.erpnext_id,
        "shift_type_name": st.shift_type_name,
        "start_time": st.start_time.isoformat() if st.start_time else None,
        "end_time": st.end_time.isoformat() if st.end_time else None,
        "working_hours_threshold_for_half_day": float(st.working_hours_threshold_for_half_day) if st.working_hours_threshold_for_half_day else 0,
        "working_hours_threshold_for_absent": float(st.working_hours_threshold_for_absent) if st.working_hours_threshold_for_absent else 0,
        "determine_check_in_and_check_out": st.determine_check_in_and_check_out,
        "begin_check_in_before_shift_start_time": st.begin_check_in_before_shift_start_time,
        "allow_check_out_after_shift_end_time": st.allow_check_out_after_shift_end_time,
        "enable_auto_attendance": st.enable_auto_attendance,
        "enable_entry_grace_period": st.enable_entry_grace_period,
        "late_entry_grace_period": st.late_entry_grace_period,
        "enable_exit_grace_period": st.enable_exit_grace_period,
        "early_exit_grace_period": st.early_exit_grace_period,
        "holiday_list": st.holiday_list,
        "created_at": st.created_at.isoformat() if st.created_at else None,
        "updated_at": st.updated_at.isoformat() if st.updated_at else None,
    }


# =============================================================================
# SHIFT ASSIGNMENT
# =============================================================================

class ShiftAssignmentCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    shift_type: str
    shift_type_id: Optional[int] = None
    start_date: date
    end_date: Optional[date] = None
    company: Optional[str] = None
    docstatus: Optional[int] = 0


class ShiftAssignmentUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    shift_type: Optional[str] = None
    shift_type_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None


@router.get("/shift-assignments", dependencies=[Depends(Require("hr:read"))])
async def list_shift_assignments(
    employee_id: Optional[int] = None,
    shift_type_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List shift assignments with filtering."""
    query = db.query(ShiftAssignment)

    if employee_id:
        query = query.filter(ShiftAssignment.employee_id == employee_id)
    if shift_type_id:
        query = query.filter(ShiftAssignment.shift_type_id == shift_type_id)
    if start_date:
        query = query.filter(ShiftAssignment.start_date >= start_date)
    if end_date:
        query = query.filter(
            (ShiftAssignment.end_date <= end_date) | (ShiftAssignment.end_date == None)
        )
    if company:
        query = query.filter(ShiftAssignment.company.ilike(f"%{company}%"))

    total = query.count()
    assignments = query.order_by(ShiftAssignment.start_date.desc()).offset(offset).limit(limit).all()

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
                "shift_type": a.shift_type,
                "shift_type_id": a.shift_type_id,
                "start_date": a.start_date.isoformat() if a.start_date else None,
                "end_date": a.end_date.isoformat() if a.end_date else None,
                "company": a.company,
            }
            for a in assignments
        ],
    }


@router.get("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:read"))])
async def get_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get shift assignment detail."""
    a = db.query(ShiftAssignment).filter(ShiftAssignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    return {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "shift_type": a.shift_type,
        "shift_type_id": a.shift_type_id,
        "start_date": a.start_date.isoformat() if a.start_date else None,
        "end_date": a.end_date.isoformat() if a.end_date else None,
        "company": a.company,
        "docstatus": a.docstatus,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/shift-assignments", dependencies=[Depends(Require("hr:write"))])
async def create_shift_assignment(
    payload: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new shift assignment."""
    validate_date_order(payload.start_date, payload.end_date, "start_date/end_date")

    assignment = ShiftAssignment(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        shift_type=payload.shift_type,
        shift_type_id=payload.shift_type_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
        docstatus=payload.docstatus or 0,
    )
    db.add(assignment)
    db.commit()
    return await get_shift_assignment(assignment.id, db)


@router.patch("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def update_shift_assignment(
    assignment_id: int,
    payload: ShiftAssignmentUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a shift assignment."""
    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(assignment, field, value)

    validate_date_order(assignment.start_date, assignment.end_date, "start_date/end_date")

    db.commit()
    return await get_shift_assignment(assignment.id, db)


@router.delete("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a shift assignment."""
    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    db.delete(assignment)
    db.commit()
    return {"message": "Shift assignment deleted", "id": assignment_id}


# =============================================================================
# ATTENDANCE
# =============================================================================

class AttendanceCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    attendance_date: date
    status: Optional[AttendanceStatus] = AttendanceStatus.PRESENT
    leave_type: Optional[str] = None
    leave_application: Optional[str] = None
    shift: Optional[str] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    working_hours: Optional[Decimal] = Decimal("0")
    late_entry: Optional[bool] = False
    early_exit: Optional[bool] = False
    company: Optional[str] = None
    docstatus: Optional[int] = 0
    # Geolocation fields
    check_in_latitude: Optional[float] = None
    check_in_longitude: Optional[float] = None
    check_out_latitude: Optional[float] = None
    check_out_longitude: Optional[float] = None
    device_info: Optional[str] = None


class AttendanceUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    attendance_date: Optional[date] = None
    status: Optional[AttendanceStatus] = None
    leave_type: Optional[str] = None
    leave_application: Optional[str] = None
    shift: Optional[str] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    working_hours: Optional[Decimal] = None
    late_entry: Optional[bool] = None
    early_exit: Optional[bool] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None
    # Geolocation fields
    check_in_latitude: Optional[float] = None
    check_in_longitude: Optional[float] = None
    check_out_latitude: Optional[float] = None
    check_out_longitude: Optional[float] = None
    device_info: Optional[str] = None


class BulkAttendancePayload(BaseModel):
    employee_ids: List[int]
    attendance_date: date
    status: AttendanceStatus


class CheckInPayload(BaseModel):
    """Payload for check-in with optional geolocation and device info."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None


class CheckOutPayload(BaseModel):
    """Payload for check-out with optional geolocation."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.get("/attendances", dependencies=[Depends(Require("hr:read"))])
async def list_attendances(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    late_entry: Optional[bool] = None,
    early_exit: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attendances with filtering."""
    query = db.query(Attendance)

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if status:
        try:
            status_enum = AttendanceStatus(status)
            query = query.filter(Attendance.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        query = query.filter(Attendance.attendance_date <= to_date)
    if company:
        query = query.filter(Attendance.company.ilike(f"%{company}%"))
    if late_entry is not None:
        query = query.filter(Attendance.late_entry == late_entry)
    if early_exit is not None:
        query = query.filter(Attendance.early_exit == early_exit)

    total = query.count()
    attendances = query.order_by(Attendance.attendance_date.desc()).offset(offset).limit(limit).all()

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
                "attendance_date": a.attendance_date.isoformat() if a.attendance_date else None,
                "status": a.status.value if a.status else None,
                "shift": a.shift,
                "in_time": a.in_time.isoformat() if a.in_time else None,
                "out_time": a.out_time.isoformat() if a.out_time else None,
                "working_hours": float(a.working_hours) if a.working_hours else 0,
                "late_entry": a.late_entry,
                "early_exit": a.early_exit,
                "company": a.company,
            }
            for a in attendances
        ],
    }


@router.get("/attendances/export", dependencies=[Depends(Require("hr:read"))])
async def export_attendances(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export attendances to CSV."""
    query = db.query(Attendance)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if status:
        try:
            status_enum = AttendanceStatus(status)
            query = query.filter(Attendance.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        query = query.filter(Attendance.attendance_date <= to_date)
    if company:
        query = query.filter(Attendance.company.ilike(f"%{company}%"))

    rows = [["id", "employee", "employee_id", "attendance_date", "status", "in_time", "out_time", "working_hours", "late_entry", "early_exit", "company"]]
    for a in query.order_by(Attendance.attendance_date.desc()).all():
        rows.append([
            str(a.id),
            a.employee,
            str(a.employee_id) if a.employee_id is not None else "",
            a.attendance_date.isoformat() if a.attendance_date else "",
            a.status.value if a.status else "",
            a.in_time.isoformat() if a.in_time else "",
            a.out_time.isoformat() if a.out_time else "",
            str(float(a.working_hours or 0)),
            str(bool(a.late_entry)),
            str(bool(a.early_exit)),
            a.company or "",
        ])
    return csv_response(rows, "attendances.csv")


@router.get("/attendances/summary", dependencies=[Depends(Require("hr:read"))])
async def attendance_summary(
    employee_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance summary statistics."""
    query = db.query(Attendance.status, func.count(Attendance.id))

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if from_date:
        query = query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        query = query.filter(Attendance.attendance_date <= to_date)
    if company:
        query = query.filter(Attendance.company.ilike(f"%{company}%"))

    results = query.group_by(Attendance.status).all()
    status_counts = {row[0].value if row[0] else None: int(row[1] or 0) for row in results}

    late_count = db.query(func.count(Attendance.id)).filter(Attendance.late_entry == True)
    early_count = db.query(func.count(Attendance.id)).filter(Attendance.early_exit == True)

    if employee_id:
        late_count = late_count.filter(Attendance.employee_id == employee_id)
        early_count = early_count.filter(Attendance.employee_id == employee_id)
    if from_date:
        late_count = late_count.filter(Attendance.attendance_date >= from_date)
        early_count = early_count.filter(Attendance.attendance_date >= from_date)
    if to_date:
        late_count = late_count.filter(Attendance.attendance_date <= to_date)
        early_count = early_count.filter(Attendance.attendance_date <= to_date)
    if company:
        late_count = late_count.filter(Attendance.company.ilike(f"%{company}%"))
        early_count = early_count.filter(Attendance.company.ilike(f"%{company}%"))

    return {
        "status_counts": status_counts,
        "late_entries": late_count.scalar() or 0,
        "early_exits": early_count.scalar() or 0,
    }


@router.get("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:read"))])
async def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance detail."""
    a = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attendance not found")

    return {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "attendance_date": a.attendance_date.isoformat() if a.attendance_date else None,
        "status": a.status.value if a.status else None,
        "leave_type": a.leave_type,
        "leave_application": a.leave_application,
        "shift": a.shift,
        "in_time": a.in_time.isoformat() if a.in_time else None,
        "out_time": a.out_time.isoformat() if a.out_time else None,
        "working_hours": float(a.working_hours) if a.working_hours else 0,
        "check_in_latitude": a.check_in_latitude,
        "check_in_longitude": a.check_in_longitude,
        "check_out_latitude": a.check_out_latitude,
        "check_out_longitude": a.check_out_longitude,
        "device_info": a.device_info,
        "late_entry": a.late_entry,
        "early_exit": a.early_exit,
        "company": a.company,
        "docstatus": a.docstatus,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/attendances", dependencies=[Depends(Require("hr:write"))])
async def create_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new attendance record."""
    # Check for duplicate attendance (employee_id + attendance_date)
    if payload.employee_id:
        existing = db.query(Attendance).filter(
            Attendance.employee_id == payload.employee_id,
            Attendance.attendance_date == payload.attendance_date,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Attendance already exists for employee on {payload.attendance_date} (ID: {existing.id})"
            )

    # Validate in_time < out_time if both are provided
    if payload.in_time and payload.out_time and payload.in_time >= payload.out_time:
        raise HTTPException(
            status_code=400,
            detail="in_time must be before out_time"
        )

    attendance = Attendance(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        attendance_date=payload.attendance_date,
        status=payload.status or AttendanceStatus.PRESENT,
        leave_type=payload.leave_type,
        leave_application=payload.leave_application,
        shift=payload.shift,
        in_time=payload.in_time,
        out_time=payload.out_time,
        working_hours=decimal_or_default(payload.working_hours),
        check_in_latitude=payload.check_in_latitude,
        check_in_longitude=payload.check_in_longitude,
        check_out_latitude=payload.check_out_latitude,
        check_out_longitude=payload.check_out_longitude,
        device_info=payload.device_info,
        late_entry=payload.late_entry or False,
        early_exit=payload.early_exit or False,
        company=payload.company,
        docstatus=payload.docstatus or 0,
    )
    db.add(attendance)
    db.commit()
    return await get_attendance(attendance.id, db)


@router.patch("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:write"))])
async def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an attendance record."""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Determine target employee/date for duplicate check
    target_employee_id = update_data.get("employee_id", attendance.employee_id)
    target_date = update_data.get("attendance_date", attendance.attendance_date)
    if target_employee_id and target_date:
        existing = db.query(Attendance).filter(
            Attendance.employee_id == target_employee_id,
            Attendance.attendance_date == target_date,
            Attendance.id != attendance_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Attendance already exists for employee on {target_date} (ID: {existing.id})"
            )

    # Validate time ordering with prospective values
    prospective_in_time = update_data.get("in_time", attendance.in_time)
    prospective_out_time = update_data.get("out_time", attendance.out_time)
    if prospective_in_time and prospective_out_time and prospective_in_time >= prospective_out_time:
        raise HTTPException(status_code=400, detail="in_time must be before out_time")

    for field, value in update_data.items():
        if value is not None:
            if field == "working_hours":
                setattr(attendance, field, decimal_or_default(value))
            else:
                setattr(attendance, field, value)

    db.commit()
    return await get_attendance(attendance.id, db)


@router.delete("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an attendance record."""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")

    db.delete(attendance)
    db.commit()
    return {"message": "Attendance deleted", "id": attendance_id}


@router.post("/attendances/{attendance_id}/check-in", dependencies=[Depends(Require("hr:write"))])
async def check_in(
    attendance_id: int,
    payload: Optional[CheckInPayload] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record check-in time for attendance with optional geolocation."""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")

    if attendance.in_time:
        raise HTTPException(status_code=400, detail="Already checked in")

    attendance.in_time = now()

    # Store geolocation and device info if provided
    if payload:
        if payload.latitude is not None:
            attendance.check_in_latitude = payload.latitude
        if payload.longitude is not None:
            attendance.check_in_longitude = payload.longitude
        if payload.device_info:
            attendance.device_info = payload.device_info

    db.commit()
    return await get_attendance(attendance_id, db)


@router.post("/attendances/{attendance_id}/check-out", dependencies=[Depends(Require("hr:write"))])
async def check_out(
    attendance_id: int,
    payload: Optional[CheckOutPayload] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record check-out time for attendance with optional geolocation."""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")

    if not attendance.in_time:
        raise HTTPException(status_code=400, detail="Must check in before checking out")
    if attendance.out_time:
        raise HTTPException(status_code=400, detail="Already checked out")

    attendance.out_time = now()

    # Store geolocation if provided
    if payload:
        if payload.latitude is not None:
            attendance.check_out_latitude = payload.latitude
        if payload.longitude is not None:
            attendance.check_out_longitude = payload.longitude

    # Calculate working hours
    if attendance.in_time and attendance.out_time:
        delta = attendance.out_time - attendance.in_time
        attendance.working_hours = Decimal(str(delta.total_seconds() / 3600))

    db.commit()
    return await get_attendance(attendance_id, db)


@router.post("/attendances/bulk/mark", dependencies=[Depends(Require("hr:write"))])
async def bulk_mark_attendance(
    payload: BulkAttendancePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Bulk mark attendance for multiple employees on a given date.

    Returns details on created vs skipped (already existed) entries.
    """
    created = []
    skipped = []
    audit = AuditLogger(db)

    for emp_id in payload.employee_ids:
        existing = db.query(Attendance).filter(
            Attendance.employee_id == emp_id,
            Attendance.attendance_date == payload.attendance_date,
        ).first()

        if existing:
            # Skip - attendance already exists for this employee on this date
            skipped.append({
                "employee_id": emp_id,
                "existing_id": existing.id,
                "existing_status": existing.status.value if existing.status else None,
            })
        else:
            attendance = Attendance(
                employee=f"EMP-{emp_id}",
                employee_id=emp_id,
                attendance_date=payload.attendance_date,
                status=payload.status,
                created_by_id=current_user.id if current_user else None,
            )
            db.add(attendance)
            db.flush()
            created.append({
                "employee_id": emp_id,
                "id": attendance.id,
            })

    # Log audit event for bulk operation
    if created:
        audit.log_create(
            doctype="attendance",
            document_id=0,  # Bulk operation
            new_values={"employee_ids": [c["employee_id"] for c in created], "status": payload.status.value},
            user_id=current_user.id if current_user else None,
            document_name=f"Bulk attendance for {payload.attendance_date}",
            remarks=f"Bulk created {len(created)} attendance records",
        )

    db.commit()
    return {
        "created": len(created),
        "skipped": len(skipped),
        "total": len(payload.employee_ids),
        "created_details": created,
        "skipped_details": skipped,
    }


# =============================================================================
# ATTENDANCE REQUEST
# =============================================================================

class AttendanceRequestCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    from_date: date
    to_date: date
    half_day: Optional[bool] = False
    half_day_date: Optional[date] = None
    reason: Optional[str] = None
    explanation: Optional[str] = None
    status: Optional[AttendanceRequestStatus] = AttendanceRequestStatus.DRAFT
    company: Optional[str] = None
    docstatus: Optional[int] = 0


class AttendanceRequestUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    half_day: Optional[bool] = None
    half_day_date: Optional[date] = None
    reason: Optional[str] = None
    explanation: Optional[str] = None
    status: Optional[AttendanceRequestStatus] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None


class AttendanceRequestBulkAction(BaseModel):
    request_ids: List[int]


def _require_request_status(request: AttendanceRequest, allowed: List[AttendanceRequestStatus]):
    if request.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {request.status.value if request.status else None}",
        )


def _load_request(db: Session, request_id: int) -> AttendanceRequest:
    request = db.query(AttendanceRequest).filter(AttendanceRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Attendance request not found")
    return request


@router.get("/attendance-requests", dependencies=[Depends(Require("hr:read"))])
async def list_attendance_requests(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attendance requests with filtering."""
    query = db.query(AttendanceRequest)

    if employee_id:
        query = query.filter(AttendanceRequest.employee_id == employee_id)
    if status:
        try:
            status_enum = AttendanceRequestStatus(status)
            query = query.filter(AttendanceRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(AttendanceRequest.from_date >= from_date)
    if to_date:
        query = query.filter(AttendanceRequest.to_date <= to_date)
    if company:
        query = query.filter(AttendanceRequest.company.ilike(f"%{company}%"))

    total = query.count()
    requests = query.order_by(AttendanceRequest.from_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "erpnext_id": r.erpnext_id,
                "employee": r.employee,
                "employee_id": r.employee_id,
                "employee_name": r.employee_name,
                "from_date": r.from_date.isoformat() if r.from_date else None,
                "to_date": r.to_date.isoformat() if r.to_date else None,
                "half_day": r.half_day,
                "reason": r.reason,
                "status": r.status.value if r.status else None,
                "company": r.company,
            }
            for r in requests
        ],
    }


@router.get("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:read"))])
async def get_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance request detail."""
    r = db.query(AttendanceRequest).filter(AttendanceRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    return {
        "id": r.id,
        "erpnext_id": r.erpnext_id,
        "employee": r.employee,
        "employee_id": r.employee_id,
        "employee_name": r.employee_name,
        "from_date": r.from_date.isoformat() if r.from_date else None,
        "to_date": r.to_date.isoformat() if r.to_date else None,
        "half_day": r.half_day,
        "half_day_date": r.half_day_date.isoformat() if r.half_day_date else None,
        "reason": r.reason,
        "explanation": r.explanation,
        "status": r.status.value if r.status else None,
        "docstatus": r.docstatus,
        "company": r.company,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("/attendance-requests", dependencies=[Depends(Require("hr:write"))])
async def create_attendance_request(
    payload: AttendanceRequestCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new attendance request."""
    validate_date_order(payload.from_date, payload.to_date)

    request = AttendanceRequest(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        from_date=payload.from_date,
        to_date=payload.to_date,
        half_day=payload.half_day or False,
        half_day_date=payload.half_day_date,
        reason=payload.reason,
        explanation=payload.explanation,
        status=payload.status or AttendanceRequestStatus.DRAFT,
        company=payload.company,
        docstatus=payload.docstatus or 0,
    )
    db.add(request)
    db.commit()
    return await get_attendance_request(request.id, db)


@router.patch("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:write"))])
async def update_attendance_request(
    request_id: int,
    payload: AttendanceRequestUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an attendance request."""
    request = db.query(AttendanceRequest).filter(AttendanceRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(request, field, value)

    validate_date_order(request.from_date, request.to_date)

    db.commit()
    return await get_attendance_request(request.id, db)


@router.delete("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an attendance request."""
    request = db.query(AttendanceRequest).filter(AttendanceRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    db.delete(request)
    db.commit()
    return {"message": "Attendance request deleted", "id": request_id}


@router.post("/attendance-requests/{request_id}/submit", dependencies=[Depends(Require("hr:write"))])
async def submit_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit an attendance request for approval."""
    request = _load_request(db, request_id)
    _require_request_status(request, [AttendanceRequestStatus.DRAFT])
    request.status = AttendanceRequestStatus.PENDING
    db.commit()
    return await get_attendance_request(request_id, db)


@router.post("/attendance-requests/{request_id}/approve", dependencies=[Depends(Require("hr:write"))])
async def approve_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve an attendance request."""
    request = _load_request(db, request_id)
    _require_request_status(request, [AttendanceRequestStatus.PENDING])

    old_status = request.status
    request.status = AttendanceRequestStatus.APPROVED
    request.status_changed_by_id = current_user.id if current_user else None
    request.status_changed_at = now()
    request.updated_by_id = current_user.id if current_user else None

    # Log audit event
    audit = AuditLogger(db)
    audit.log_approve(
        doctype="attendance_request",
        document_id=request.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{request.employee} ({request.from_date} to {request.to_date})",
        remarks=f"Status changed from {old_status.value} to approved",
    )

    db.commit()
    return await get_attendance_request(request_id, db)


@router.post("/attendance-requests/{request_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject an attendance request."""
    request = _load_request(db, request_id)
    _require_request_status(request, [AttendanceRequestStatus.PENDING])

    old_status = request.status
    request.status = AttendanceRequestStatus.REJECTED
    request.status_changed_by_id = current_user.id if current_user else None
    request.status_changed_at = now()
    request.updated_by_id = current_user.id if current_user else None

    # Log audit event
    audit = AuditLogger(db)
    audit.log_reject(
        doctype="attendance_request",
        document_id=request.id,
        user_id=current_user.id if current_user else None,
        document_name=f"{request.employee} ({request.from_date} to {request.to_date})",
        remarks=f"Status changed from {old_status.value} to rejected",
    )

    db.commit()
    return await get_attendance_request(request_id, db)


@router.post("/attendance-requests/bulk/approve", dependencies=[Depends(Require("hr:write"))])
async def bulk_approve_attendance_requests(
    payload: AttendanceRequestBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk approve attendance requests."""
    updated = 0
    for req_id in payload.request_ids:
        request = db.query(AttendanceRequest).filter(AttendanceRequest.id == req_id).first()
        if request and request.status == AttendanceRequestStatus.PENDING:
            request.status = AttendanceRequestStatus.APPROVED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.request_ids)}


@router.post("/attendance-requests/bulk/reject", dependencies=[Depends(Require("hr:write"))])
async def bulk_reject_attendance_requests(
    payload: AttendanceRequestBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk reject attendance requests."""
    updated = 0
    for req_id in payload.request_ids:
        request = db.query(AttendanceRequest).filter(AttendanceRequest.id == req_id).first()
        if request and request.status == AttendanceRequestStatus.PENDING:
            request.status = AttendanceRequestStatus.REJECTED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.request_ids)}

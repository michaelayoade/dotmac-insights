"""
Attendance Management Router

Endpoints for ShiftType, ShiftAssignment, Attendance, AttendanceRequest.

Uses AttendanceService for all business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, time, datetime
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.models.hr_attendance import AttendanceStatus, AttendanceRequestStatus
from app.services.hr.attendance import AttendanceService
from app.services.hr.attendance_types import (
    ShiftTypeCreateData,
    ShiftTypeUpdateData,
    ShiftAssignmentFilters,
    ShiftAssignmentCreateData,
    ShiftAssignmentUpdateData,
    AttendanceFilters,
    AttendanceCreateData,
    AttendanceUpdateData,
    CheckInData,
    CheckOutData,
    AttendanceRequestFilters,
    AttendanceRequestCreateData,
    BulkShiftAssignmentData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import (
    ShiftTypeNotFoundError,
    ShiftAssignmentNotFoundError,
    AttendanceNotFoundError,
    DuplicateAttendanceError,
    CheckInError,
    CheckOutError,
    AttendanceRequestNotFoundError,
    AttendanceRequestStatusError,
    ValidationError as HRValidationError,
)
from .helpers import csv_response

router = APIRouter()


# =============================================================================
# SHIFT TYPE
# =============================================================================


def _serialize_shift_type(st, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a ShiftType model to dict."""
    result = {
        "id": st.id,
        "erpnext_id": st.erpnext_id,
        "shift_type_name": st.shift_type_name,
        "start_time": st.start_time.isoformat() if st.start_time else None,
        "end_time": st.end_time.isoformat() if st.end_time else None,
        "enable_auto_attendance": st.enable_auto_attendance,
        "holiday_list": st.holiday_list,
    }
    if include_details:
        result.update({
            "working_hours_threshold_for_half_day": float(st.working_hours_threshold_for_half_day) if st.working_hours_threshold_for_half_day else 0,
            "working_hours_threshold_for_absent": float(st.working_hours_threshold_for_absent) if st.working_hours_threshold_for_absent else 0,
            "determine_check_in_and_check_out": st.determine_check_in_and_check_out,
            "begin_check_in_before_shift_start_time": st.begin_check_in_before_shift_start_time,
            "allow_check_out_after_shift_end_time": st.allow_check_out_after_shift_end_time,
            "enable_entry_grace_period": st.enable_entry_grace_period,
            "late_entry_grace_period": st.late_entry_grace_period,
            "enable_exit_grace_period": st.enable_exit_grace_period,
            "early_exit_grace_period": st.early_exit_grace_period,
            "created_at": st.created_at.isoformat() if st.created_at else None,
            "updated_at": st.updated_at.isoformat() if st.updated_at else None,
        })
    return result


@router.get("/shift-types", dependencies=[Depends(Require("hr:read"))])
async def list_shift_types(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List shift types."""
    service = AttendanceService(db)
    result = service.list_shift_types(
        pagination=PaginationParams(offset=offset, limit=limit),
    )

    # Apply search filter (service doesn't support text search)
    data = result.items
    if search:
        search_lower = search.lower()
        data = [st for st in data if search_lower in st.shift_type_name.lower()]

    return {
        "total": result.total if not search else len(data),
        "limit": limit,
        "offset": offset,
        "data": [_serialize_shift_type(st) for st in data],
    }


@router.get("/shift-types/{shift_type_id}", dependencies=[Depends(Require("hr:read"))])
async def get_shift_type(
    shift_type_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get shift type detail."""
    service = AttendanceService(db)
    try:
        st = service.get_shift_type(shift_type_id)
    except ShiftTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Shift type not found")

    return _serialize_shift_type(st, include_details=True)


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


def _serialize_assignment(a, include_details: bool = False) -> Dict[str, Any]:
    """Serialize a ShiftAssignment model to dict."""
    result = {
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
    if include_details:
        result.update({
            "docstatus": a.docstatus,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return result


@router.get("/shift-assignments", dependencies=[Depends(Require("hr:read"))])
async def list_shift_assignments(
    employee_id: Optional[int] = None,
    shift_type_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List shift assignments with filtering."""
    service = AttendanceService(db)
    filters = ShiftAssignmentFilters(
        employee_id=employee_id,
        shift_type_id=shift_type_id,
        start_date=start_date,
        end_date=end_date,
        company=company,
    )
    result = service.list_shift_assignments(
        filters=filters,
        pagination=PaginationParams(offset=offset, limit=limit),
    )

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_assignment(a) for a in result.items],
    }


@router.get("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:read"))])
async def get_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get shift assignment detail."""
    service = AttendanceService(db)
    try:
        a = service.get_shift_assignment(assignment_id)
    except ShiftAssignmentNotFoundError:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    return _serialize_assignment(a, include_details=True)


@router.post("/shift-assignments", dependencies=[Depends(Require("hr:write"))])
async def create_shift_assignment(
    payload: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new shift assignment."""
    service = AttendanceService(db, current_user)

    if payload.end_date and payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    create_data = ShiftAssignmentCreateData(
        employee_id=payload.employee_id or 0,
        employee=payload.employee,
        employee_name=payload.employee_name,
        shift_type_id=payload.shift_type_id or 0,
        shift_type=payload.shift_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        company=payload.company,
    )

    try:
        assignment = service.create_shift_assignment(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_shift_assignment(assignment.id, db)


@router.patch("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def update_shift_assignment(
    assignment_id: int,
    payload: ShiftAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a shift assignment."""
    service = AttendanceService(db, current_user)

    update_data = ShiftAssignmentUpdateData(
        shift_type_id=payload.shift_type_id,
        shift_type=payload.shift_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    try:
        service.update_shift_assignment(assignment_id, update_data)
        db.commit()
    except ShiftAssignmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Shift assignment not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_shift_assignment(assignment_id, db)


@router.delete("/shift-assignments/{assignment_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a shift assignment."""
    service = AttendanceService(db, current_user)

    try:
        service.delete_shift_assignment(assignment_id)
        db.commit()
    except ShiftAssignmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Shift assignment not found")

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


def _serialize_attendance(a, include_details: bool = False) -> Dict[str, Any]:
    """Serialize an Attendance model to dict."""
    result = {
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
    if include_details:
        result.update({
            "leave_type": a.leave_type,
            "leave_application": a.leave_application,
            "check_in_latitude": a.check_in_latitude,
            "check_in_longitude": a.check_in_longitude,
            "check_out_latitude": a.check_out_latitude,
            "check_out_longitude": a.check_out_longitude,
            "device_info": a.device_info,
            "docstatus": a.docstatus,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return result


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
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attendances with filtering."""
    service = AttendanceService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = AttendanceStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = AttendanceFilters(
        employee_id=employee_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        late_entry=late_entry,
        early_exit=early_exit,
        company=company,
    )
    result = service.list_attendances(
        filters=filters,
        pagination=PaginationParams(offset=offset, limit=limit),
    )

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_attendance(a) for a in result.items],
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
    service = AttendanceService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = AttendanceStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = AttendanceFilters(
        employee_id=employee_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    result = service.list_attendances(
        filters=filters,
        pagination=PaginationParams(offset=0, limit=10000),
    )

    rows = [["id", "employee", "employee_id", "attendance_date", "status", "in_time", "out_time", "working_hours", "late_entry", "early_exit", "company"]]
    for a in result.items:
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
    """Get attendance summary statistics.

    Note: This endpoint uses direct DB queries for aggregation since the service
    doesn't have a dedicated summary method with these specific filters.
    """
    service = AttendanceService(db)

    # Get all attendances matching filters
    filters = AttendanceFilters(
        employee_id=employee_id,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    result = service.list_attendances(
        filters=filters,
        pagination=PaginationParams(offset=0, limit=10000),
    )

    # Aggregate counts manually
    status_counts: Dict[str, int] = {}
    late_entries = 0
    early_exits = 0

    for a in result.items:
        status_key = a.status.value if a.status else None
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        if a.late_entry:
            late_entries += 1
        if a.early_exit:
            early_exits += 1

    return {
        "status_counts": status_counts,
        "late_entries": late_entries,
        "early_exits": early_exits,
    }


@router.get("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:read"))])
async def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance detail."""
    service = AttendanceService(db)

    try:
        a = service.get_attendance(attendance_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance not found")

    return _serialize_attendance(a, include_details=True)


@router.post("/attendances", dependencies=[Depends(Require("hr:write"))])
async def create_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new attendance record."""
    service = AttendanceService(db, current_user)

    create_data = AttendanceCreateData(
        employee_id=payload.employee_id or 0,
        employee=payload.employee,
        employee_name=payload.employee_name,
        attendance_date=payload.attendance_date,
        status=payload.status or AttendanceStatus.PRESENT,
        shift=payload.shift,
        in_time=payload.in_time,
        out_time=payload.out_time,
        working_hours=payload.working_hours or Decimal("0"),
        leave_type=payload.leave_type,
        leave_application=payload.leave_application,
        late_entry=payload.late_entry or False,
        early_exit=payload.early_exit or False,
        company=payload.company,
    )

    try:
        attendance = service.create_attendance(create_data)
        db.commit()
    except DuplicateAttendanceError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance(attendance.id, db)


@router.patch("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:write"))])
async def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an attendance record."""
    service = AttendanceService(db, current_user)

    update_data = AttendanceUpdateData(
        status=payload.status,
        shift=payload.shift,
        in_time=payload.in_time,
        out_time=payload.out_time,
        working_hours=payload.working_hours,
        late_entry=payload.late_entry,
        early_exit=payload.early_exit,
        leave_type=payload.leave_type,
        leave_application=payload.leave_application,
    )

    try:
        service.update_attendance(attendance_id, update_data)
        db.commit()
    except AttendanceNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Attendance not found")
    except DuplicateAttendanceError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance(attendance_id, db)


@router.delete("/attendances/{attendance_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an attendance record."""
    service = AttendanceService(db, current_user)

    try:
        service.delete_attendance(attendance_id)
        db.commit()
    except AttendanceNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Attendance not found")

    return {"message": "Attendance deleted", "id": attendance_id}


@router.post("/attendances/{attendance_id}/check-in", dependencies=[Depends(Require("hr:write"))])
async def check_in_attendance(
    attendance_id: int,
    payload: Optional[CheckInPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Record check-in time for attendance with optional geolocation."""
    service = AttendanceService(db, current_user)

    # Get employee_id from existing attendance
    try:
        attendance = service.get_attendance(attendance_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance not found")

    check_in_data = CheckInData(
        attendance_date=attendance.attendance_date,
        latitude=payload.latitude if payload else None,
        longitude=payload.longitude if payload else None,
        device_info=payload.device_info if payload else None,
    )

    try:
        service.check_in(attendance.employee_id, check_in_data)
        db.commit()
    except CheckInError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance(attendance_id, db)


@router.post("/attendances/{attendance_id}/check-out", dependencies=[Depends(Require("hr:write"))])
async def check_out_attendance(
    attendance_id: int,
    payload: Optional[CheckOutPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Record check-out time for attendance with optional geolocation."""
    service = AttendanceService(db, current_user)

    # Get employee_id from existing attendance
    try:
        attendance = service.get_attendance(attendance_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance not found")

    check_out_data = CheckOutData(
        attendance_date=attendance.attendance_date,
        latitude=payload.latitude if payload else None,
        longitude=payload.longitude if payload else None,
    )

    try:
        service.check_out(attendance.employee_id, check_out_data)
        db.commit()
    except CheckOutError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    service = AttendanceService(db, current_user)

    created = []
    skipped = []

    for emp_id in payload.employee_ids:
        # Check if attendance already exists
        existing = service.get_attendance_by_employee_date(emp_id, payload.attendance_date)

        if existing:
            skipped.append({
                "employee_id": emp_id,
                "existing_id": existing.id,
                "existing_status": existing.status.value if existing.status else None,
            })
        else:
            create_data = AttendanceCreateData(
                employee_id=emp_id,
                employee=f"EMP-{emp_id}",
                attendance_date=payload.attendance_date,
                status=payload.status,
            )
            try:
                attendance = service.create_attendance(create_data)
                created.append({
                    "employee_id": emp_id,
                    "id": attendance.id,
                })
            except (DuplicateAttendanceError, HRValidationError):
                skipped.append({
                    "employee_id": emp_id,
                    "reason": "Failed to create",
                })

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


def _serialize_request(r, include_details: bool = False) -> Dict[str, Any]:
    """Serialize an AttendanceRequest model to dict."""
    result = {
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
    if include_details:
        result.update({
            "half_day_date": r.half_day_date.isoformat() if r.half_day_date else None,
            "explanation": r.explanation,
            "docstatus": r.docstatus,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return result


@router.get("/attendance-requests", dependencies=[Depends(Require("hr:read"))])
async def list_attendance_requests(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attendance requests with filtering."""
    service = AttendanceService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = AttendanceRequestStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    filters = AttendanceRequestFilters(
        employee_id=employee_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date,
        company=company,
    )
    result = service.list_attendance_requests(
        filters=filters,
        pagination=PaginationParams(offset=offset, limit=limit),
    )

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_request(r) for r in result.items],
    }


@router.get("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:read"))])
async def get_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attendance request detail."""
    service = AttendanceService(db)

    try:
        r = service.get_attendance_request(request_id)
    except AttendanceRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    return _serialize_request(r, include_details=True)


@router.post("/attendance-requests", dependencies=[Depends(Require("hr:write"))])
async def create_attendance_request(
    payload: AttendanceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new attendance request."""
    service = AttendanceService(db, current_user)

    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")

    create_data = AttendanceRequestCreateData(
        employee_id=payload.employee_id or 0,
        employee=payload.employee,
        employee_name=payload.employee_name,
        from_date=payload.from_date,
        to_date=payload.to_date,
        reason=payload.reason,
        explanation=payload.explanation,
        half_day=payload.half_day or False,
        half_day_date=payload.half_day_date,
        company=payload.company,
    )

    try:
        request = service.create_attendance_request(create_data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance_request(request.id, db)


@router.patch("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:write"))])
async def update_attendance_request(
    request_id: int,
    payload: AttendanceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an attendance request.

    Note: The service doesn't have update_attendance_request yet.
    For now, we get the request via service and update directly.
    """
    service = AttendanceService(db, current_user)

    try:
        request = service.get_attendance_request(request_id)
    except AttendanceRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    # Update fields directly (service enhancement needed)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(request, field, value)

    if request.from_date and request.to_date and request.from_date > request.to_date:
        raise HTTPException(status_code=400, detail="from_date must be on or before to_date")

    db.commit()
    return await get_attendance_request(request_id, db)


@router.delete("/attendance-requests/{request_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an attendance request."""
    service = AttendanceService(db, current_user)

    try:
        service.delete_attendance_request(request_id)
        db.commit()
    except AttendanceRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    return {"message": "Attendance request deleted", "id": request_id}


@router.post("/attendance-requests/{request_id}/submit", dependencies=[Depends(Require("hr:write"))])
async def submit_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit an attendance request for approval."""
    service = AttendanceService(db, current_user)

    try:
        request = service.get_attendance_request(request_id)
    except AttendanceRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance request not found")

    if request.status != AttendanceRequestStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {request.status.value}",
        )

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
    service = AttendanceService(db, current_user)

    try:
        service.approve_attendance_request(request_id)
        db.commit()
    except AttendanceRequestNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Attendance request not found")
    except AttendanceRequestStatusError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance_request(request_id, db)


@router.post("/attendance-requests/{request_id}/reject", dependencies=[Depends(Require("hr:write"))])
async def reject_attendance_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject an attendance request."""
    service = AttendanceService(db, current_user)

    try:
        service.reject_attendance_request(request_id)
        db.commit()
    except AttendanceRequestNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Attendance request not found")
    except AttendanceRequestStatusError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return await get_attendance_request(request_id, db)


@router.post("/attendance-requests/bulk/approve", dependencies=[Depends(Require("hr:write"))])
async def bulk_approve_attendance_requests(
    payload: AttendanceRequestBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk approve attendance requests."""
    service = AttendanceService(db, current_user)
    updated = 0
    for req_id in payload.request_ids:
        try:
            service.approve_attendance_request(req_id)
            updated += 1
        except (AttendanceRequestNotFoundError, AttendanceRequestStatusError):
            pass
    db.commit()
    return {"updated": updated, "requested": len(payload.request_ids)}


@router.post("/attendance-requests/bulk/reject", dependencies=[Depends(Require("hr:write"))])
async def bulk_reject_attendance_requests(
    payload: AttendanceRequestBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Bulk reject attendance requests."""
    service = AttendanceService(db, current_user)
    updated = 0
    for req_id in payload.request_ids:
        try:
            service.reject_attendance_request(req_id)
            updated += 1
        except (AttendanceRequestNotFoundError, AttendanceRequestStatusError):
            pass
    db.commit()
    return {"updated": updated, "requested": len(payload.request_ids)}

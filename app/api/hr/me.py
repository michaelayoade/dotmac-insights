"""
HR Self-Service API - Employee Self-Service endpoints.

Permission Requirements:
- hr:read - View own HR data (any authenticated user can access their own data)

These endpoints provide employees with API access to their own HR data:
- /me - Dashboard summary
- /me/leave/* - Leave balance and applications
- /me/attendance/* - Attendance records and check-in/out
- /me/payslips/* - Salary slips
- /me/appraisals/* - Performance appraisals
- /me/training/* - Training events
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.models.employee import Employee
from app.models.hr_leave import (
    LeaveApplication,
    LeaveType,
    LeaveAllocation,
    LeaveApplicationStatus,
)
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_payroll import SalarySlip
from app.models.hr_appraisal import Appraisal
from app.models.hr_training import TrainingEvent, TrainingEventEmployee
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import ApplicationCreateData
from app.services.hr.attendance import AttendanceService
from app.services.hr.attendance_types import CheckInData, CheckOutData
from app.services.hr.errors import (
    ValidationError as HRValidationError,
    CheckInError,
    CheckOutError,
    LeaveApplicationNotFoundError,
    LeaveStatusTransitionError,
)
from app.services.workflow_task_service import WorkflowTaskService
from app.services.expense_service import ExpenseService
from app.services.cash_advance_service import CashAdvanceService
from app.services.errors import ValidationError as ServiceValidationError, NotFoundError
from app.services.expenses.types import ExpenseClaimFilters, CashAdvanceFilters
from app.services.types import PaginationParams
from app.models.expense_management import ExpenseClaim, CashAdvance, ExpenseClaimStatus, CashAdvanceStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.notification import Notification
from app.models.performance import EmployeeScorecardInstance, EvaluationPeriod

router = APIRouter(prefix="/me")


# =============================================================================
# Request/Response Models
# =============================================================================


class LeaveApplicationRequest(BaseModel):
    """Request model for creating a leave application."""

    leave_type_id: int
    from_date: date
    to_date: date
    half_day: bool = False
    half_day_date: Optional[date] = None
    description: Optional[str] = None


class CheckInRequest(BaseModel):
    """Request model for check-in."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None


class CheckOutRequest(BaseModel):
    """Request model for check-out."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_employee_from_principal(db: Session, principal: Principal) -> Employee:
    """Get employee record for authenticated user via email."""
    if not principal or not principal.email:
        raise HTTPException(status_code=401, detail="Authentication required")

    employee = (
        db.query(Employee)
        .filter(
            Employee.email == principal.email,
            Employee.is_deleted == False,
        )
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404, detail="No employee record found for your account"
        )

    return employee


def _serialize_leave_application(app: LeaveApplication) -> Dict[str, Any]:
    """Serialize a leave application to dict."""
    return {
        "id": app.id,
        "leave_type": app.leave_type,
        "leave_type_id": app.leave_type_id,
        "from_date": app.from_date.isoformat() if app.from_date else None,
        "to_date": app.to_date.isoformat() if app.to_date else None,
        "total_leave_days": float(app.total_leave_days or 0),
        "status": app.status.value if app.status else None,
        "half_day": app.half_day,
        "description": app.description,
        "posting_date": app.posting_date.isoformat() if app.posting_date else None,
        "leave_approver": app.leave_approver,
        "leave_approver_name": app.leave_approver_name,
    }


def _serialize_attendance(att: Attendance) -> Dict[str, Any]:
    """Serialize an attendance record to dict."""
    return {
        "id": att.id,
        "attendance_date": att.attendance_date.isoformat() if att.attendance_date else None,
        "status": att.status.value if att.status else None,
        "in_time": att.in_time.isoformat() if att.in_time else None,
        "out_time": att.out_time.isoformat() if att.out_time else None,
        "working_hours": float(att.working_hours or 0),
        "late_entry": att.late_entry,
        "early_exit": att.early_exit,
        "shift": att.shift,
    }


def _serialize_payslip(slip: SalarySlip) -> Dict[str, Any]:
    """Serialize a salary slip to dict."""
    return {
        "id": slip.id,
        "posting_date": slip.posting_date.isoformat() if slip.posting_date else None,
        "start_date": slip.start_date.isoformat() if slip.start_date else None,
        "end_date": slip.end_date.isoformat() if slip.end_date else None,
        "status": slip.status.value if slip.status else None,
        "gross_pay": float(slip.gross_pay or 0),
        "total_deduction": float(slip.total_deduction or 0),
        "net_pay": float(slip.net_pay or 0),
        "payment_days": float(slip.payment_days or 0),
        "currency": slip.currency,
    }


def _serialize_appraisal(appraisal: Appraisal) -> Dict[str, Any]:
    """Serialize an appraisal to dict."""
    return {
        "id": appraisal.id,
        "start_date": appraisal.start_date.isoformat() if appraisal.start_date else None,
        "end_date": appraisal.end_date.isoformat() if appraisal.end_date else None,
        "status": appraisal.status.value if appraisal.status else None,
        "final_score": float(appraisal.final_score or 0),
        "appraisal_template": appraisal.appraisal_template,
        "remarks": appraisal.remarks,
    }


def _serialize_training_event(event: TrainingEvent) -> Dict[str, Any]:
    """Serialize a training event to dict."""
    return {
        "id": event.id,
        "event_name": event.event_name,
        "training_program": event.training_program,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "status": event.status.value if event.status else None,
        "trainer_name": event.trainer_name,
        "type": event.type,
        "location": event.location,
    }


# =============================================================================
# DASHBOARD
# =============================================================================


@router.get("", dependencies=[Depends(Require("hr:read"))])
async def my_dashboard(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get self-service dashboard summary."""
    employee = _get_employee_from_principal(db, principal)
    today = date.today()

    # Leave balance summary
    leave_balances = (
        db.query(LeaveAllocation)
        .filter(
            LeaveAllocation.employee_id == employee.id,
            LeaveAllocation.from_date <= today,
            LeaveAllocation.to_date >= today,
        )
        .all()
    )

    # Pending leave requests
    pending_leave = (
        db.query(LeaveApplication)
        .filter(
            LeaveApplication.employee_id == employee.id,
            LeaveApplication.status == LeaveApplicationStatus.OPEN,
        )
        .count()
    )

    # Recent attendance
    recent_attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee.id)
        .order_by(Attendance.attendance_date.desc())
        .limit(5)
        .all()
    )

    # Today's attendance
    today_attendance = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date == today,
        )
        .first()
    )

    # Recent payslips
    recent_payslips = (
        db.query(SalarySlip)
        .filter(SalarySlip.employee_id == employee.id)
        .order_by(SalarySlip.posting_date.desc())
        .limit(3)
        .all()
    )

    # Upcoming training
    upcoming_training = (
        db.query(TrainingEvent)
        .join(
            TrainingEventEmployee,
            TrainingEventEmployee.training_event_id == TrainingEvent.id,
        )
        .filter(
            TrainingEventEmployee.employee_id == employee.id,
            TrainingEvent.start_date >= today,
        )
        .order_by(TrainingEvent.start_date)
        .limit(3)
        .all()
    )

    return {
        "employee": {
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "employee_number": employee.employee_number,
            "department": employee.department,
            "designation": employee.designation,
        },
        "leave_balances": [
            {
                "leave_type": alloc.leave_type,
                "leave_type_id": alloc.leave_type_id,
                "allocated": float(alloc.new_leaves_allocated or 0),
                "carry_forward": float(alloc.carry_forwarded_leaves or 0),
                "total": float(alloc.total_leaves_allocated or 0),
            }
            for alloc in leave_balances
        ],
        "pending_leave_count": pending_leave,
        "recent_attendance": [_serialize_attendance(att) for att in recent_attendance],
        "today_attendance": (
            _serialize_attendance(today_attendance) if today_attendance else None
        ),
        "recent_payslips": [_serialize_payslip(slip) for slip in recent_payslips],
        "upcoming_training": [
            _serialize_training_event(event) for event in upcoming_training
        ],
    }


# =============================================================================
# LEAVE
# =============================================================================


@router.get("/leave/balance", dependencies=[Depends(Require("hr:read"))])
async def my_leave_balance(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get all leave balances for current period."""
    employee = _get_employee_from_principal(db, principal)
    today = date.today()

    # Get all leave allocations for current period
    allocations = (
        db.query(LeaveAllocation)
        .filter(
            LeaveAllocation.employee_id == employee.id,
            LeaveAllocation.from_date <= today,
            LeaveAllocation.to_date >= today,
        )
        .all()
    )

    # Calculate used leave by type
    balances = []
    for alloc in allocations:
        used = (
            db.query(func.sum(LeaveApplication.total_leave_days))
            .filter(
                LeaveApplication.employee_id == employee.id,
                LeaveApplication.leave_type_id == alloc.leave_type_id,
                LeaveApplication.status == LeaveApplicationStatus.APPROVED,
                LeaveApplication.from_date >= alloc.from_date,
                LeaveApplication.to_date <= alloc.to_date,
            )
            .scalar()
            or 0
        )

        pending = (
            db.query(func.sum(LeaveApplication.total_leave_days))
            .filter(
                LeaveApplication.employee_id == employee.id,
                LeaveApplication.leave_type_id == alloc.leave_type_id,
                LeaveApplication.status == LeaveApplicationStatus.OPEN,
                LeaveApplication.from_date >= alloc.from_date,
                LeaveApplication.to_date <= alloc.to_date,
            )
            .scalar()
            or 0
        )

        allocated = float(alloc.new_leaves_allocated or 0)
        carry_forward = float(alloc.carry_forwarded_leaves or 0)
        total_allocated = allocated + carry_forward
        used_float = float(used)
        pending_float = float(pending)

        balances.append(
            {
                "leave_type": alloc.leave_type,
                "leave_type_id": alloc.leave_type_id,
                "allocated": allocated,
                "carry_forward": carry_forward,
                "total_allocated": total_allocated,
                "used": used_float,
                "pending": pending_float,
                "remaining": total_allocated - used_float,
                "available": total_allocated - used_float - pending_float,
            }
        )

    return {"balances": balances}


@router.get("/leave/applications", dependencies=[Depends(Require("hr:read"))])
async def my_leave_applications(
    status: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my leave applications."""
    employee = _get_employee_from_principal(db, principal)

    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee.id
    )

    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
            query = query.filter(LeaveApplication.status == status_enum)
        except ValueError:
            pass  # Invalid status - ignore filter

    total = query.count()
    applications = (
        query.order_by(LeaveApplication.from_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_leave_application(app) for app in applications],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/leave/applications", dependencies=[Depends(Require("hr:read"))])
async def create_leave_application(
    data: LeaveApplicationRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Apply for leave."""
    employee = _get_employee_from_principal(db, principal)

    # Get leave type
    leave_type = db.query(LeaveType).filter(LeaveType.id == data.leave_type_id).first()
    if not leave_type:
        raise HTTPException(status_code=400, detail="Invalid leave type")

    service = LeaveService(db)

    try:
        application = service.create_application(
            ApplicationCreateData(
                employee_id=employee.id,
                employee=employee.erpnext_id or str(employee.id),
                employee_name=employee.name,
                leave_type_id=data.leave_type_id,
                leave_type=leave_type.leave_type_name,
                from_date=data.from_date,
                to_date=data.to_date,
                half_day=data.half_day,
                half_day_date=data.half_day_date,
                description=data.description,
                company=employee.company,
            )
        )
        db.commit()

        return {
            "success": True,
            "message": "Leave application submitted successfully",
            "application": _serialize_leave_application(application),
        }

    except HRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leave/applications/{application_id}", dependencies=[Depends(Require("hr:read"))])
async def get_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get leave application detail."""
    employee = _get_employee_from_principal(db, principal)

    application = (
        db.query(LeaveApplication)
        .filter(
            LeaveApplication.id == application_id,
            LeaveApplication.employee_id == employee.id,
        )
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    return _serialize_leave_application(application)


@router.post("/leave/applications/{application_id}/cancel", dependencies=[Depends(Require("hr:read"))])
async def cancel_leave_application(
    application_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a pending leave application."""
    employee = _get_employee_from_principal(db, principal)

    # Verify ownership
    application = (
        db.query(LeaveApplication)
        .filter(
            LeaveApplication.id == application_id,
            LeaveApplication.employee_id == employee.id,
        )
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    service = LeaveService(db)

    try:
        service.cancel_application(application_id)
        db.commit()

        return {
            "success": True,
            "message": "Leave application cancelled successfully",
        }

    except LeaveStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")


# =============================================================================
# ATTENDANCE
# =============================================================================


@router.get("/attendance", dependencies=[Depends(Require("hr:read"))])
async def my_attendance(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format"),
    limit: int = Query(31, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my attendance records."""
    employee = _get_employee_from_principal(db, principal)

    query = db.query(Attendance).filter(Attendance.employee_id == employee.id)

    # Parse month filter
    if month:
        try:
            year, month_num = month.split("-")
            start_date = date(int(year), int(month_num), 1)
            if int(month_num) == 12:
                end_date = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(int(year), int(month_num) + 1, 1) - timedelta(days=1)
            query = query.filter(
                Attendance.attendance_date >= start_date,
                Attendance.attendance_date <= end_date,
            )
        except (ValueError, IndexError):
            pass  # Invalid format - ignore filter

    total = query.count()
    records = (
        query.order_by(Attendance.attendance_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_attendance(att) for att in records],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/attendance/today", dependencies=[Depends(Require("hr:read"))])
async def my_attendance_today(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get today's attendance status."""
    employee = _get_employee_from_principal(db, principal)
    today = date.today()

    attendance = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date == today,
        )
        .first()
    )

    return {
        "date": today.isoformat(),
        "attendance": _serialize_attendance(attendance) if attendance else None,
        "checked_in": attendance.in_time is not None if attendance else False,
        "checked_out": attendance.out_time is not None if attendance else False,
    }


@router.post("/attendance/check-in", dependencies=[Depends(Require("hr:read"))])
async def my_check_in(
    data: CheckInRequest = CheckInRequest(),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Check in for today."""
    employee = _get_employee_from_principal(db, principal)

    service = AttendanceService(db)

    try:
        check_in_data = CheckInData(
            latitude=data.latitude,
            longitude=data.longitude,
            device_info=data.device_info,
        )
        attendance = service.check_in(employee.id, check_in_data)
        db.commit()

        return {
            "success": True,
            "message": f"Checked in at {attendance.in_time.strftime('%H:%M') if attendance.in_time else 'now'}",
            "attendance": _serialize_attendance(attendance),
        }

    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/attendance/check-out", dependencies=[Depends(Require("hr:read"))])
async def my_check_out(
    data: CheckOutRequest = CheckOutRequest(),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Check out for today."""
    employee = _get_employee_from_principal(db, principal)

    service = AttendanceService(db)

    try:
        check_out_data = CheckOutData(
            latitude=data.latitude,
            longitude=data.longitude,
            device_info=data.device_info,
        )
        attendance = service.check_out(employee.id, check_out_data)
        db.commit()

        return {
            "success": True,
            "message": f"Checked out at {attendance.out_time.strftime('%H:%M') if attendance.out_time else 'now'}",
            "attendance": _serialize_attendance(attendance),
        }

    except CheckOutError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/attendance/summary", dependencies=[Depends(Require("hr:read"))])
async def my_attendance_summary(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get monthly attendance summary."""
    employee = _get_employee_from_principal(db, principal)

    # Default to current month
    today = date.today()
    if month:
        try:
            year, month_num = month.split("-")
            start_date = date(int(year), int(month_num), 1)
        except (ValueError, IndexError):
            start_date = today.replace(day=1)
    else:
        start_date = today.replace(day=1)

    # Calculate end of month
    if start_date.month == 12:
        end_date = date(start_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(start_date.year, start_date.month + 1, 1) - timedelta(days=1)

    # Get attendance records for the month
    records = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
        )
        .all()
    )

    # Calculate summary
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.late_entry)
    early_exit_count = sum(1 for r in records if r.early_exit)
    total_working_hours = sum(float(r.working_hours or 0) for r in records)

    return {
        "month": start_date.strftime("%Y-%m"),
        "total_days": len(records),
        "present": present_count,
        "absent": absent_count,
        "late_entries": late_count,
        "early_exits": early_exit_count,
        "total_working_hours": round(total_working_hours, 2),
        "avg_working_hours": (
            round(total_working_hours / present_count, 2) if present_count > 0 else 0
        ),
    }


# =============================================================================
# PAYSLIPS
# =============================================================================


@router.get("/payslips", dependencies=[Depends(Require("hr:read"))])
async def my_payslips(
    year: Optional[int] = Query(None),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my salary slips."""
    employee = _get_employee_from_principal(db, principal)

    query = db.query(SalarySlip).filter(SalarySlip.employee_id == employee.id)

    if year:
        query = query.filter(func.extract("year", SalarySlip.posting_date) == year)

    total = query.count()
    payslips = (
        query.order_by(SalarySlip.posting_date.desc()).offset(offset).limit(limit).all()
    )

    # Get available years
    years = (
        db.query(func.distinct(func.extract("year", SalarySlip.posting_date)))
        .filter(SalarySlip.employee_id == employee.id)
        .order_by(func.extract("year", SalarySlip.posting_date).desc())
        .all()
    )
    year_options = [int(y[0]) for y in years if y[0]]

    return {
        "items": [_serialize_payslip(slip) for slip in payslips],
        "total": total,
        "limit": limit,
        "offset": offset,
        "year_options": year_options,
    }


@router.get("/payslips/{payslip_id}", dependencies=[Depends(Require("hr:read"))])
async def my_payslip_detail(
    payslip_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get salary slip detail."""
    employee = _get_employee_from_principal(db, principal)

    payslip = (
        db.query(SalarySlip)
        .filter(
            SalarySlip.id == payslip_id,
            SalarySlip.employee_id == employee.id,
        )
        .first()
    )

    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")

    # Get earnings and deductions
    earnings = [
        {
            "salary_component": e.salary_component,
            "amount": float(e.amount or 0),
        }
        for e in payslip.earnings
    ]

    deductions = [
        {
            "salary_component": d.salary_component,
            "amount": float(d.amount or 0),
        }
        for d in payslip.deductions
    ]

    result = _serialize_payslip(payslip)
    result["earnings"] = earnings
    result["deductions"] = deductions

    return result


# =============================================================================
# APPRAISALS
# =============================================================================


@router.get("/appraisals", dependencies=[Depends(Require("hr:read"))])
async def my_appraisals(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my appraisals."""
    employee = _get_employee_from_principal(db, principal)

    query = db.query(Appraisal).filter(Appraisal.employee_id == employee.id)

    total = query.count()
    appraisals = (
        query.order_by(Appraisal.start_date.desc()).offset(offset).limit(limit).all()
    )

    return {
        "items": [_serialize_appraisal(app) for app in appraisals],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/appraisals/{appraisal_id}", dependencies=[Depends(Require("hr:read"))])
async def my_appraisal_detail(
    appraisal_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get appraisal detail."""
    employee = _get_employee_from_principal(db, principal)

    appraisal = (
        db.query(Appraisal)
        .filter(
            Appraisal.id == appraisal_id,
            Appraisal.employee_id == employee.id,
        )
        .first()
    )

    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    result = _serialize_appraisal(appraisal)

    # Add goals if available
    if hasattr(appraisal, "goals") and appraisal.goals:
        result["goals"] = [
            {
                "kra": g.kra,
                "per_weightage": float(g.per_weightage or 0),
                "goal_completion": float(g.goal_completion or 0),
                "score": float(g.score or 0),
            }
            for g in appraisal.goals
        ]

    return result


# =============================================================================
# TRAINING
# =============================================================================


@router.get("/training", dependencies=[Depends(Require("hr:read"))])
async def my_training(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my training events."""
    employee = _get_employee_from_principal(db, principal)

    query = (
        db.query(TrainingEvent)
        .join(
            TrainingEventEmployee,
            TrainingEventEmployee.training_event_id == TrainingEvent.id,
        )
        .filter(TrainingEventEmployee.employee_id == employee.id)
    )

    total = query.count()
    events = (
        query.order_by(TrainingEvent.start_date.desc()).offset(offset).limit(limit).all()
    )

    return {
        "items": [_serialize_training_event(event) for event in events],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/training/{event_id}", dependencies=[Depends(Require("hr:read"))])
async def my_training_detail(
    event_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get training event detail."""
    employee = _get_employee_from_principal(db, principal)

    # Verify enrollment
    enrollment = (
        db.query(TrainingEventEmployee)
        .filter(
            TrainingEventEmployee.training_event_id == event_id,
            TrainingEventEmployee.employee_id == employee.id,
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(status_code=404, detail="Training event not found")

    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")

    result = _serialize_training_event(event)
    result["enrollment"] = {
        "status": enrollment.status.value if enrollment.status else None,
        "attendance": enrollment.attendance,
        "feedback": enrollment.feedback,
    }

    return result


# =============================================================================
# WORKFLOW TASKS
# =============================================================================


def _serialize_workflow_task(task) -> Dict[str, Any]:
    """Serialize a workflow task to dict."""
    return {
        "id": task.id,
        "source_type": task.source_type,
        "source_id": task.source_id,
        "title": task.title,
        "description": task.description,
        "action_url": task.action_url,
        "priority": task.priority,
        "status": task.status,
        "module": task.module,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "is_overdue": getattr(task, "is_overdue", False),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
    }


@router.get("/tasks", dependencies=[Depends(Require("hr:read"))])
async def my_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    module: Optional[str] = Query(None, description="Filter by module"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my pending workflow tasks."""
    service = WorkflowTaskService(db)

    tasks = service.get_my_tasks(
        user_id=principal.id,
        status=status,
        module=module,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    total = service.count_my_tasks(
        user_id=principal.id,
        status=status,
        module=module,
        priority=priority,
    )

    return {
        "items": [_serialize_workflow_task(t) for t in tasks],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tasks/summary", dependencies=[Depends(Require("hr:read"))])
async def my_tasks_summary(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get task counts summary."""
    service = WorkflowTaskService(db)
    return service.get_task_summary(user_id=principal.id)


@router.post("/tasks/{task_id}/complete", dependencies=[Depends(Require("hr:read"))])
async def complete_my_task(
    task_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Complete a workflow task assigned to me."""
    service = WorkflowTaskService(db)

    # Get task with ownership check
    task = service.get_task_by_id(task_id, user_id=principal.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    from app.models.workflow_task import WorkflowTaskStatus

    if task.status == WorkflowTaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Task is already completed")

    task = service.update_task_status(task_id, WorkflowTaskStatus.COMPLETED.value, principal.id)
    db.commit()

    return {
        "success": True,
        "message": "Task completed",
        "task": _serialize_workflow_task(task),
    }


# =============================================================================
# EXPENSE CLAIMS
# =============================================================================


def _serialize_expense_claim(claim: ExpenseClaim) -> Dict[str, Any]:
    """Serialize an expense claim to dict."""
    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "title": claim.title,
        "description": claim.description,
        "claim_date": claim.claim_date.isoformat() if claim.claim_date else None,
        "status": claim.status.value if claim.status else None,
        "total_claimed_amount": float(claim.total_claimed_amount or 0),
        "total_sanctioned_amount": float(claim.total_sanctioned_amount or 0),
        "currency": claim.currency,
        "project_id": claim.project_id,
        "cost_center": claim.cost_center,
        "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
        "approved_at": claim.approved_at.isoformat() if claim.approved_at else None,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
    }


def _serialize_expense_line(line) -> Dict[str, Any]:
    """Serialize an expense claim line to dict."""
    return {
        "id": line.id,
        "category_id": line.category_id,
        "expense_date": line.expense_date.isoformat() if line.expense_date else None,
        "description": line.description,
        "merchant_name": line.merchant_name,
        "claimed_amount": float(line.claimed_amount or 0),
        "sanctioned_amount": float(line.sanctioned_amount or 0),
        "currency": line.currency,
        "funding_method": line.funding_method.value if line.funding_method else None,
        "has_receipt": line.has_receipt,
    }


@router.get("/expenses", dependencies=[Depends(Require("hr:read"))])
async def my_expenses(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my expense claims."""
    employee = _get_employee_from_principal(db, principal)

    service = ExpenseService(db)
    filters = ExpenseClaimFilters(
        employee_id=employee.id,
        status=status,
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    result = service.list_claims(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_expense_claim(c) for c in result.items],
        "total": result.total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/expenses/{claim_id}", dependencies=[Depends(Require("hr:read"))])
async def my_expense_detail(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get expense claim detail with lines."""
    employee = _get_employee_from_principal(db, principal)

    service = ExpenseService(db)
    try:
        claim = service.get_claim(claim_id, include_lines=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    # Verify ownership
    if claim.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    result = _serialize_expense_claim(claim)
    result["lines"] = [_serialize_expense_line(line) for line in (claim.lines or [])]

    return result


@router.post("/expenses/{claim_id}/submit", dependencies=[Depends(Require("hr:read"))])
async def submit_my_expense(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit expense claim for approval."""
    employee = _get_employee_from_principal(db, principal)

    service = ExpenseService(db)
    try:
        claim = service.get_claim(claim_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    # Verify ownership
    if claim.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    try:
        claim = service.submit_claim(claim, user_id=principal.id, company_code=employee.company)
        db.commit()
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Expense claim submitted for approval",
        "claim": _serialize_expense_claim(claim),
    }


@router.post("/expenses/{claim_id}/recall", dependencies=[Depends(Require("hr:read"))])
async def recall_my_expense(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Recall a pending expense claim."""
    employee = _get_employee_from_principal(db, principal)

    service = ExpenseService(db)
    try:
        claim = service.get_claim(claim_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    # Verify ownership
    if claim.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    try:
        claim = service.recall_claim(claim, user_id=principal.id)
        db.commit()
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Expense claim recalled",
        "claim": _serialize_expense_claim(claim),
    }


# =============================================================================
# CASH ADVANCES
# =============================================================================


def _serialize_cash_advance(advance: CashAdvance) -> Dict[str, Any]:
    """Serialize a cash advance to dict."""
    return {
        "id": advance.id,
        "advance_number": advance.advance_number,
        "purpose": advance.purpose,
        "request_date": advance.request_date.isoformat() if advance.request_date else None,
        "required_by_date": advance.required_by_date.isoformat() if advance.required_by_date else None,
        "status": advance.status.value if advance.status else None,
        "requested_amount": float(advance.requested_amount or 0),
        "approved_amount": float(advance.approved_amount or 0),
        "disbursed_amount": float(advance.disbursed_amount or 0),
        "outstanding_amount": float(advance.outstanding_amount or 0),
        "currency": advance.currency,
        "project_id": advance.project_id,
        "destination": advance.destination,
        "submitted_at": advance.submitted_at.isoformat() if advance.submitted_at else None,
        "approved_at": advance.approved_at.isoformat() if advance.approved_at else None,
        "created_at": advance.created_at.isoformat() if advance.created_at else None,
    }


@router.get("/cash-advances", dependencies=[Depends(Require("hr:read"))])
async def my_cash_advances(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my cash advances."""
    employee = _get_employee_from_principal(db, principal)

    service = CashAdvanceService(db)
    filters = CashAdvanceFilters(
        employee_id=employee.id,
        status=status,
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    result = service.list_advances(filters=filters, pagination=pagination)

    return {
        "items": [_serialize_cash_advance(a) for a in result.items],
        "total": result.total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/cash-advances/{advance_id}", dependencies=[Depends(Require("hr:read"))])
async def my_cash_advance_detail(
    advance_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get cash advance detail."""
    employee = _get_employee_from_principal(db, principal)

    service = CashAdvanceService(db)
    try:
        advance = service.get_advance(advance_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    # Verify ownership
    if advance.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    return _serialize_cash_advance(advance)


@router.post("/cash-advances/{advance_id}/submit", dependencies=[Depends(Require("hr:read"))])
async def submit_my_cash_advance(
    advance_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit cash advance for approval."""
    employee = _get_employee_from_principal(db, principal)

    service = CashAdvanceService(db)
    try:
        advance = service.get_advance(advance_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    # Verify ownership
    if advance.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Cash advance not found")

    try:
        advance = service.submit(advance, user_id=principal.id, company_code=employee.company)
        db.commit()
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Cash advance submitted for approval",
        "advance": _serialize_cash_advance(advance),
    }


# =============================================================================
# TEAM / REPORTING STRUCTURE
# =============================================================================


def _serialize_employee_brief(emp: Employee) -> Dict[str, Any]:
    """Serialize employee to brief dict."""
    return {
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "employee_number": emp.employee_number,
        "designation": emp.designation,
        "department": emp.department,
        "status": emp.status.value if emp.status else None,
    }


@router.get("/team", dependencies=[Depends(Require("hr:read"))])
async def my_team(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get my reporting structure - manager and direct reports."""
    employee = _get_employee_from_principal(db, principal)

    # Get manager
    manager = None
    if employee.reports_to_id:
        manager_emp = (
            db.query(Employee)
            .filter(Employee.id == employee.reports_to_id, Employee.is_deleted == False)
            .first()
        )
        if manager_emp:
            manager = _serialize_employee_brief(manager_emp)

    # Get direct reports
    direct_reports = (
        db.query(Employee)
        .filter(
            Employee.reports_to_id == employee.id,
            Employee.is_deleted == False,
        )
        .order_by(Employee.name)
        .all()
    )

    return {
        "employee": _serialize_employee_brief(employee),
        "manager": manager,
        "direct_reports": [_serialize_employee_brief(e) for e in direct_reports],
        "direct_reports_count": len(direct_reports),
    }


@router.get("/team/leave-requests", dependencies=[Depends(Require("hr:read"))])
async def my_team_leave_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get pending leave requests from my direct reports (for approval)."""
    employee = _get_employee_from_principal(db, principal)

    # Get direct report IDs
    direct_report_ids = (
        db.query(Employee.id)
        .filter(
            Employee.reports_to_id == employee.id,
            Employee.is_deleted == False,
        )
        .all()
    )
    direct_report_ids = [r[0] for r in direct_report_ids]

    if not direct_report_ids:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    # Query leave applications from direct reports
    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id.in_(direct_report_ids)
    )

    # Default to pending status
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
            query = query.filter(LeaveApplication.status == status_enum)
        except ValueError:
            pass
    else:
        query = query.filter(LeaveApplication.status == LeaveApplicationStatus.OPEN)

    total = query.count()
    applications = (
        query.order_by(LeaveApplication.from_date.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Enrich with employee names
    items = []
    for app in applications:
        data = _serialize_leave_application(app)
        emp = db.query(Employee).filter(Employee.id == app.employee_id).first()
        if emp:
            data["employee_name"] = emp.name
            data["employee_email"] = emp.email
        items.append(data)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/team/leave-requests/{application_id}/approve", dependencies=[Depends(Require("hr:read"))])
async def approve_team_leave(
    application_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve a leave request from a direct report."""
    employee = _get_employee_from_principal(db, principal)

    # Get the leave application
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    # Verify the applicant reports to current user
    applicant = db.query(Employee).filter(Employee.id == application.employee_id).first()
    if not applicant or applicant.reports_to_id != employee.id:
        raise HTTPException(status_code=403, detail="You are not authorized to approve this request")

    if application.status != LeaveApplicationStatus.OPEN:
        raise HTTPException(status_code=400, detail="Leave application is not pending")

    # Approve
    service = LeaveService(db)
    try:
        service.approve_application(application_id, approved_by=employee.erpnext_id or str(employee.id))
        db.commit()
    except HRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Leave application approved",
    }


@router.post("/team/leave-requests/{application_id}/reject", dependencies=[Depends(Require("hr:read"))])
async def reject_team_leave(
    application_id: int,
    reason: Optional[str] = Query(None, description="Rejection reason"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject a leave request from a direct report."""
    employee = _get_employee_from_principal(db, principal)

    # Get the leave application
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    # Verify the applicant reports to current user
    applicant = db.query(Employee).filter(Employee.id == application.employee_id).first()
    if not applicant or applicant.reports_to_id != employee.id:
        raise HTTPException(status_code=403, detail="You are not authorized to reject this request")

    if application.status != LeaveApplicationStatus.OPEN:
        raise HTTPException(status_code=400, detail="Leave application is not pending")

    # Reject
    service = LeaveService(db)
    try:
        service.reject_application(application_id, reason=reason)
        db.commit()
    except HRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Leave application rejected",
    }


# =============================================================================
# SUPPORT TICKETS
# =============================================================================


def _serialize_ticket(ticket: Ticket) -> Dict[str, Any]:
    """Serialize a ticket to dict."""
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "description": ticket.description[:200] + "..." if ticket.description and len(ticket.description) > 200 else ticket.description,
        "status": ticket.status.value if ticket.status else None,
        "priority": ticket.priority.value if ticket.priority else None,
        "ticket_type": ticket.ticket_type,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolution_date": ticket.resolution_date.isoformat() if hasattr(ticket, 'resolution_date') and ticket.resolution_date else None,
    }


@router.get("/tickets", dependencies=[Depends(Require("hr:read"))])
async def my_tickets(
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned: bool = Query(False, description="Show tickets assigned to me (vs created by me)"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my tickets (created by me or assigned to me)."""
    employee = _get_employee_from_principal(db, principal)

    if assigned:
        query = db.query(Ticket).filter(
            Ticket.assigned_employee_id == employee.id,
            Ticket.is_deleted == False,
        )
    else:
        query = db.query(Ticket).filter(
            Ticket.employee_id == employee.id,
            Ticket.is_deleted == False,
        )

    if status:
        try:
            status_enum = TicketStatus(status)
            query = query.filter(Ticket.status == status_enum)
        except ValueError:
            pass

    total = query.count()
    tickets = (
        query.order_by(Ticket.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_ticket(t) for t in tickets],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tickets/summary", dependencies=[Depends(Require("hr:read"))])
async def my_tickets_summary(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get ticket counts summary."""
    employee = _get_employee_from_principal(db, principal)

    # Tickets created by me
    created_open = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.employee_id == employee.id,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]),
            Ticket.is_deleted == False,
        )
        .scalar()
        or 0
    )

    # Tickets assigned to me
    assigned_open = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.assigned_employee_id == employee.id,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]),
            Ticket.is_deleted == False,
        )
        .scalar()
        or 0
    )

    return {
        "created_open": created_open,
        "assigned_open": assigned_open,
        "total_open": created_open + assigned_open,
    }


# =============================================================================
# NOTIFICATIONS
# =============================================================================


def _serialize_notification(notif: Notification) -> Dict[str, Any]:
    """Serialize a notification to dict."""
    return {
        "id": notif.id,
        "event_type": notif.event_type.value if notif.event_type else None,
        "title": notif.title,
        "message": notif.message,
        "icon": notif.icon,
        "action_url": notif.action_url,
        "entity_type": notif.entity_type,
        "entity_id": notif.entity_id,
        "priority": notif.priority,
        "is_read": notif.is_read,
        "read_at": notif.read_at.isoformat() if notif.read_at else None,
        "created_at": notif.created_at.isoformat() if notif.created_at else None,
    }


@router.get("/notifications", dependencies=[Depends(Require("hr:read"))])
async def my_notifications(
    unread_only: bool = Query(True, description="Only show unread notifications"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List my notifications."""
    query = db.query(Notification).filter(Notification.user_id == principal.id)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    total = query.count()
    notifications = (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Count unread
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == principal.id, Notification.is_read == False)
        .scalar()
        or 0
    )

    return {
        "items": [_serialize_notification(n) for n in notifications],
        "total": total,
        "unread_count": unread_count,
        "limit": limit,
        "offset": offset,
    }


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(Require("hr:read"))])
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a notification as read."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == principal.id)
        .first()
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now()
        db.commit()

    return {"success": True, "message": "Notification marked as read"}


@router.post("/notifications/read-all", dependencies=[Depends(Require("hr:read"))])
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark all notifications as read."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == principal.id, Notification.is_read == False)
        .update({"is_read": True, "read_at": datetime.now()})
    )
    db.commit()

    return {"success": True, "message": f"Marked {count} notifications as read"}


# =============================================================================
# PERFORMANCE / SCORECARDS
# =============================================================================


def _serialize_scorecard(scorecard: EmployeeScorecardInstance) -> Dict[str, Any]:
    """Serialize a scorecard to dict."""
    return {
        "id": scorecard.id,
        "status": scorecard.status.value if scorecard.status else None,
        "total_weighted_score": float(scorecard.total_weighted_score or 0) if scorecard.total_weighted_score else None,
        "final_rating": scorecard.final_rating,
        "rating_label": scorecard.rating_label,
        "created_at": scorecard.created_at.isoformat() if scorecard.created_at else None,
        "computed_at": scorecard.computed_at.isoformat() if hasattr(scorecard, 'computed_at') and scorecard.computed_at else None,
        "approved_at": scorecard.approved_at.isoformat() if hasattr(scorecard, 'approved_at') and scorecard.approved_at else None,
    }


def _serialize_evaluation_period(period: EvaluationPeriod) -> Dict[str, Any]:
    """Serialize an evaluation period to dict."""
    return {
        "id": period.id,
        "name": period.name,
        "start_date": period.start_date.isoformat() if period.start_date else None,
        "end_date": period.end_date.isoformat() if period.end_date else None,
        "status": period.status.value if period.status else None,
    }


@router.get("/performance", dependencies=[Depends(Require("hr:read"))])
async def my_performance(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get my performance scorecards."""
    employee = _get_employee_from_principal(db, principal)

    query = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.employee_id == employee.id
    )

    total = query.count()
    scorecards = (
        query.order_by(EmployeeScorecardInstance.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Enrich with period info
    items = []
    for sc in scorecards:
        data = _serialize_scorecard(sc)
        if sc.evaluation_period_id:
            period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == sc.evaluation_period_id).first()
            if period:
                data["period"] = _serialize_evaluation_period(period)
        items.append(data)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/performance/{scorecard_id}", dependencies=[Depends(Require("hr:read"))])
async def my_performance_detail(
    scorecard_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get scorecard detail with KPI/KRA results."""
    employee = _get_employee_from_principal(db, principal)

    scorecard = (
        db.query(EmployeeScorecardInstance)
        .filter(
            EmployeeScorecardInstance.id == scorecard_id,
            EmployeeScorecardInstance.employee_id == employee.id,
        )
        .first()
    )

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    result = _serialize_scorecard(scorecard)

    # Add period info
    if scorecard.evaluation_period_id:
        period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
        if period:
            result["period"] = _serialize_evaluation_period(period)

    # Add KPI results if available
    if hasattr(scorecard, 'kpi_results') and scorecard.kpi_results:
        result["kpi_results"] = [
            {
                "id": kpi.id,
                "kpi_name": kpi.kpi_definition.name if hasattr(kpi, 'kpi_definition') and kpi.kpi_definition else None,
                "target_value": float(kpi.target_value or 0) if kpi.target_value else None,
                "actual_value": float(kpi.actual_value or 0) if kpi.actual_value else None,
                "weighted_score": float(kpi.weighted_score or 0) if kpi.weighted_score else None,
            }
            for kpi in scorecard.kpi_results
        ]

    # Add KRA results if available
    if hasattr(scorecard, 'kra_results') and scorecard.kra_results:
        result["kra_results"] = [
            {
                "id": kra.id,
                "kra_name": kra.kra_definition.name if hasattr(kra, 'kra_definition') and kra.kra_definition else None,
                "weighted_score": float(kra.weighted_score or 0) if kra.weighted_score else None,
            }
            for kra in scorecard.kra_results
        ]

    return result

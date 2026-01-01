"""
Hr Dashboard Endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.api.dashboards.common import resolve_currency_or_raise, parse_date_param

router = APIRouter(tags=["dashboards"])

# =============================================================================
# HR DASHBOARD - Consolidated (11 calls → 1)
# =============================================================================

@router.get("/hr", dependencies=[Depends(Require("hr:read"))])
@cached("dashboard-hr", ttl=CACHE_TTL["short"])
async def get_hr_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated HR Dashboard endpoint.

    Combines data from:
    - Employee summary (total, active, on leave)
    - Leave applications (pending, by status, trend)
    - Attendance summary (30 days)
    - Payroll summary (last 30 days)
    - Recruitment (open positions, funnel)
    - Training events (scheduled)
    - Onboarding (active)
    """
    from app.models.employee import Employee, EmploymentStatus
    from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus
    from app.models.hr_attendance import Attendance
    from app.models.hr_payroll import SalarySlip, SalarySlipStatus
    from app.models.hr_recruitment import JobOpening, JobApplicant
    from app.models.hr_training import TrainingEvent
    from app.models.hr_lifecycle import EmployeeOnboarding, BoardingStatus

    now = datetime.now(timezone.utc)
    today = date.today()
    thirty_days_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)

    # =========== EMPLOYEE SUMMARY ===========
    total_employees = db.query(func.count(Employee.id)).scalar() or 0
    active_employees = db.query(func.count(Employee.id)).filter(
        Employee.status == EmploymentStatus.ACTIVE
    ).scalar() or 0

    # On leave today (check active leave applications)
    on_leave_today = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= today,
    ).scalar() or 0

    # =========== LEAVE DATA ===========
    pending_leave = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).scalar() or 0

    leave_by_status = db.query(
        LeaveApplication.status,
        func.count(LeaveApplication.id).label("count")
    ).group_by(LeaveApplication.status).all()
    leave_status_map = {
        row.status.value if row.status else "unknown": row.count
        for row in leave_by_status
    }

    # Leave trend (last 6 months)
    trunc_month = func.date_trunc("month", LeaveApplication.posting_date)
    leave_trend = [
        {"month": r.period, "count": r.count}
        for r in db.query(
            func.to_char(trunc_month, "YYYY-MM").label("period"),
            func.count(LeaveApplication.id).label("count")
        ).filter(
            LeaveApplication.posting_date >= six_months_ago
        ).group_by(trunc_month).order_by(trunc_month).all()
    ]

    # =========== ATTENDANCE (30 days) ===========
    attendance_summary = db.query(
        Attendance.status,
        func.count(Attendance.id).label("count")
    ).filter(
        Attendance.attendance_date >= (today - timedelta(days=30))
    ).group_by(Attendance.status).all()
    attendance_30d = {
        row.status.value if hasattr(row.status, 'value') else str(row.status): row.count
        for row in attendance_summary
    }

    # Present today
    present_today = db.query(func.count(Attendance.id)).filter(
        Attendance.attendance_date == today,
        Attendance.status.in_(["Present", "present", "PRESENT"])
    ).scalar() or 0

    # Attendance trend (14 days)
    attendance_trend = []
    for i in range(14):
        day = today - timedelta(days=13 - i)
        day_counts = db.query(
            Attendance.status,
            func.count(Attendance.id).label("count")
        ).filter(
            Attendance.attendance_date == day
        ).group_by(Attendance.status).all()
        status_counts = {
            row.status.value if hasattr(row.status, 'value') else str(row.status): row.count
            for row in day_counts
        }
        attendance_trend.append({
            "date": day.isoformat(),
            "status_counts": status_counts
        })

    # =========== PAYROLL (30 days) ===========
    payroll_summary = db.query(
        func.count(SalarySlip.id).label("slip_count"),
        func.sum(SalarySlip.gross_pay).label("gross_total"),
        func.sum(SalarySlip.total_deduction).label("deduction_total"),
        func.sum(SalarySlip.net_pay).label("net_total"),
    ).filter(
        SalarySlip.posting_date >= thirty_days_ago,
        SalarySlip.docstatus == 1,
    ).first()

    payroll_30d = {
        "slip_count": payroll_summary.slip_count or 0 if payroll_summary else 0,
        "gross_total": float(payroll_summary.gross_total or 0) if payroll_summary else 0,
        "deduction_total": float(payroll_summary.deduction_total or 0) if payroll_summary else 0,
        "net_total": float(payroll_summary.net_total or 0) if payroll_summary else 0,
    }

    # =========== RECRUITMENT ===========
    open_positions = db.query(func.count(JobOpening.id)).filter(
        JobOpening.status == "Open"
    ).scalar() or 0

    # Recruitment funnel
    total_applicants = db.query(func.count(JobApplicant.id)).scalar() or 0
    screened = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Screening", "Interview Scheduled", "Selected", "Offer Sent", "Accepted", "Rejected"])
    ).scalar() or 0
    interviewed = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Interview Scheduled", "Selected", "Offer Sent", "Accepted", "Rejected"])
    ).scalar() or 0
    offered = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status.in_(["Offer Sent", "Accepted"])
    ).scalar() or 0
    hired = db.query(func.count(JobApplicant.id)).filter(
        JobApplicant.status == "Accepted"
    ).scalar() or 0

    recruitment_funnel = {
        "applications": total_applicants,
        "screened": screened,
        "interviewed": interviewed,
        "offered": offered,
        "hired": hired,
    }

    # =========== TRAINING ===========
    scheduled_training = db.query(func.count(TrainingEvent.id)).filter(
        TrainingEvent.start_time >= now
    ).scalar() or 0

    upcoming_training = [
        {
            "id": t.id,
            "event_name": t.event_name,
            "start_time": t.start_time.isoformat() if t.start_time else None,
            "type": t.type,
        }
        for t in db.query(TrainingEvent).filter(
            TrainingEvent.start_time >= now
        ).order_by(TrainingEvent.start_time.asc()).limit(5).all()
    ]

    # =========== ONBOARDING ===========
    active_onboardings = db.query(func.count(EmployeeOnboarding.id)).filter(
        EmployeeOnboarding.boarding_status.in_(
            [BoardingStatus.PENDING, BoardingStatus.IN_PROGRESS]
        )
    ).scalar() or 0

    recent_onboardings = [
        {
            "id": o.id,
            "employee_name": o.employee_name,
            "status": o.boarding_status.value if o.boarding_status else None,
            "date_of_joining": o.date_of_joining.isoformat() if o.date_of_joining else None,
        }
        for o in db.query(EmployeeOnboarding).filter(
            EmployeeOnboarding.boarding_status.in_(
                [BoardingStatus.PENDING, BoardingStatus.IN_PROGRESS]
            )
        ).order_by(EmployeeOnboarding.date_of_joining.desc()).limit(5).all()
    ]

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "on_leave_today": on_leave_today,
            "present_today": present_today,
        },

        "leave": {
            "pending_approvals": pending_leave,
            "by_status": leave_status_map,
            "trend": leave_trend,
        },

        "attendance": {
            "status_30d": attendance_30d,
            "trend": attendance_trend,
        },

        "payroll_30d": payroll_30d,

        "recruitment": {
            "open_positions": open_positions,
            "funnel": recruitment_funnel,
        },

        "training": {
            "scheduled_events": scheduled_training,
            "upcoming": upcoming_training,
        },

        "onboarding": {
            "active_count": active_onboardings,
            "recent": recent_onboardings,
        },
    }


# =============================================================================
# HR LEAVE DASHBOARD - Calendar/Schedule View (3 calls → 1)
# =============================================================================

@router.get("/hr-leave", dependencies=[Depends(Require("hr:read"))])
@cached("dashboard-hr-leave", ttl=CACHE_TTL["short"])
async def get_hr_leave_dashboard(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[int] = Query(default=None, description="Filter by department ID"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated HR Leave Dashboard for calendar and scheduling views.

    Combines data from:
    - Leave calendar events
    - Pending leave requests
    - Leave balance summary
    - Department-wise leave
    """
    from app.models.employee import Employee, EmploymentStatus
    from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus, LeaveType, LeaveAllocation

    now = datetime.now(timezone.utc)

    # Parse dates
    start = parse_date_param(start_date, "start_date")
    end = parse_date_param(end_date, "end_date")
    if not start or not end:
        raise HTTPException(status_code=400, detail="start_date and end_date are required")

    # =========== SUMMARY METRICS ===========
    pending_count = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).scalar() or 0

    approved_count = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date >= start,
        LeaveApplication.to_date <= end,
    ).scalar() or 0

    # Today's absences
    today = date.today()
    on_leave_today = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= today,
    ).scalar() or 0

    # =========== CALENDAR EVENTS ===========
    leave_query = db.query(LeaveApplication).filter(
        LeaveApplication.status.in_([LeaveApplicationStatus.APPROVED, LeaveApplicationStatus.OPEN]),
        LeaveApplication.from_date <= end,
        LeaveApplication.to_date >= start,
    )

    calendar_events = []
    for leave in leave_query.order_by(LeaveApplication.from_date.asc()).all():
        # Get employee info
        employee = db.query(Employee).filter(Employee.id == leave.employee_id).first() if leave.employee_id else None
        employee_name = leave.employee_name or (employee.name if employee else "Unknown")

        # Determine color based on status and leave type
        if leave.status == LeaveApplicationStatus.OPEN:
            color = "warning"  # Pending
        else:
            color = "info"  # Approved

        calendar_events.append({
            "id": str(leave.id),
            "title": f"{employee_name} - {leave.leave_type or 'Leave'}",
            "start": leave.from_date.isoformat() if leave.from_date else None,
            "end": leave.to_date.isoformat() if leave.to_date else None,
            "allDay": True,
            "color": color,
            "resourceId": str(leave.employee_id) if leave.employee_id else None,
            "metadata": {
                "employee_id": leave.employee_id,
                "employee_name": employee_name,
                "leave_type": leave.leave_type,
                "status": leave.status.value if leave.status else None,
                "total_days": float(leave.total_leave_days) if leave.total_leave_days else None,
                "reason": leave.description,
                "department": employee.department if employee else None,
            },
        })

    # =========== PENDING REQUESTS ===========
    pending_requests = []
    for leave in db.query(LeaveApplication).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).order_by(LeaveApplication.posting_date.desc()).limit(10).all():
        employee = db.query(Employee).filter(Employee.id == leave.employee_id).first() if leave.employee_id else None
        employee_name = leave.employee_name or (employee.name if employee else "Unknown")

        pending_requests.append({
            "id": leave.id,
            "employee_id": leave.employee_id,
            "employee_name": employee_name,
            "leave_type": leave.leave_type,
            "from_date": leave.from_date.isoformat() if leave.from_date else None,
            "to_date": leave.to_date.isoformat() if leave.to_date else None,
            "total_days": float(leave.total_leave_days) if leave.total_leave_days else None,
            "reason": leave.description,
            "posting_date": leave.posting_date.isoformat() if leave.posting_date else None,
            "department": employee.department if employee else None,
        })

    # =========== LEAVE BY TYPE ===========
    leave_by_type = {}
    type_query = db.query(
        LeaveApplication.leave_type,
        func.count(LeaveApplication.id).label("count"),
        func.sum(LeaveApplication.total_leave_days).label("total_days"),
    ).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date >= start,
        LeaveApplication.to_date <= end,
    ).group_by(LeaveApplication.leave_type).all()

    for row in type_query:
        leave_by_type[row.leave_type or "Unknown"] = {
            "count": row.count,
            "total_days": float(row.total_days or 0),
        }

    # =========== AVAILABLE LEAVE TYPES ===========
    leave_types = []
    for lt in db.query(LeaveType).all():
        leave_types.append({
            "name": lt.leave_type_name,
            "max_days_allowed": float(lt.max_leaves_allowed) if lt.max_leaves_allowed else None,
            "is_carry_forward": lt.is_carry_forward,
        })

    return {
        "generated_at": now.isoformat(),

        "summary": {
            "pending_approvals": pending_count,
            "approved_in_range": approved_count,
            "on_leave_today": on_leave_today,
        },

        "calendar_events": calendar_events,
        "pending_requests": pending_requests,
        "leave_by_type": leave_by_type,
        "leave_types": leave_types,
    }


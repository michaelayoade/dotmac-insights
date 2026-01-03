"""
HR Dashboard Routes - HR Overview with SSR + HTMX.

Permission Requirements:
- hr:read - View HR dashboard
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, and_

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department
from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus
from app.models.hr_attendance import Attendance
from app.models.hr_payroll import SalarySlip, PayrollEntry

RequireHRRead = Depends(require_scope("hr:read"))

router = APIRouter(tags=["hr-dashboard"])
templates = get_template_env()


@router.get("/", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def hr_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """HR Dashboard with overview stats and quick actions."""
    today = date.today()
    start_of_month = today.replace(day=1)

    # Employee Stats
    total_employees = db.query(func.count(Employee.id)).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE
    ).scalar() or 0

    # Today's attendance
    today_present = db.query(func.count(Attendance.id)).filter(
        func.date(Attendance.attendance_date) == today,
        Attendance.status == "Present"
    ).scalar() or 0

    # On leave today
    on_leave_today = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.APPROVED,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= today
    ).scalar() or 0

    # Pending leave requests
    pending_leave = db.query(func.count(LeaveApplication.id)).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).scalar() or 0

    # Recent leave applications
    recent_leave_requests = db.query(LeaveApplication).filter(
        LeaveApplication.status == LeaveApplicationStatus.OPEN
    ).order_by(LeaveApplication.posting_date.desc()).limit(5).all()

    # Employees by department
    dept_counts = db.query(
        Department.department_name,
        func.count(Employee.id).label("count")
    ).outerjoin(
        Employee, and_(
            Employee.department_id == Department.id,
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE
        )
    ).group_by(Department.id, Department.department_name).order_by(
        func.count(Employee.id).desc()
    ).limit(8).all()

    department_stats = [
        {"name": d[0], "count": d[1]}
        for d in dept_counts
    ]

    # Birthday tracking is omitted (Employee has no date_of_birth field)
    employees_with_birthdays: list[dict[str, Any]] = []

    # Work anniversaries this month
    work_anniversaries = []
    try:
        anniversary_query = db.query(Employee).filter(
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE,
            func.extract('month', Employee.date_of_joining) == today.month,
            Employee.date_of_joining < today.replace(year=today.year)
        ).order_by(func.extract('day', Employee.date_of_joining)).limit(5).all()

        for emp in anniversary_query:
            if emp.date_of_joining:
                years = today.year - emp.date_of_joining.year
                if years > 0:
                    work_anniversaries.append({
                        "id": emp.id,
                        "name": emp.name,
                        "date": emp.date_of_joining,
                        "years": years
                    })
    except Exception:
        pass

    # Next payroll due
    next_payroll = None
    try:
        upcoming_payroll = db.query(PayrollEntry).filter(
            PayrollEntry.docstatus == 0
        ).order_by(PayrollEntry.posting_date.desc()).first()
        if upcoming_payroll:
            next_payroll = {
                "id": upcoming_payroll.id,
                "name": f"Payroll #{upcoming_payroll.id}",
                "date": upcoming_payroll.end_date
            }
    except Exception:
        pass

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "HR Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR"},
    ])

    context["stats"] = {
        "total_employees": total_employees,
        "present_today": today_present,
        "on_leave_today": on_leave_today,
        "pending_leave": pending_leave,
    }
    context["recent_leave_requests"] = recent_leave_requests
    context["department_stats"] = department_stats
    context["birthdays"] = employees_with_birthdays
    context["anniversaries"] = work_anniversaries
    context["next_payroll"] = next_payroll
    context["today"] = today

    template = templates.get_template("modules/hr/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))

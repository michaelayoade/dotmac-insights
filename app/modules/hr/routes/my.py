"""
HR Self-Service Routes - Employee Self-Service with SSR + HTMX.

Permission Requirements:
- hr:read - View own HR data (any authenticated user can access their own data)

These routes provide employees with access to their own HR data:
- /hr/my/leave - My leave requests and balance
- /hr/my/attendance - My attendance records and check-in/out
- /hr/my/payslips - My salary slips
- /hr/my/appraisals - My performance appraisals
- /hr/my/training - My training history
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, and_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.employee import Employee, EmploymentStatus
from app.models.hr_leave import LeaveApplication, LeaveType, LeaveAllocation, LeaveApplicationStatus
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_payroll import SalarySlip
from app.models.hr_appraisal import Appraisal
from app.models.hr_training import TrainingEvent, TrainingEventEmployee
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.utils.datetime_utils import utc_now

RequireHRRead = Depends(require_scope("hr:read"))

router = APIRouter(prefix="/my", tags=["hr-self-service"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str) -> Optional[int]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _form_date(form: Any, key: str) -> Optional[date]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _get_current_employee(db, user) -> Optional[Employee]:
    """Get the employee record for the current user."""
    if not user or not user.email:
        return None
    return db.query(Employee).filter(
        Employee.email == user.email,
        Employee.is_deleted == False,
    ).first()


def get_leave_type_options(db):
    types = db.query(LeaveType).order_by(LeaveType.leave_type_name).all()
    return [{"value": str(t.id), "label": t.leave_type_name} for t in types]


# =============================================================================
# MY HR DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_hr_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """My HR self-service dashboard."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    today = date.today()

    # Leave balance summary
    leave_balances = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee.id,
        LeaveAllocation.from_date <= today,
        LeaveAllocation.to_date >= today,
    ).all()

    # Pending leave requests
    pending_leave = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee.id,
        LeaveApplication.status == LeaveApplicationStatus.OPEN,
    ).count()

    # Recent attendance
    recent_attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
    ).order_by(Attendance.attendance_date.desc()).limit(5).all()

    # Today's attendance
    today_attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date == today,
    ).first()

    # Recent payslips
    recent_payslips = db.query(SalarySlip).filter(
        SalarySlip.employee_id == employee.id,
    ).order_by(SalarySlip.posting_date.desc()).limit(3).all()

    # Upcoming training
    upcoming_training = db.query(TrainingEvent).join(
        TrainingEventEmployee,
        TrainingEventEmployee.training_event_id == TrainingEvent.id,
    ).filter(
        TrainingEventEmployee.employee_id == employee.id,
        TrainingEvent.start_date >= today,
    ).order_by(TrainingEvent.start_date).limit(3).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My HR"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR"},
    ])
    context["employee"] = employee
    context["leave_balances"] = leave_balances
    context["pending_leave"] = pending_leave
    context["recent_attendance"] = recent_attendance
    context["today_attendance"] = today_attendance
    context["recent_payslips"] = recent_payslips
    context["upcoming_training"] = upcoming_training
    context["today"] = today

    template = templates.get_template("modules/hr/templates/my/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# MY LEAVE
# =============================================================================

@router.get("/leave", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """My leave requests list."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee.id,
    )

    if status:
        query = query.filter(LeaveApplication.status == status)

    total = query.count()
    offset = (page - 1) * per_page
    applications = query.order_by(LeaveApplication.from_date.desc()).offset(offset).limit(per_page).all()

    # Get leave balances
    today = date.today()
    leave_balances = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee.id,
        LeaveAllocation.from_date <= today,
        LeaveAllocation.to_date >= today,
    ).all()

    context = get_base_context(request, response, user, csrf_token)
    context["applications"] = applications
    context["leave_balances"] = leave_balances
    context["current_status"] = status
    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in LeaveApplicationStatus
    ]
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/my/partials/leave_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Leave"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Leave"},
    ])
    context["employee"] = employee

    template = templates.get_template("modules/hr/templates/my/pages/leave.html")
    return HTMLResponse(template.render(context))


@router.get("/leave/balance", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_balance(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """My leave balance detail."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    today = date.today()

    # Get all leave allocations for current period
    allocations = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee.id,
        LeaveAllocation.from_date <= today,
        LeaveAllocation.to_date >= today,
    ).all()

    # Calculate used leave by type
    leave_usage = {}
    for alloc in allocations:
        used = db.query(func.sum(LeaveApplication.total_leave_days)).filter(
            LeaveApplication.employee_id == employee.id,
            LeaveApplication.leave_type_id == alloc.leave_type_id,
            LeaveApplication.status == LeaveApplicationStatus.APPROVED,
            LeaveApplication.from_date >= alloc.from_date,
            LeaveApplication.to_date <= alloc.to_date,
        ).scalar() or 0

        leave_usage[alloc.leave_type_id] = {
            "allocation": alloc,
            "allocated": alloc.new_leaves_allocated or 0,
            "used": float(used),
            "remaining": (alloc.new_leaves_allocated or 0) - float(used),
        }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Leave Balance"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Leave", "href": "/hr/my/leave"},
        {"label": "Balance"},
    ])
    context["employee"] = employee
    context["leave_usage"] = leave_usage.values()

    template = templates.get_template("modules/hr/templates/my/pages/leave_balance.html")
    return HTMLResponse(template.render(context))


@router.get("/leave/new", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Apply for leave form."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Apply for Leave"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Leave", "href": "/hr/my/leave"},
        {"label": "Apply"},
    ])
    context["employee"] = employee
    context["leave_type_options"] = get_leave_type_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/my/pages/leave_form.html")
    return HTMLResponse(template.render(context))


@router.post("/leave", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Submit leave application."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    form = await request.form()

    errors = {}
    leave_type_id = _form_int(form, "leave_type_id")
    from_date = _form_date(form, "from_date")
    to_date = _form_date(form, "to_date")

    if leave_type_id is None:
        errors["leave_type_id"] = "Leave type is required"
    if from_date is None:
        errors["from_date"] = "From date is required"
    if to_date is None:
        errors["to_date"] = "To date is required"
    if from_date and to_date and from_date > to_date:
        errors["to_date"] = "To date must be after from date"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Apply for Leave"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "My HR", "href": "/hr/my"},
            {"label": "My Leave", "href": "/hr/my/leave"},
            {"label": "Apply"},
        ])
        context["employee"] = employee
        context["leave_type_options"] = get_leave_type_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/my/pages/leave_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    if leave_type_id is None or from_date is None or to_date is None:
        raise HTTPException(status_code=400, detail="Invalid leave data")

    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        errors["leave_type_id"] = "Leave type not found"
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Apply for Leave"
        context["employee"] = employee
        context["leave_type_options"] = get_leave_type_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/my/pages/leave_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    total_days = (to_date - from_date).days + 1

    application = LeaveApplication(
        employee_id=employee.id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        leave_type_id=leave_type_id,
        leave_type=leave_type.leave_type_name,
        from_date=from_date,
        to_date=to_date,
        total_leave_days=total_days,
        posting_date=date.today(),
        description=_form_str(form, "description") or None,
        half_day=_form_str(form, "half_day") == "on",
        status=LeaveApplicationStatus.OPEN,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    set_flash(response, "Leave application submitted successfully.", "success")
    return RedirectResponse(url="/hr/my/leave", status_code=303)


@router.get("/leave/{application_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    application_id: int,
):
    """View my leave application detail."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    application = db.query(LeaveApplication).filter(
        LeaveApplication.id == application_id,
        LeaveApplication.employee_id == employee.id,
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Leave Application"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Leave", "href": "/hr/my/leave"},
        {"label": f"#{application.id}"},
    ])
    context["employee"] = employee
    context["application"] = application

    template = templates.get_template("modules/hr/templates/my/pages/leave_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/leave/{application_id}/cancel", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_leave_cancel(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    application_id: int,
):
    """Cancel my leave application."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    application = db.query(LeaveApplication).filter(
        LeaveApplication.id == application_id,
        LeaveApplication.employee_id == employee.id,
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    if application.status != LeaveApplicationStatus.OPEN:
        if is_htmx_request(request):
            htmx_toast(response, "Only pending applications can be cancelled.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, "Only pending applications can be cancelled.", "error")
        return RedirectResponse(url=f"/hr/my/leave/{application_id}", status_code=303)

    application.status = LeaveApplicationStatus.CANCELLED
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Leave application cancelled.", "success")
        response.headers["HX-Redirect"] = "/hr/my/leave"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave application cancelled.", "success")
    return RedirectResponse(url="/hr/my/leave", status_code=303)


# =============================================================================
# MY ATTENDANCE
# =============================================================================

@router.get("/attendance", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_attendance_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    month: Optional[str] = Query(None, description="Month in YYYY-MM format"),
    page: int = Query(1, ge=1),
    per_page: int = Query(31, ge=10, le=100),
):
    """My attendance records."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    today = date.today()

    # Parse month filter
    if month:
        try:
            year, month_num = map(int, month.split("-"))
            start_date = date(year, month_num, 1)
            if month_num == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month_num + 1, 1) - timedelta(days=1)
        except (ValueError, TypeError):
            start_date = today.replace(day=1)
            end_date = today
    else:
        start_date = today.replace(day=1)
        end_date = today

    query = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date >= start_date,
        Attendance.attendance_date <= end_date,
    )

    total = query.count()
    offset = (page - 1) * per_page
    records = query.order_by(Attendance.attendance_date.desc()).offset(offset).limit(per_page).all()

    # Summary stats
    present_count = db.query(func.count(Attendance.id)).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date >= start_date,
        Attendance.attendance_date <= end_date,
        Attendance.status == "Present",
    ).scalar() or 0

    absent_count = db.query(func.count(Attendance.id)).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date >= start_date,
        Attendance.attendance_date <= end_date,
        Attendance.status == "Absent",
    ).scalar() or 0

    # Today's attendance for check-in/out buttons
    today_attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date == today,
    ).first()

    context = get_base_context(request, response, user, csrf_token)
    context["records"] = records
    context["current_month"] = month or today.strftime("%Y-%m")
    context["start_date"] = start_date
    context["end_date"] = end_date
    context["present_count"] = present_count
    context["absent_count"] = absent_count
    context["today_attendance"] = today_attendance
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/my/partials/attendance_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Attendance"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Attendance"},
    ])
    context["employee"] = employee
    context["today"] = today

    template = templates.get_template("modules/hr/templates/my/pages/attendance.html")
    return HTMLResponse(template.render(context))


@router.post("/attendance/check-in", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_check_in(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Check in for today."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    today = date.today()
    now = utc_now()

    # Check for existing attendance today
    existing = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date == today,
    ).first()

    if existing:
        if is_htmx_request(request):
            htmx_toast(response, "You have already checked in today.", "warning")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, "You have already checked in today.", "warning")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)

    # Create attendance record
    attendance = Attendance(
        employee_id=employee.id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        attendance_date=today,
        status="Present",
        in_time=now.time(),
    )
    db.add(attendance)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Checked in at {now.strftime('%H:%M')}.", "success")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Checked in at {now.strftime('%H:%M')}.", "success")
    return RedirectResponse(url="/hr/my/attendance", status_code=303)


@router.post("/attendance/check-out", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_check_out(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Check out for today."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    today = date.today()
    now = utc_now()

    # Find today's attendance
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date == today,
    ).first()

    if not attendance:
        if is_htmx_request(request):
            htmx_toast(response, "You have not checked in today.", "warning")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, "You have not checked in today.", "warning")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)

    if attendance.out_time:
        if is_htmx_request(request):
            htmx_toast(response, "You have already checked out.", "warning")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, "You have already checked out.", "warning")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)

    attendance.out_time = now.time()
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Checked out at {now.strftime('%H:%M')}.", "success")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Checked out at {now.strftime('%H:%M')}.", "success")
    return RedirectResponse(url="/hr/my/attendance", status_code=303)


# =============================================================================
# MY PAYSLIPS
# =============================================================================

@router.get("/payslips", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_payslips_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=6, le=24),
):
    """My payslips list."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    query = db.query(SalarySlip).filter(
        SalarySlip.employee_id == employee.id,
    )

    if year:
        query = query.filter(func.extract('year', SalarySlip.posting_date) == year)

    total = query.count()
    offset = (page - 1) * per_page
    payslips = query.order_by(SalarySlip.posting_date.desc()).offset(offset).limit(per_page).all()

    # Get available years
    years = db.query(func.distinct(func.extract('year', SalarySlip.posting_date))).filter(
        SalarySlip.employee_id == employee.id,
    ).order_by(func.extract('year', SalarySlip.posting_date).desc()).all()
    year_options = [int(y[0]) for y in years if y[0]]

    context = get_base_context(request, response, user, csrf_token)
    context["payslips"] = payslips
    context["current_year"] = year
    context["year_options"] = year_options
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/my/partials/payslips_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Payslips"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Payslips"},
    ])
    context["employee"] = employee

    template = templates.get_template("modules/hr/templates/my/pages/payslips.html")
    return HTMLResponse(template.render(context))


@router.get("/payslips/{payslip_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_payslip_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payslip_id: int,
):
    """View my payslip detail."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    payslip = db.query(SalarySlip).filter(
        SalarySlip.id == payslip_id,
        SalarySlip.employee_id == employee.id,
    ).first()

    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Payslip - {payslip.posting_date}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Payslips", "href": "/hr/my/payslips"},
        {"label": str(payslip.posting_date)},
    ])
    context["employee"] = employee
    context["payslip"] = payslip

    template = templates.get_template("modules/hr/templates/my/pages/payslip_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# MY APPRAISALS
# =============================================================================

@router.get("/appraisals", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_appraisals_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=5, le=25),
):
    """My appraisals list."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    query = db.query(Appraisal).filter(
        Appraisal.employee_id == employee.id,
    )

    total = query.count()
    offset = (page - 1) * per_page
    appraisals = query.order_by(Appraisal.start_date.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["appraisals"] = appraisals
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/my/partials/appraisals_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Appraisals"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Appraisals"},
    ])
    context["employee"] = employee

    template = templates.get_template("modules/hr/templates/my/pages/appraisals.html")
    return HTMLResponse(template.render(context))


@router.get("/appraisals/{appraisal_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_appraisal_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    appraisal_id: int,
):
    """View my appraisal detail."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    appraisal = db.query(Appraisal).filter(
        Appraisal.id == appraisal_id,
        Appraisal.employee_id == employee.id,
    ).first()

    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Appraisal - {appraisal.start_date.year}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Appraisals", "href": "/hr/my/appraisals"},
        {"label": str(appraisal.start_date.year)},
    ])
    context["employee"] = employee
    context["appraisal"] = appraisal

    template = templates.get_template("modules/hr/templates/my/pages/appraisal_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# MY TRAINING
# =============================================================================

@router.get("/training", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_training_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=5, le=25),
):
    """My training events list."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    query = db.query(TrainingEvent).join(
        TrainingEventEmployee,
        TrainingEventEmployee.training_event_id == TrainingEvent.id,
    ).filter(
        TrainingEventEmployee.employee_id == employee.id,
    )

    total = query.count()
    offset = (page - 1) * per_page
    events = query.order_by(TrainingEvent.start_date.desc()).offset(offset).limit(per_page).all()

    today = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["events"] = events
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["today"] = today

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/my/partials/training_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Training"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Training"},
    ])
    context["employee"] = employee

    template = templates.get_template("modules/hr/templates/my/pages/training.html")
    return HTMLResponse(template.render(context))


@router.get("/training/{event_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def my_training_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    event_id: int,
):
    """View my training event detail."""
    employee = _get_current_employee(db, user)

    if not employee:
        set_flash(response, "No employee record found for your account.", "warning")
        return RedirectResponse(url="/hr", status_code=303)

    # Verify employee is enrolled
    enrollment = db.query(TrainingEventEmployee).filter(
        TrainingEventEmployee.training_event_id == event_id,
        TrainingEventEmployee.employee_id == employee.id,
    ).first()

    if not enrollment:
        raise HTTPException(status_code=404, detail="Training event not found")

    event = db.query(TrainingEvent).filter(
        TrainingEvent.id == event_id,
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Training - {event.event_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Training", "href": "/hr/my/training"},
        {"label": event.event_name},
    ])
    context["employee"] = employee
    context["event"] = event
    context["enrollment"] = enrollment

    template = templates.get_template("modules/hr/templates/my/pages/training_detail.html")
    return HTMLResponse(template.render(context))

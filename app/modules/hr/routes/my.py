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
from typing import Optional, Any
from datetime import date, timedelta

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.employee import Employee
from app.models.hr_leave import LeaveApplicationStatus
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.utils.datetime_utils import utc_now
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import ApplicationCreateData, ApplicationFilters
from app.services.hr.attendance import AttendanceService
from app.services.hr.attendance_types import (
    CheckInData,
    CheckOutData,
    AttendanceFilters,
)
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import SalarySlipFilters
from app.services.hr.training import TrainingService
from app.services.hr.training_types import TrainingEventFilters
from app.services.hr.appraisal import AppraisalService
from app.services.hr.appraisal_types import AppraisalFilters
from app.services.types import PaginationParams
from app.services.hr.errors import (
    ValidationError as HRValidationError,
    CheckInError,
    CheckOutError,
    LeaveApplicationNotFoundError,
    LeaveStatusTransitionError,
)
from app.services.hr.employees import EmployeeService

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
    service = EmployeeService(db, principal=user)
    return service.get_employee_by_email(user.email)


def get_leave_type_options(db):
    """Get leave type options using LeaveService."""
    leave_service = LeaveService(db)
    types = leave_service.list_leave_types()
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
    leave_service = LeaveService(db)
    attendance_service = AttendanceService(db)
    payroll_service = PayrollService(db)
    training_service = TrainingService(db)

    # Leave balance summary - use LeaveService
    leave_balances = leave_service.get_current_allocations(employee.id, today)

    # Pending leave requests - use LeaveService
    pending_apps = leave_service.list_applications(
        ApplicationFilters(employee_id=employee.id, status=LeaveApplicationStatus.OPEN),
        PaginationParams(limit=1),  # Only need count
    )
    pending_leave = pending_apps.total

    # Recent attendance - use AttendanceService
    recent_result = attendance_service.list_attendances(
        AttendanceFilters(employee_id=employee.id),
        PaginationParams(limit=5),
    )
    recent_attendance = recent_result.items

    # Today's attendance - use AttendanceService
    today_attendance = attendance_service.get_attendance_by_employee_date(employee.id, today)

    # Recent payslips - use PayrollService
    payslips_result = payroll_service.list_salary_slips(
        SalarySlipFilters(employee_id=employee.id),
        PaginationParams(limit=3),
    )
    recent_payslips = payslips_result.items

    # Upcoming training - use TrainingService
    upcoming_training = training_service.get_events_for_employee(
        employee.id, include_completed=False
    )[:3]  # Limit to 3

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

    leave_service = LeaveService(db)

    # Build filters for service
    status_enum = None
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
        except ValueError:
            pass  # Invalid status - ignore filter

    # Use LeaveService for applications list
    result = leave_service.list_applications(
        ApplicationFilters(employee_id=employee.id, status=status_enum),
        PaginationParams(offset=(page - 1) * per_page, limit=per_page),
    )
    applications = result.items
    total = result.total

    # Get leave balances - use LeaveService
    today = date.today()
    leave_balances = leave_service.get_current_allocations(employee.id, today)

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
    leave_service = LeaveService(db)

    # Get all leave balances using LeaveService
    balances = leave_service.get_employee_all_balances(employee.id, today)

    # Transform to template-expected format
    leave_usage = [
        {
            "leave_type_name": b.leave_type_name,
            "allocated": float(b.total_allocated),
            "used": float(b.used),
            "remaining": float(b.available),
            "pending": float(b.pending_approval),
            "carry_forwarded": float(b.carry_forwarded),
        }
        for b in balances
        if b.total_allocated > 0  # Only show types with allocations
    ]

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
    context["leave_usage"] = leave_usage

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

    # Use LeaveService for business logic
    leave_service = LeaveService(db)

    try:
        leave_type = leave_service.get_leave_type(leave_type_id)
    except Exception:
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

    # Build application data for service
    is_half_day = _form_str(form, "half_day") == "on"
    app_data = ApplicationCreateData(
        employee_id=employee.id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        leave_type_id=leave_type_id,
        leave_type=leave_type.leave_type_name,
        from_date=from_date,
        to_date=to_date,
        half_day=is_half_day,
        description=_form_str(form, "description") or None,
        company=employee.company,
    )

    # Service handles half-day calculation and validation
    application = leave_service.create_application(app_data)
    db.commit()

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

    leave_service = LeaveService(db)
    try:
        application = leave_service.get_application(application_id)
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")

    if application.employee_id != employee.id:
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

    # Verify ownership
    leave_service = LeaveService(db)
    try:
        application = leave_service.get_application(application_id)
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")

    if application.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Leave application not found")

    # Use LeaveService for cancellation (handles status transitions and balance restoration)
    try:
        leave_service.cancel_application(application_id)
        db.commit()
    except LeaveStatusTransitionError:
        if is_htmx_request(request):
            htmx_toast(response, "Only pending applications can be cancelled.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, "Only pending applications can be cancelled.", "error")
        return RedirectResponse(url=f"/hr/my/leave/{application_id}", status_code=303)

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

    attendance_service = AttendanceService(db)

    # Use AttendanceService for main list
    result = attendance_service.list_attendances(
        AttendanceFilters(
            employee_id=employee.id,
            from_date=start_date,
            to_date=end_date,
        ),
        PaginationParams(offset=(page - 1) * per_page, limit=per_page),
    )
    records = result.items
    total = result.total

    # Summary stats - use AttendanceService
    stats = attendance_service.get_employee_stats(employee.id, start_date, end_date)
    present_count = stats.present_count
    absent_count = stats.absent_count

    # Today's attendance for check-in/out buttons - use service
    today_attendance = attendance_service.get_attendance_by_employee_date(employee.id, today)

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

    # Use AttendanceService for check-in (handles validation, shift detection, late entry)
    attendance_service = AttendanceService(db)
    try:
        check_in_data = CheckInData()
        attendance = attendance_service.check_in(employee.id, check_in_data)
        db.commit()

        time_str = attendance.in_time.strftime('%H:%M') if attendance.in_time else utc_now().strftime('%H:%M')
        if is_htmx_request(request):
            htmx_toast(response, f"Checked in at {time_str}.", "success")
            response.headers["HX-Refresh"] = "true"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Checked in at {time_str}.", "success")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)

    except CheckInError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "warning")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "warning")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)
    except HRValidationError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "error")
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

    # Use AttendanceService for check-out (handles working hours calculation, early exit detection)
    attendance_service = AttendanceService(db)
    try:
        check_out_data = CheckOutData()
        attendance = attendance_service.check_out(employee.id, check_out_data)
        db.commit()

        time_str = attendance.out_time.strftime('%H:%M') if attendance.out_time else utc_now().strftime('%H:%M')
        if is_htmx_request(request):
            htmx_toast(response, f"Checked out at {time_str}.", "success")
            response.headers["HX-Refresh"] = "true"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Checked out at {time_str}.", "success")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)

    except CheckOutError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "warning")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "warning")
        return RedirectResponse(url="/hr/my/attendance", status_code=303)
    except HRValidationError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "error")
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

    payroll_service = PayrollService(db)

    # Build filters - use date range for year filtering
    from_date = None
    to_date = None
    if year:
        from_date = date(year, 1, 1)
        to_date = date(year, 12, 31)

    # Use PayrollService for main list
    result = payroll_service.list_salary_slips(
        SalarySlipFilters(employee_id=employee.id, from_date=from_date, to_date=to_date),
        PaginationParams(offset=(page - 1) * per_page, limit=per_page),
    )
    payslips = result.items
    total = result.total

    year_options = payroll_service.list_salary_slip_years(employee.id)

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

    payroll_service = PayrollService(db)

    try:
        payslip = payroll_service.get_salary_slip(payslip_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Payslip not found")

    # Verify ownership
    if payslip.employee_id != employee.id:
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

    appraisal_service = AppraisalService(db)

    # Use AppraisalService for list
    result = appraisal_service.list_appraisals(
        AppraisalFilters(employee_id=employee.id),
        PaginationParams(offset=(page - 1) * per_page, limit=per_page),
    )
    appraisals = result.items
    total = result.total

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

    appraisal_service = AppraisalService(db)

    try:
        appraisal = appraisal_service.get_appraisal(appraisal_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    # Verify ownership
    if appraisal.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    # Safe access for appraisal dates (may be None)
    year_label = str(appraisal.start_date.year) if appraisal.start_date else "N/A"

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Appraisal - {year_label}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "My HR", "href": "/hr/my"},
        {"label": "My Appraisals", "href": "/hr/my/appraisals"},
        {"label": year_label},
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

    training_service = TrainingService(db)

    # Use TrainingService with employee_id filter
    result = training_service.list_events(
        TrainingEventFilters(employee_id=employee.id),
        PaginationParams(offset=(page - 1) * per_page, limit=per_page),
    )
    events = result.items
    total = result.total

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

    training_service = TrainingService(db)

    # Get event using service
    try:
        event = training_service.get_event(event_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Training event not found")

    # Verify employee is enrolled - check in loaded employees relationship
    enrollment = None
    for emp in event.employees:
        if emp.employee_id == employee.id:
            enrollment = emp
            break

    if not enrollment:
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

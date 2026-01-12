"""
HR Attendance Routes - Attendance Management with SSR + HTMX.

Uses AttendanceService for all business logic.

Permission Requirements:
- hr:read - View attendance records, shifts
- hr:write - Create, update attendance
"""
from typing import Optional, Any
from datetime import date, datetime, time

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
from app.models.hr_attendance import AttendanceStatus
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.hr.attendance import AttendanceService
from app.services.hr.attendance_types import (
    AttendanceFilters,
    AttendanceCreateData,
    AttendanceUpdateData,
)
from app.services.hr.employees import EmployeeService
from app.services.types import PaginationParams
from app.services.hr.errors import (
    AttendanceNotFoundError,
    DuplicateAttendanceError,
    EmployeeNotFoundError,
    ValidationError as HRValidationError,
)

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/attendance", tags=["hr-attendance"])
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


def _form_time(form: Any, key: str) -> Optional[time]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _parse_status(value: str) -> Optional[AttendanceStatus]:
    if not value:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    try:
        return AttendanceStatus(normalized)
    except ValueError:
        return None


def get_status_options():
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in AttendanceStatus
    ]


def get_employee_options(db):
    """Get employee options using EmployeeService."""
    service = EmployeeService(db)
    result = service.list_employees(pagination=PaginationParams(offset=0, limit=10000))
    return [{"value": str(e.id), "label": e.name} for e in result.items]


def get_shift_options(db):
    """Get shift types using service layer."""
    service = AttendanceService(db)
    result = service.list_shift_types()
    return [{"value": str(s.id), "label": s.shift_type_name} for s in result.items]


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def attendance_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    attendance_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("attendance_date"),
    dir: str = Query("desc"),
):
    """Attendance records list page using AttendanceService."""
    service = AttendanceService(db)
    offset = (page - 1) * per_page

    # Parse status and date
    status_enum = None
    if status:
        try:
            status_enum = AttendanceStatus(status)
        except ValueError:
            pass

    att_date = None
    if attendance_date:
        try:
            att_date = date.fromisoformat(attendance_date)
        except ValueError:
            pass

    # Use service for filtering - search is handled via post-filter
    if q:
        # Search requires post-filtering since service doesn't support text search
        all_result = service.list_attendances(
            filters=AttendanceFilters(status=status_enum, from_date=att_date, to_date=att_date),
            pagination=PaginationParams(offset=0, limit=10000),
        )
        q_lower = q.lower()
        filtered = [
            a for a in all_result.items
            if (a.employee_name and q_lower in a.employee_name.lower())
            or (a.employee and q_lower in a.employee.lower())
        ]
        total = len(filtered)
        records = filtered[offset : offset + per_page]
    else:
        filters = AttendanceFilters(
            status=status_enum,
            from_date=att_date,
            to_date=att_date,
        )
        result = service.list_attendances(
            filters=filters,
            pagination=PaginationParams(offset=offset, limit=per_page),
        )
        records = result.items
        total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["records"] = records
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_date"] = attendance_date
    context["status_options"] = get_status_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/attendance/partials/attendance_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Attendance"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Attendance"},
    ])

    template = templates.get_template("modules/hr/templates/attendance/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def attendance_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    attendance_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("attendance_date"),
    dir: str = Query("desc"),
):
    return await attendance_list(
        request, response, user, csrf_token, db,
        q, status, attendance_date, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def attendance_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Record Attendance"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Attendance", "href": "/hr/attendance"},
        {"label": "Record Attendance"},
    ])
    context["record"] = None
    context["status_options"] = get_status_options()
    context["employee_options"] = get_employee_options(db)
    context["shift_options"] = get_shift_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def attendance_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    form = await request.form()

    errors = {}
    employee_id = _form_int(form, "employee_id")
    attendance_date_val = _form_date(form, "attendance_date")
    status_val = _form_str(form, "status")
    status_enum = _parse_status(status_val)

    if employee_id is None:
        errors["employee_id"] = "Employee is required"
    if attendance_date_val is None:
        errors["attendance_date"] = "Date is required"
    if not status_enum:
        errors["status"] = "Status is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Record Attendance"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Attendance", "href": "/hr/attendance"},
            {"label": "Record Attendance"},
        ])
        context["record"] = None
        context["status_options"] = get_status_options()
        context["employee_options"] = get_employee_options(db)
        context["shift_options"] = get_shift_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    if employee_id is None or attendance_date_val is None:
        raise HTTPException(status_code=400, detail="Invalid attendance data")

    # Look up employee using service
    employee_service = EmployeeService(db)
    try:
        employee = employee_service.get_employee(employee_id)
    except EmployeeNotFoundError:
        errors["employee_id"] = "Employee not found"
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Record Attendance"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Attendance", "href": "/hr/attendance"},
            {"label": "Record Attendance"},
        ])
        context["record"] = None
        context["status_options"] = get_status_options()
        context["employee_options"] = get_employee_options(db)
        context["shift_options"] = get_shift_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create attendance via service
    service = AttendanceService(db)
    shift_id = _form_int(form, "shift_id")
    shift_name = None
    if shift_id:
        try:
            shift_name = service.get_shift_type(shift_id).shift_type_name
        except Exception:
            shift_name = None

    create_data = AttendanceCreateData(
        employee_id=employee_id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        attendance_date=attendance_date_val,
        status=status_enum,
        shift=shift_name,
    )

    try:
        record = service.create_attendance(create_data)
        db.commit()
    except DuplicateAttendanceError:
        db.rollback()
        errors["attendance_date"] = "Attendance already exists for this date"
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Record Attendance"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Attendance", "href": "/hr/attendance"},
            {"label": "Record Attendance"},
        ])
        context["record"] = None
        context["status_options"] = get_status_options()
        context["employee_options"] = get_employee_options(db)
        context["shift_options"] = get_shift_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)
    except HRValidationError as e:
        db.rollback()
        errors["_form"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Record Attendance"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Attendance", "href": "/hr/attendance"},
            {"label": "Record Attendance"},
        ])
        context["record"] = None
        context["status_options"] = get_status_options()
        context["employee_options"] = get_employee_options(db)
        context["shift_options"] = get_shift_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Attendance recorded successfully.", "success")
    return RedirectResponse(url=f"/hr/attendance/{record.id}", status_code=303)


@router.get("/{record_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def attendance_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    record_id: int,
):
    """Edit attendance record form."""
    service = AttendanceService(db, user)
    try:
        record = service.get_attendance(record_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Attendance"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Attendance", "href": "/hr/attendance"},
        {"label": str(record.attendance_date), "href": f"/hr/attendance/{record.id}"},
        {"label": "Edit"},
    ])
    context["record"] = record
    context["status_options"] = get_status_options()
    context["employee_options"] = get_employee_options(db)
    context["shift_options"] = get_shift_options(db)
    context["errors"] = {}
    context["form_data"] = {}

    template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{record_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def attendance_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    record_id: int,
):
    """Update an attendance record."""
    form = await request.form()
    service = AttendanceService(db, user)

    try:
        record = service.get_attendance(record_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    errors = {}
    status_val = _form_str(form, "status")
    status_enum = _parse_status(status_val)
    if not status_enum:
        errors["status"] = "Status is required"

    shift_id = _form_int(form, "shift_id")
    shift_name = None
    if shift_id:
        try:
            shift_name = service.get_shift_type(shift_id).shift_type_name
        except Exception:
            shift_name = None

    in_time_val = _form_time(form, "in_time")
    out_time_val = _form_time(form, "out_time")
    attendance_date_val = record.attendance_date
    in_time_dt = datetime.combine(attendance_date_val, in_time_val) if in_time_val else None
    out_time_dt = datetime.combine(attendance_date_val, out_time_val) if out_time_val else None

    late_entry = _form_str(form, "late_entry") == "on"
    early_exit = _form_str(form, "early_exit") == "on"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Attendance"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Attendance", "href": "/hr/attendance"},
            {"label": str(record.attendance_date), "href": f"/hr/attendance/{record.id}"},
            {"label": "Edit"},
        ])
        context["record"] = record
        context["status_options"] = get_status_options()
        context["employee_options"] = get_employee_options(db)
        context["shift_options"] = get_shift_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/attendance/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service.update_attendance(
        record_id,
        AttendanceUpdateData(
            status=status_enum,
            shift=shift_name,
            in_time=in_time_dt,
            out_time=out_time_dt,
            late_entry=late_entry,
            early_exit=early_exit,
        ),
    )
    db.commit()

    set_flash(response, "Attendance record updated successfully.", "success")
    return RedirectResponse(url=f"/hr/attendance/{record_id}", status_code=303)


@router.get("/shifts", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def shifts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Shift types list page using AttendanceService."""
    service = AttendanceService(db)
    offset = (page - 1) * per_page

    # Search requires post-filtering since service doesn't support text search
    if q:
        all_result = service.list_shift_types(
            pagination=PaginationParams(offset=0, limit=10000),
        )
        q_lower = q.lower()
        filtered = [
            s for s in all_result.items
            if s.shift_type_name and q_lower in s.shift_type_name.lower()
        ]
        total = len(filtered)
        shifts = filtered[offset : offset + per_page]
    else:
        result = service.list_shift_types(
            pagination=PaginationParams(offset=offset, limit=per_page),
        )
        shifts = result.items
        total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["shifts"] = shifts
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/attendance/partials/shifts_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Shift Types"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Shift Types"},
    ])

    template = templates.get_template("modules/hr/templates/attendance/pages/shifts_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{record_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def attendance_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    record_id: int,
):
    """Attendance detail page using AttendanceService."""
    service = AttendanceService(db)
    try:
        record = service.get_attendance(record_id)
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Attendance - {record.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Attendance", "href": "/hr/attendance"},
        {"label": str(record.attendance_date)},
    ])
    context["record"] = record

    template = templates.get_template("modules/hr/templates/attendance/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.delete("/{record_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def attendance_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    record_id: int,
):
    """Delete attendance record using AttendanceService."""
    service = AttendanceService(db)
    try:
        service.delete_attendance(record_id)
        db.commit()
    except AttendanceNotFoundError:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if is_htmx_request(request):
        htmx_toast(response, "Attendance record deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Attendance record deleted.", "success")
    return RedirectResponse(url="/hr/attendance", status_code=303)

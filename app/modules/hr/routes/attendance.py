"""
HR Attendance Routes - Attendance Management with SSR + HTMX.

Permission Requirements:
- hr:read - View attendance records, shifts
- hr:write - Create, update attendance
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import date

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.hr_attendance import Attendance, AttendanceStatus, ShiftType
from app.models.employee import Employee
from app.core.security import is_htmx_request, htmx_toast, set_flash

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


def get_status_options():
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in AttendanceStatus
    ]


def get_employee_options(db):
    employees = db.query(Employee).filter(Employee.is_deleted == False).order_by(Employee.name).all()
    return [{"value": str(e.id), "label": e.name} for e in employees]


def get_shift_options(db):
    shifts = db.query(ShiftType).order_by(ShiftType.shift_type_name).all()
    return [{"value": str(s.id), "label": s.shift_type_name} for s in shifts]


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
    """Attendance records list page."""
    query = db.query(Attendance)

    if q:
        search_filter = or_(
            Attendance.employee_name.ilike(f"%{q}%"),
            Attendance.employee.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    if status:
        query = query.filter(Attendance.status == status)
    if attendance_date:
        query = query.filter(Attendance.attendance_date == date.fromisoformat(attendance_date))

    total = query.count()

    sort_column = getattr(Attendance, sort, Attendance.attendance_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    offset = (page - 1) * per_page
    records = query.offset(offset).limit(per_page).all()

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

    if employee_id is None:
        errors["employee_id"] = "Employee is required"
    if attendance_date_val is None:
        errors["attendance_date"] = "Date is required"
    if not status_val:
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

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
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

    # Check for existing attendance
    existing = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.attendance_date == attendance_date_val
    ).first()
    if existing:
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

    record = Attendance(
        employee_id=employee_id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        attendance_date=attendance_date_val,
        status=status_val,
        shift=_form_str(form, "shift") or None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    set_flash(response, "Attendance recorded successfully.", "success")
    return RedirectResponse(url=f"/hr/attendance/{record.id}", status_code=303)


@router.get("/{record_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def attendance_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    record_id: int,
):
    record = db.query(Attendance).filter(Attendance.id == record_id).first()

    if not record:
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
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(record)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Attendance record deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Attendance record deleted.", "success")
    return RedirectResponse(url="/hr/attendance", status_code=303)


# === Shift Types Routes ===
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
    query = db.query(ShiftType)

    if q:
        query = query.filter(ShiftType.shift_type_name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * per_page
    shifts = query.order_by(ShiftType.shift_type_name).offset(offset).limit(per_page).all()

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

"""
HR Leave Routes - Leave Management with SSR + HTMX.

Permission Requirements:
- hr:read - View leave applications, types, allocations
- hr:write - Create, update, manage leave
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
from app.models.hr_leave import LeaveApplication, LeaveType, LeaveAllocation, LeaveApplicationStatus
from app.models.employee import Employee
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/leave", tags=["hr-leave"])
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
        for s in LeaveApplicationStatus
    ]


def get_leave_type_options(db):
    types = db.query(LeaveType).order_by(LeaveType.leave_type_name).all()
    return [{"value": str(t.id), "label": t.leave_type_name} for t in types]


def get_employee_options(db):
    employees = db.query(Employee).filter(Employee.is_deleted == False).order_by(Employee.name).all()
    return [{"value": str(e.id), "label": e.name} for e in employees]


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_applications_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("from_date"),
    dir: str = Query("desc"),
):
    """Leave applications list page."""
    query = db.query(LeaveApplication)

    if q:
        search_filter = or_(
            LeaveApplication.employee_name.ilike(f"%{q}%"),
            LeaveApplication.employee.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    if status:
        query = query.filter(LeaveApplication.status == status)
    if leave_type:
        query = query.filter(LeaveApplication.leave_type_id == int(leave_type))

    total = query.count()

    sort_column = getattr(LeaveApplication, sort, LeaveApplication.from_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    offset = (page - 1) * per_page
    applications = query.offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["applications"] = applications
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_leave_type"] = leave_type
    context["status_options"] = get_status_options()
    context["leave_type_options"] = get_leave_type_options(db)
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/leave/partials/applications_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leave Applications"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Leave Applications"},
    ])

    template = templates.get_template("modules/hr/templates/leave/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_applications_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("from_date"),
    dir: str = Query("desc"),
):
    return await leave_applications_list(
        request, response, user, csrf_token, db,
        q, status, leave_type, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_application_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Apply for Leave"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Apply for Leave"},
    ])
    context["application"] = None
    context["leave_type_options"] = get_leave_type_options(db)
    context["employee_options"] = get_employee_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/leave/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_application_create(
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
    leave_type_id = _form_int(form, "leave_type_id")
    from_date = _form_date(form, "from_date")
    to_date = _form_date(form, "to_date")

    if employee_id is None:
        errors["employee_id"] = "Employee is required"
    if leave_type_id is None:
        errors["leave_type_id"] = "Leave type is required"
    if from_date is None:
        errors["from_date"] = "From date is required"
    if to_date is None:
        errors["to_date"] = "To date is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Apply for Leave"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Apply for Leave"},
        ])
        context["application"] = None
        context["leave_type_options"] = get_leave_type_options(db)
        context["employee_options"] = get_employee_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    if employee_id is None or leave_type_id is None or from_date is None or to_date is None:
        raise HTTPException(status_code=400, detail="Invalid leave application data")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        errors["employee_id"] = "Employee not found"

    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        errors["leave_type_id"] = "Leave type not found"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Apply for Leave"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Apply for Leave"},
        ])
        context["application"] = None
        context["leave_type_options"] = get_leave_type_options(db)
        context["employee_options"] = get_employee_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    if employee is None or leave_type is None:
        raise HTTPException(status_code=400, detail="Invalid leave application data")

    total_days = (to_date - from_date).days + 1

    application = LeaveApplication(
        employee_id=employee_id,
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
    return RedirectResponse(url=f"/hr/leave/{application.id}", status_code=303)


@router.get("/{application_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_application_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    application_id: int,
):
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Leave Application - {application.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": f"Application #{application.id}"},
    ])
    context["application"] = application

    template = templates.get_template("modules/hr/templates/leave/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.post("/{application_id}/approve", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_application_approve(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    application_id: int,
):
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    application.status = LeaveApplicationStatus.APPROVED
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Leave application approved.", "success")
        response.headers["HX-Redirect"] = f"/hr/leave/{application_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave application approved.", "success")
    return RedirectResponse(url=f"/hr/leave/{application_id}", status_code=303)


@router.post("/{application_id}/reject", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_application_reject(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    application_id: int,
):
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    application.status = LeaveApplicationStatus.REJECTED
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Leave application rejected.", "success")
        response.headers["HX-Redirect"] = f"/hr/leave/{application_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave application rejected.", "success")
    return RedirectResponse(url=f"/hr/leave/{application_id}", status_code=303)


@router.delete("/{application_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_application_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    application_id: int,
):
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Leave application not found")

    db.delete(application)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Leave application deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave application deleted.", "success")
    return RedirectResponse(url="/hr/leave", status_code=303)


# === Leave Types Routes ===
@router.get("/types", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_types_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    query = db.query(LeaveType)

    if q:
        query = query.filter(LeaveType.leave_type_name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * per_page
    leave_types = query.order_by(LeaveType.leave_type_name).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["leave_types"] = leave_types
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/leave/partials/types_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leave Types"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Leave Types"},
    ])

    template = templates.get_template("modules/hr/templates/leave/pages/types_list.html")
    return HTMLResponse(template.render(context))


# === Leave Allocations Routes ===
@router.get("/allocations", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_allocations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    query = db.query(LeaveAllocation)

    if q:
        query = query.filter(or_(
            LeaveAllocation.employee_name.ilike(f"%{q}%"),
            LeaveAllocation.leave_type.ilike(f"%{q}%"),
        ))

    total = query.count()
    offset = (page - 1) * per_page
    allocations = query.order_by(LeaveAllocation.from_date.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["allocations"] = allocations
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/leave/partials/allocations_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leave Allocations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Leave Allocations"},
    ])

    template = templates.get_template("modules/hr/templates/leave/pages/allocations_list.html")
    return HTMLResponse(template.render(context))

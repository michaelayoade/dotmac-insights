"""
HR Leave Routes - Leave Management with SSR + HTMX.

Uses LeaveService for all business logic.

Permission Requirements:
- hr:read - View leave applications, types, allocations
- hr:write - Create, update, manage leave
"""
from typing import Optional, Any
from datetime import date

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
from app.models.hr_leave import LeaveApplicationStatus
from app.services.hr.employees import EmployeeService
from app.services.hr.employee_types import EmployeeFilters
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import ApplicationFilters, ApplicationCreateData, AllocationFilters
from app.services.types import PaginationParams
from app.services.hr.errors import (
    EmployeeNotFoundError,
    LeaveApplicationNotFoundError,
    LeaveTypeNotFoundError,
    LeaveStatusTransitionError,
    InsufficientLeaveBalanceError,
    LeaveOverlapError,
    ValidationError as HRValidationError,
)

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
    """Get leave types using service layer."""
    service = LeaveService(db)
    types = service.list_leave_types()
    return [{"value": str(t.id), "label": t.leave_type_name} for t in types]


def get_employee_options(db):
    """Get employees using EmployeeService."""
    service = EmployeeService(db)
    result = service.list_employees(
        filters=EmployeeFilters(),
        pagination=PaginationParams(offset=0, limit=500),
    )
    employees = sorted(result.items, key=lambda e: e.name or "")
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
    service = LeaveService(db)

    # Parse status enum
    status_enum = None
    if status:
        try:
            status_enum = LeaveApplicationStatus(status)
        except ValueError:
            pass

    filters = ApplicationFilters(
        status=status_enum,
        leave_type_id=int(leave_type) if leave_type else None,
        search=q,
    )
    offset = (page - 1) * per_page
    pagination = PaginationParams(offset=offset, limit=per_page)

    result = service.list_applications(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["applications"] = result.items
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_leave_type"] = leave_type
    context["status_options"] = get_status_options()
    context["leave_type_options"] = get_leave_type_options(db)
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    service = LeaveService(db)

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

    # Resolve employee and leave type
    employee_service = EmployeeService(db)
    try:
        employee = employee_service.get_employee(employee_id)
    except EmployeeNotFoundError:
        employee = None
        errors["employee_id"] = "Employee not found"

    try:
        leave_type = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        errors["leave_type_id"] = "Leave type not found"
        leave_type = None

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

    # Create application via service
    create_data = ApplicationCreateData(
        employee_id=employee_id,
        employee=employee.erpnext_id or str(employee.id),
        employee_name=employee.name,
        leave_type_id=leave_type_id,
        leave_type=leave_type.leave_type_name,
        from_date=from_date,
        to_date=to_date,
        half_day=_form_str(form, "half_day") == "on",
        description=_form_str(form, "description") or None,
        company=employee.company,
    )

    try:
        application = service.create_application(create_data)
        db.commit()
    except (InsufficientLeaveBalanceError, LeaveOverlapError, HRValidationError) as e:
        db.rollback()
        errors["_form"] = str(e)
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
    service = LeaveService(db)

    try:
        application = service.get_application(application_id)
    except LeaveApplicationNotFoundError:
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
    service = LeaveService(db)

    try:
        service.approve_application(application_id)
        db.commit()
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")
    except (LeaveStatusTransitionError, InsufficientLeaveBalanceError) as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "error")
        return RedirectResponse(url=f"/hr/leave/{application_id}", status_code=303)

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
    service = LeaveService(db)

    try:
        service.reject_application(application_id)
        db.commit()
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")
    except LeaveStatusTransitionError as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(e), "error")
        return RedirectResponse(url=f"/hr/leave/{application_id}", status_code=303)

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
    service = LeaveService(db)

    try:
        application = service.get_application(application_id)
        db.delete(application)
        db.commit()
    except LeaveApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Leave application not found")

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
    """Leave types list page using LeaveService."""
    service = LeaveService(db)
    all_types = service.list_leave_types()

    # Apply search filter (service doesn't support search yet)
    if q:
        q_lower = q.lower()
        all_types = [t for t in all_types if q_lower in t.leave_type_name.lower()]

    # Sort by name
    all_types = sorted(all_types, key=lambda t: t.leave_type_name)

    # Manual pagination
    total = len(all_types)
    offset = (page - 1) * per_page
    leave_types = all_types[offset : offset + per_page]

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
    """Leave allocations list page using LeaveService."""
    service = LeaveService(db)
    offset = (page - 1) * per_page

    if q:
        # Search requires post-filtering since service doesn't support text search
        all_result = service.list_allocations(
            AllocationFilters(),
            PaginationParams(offset=0, limit=10000),
        )
        q_lower = q.lower()
        filtered = [
            a for a in all_result.items
            if (a.employee_name and q_lower in a.employee_name.lower())
            or (a.leave_type and q_lower in a.leave_type.lower())
        ]
        total = len(filtered)
        allocations = filtered[offset : offset + per_page]
    else:
        # No search - use service pagination directly
        result = service.list_allocations(
            AllocationFilters(),
            PaginationParams(offset=offset, limit=per_page),
        )
        allocations = result.items
        total = result.total

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

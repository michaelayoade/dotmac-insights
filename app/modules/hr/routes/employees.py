"""
HR Employees Routes - Employee Directory with SSR + HTMX.

Permission Requirements:
- hr:read - View employees and employee details
- hr:write - Create, update, delete employees
"""
from __future__ import annotations

from typing import Optional, Any

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
from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department, Designation
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Permission dependencies
RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/employees", tags=["hr-employees"])
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


def _form_status(form: Any, key: str, default: EmploymentStatus) -> EmploymentStatus:
    value = _form_str(form, key, default.value)
    try:
        return EmploymentStatus(value)
    except ValueError:
        return default


def get_status_options():
    """Get employment status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in EmploymentStatus
    ]


def get_department_options(db):
    """Get department options for select dropdown."""
    departments = db.query(Department).order_by(Department.department_name).all()
    return [
        {"value": str(d.id), "label": d.department_name}
        for d in departments
    ]


def get_designation_options(db):
    """Get designation options for select dropdown."""
    designations = db.query(Designation).order_by(Designation.designation_name).all()
    return [
        {"value": str(d.id), "label": d.designation_name}
        for d in designations
    ]


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def employees_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    department: Optional[str] = Query(None, description="Filter by department"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Employee list page.

    Returns full page for normal requests, table partial for HTMX requests.
    """
    # Build query - exclude soft-deleted employees
    query = db.query(Employee).filter(Employee.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            Employee.name.ilike(f"%{q}%"),
            Employee.email.ilike(f"%{q}%"),
            Employee.employee_number.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Employee.status == status)
    if department:
        query = query.filter(Employee.department_id == int(department))

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Employee, sort, Employee.name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    employees = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["employees"] = employees
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_department"] = department
    context["status_options"] = get_status_options()
    context["department_options"] = get_department_options(db)
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/employees/partials/employees_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employees"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Employees"},
    ])

    template = templates.get_template("modules/hr/templates/employees/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def employees_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name"),
    dir: str = Query("asc"),
):
    """Employee table partial for HTMX updates."""
    return await employees_list(
        request, response, user, csrf_token, db,
        q, status, department, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def employee_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New employee form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Employee"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Employees", "href": "/hr/employees"},
        {"label": "New Employee"},
    ])
    context["employee"] = None
    context["status_options"] = get_status_options()
    context["department_options"] = get_department_options(db)
    context["designation_options"] = get_designation_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/employees/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def employee_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new employee."""
    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    email = _form_str(form, "email")
    employee_number = _form_str(form, "employee_number")

    if not name:
        errors["name"] = "Name is required"
    if email and "@" not in email:
        errors["email"] = "Invalid email address"
    if employee_number:
        existing = db.query(Employee).filter(
            Employee.employee_number == employee_number,
            Employee.is_deleted == False
        ).first()
        if existing:
            errors["employee_number"] = "Employee number already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Employee"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Employees", "href": "/hr/employees"},
            {"label": "New Employee"},
        ])
        context["employee"] = None
        context["status_options"] = get_status_options()
        context["department_options"] = get_department_options(db)
        context["designation_options"] = get_designation_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/employees/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create employee
    department_id = _form_int(form, "department_id")
    designation_id = _form_int(form, "designation_id")

    employee = Employee(
        name=name,
        email=email or None,
        phone=_form_str(form, "phone") or None,
        employee_number=employee_number or None,
        department_id=department_id,
        designation_id=designation_id,
        status=_form_status(form, "status", EmploymentStatus.ACTIVE),
        employment_type=_form_str(form, "employment_type") or None,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)

    set_flash(response, f"Employee '{employee.name}' created successfully.", "success")

    return RedirectResponse(url=f"/hr/employees/{employee.id}", status_code=303)


@router.get("/{employee_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def employee_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    employee_id: int,
):
    """Employee detail page."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False,
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Load assigned tasks
    from app.models.task import Task, TaskStatus
    assigned_tasks = db.query(Task).filter(
        Task.assigned_to_id == employee_id,
        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
    ).order_by(Task.exp_end_date).limit(10).all()

    # Load assigned service orders
    from app.models.field_service import ServiceOrder, ServiceOrderStatus
    assigned_orders = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_technician_id == employee_id,
        ServiceOrder.status.in_([
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.EN_ROUTE,
            ServiceOrderStatus.ON_SITE,
            ServiceOrderStatus.IN_PROGRESS,
            ServiceOrderStatus.PENDING_PARTS,
        ]),
    ).order_by(ServiceOrder.scheduled_date).limit(10).all()

    # Load assigned tickets
    from app.models.unified_ticket import UnifiedTicket
    assigned_tickets = db.query(UnifiedTicket).filter(
        UnifiedTicket.assigned_to_id == employee_id,
        UnifiedTicket.is_deleted == False,
        UnifiedTicket.status.in_(["open", "in_progress"]),
    ).order_by(UnifiedTicket.created_at.desc()).limit(10).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = employee.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Employees", "href": "/hr/employees"},
        {"label": employee.name},
    ])
    context["employee"] = employee
    context["assigned_tasks"] = assigned_tasks
    context["assigned_orders"] = assigned_orders
    context["assigned_tickets"] = assigned_tickets

    template = templates.get_template("modules/hr/templates/employees/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{employee_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def employee_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    employee_id: int,
):
    """Employee edit form page."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False,
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {employee.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Employees", "href": "/hr/employees"},
        {"label": employee.name, "href": f"/hr/employees/{employee.id}"},
        {"label": "Edit"},
    ])
    context["employee"] = employee
    context["status_options"] = get_status_options()
    context["department_options"] = get_department_options(db)
    context["designation_options"] = get_designation_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/employees/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{employee_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def employee_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    employee_id: int,
):
    """Update an employee."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False,
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    email = _form_str(form, "email")
    employee_number = _form_str(form, "employee_number")

    if not name:
        errors["name"] = "Name is required"
    if email and "@" not in email:
        errors["email"] = "Invalid email address"
    if employee_number and employee_number != employee.employee_number:
        existing = db.query(Employee).filter(
            Employee.employee_number == employee_number,
            Employee.id != employee_id,
            Employee.is_deleted == False
        ).first()
        if existing:
            errors["employee_number"] = "Employee number already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {employee.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Employees", "href": "/hr/employees"},
            {"label": employee.name, "href": f"/hr/employees/{employee.id}"},
            {"label": "Edit"},
        ])
        context["employee"] = employee
        context["status_options"] = get_status_options()
        context["department_options"] = get_department_options(db)
        context["designation_options"] = get_designation_options(db)
        context["errors"] = errors

        template = templates.get_template("modules/hr/templates/employees/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update employee
    department_id = _form_int(form, "department_id")
    designation_id = _form_int(form, "designation_id")

    employee.name = name
    employee.email = email or None
    employee.phone = _form_str(form, "phone") or None
    employee.employee_number = employee_number or None
    employee.department_id = department_id
    employee.designation_id = designation_id
    employee.status = _form_status(form, "status", employee.status)
    employee.employment_type = _form_str(form, "employment_type") or None
    db.commit()

    set_flash(response, f"Employee '{employee.name}' updated successfully.", "success")

    return RedirectResponse(url=f"/hr/employees/{employee.id}", status_code=303)


@router.delete("/{employee_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def employee_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    employee_id: int,
):
    """Soft delete an employee."""
    from datetime import datetime

    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False,
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    name = employee.name
    # Soft delete
    employee.is_deleted = True
    employee.deleted_at = datetime.utcnow()
    db.commit()

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Employee '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Employee '{name}' deleted.", "success")
    return RedirectResponse(url="/hr/employees", status_code=303)


@router.get("/{employee_id}/row", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def employee_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    employee_id: int,
):
    """Single employee row partial for HTMX updates."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False,
    ).first()

    if not employee:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["employee"] = employee

    template = templates.get_template("modules/hr/templates/employees/partials/employee_row.html")
    return HTMLResponse(template.render(context))

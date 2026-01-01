"""
HR Departments Routes - Department Management with SSR + HTMX.

Permission Requirements:
- hr:read - View departments
- hr:write - Create, update, delete departments
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
from app.models.hr import Department
from app.models.employee import Employee
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Permission dependencies
RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/departments", tags=["hr-departments"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def get_parent_department_options(db, exclude_id=None):
    """Get parent department options for select dropdown."""
    query = db.query(Department)
    if exclude_id:
        query = query.filter(Department.id != exclude_id)
    departments = query.order_by(Department.department_name).all()
    return [
        {"value": str(d.id), "label": d.department_name}
        for d in departments
    ]


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def departments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("department_name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Department list page."""
    query = db.query(Department)

    # Search
    if q:
        search_filter = or_(
            Department.department_name.ilike(f"%{q}%"),
            Department.company.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Department, sort, Department.department_name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    departments = query.offset(offset).limit(per_page).all()

    employee_counts = {
        dept.id: db.query(Employee).filter(
            Employee.department_id == dept.id,
            Employee.is_deleted == False
        ).count()
        for dept in departments
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["departments"] = departments
    context["employee_counts"] = employee_counts
    context["search_query"] = q or ""
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/departments/partials/departments_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Departments"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments"},
    ])

    template = templates.get_template("modules/hr/templates/departments/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def departments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("department_name"),
    dir: str = Query("asc"),
):
    """Department table partial for HTMX updates."""
    return await departments_list(
        request, response, user, csrf_token, db,
        q, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New department form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Department"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments", "href": "/hr/departments"},
        {"label": "New Department"},
    ])
    context["department"] = None
    context["parent_options"] = get_parent_department_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/departments/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new department."""
    form = await request.form()

    # Validation
    errors = {}
    department_name = _form_str(form, "department_name")

    if not department_name:
        errors["department_name"] = "Department name is required"
    else:
        existing = db.query(Department).filter(
            Department.department_name == department_name
        ).first()
        if existing:
            errors["department_name"] = "Department name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Department"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Departments", "href": "/hr/departments"},
            {"label": "New Department"},
        ])
        context["department"] = None
        context["parent_options"] = get_parent_department_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create department
    department = Department(
        department_name=department_name,
        parent_department=_form_str(form, "parent_department") or None,
        company=_form_str(form, "company") or None,
        is_group=form.get("is_group") == "on",
    )
    db.add(department)
    db.commit()
    db.refresh(department)

    set_flash(response, f"Department '{department.department_name}' created successfully.", "success")

    return RedirectResponse(url=f"/hr/departments/{department.id}", status_code=303)


@router.get("/{department_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def department_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    department_id: int,
):
    """Department detail page."""
    department = db.query(Department).filter(
        Department.id == department_id,
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    # Get employees in this department
    employees = db.query(Employee).filter(
        Employee.department_id == department_id,
        Employee.is_deleted == False
    ).order_by(Employee.name).limit(10).all()

    employee_count = db.query(Employee).filter(
        Employee.department_id == department_id,
        Employee.is_deleted == False
    ).count()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = department.department_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments", "href": "/hr/departments"},
        {"label": department.department_name},
    ])
    context["department"] = department
    context["employees"] = employees
    context["employee_count"] = employee_count

    template = templates.get_template("modules/hr/templates/departments/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{department_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    department_id: int,
):
    """Department edit form page."""
    department = db.query(Department).filter(
        Department.id == department_id,
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {department.department_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments", "href": "/hr/departments"},
        {"label": department.department_name, "href": f"/hr/departments/{department.id}"},
        {"label": "Edit"},
    ])
    context["department"] = department
    context["parent_options"] = get_parent_department_options(db, exclude_id=department_id)
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/departments/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{department_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    department_id: int,
):
    """Update a department."""
    department = db.query(Department).filter(
        Department.id == department_id,
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    form = await request.form()

    # Validation
    errors = {}
    department_name = _form_str(form, "department_name")

    if not department_name:
        errors["department_name"] = "Department name is required"
    elif department_name != department.department_name:
        existing = db.query(Department).filter(
            Department.department_name == department_name,
            Department.id != department_id
        ).first()
        if existing:
            errors["department_name"] = "Department name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {department.department_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Departments", "href": "/hr/departments"},
            {"label": department.department_name, "href": f"/hr/departments/{department.id}"},
            {"label": "Edit"},
        ])
        context["department"] = department
        context["parent_options"] = get_parent_department_options(db, exclude_id=department_id)
        context["errors"] = errors

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update department
    department.department_name = department_name
    department.parent_department = _form_str(form, "parent_department") or None
    department.company = _form_str(form, "company") or None
    department.is_group = form.get("is_group") == "on"
    db.commit()

    set_flash(response, f"Department '{department.department_name}' updated successfully.", "success")

    return RedirectResponse(url=f"/hr/departments/{department.id}", status_code=303)


@router.delete("/{department_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    department_id: int,
):
    """Delete a department."""
    department = db.query(Department).filter(
        Department.id == department_id,
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check for employees
    employee_count = db.query(Employee).filter(
        Employee.department_id == department_id,
        Employee.is_deleted == False
    ).count()

    if employee_count > 0:
        if is_htmx_request(request):
            htmx_toast(response, f"Cannot delete department with {employee_count} employees.", "error")
            return HTMLResponse("", status_code=400, headers=dict(response.headers))
        set_flash(response, f"Cannot delete department with {employee_count} employees.", "error")
        return RedirectResponse(url=f"/hr/departments/{department_id}", status_code=303)

    name = department.department_name
    db.delete(department)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Department '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Department '{name}' deleted.", "success")
    return RedirectResponse(url="/hr/departments", status_code=303)


@router.get("/{department_id}/row", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def department_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    department_id: int,
):
    """Single department row partial for HTMX updates."""
    department = db.query(Department).filter(
        Department.id == department_id,
    ).first()

    if not department:
        return HTMLResponse("", status_code=404)

    employee_count = db.query(Employee).filter(
        Employee.department_id == department_id,
        Employee.is_deleted == False
    ).count()

    context = get_base_context(request, response, user, csrf_token)
    context["department"] = department
    context["employee_counts"] = {department.id: employee_count}

    template = templates.get_template("modules/hr/templates/departments/partials/department_row.html")
    return HTMLResponse(template.render(context))

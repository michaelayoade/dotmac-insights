"""
HR Departments Routes - Department Management with SSR + HTMX.

Permission Requirements:
- hr:read - View departments
- hr:write - Create, update, delete departments

Uses OrganizationService for all business logic.
"""
from typing import Optional, Any

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
from app.services.hr.organization import OrganizationService
from app.services.hr.organization_types import (
    DepartmentFilters,
    DepartmentCreateData,
    DepartmentUpdateData,
)
from app.services.hr.employees import EmployeeService
from app.services.hr.employee_types import EmployeeFilters
from app.services.types import PaginationParams
from app.services.hr.errors import DepartmentNotFoundError, ValidationError as HRValidationError
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


def get_parent_department_options(service: OrganizationService, exclude_id=None):
    """Get parent department options for select dropdown."""
    result = service.list_departments(pagination=PaginationParams(offset=0, limit=500))
    departments = [d for d in result.items if d.id != exclude_id] if exclude_id else result.items
    return [
        {"value": str(d.id), "label": d.department_name}
        for d in sorted(departments, key=lambda x: x.department_name or "")
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
    service = OrganizationService(db, user)

    filters = DepartmentFilters(search=q) if q else DepartmentFilters()
    offset = (page - 1) * per_page
    pagination = PaginationParams(offset=offset, limit=per_page)

    result = service.list_departments(filters, pagination)
    departments = result.items
    total = result.total

    # Get headcount for each department
    employee_counts = {}
    for dept in departments:
        try:
            headcount = service.get_department_headcount(dept.id)
            employee_counts[dept.id] = headcount.total_employees
        except DepartmentNotFoundError:
            employee_counts[dept.id] = 0

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


def _serialize_dept_node(node):
    """Serialize department tree node for JSON."""
    return {
        "id": node.id,
        "name": node.department_name or "Unknown",
        "company": node.company if hasattr(node, "company") else None,
        "headcount": getattr(node, "headcount", 0),
        "children": [_serialize_dept_node(child) for child in (node.children or [])],
    }


@router.get("/tree", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def departments_tree(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    company: Optional[str] = Query(None, description="Filter by company"),
):
    """Department tree visualization page."""
    service = OrganizationService(db, user)

    # Get tree structure
    nodes = service.get_department_tree(company=company)
    tree_data = [_serialize_dept_node(node) for node in nodes]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Department Tree"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments", "href": "/hr/departments"},
        {"label": "Tree View"},
    ])
    context["tree_data"] = tree_data
    context["company_filter"] = company

    template = templates.get_template("modules/hr/templates/departments/pages/tree.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def department_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New department form page."""
    service = OrganizationService(db, user)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Department"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Departments", "href": "/hr/departments"},
        {"label": "New Department"},
    ])
    context["department"] = None
    context["parent_options"] = get_parent_department_options(service)
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
    service = OrganizationService(db, user)
    form = await request.form()

    # Basic validation
    errors = {}
    department_name = _form_str(form, "department_name")

    if not department_name:
        errors["department_name"] = "Department name is required"

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
        context["parent_options"] = get_parent_department_options(service)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create department using service
    try:
        data = DepartmentCreateData(
            department_name=department_name,
            parent_department=_form_str(form, "parent_department") or None,
            company=_form_str(form, "company") or None,
            is_group=form.get("is_group") == "on",
        )
        department = service.create_department(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["department_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Department"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Departments", "href": "/hr/departments"},
            {"label": "New Department"},
        ])
        context["department"] = None
        context["parent_options"] = get_parent_department_options(service)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

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
    service = OrganizationService(db, user)

    try:
        department = service.get_department(department_id)
    except DepartmentNotFoundError:
        raise HTTPException(status_code=404, detail="Department not found")

    # Get headcount for the department
    headcount = service.get_department_headcount(department_id)

    employee_service = EmployeeService(db, user)
    employees_result = employee_service.list_employees(
        filters=EmployeeFilters(department_id=department_id),
        pagination=PaginationParams(offset=0, limit=10),
    )
    employees = employees_result.items

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
    context["employee_count"] = headcount.total_employees

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
    service = OrganizationService(db, user)

    try:
        department = service.get_department(department_id)
    except DepartmentNotFoundError:
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
    context["parent_options"] = get_parent_department_options(service, exclude_id=department_id)
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
    service = OrganizationService(db, user)

    try:
        department = service.get_department(department_id)
    except DepartmentNotFoundError:
        raise HTTPException(status_code=404, detail="Department not found")

    form = await request.form()

    # Basic validation
    errors = {}
    department_name = _form_str(form, "department_name")

    if not department_name:
        errors["department_name"] = "Department name is required"

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
        context["parent_options"] = get_parent_department_options(service, exclude_id=department_id)
        context["errors"] = errors

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update department using service
    try:
        data = DepartmentUpdateData(
            department_name=department_name,
            parent_department=_form_str(form, "parent_department") or None,
            company=_form_str(form, "company") or None,
            is_group=form.get("is_group") == "on",
        )
        department = service.update_department(department_id, data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["department_name"] = str(e)
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
        context["parent_options"] = get_parent_department_options(service, exclude_id=department_id)
        context["errors"] = errors

        template = templates.get_template("modules/hr/templates/departments/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

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
    service = OrganizationService(db, user)

    try:
        department = service.get_department(department_id)
    except DepartmentNotFoundError:
        raise HTTPException(status_code=404, detail="Department not found")

    name = department.department_name

    try:
        service.delete_department(department_id)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", status_code=400, headers=dict(response.headers))
        set_flash(response, str(e), "error")
        return RedirectResponse(url=f"/hr/departments/{department_id}", status_code=303)

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
    service = OrganizationService(db, user)

    try:
        department = service.get_department(department_id)
        headcount = service.get_department_headcount(department_id)
    except DepartmentNotFoundError:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["department"] = department
    context["employee_counts"] = {department.id: headcount.total_employees}

    template = templates.get_template("modules/hr/templates/departments/partials/department_row.html")
    return HTMLResponse(template.render(context))

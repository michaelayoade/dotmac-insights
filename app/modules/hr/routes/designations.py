"""
HR Designations Routes - Job Designations with SSR + HTMX.

Permission Requirements:
- hr:read - View designations
- hr:write - Create, update, delete designations

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
    DesignationFilters,
    DesignationCreateData,
    DesignationUpdateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import DesignationNotFoundError, ValidationError as HRValidationError
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/designations", tags=["hr-designations"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def designations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Designations list page."""
    service = OrganizationService(db, user)

    filters = DesignationFilters(search=q) if q else DesignationFilters()
    offset = (page - 1) * per_page
    pagination = PaginationParams(offset=offset, limit=per_page)

    result = service.list_designations(filters, pagination)
    designations = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["designations"] = designations
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/designations/partials/designations_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Designations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Designations"},
    ])

    template = templates.get_template("modules/hr/templates/designations/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def designation_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New designation form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Designation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Designations", "href": "/hr/designations"},
        {"label": "New Designation"},
    ])
    context["designation"] = None
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/designations/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def designation_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new designation."""
    service = OrganizationService(db, user)
    form = await request.form()

    errors = {}
    designation_name = _form_str(form, "designation_name")
    description = _form_str(form, "description")

    if not designation_name:
        errors["designation_name"] = "Designation name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Designation"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Designations", "href": "/hr/designations"},
            {"label": "New Designation"},
        ])
        context["designation"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/designations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = DesignationCreateData(
            designation_name=designation_name,
            description=description or None,
        )
        designation = service.create_designation(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["designation_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Designation"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Designations", "href": "/hr/designations"},
            {"label": "New Designation"},
        ])
        context["designation"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/designations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Designation created successfully.", "success")
    return RedirectResponse(url=f"/hr/designations/{designation.id}", status_code=303)


@router.get("/{designation_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def designation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    designation_id: int,
):
    """Designation detail page."""
    service = OrganizationService(db, user)

    try:
        designation = service.get_designation(designation_id)
    except DesignationNotFoundError:
        raise HTTPException(status_code=404, detail="Designation not found")

    headcount = service.get_designation_headcount(designation_id)
    employee_count = headcount.total_employees

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = designation.designation_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Designations", "href": "/hr/designations"},
        {"label": designation.designation_name},
    ])
    context["designation"] = designation
    context["employee_count"] = employee_count

    template = templates.get_template("modules/hr/templates/designations/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{designation_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def designation_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    designation_id: int,
):
    """Edit designation form."""
    service = OrganizationService(db, user)

    try:
        designation = service.get_designation(designation_id)
    except DesignationNotFoundError:
        raise HTTPException(status_code=404, detail="Designation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {designation.designation_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Designations", "href": "/hr/designations"},
        {"label": designation.designation_name, "href": f"/hr/designations/{designation.id}"},
        {"label": "Edit"},
    ])
    context["designation"] = designation
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/designations/pages/form.html")
    return HTMLResponse(template.render(context))


@router.put("/{designation_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def designation_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    designation_id: int,
):
    """Update a designation."""
    service = OrganizationService(db, user)

    try:
        designation = service.get_designation(designation_id)
    except DesignationNotFoundError:
        raise HTTPException(status_code=404, detail="Designation not found")

    form = await request.form()
    errors = {}

    designation_name = _form_str(form, "designation_name")
    description = _form_str(form, "description")

    if not designation_name:
        errors["designation_name"] = "Designation name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {designation.designation_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Designations", "href": "/hr/designations"},
            {"label": designation.designation_name, "href": f"/hr/designations/{designation.id}"},
            {"label": "Edit"},
        ])
        context["designation"] = designation
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/designations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = DesignationUpdateData(
            designation_name=designation_name,
            description=description or None,
        )
        designation = service.update_designation(designation_id, data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["designation_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {designation.designation_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Designations", "href": "/hr/designations"},
            {"label": designation.designation_name, "href": f"/hr/designations/{designation.id}"},
            {"label": "Edit"},
        ])
        context["designation"] = designation
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/designations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Designation updated successfully.", "success")
    return RedirectResponse(url=f"/hr/designations/{designation.id}", status_code=303)


@router.delete("/{designation_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def designation_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    designation_id: int,
):
    """Delete a designation."""
    service = OrganizationService(db, user)

    try:
        designation = service.get_designation(designation_id)
    except DesignationNotFoundError:
        raise HTTPException(status_code=404, detail="Designation not found")

    try:
        service.delete_designation(designation_id)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail=str(e))

    if is_htmx_request(request):
        htmx_toast(response, "Designation deleted.", "success")
        response.headers["HX-Redirect"] = "/hr/designations"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Designation deleted.", "success")
    return RedirectResponse(url="/hr/designations", status_code=303)

"""
HR Salary Components Routes - Salary Component Management with SSR + HTMX.

Permission Requirements:
- hr:read - View salary components
- hr:write - Create, update, delete salary components

Uses PayrollService for all business logic.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Any

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.services.hr.payroll import PayrollService
from app.services.hr.payroll_types import SalaryComponentCreateData, SalaryComponentUpdateData
from app.services.hr.errors import SalaryComponentNotFoundError, ValidationError as HRValidationError
from app.models.hr_payroll import SalaryComponentType
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/payroll/components", tags=["hr-salary-components"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_bool(form: Any, key: str) -> bool:
    value = form.get(key)
    return value == "on" or value == "true" or value == "1"


def _form_decimal(form: Any, key: str, default: Decimal = Decimal("0")) -> Decimal:
    value = _form_str(form, key)
    if not value:
        return default
    try:
        return Decimal(value)
    except Exception:
        return default


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_components_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    component_type: Optional[str] = Query(None),
    include_disabled: bool = Query(False),
):
    """Salary components list page."""
    service = PayrollService(db, user)

    # Convert type filter
    type_filter = None
    if component_type:
        try:
            type_filter = SalaryComponentType(component_type)
        except ValueError:
            pass

    components = service.list_salary_components(
        component_type=type_filter,
        include_disabled=include_disabled,
    )

    # Filter by search if provided
    if q:
        q_lower = q.lower()
        components = [c for c in components if q_lower in c.salary_component_name.lower()]

    context = get_base_context(request, response, user, csrf_token)
    context["components"] = components
    context["search_query"] = q or ""
    context["component_type"] = component_type or ""
    context["include_disabled"] = include_disabled
    context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/components/partials/components_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Salary Components"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": "Salary Components"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/components/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_component_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New salary component form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Salary Component"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": "Salary Components", "href": "/hr/payroll/components"},
        {"label": "New Component"},
    ])
    context["component"] = None
    context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_component_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new salary component."""
    service = PayrollService(db, user)
    form = await request.form()

    errors = {}
    name = _form_str(form, "salary_component_name")
    component_type_str = _form_str(form, "component_type", "earning")

    if not name:
        errors["salary_component_name"] = "Component name is required"

    try:
        component_type = SalaryComponentType(component_type_str)
    except ValueError:
        component_type = SalaryComponentType.EARNING

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Salary Component"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "Salary Components", "href": "/hr/payroll/components"},
            {"label": "New Component"},
        ])
        context["component"] = None
        context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = SalaryComponentCreateData(
            salary_component_name=name,
            salary_component_abbr=_form_str(form, "salary_component_abbr") or None,
            description=_form_str(form, "description") or None,
            component_type=component_type,
            is_tax_applicable=_form_bool(form, "is_tax_applicable"),
            is_flexible_benefit=_form_bool(form, "is_flexible_benefit"),
            depends_on_payment_days=_form_bool(form, "depends_on_payment_days"),
            is_payable=_form_bool(form, "is_payable"),
            default_amount=_form_decimal(form, "default_amount", Decimal("0")),
            formula=_form_str(form, "formula") or None,
        )
        component = service.create_salary_component(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["salary_component_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Salary Component"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "Salary Components", "href": "/hr/payroll/components"},
            {"label": "New Component"},
        ])
        context["component"] = None
        context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Salary component created successfully.", "success")
    return RedirectResponse(url=f"/hr/payroll/components/{component.id}", status_code=303)


@router.get("/{component_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_component_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    component_id: int,
):
    """Salary component detail page."""
    service = PayrollService(db, user)

    try:
        component = service.get_salary_component(component_id)
    except SalaryComponentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary component not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = component.salary_component_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": "Salary Components", "href": "/hr/payroll/components"},
        {"label": component.salary_component_name},
    ])
    context["component"] = component

    template = templates.get_template("modules/hr/templates/payroll/components/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{component_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_component_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    component_id: int,
):
    """Edit salary component form."""
    service = PayrollService(db, user)

    try:
        component = service.get_salary_component(component_id)
    except SalaryComponentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary component not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {component.salary_component_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": "Salary Components", "href": "/hr/payroll/components"},
        {"label": component.salary_component_name, "href": f"/hr/payroll/components/{component.id}"},
        {"label": "Edit"},
    ])
    context["component"] = component
    context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{component_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_component_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    component_id: int,
):
    """Update a salary component."""
    service = PayrollService(db, user)

    try:
        component = service.get_salary_component(component_id)
    except SalaryComponentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary component not found")

    form = await request.form()
    errors = {}

    name = _form_str(form, "salary_component_name")
    component_type_str = _form_str(form, "component_type", "earning")

    if not name:
        errors["salary_component_name"] = "Component name is required"

    try:
        component_type = SalaryComponentType(component_type_str)
    except ValueError:
        component_type = SalaryComponentType.EARNING

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {component.salary_component_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "Salary Components", "href": "/hr/payroll/components"},
            {"label": component.salary_component_name, "href": f"/hr/payroll/components/{component.id}"},
            {"label": "Edit"},
        ])
        context["component"] = component
        context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = SalaryComponentUpdateData(
            salary_component_name=name,
            salary_component_abbr=_form_str(form, "salary_component_abbr") or None,
            description=_form_str(form, "description") or None,
            component_type=component_type,
            is_tax_applicable=_form_bool(form, "is_tax_applicable"),
            is_flexible_benefit=_form_bool(form, "is_flexible_benefit"),
            depends_on_payment_days=_form_bool(form, "depends_on_payment_days"),
            is_payable=_form_bool(form, "is_payable"),
            default_amount=_form_decimal(form, "default_amount", Decimal("0")),
            formula=_form_str(form, "formula") or None,
        )
        component = service.update_salary_component(component_id, data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["salary_component_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {component.salary_component_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "Salary Components", "href": "/hr/payroll/components"},
            {"label": component.salary_component_name, "href": f"/hr/payroll/components/{component.id}"},
            {"label": "Edit"},
        ])
        context["component"] = component
        context["component_types"] = [("earning", "Earning"), ("deduction", "Deduction")]
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/payroll/components/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Salary component updated successfully.", "success")
    return RedirectResponse(url=f"/hr/payroll/components/{component.id}", status_code=303)


@router.delete("/{component_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_component_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    component_id: int,
):
    """Delete (disable) a salary component."""
    service = PayrollService(db, user)

    try:
        component = service.get_salary_component(component_id)
    except SalaryComponentNotFoundError:
        raise HTTPException(status_code=404, detail="Salary component not found")

    try:
        # Soft delete by disabling
        component.disabled = True
        db.commit()
    except Exception as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail=str(e))

    if is_htmx_request(request):
        htmx_toast(response, "Salary component disabled.", "success")
        response.headers["HX-Redirect"] = "/hr/payroll/components"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Salary component disabled.", "success")
    return RedirectResponse(url="/hr/payroll/components", status_code=303)

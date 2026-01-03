"""
HR Appraisal Routes - Performance Appraisal Management with SSR + HTMX.

Permission Requirements:
- hr:read - View appraisals, templates
- hr:write - Manage appraisals
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
from app.core.security import is_htmx_request, set_flash
from app.models.employee import Employee
from app.models.hr_appraisal import AppraisalTemplate, AppraisalStatus
from app.services.hr.appraisal import AppraisalService
from app.services.hr.appraisal_types import (
    AppraisalCreateData,
    AppraisalUpdateData,
    TemplateCreateData,
    TemplateUpdateData,
)
from app.services.hr.errors import (
    AppraisalNotFoundError,
    AppraisalTemplateNotFoundError,
    ValidationError,
)

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/appraisal", tags=["hr-appraisal"])
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


def get_employee_options(db):
    employees = db.query(Employee).filter(Employee.is_deleted == False).order_by(Employee.name).all()
    return [{"value": str(e.id), "label": e.name} for e in employees]


def get_template_options(db):
    templates_list = db.query(AppraisalTemplate).order_by(AppraisalTemplate.template_name).all()
    return [{"value": str(t.id), "label": t.template_name} for t in templates_list]


def _appraisal_status(value: str) -> Optional[AppraisalStatus]:
    if not value:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    try:
        return AppraisalStatus(normalized)
    except ValueError:
        return None


def _render_template_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    *,
    template: Optional[AppraisalTemplate] = None,
    errors: Optional[dict] = None,
    form_data: Optional[dict] = None,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Appraisal Template"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisals", "href": "/hr/appraisal"},
        {"label": "Templates", "href": "/hr/appraisal/templates"},
        {"label": "Template"},
    ])
    context["template"] = template
    context["errors"] = errors or {}
    context["form_data"] = form_data

    template_view = templates.get_template("modules/hr/templates/appraisal/pages/template_form.html")
    return HTMLResponse(template_view.render(context), status_code=422 if errors else 200)


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisals_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Appraisals list page."""
    try:
        from app.models.hr_appraisal import Appraisal
        query = db.query(Appraisal)
        if q:
            query = query.filter(or_(
                Appraisal.employee_name.ilike(f"%{q}%"),
                Appraisal.employee.ilike(f"%{q}%"),
            ))
        if status:
            status_enum = _appraisal_status(status)
            if status_enum:
                query = query.filter(Appraisal.status == status_enum)
        total = query.count()
        offset = (page - 1) * per_page
        appraisals = query.order_by(Appraisal.start_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        appraisals = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["appraisals"] = appraisals
    context["search_query"] = q or ""
    context["status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/appraisal/partials/appraisals_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Performance Appraisals"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisals"},
    ])

    template = templates.get_template("modules/hr/templates/appraisal/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New appraisal form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Appraisal"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisals", "href": "/hr/appraisal"},
        {"label": "New Appraisal"},
    ])
    context["appraisal"] = None
    context["employee_options"] = get_employee_options(db)
    context["template_options"] = get_template_options(db)
    context["errors"] = {}
    context["form_data"] = None

    template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
    return HTMLResponse(template.render(context))


@router.get("/{appraisal_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    appraisal_id: int,
):
    """Edit appraisal form."""
    service = AppraisalService(db, user)
    try:
        appraisal = service.get_appraisal(appraisal_id)
    except AppraisalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit - {appraisal.employee_name or 'Appraisal'}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisals", "href": "/hr/appraisal"},
        {"label": appraisal.employee_name or f"#{appraisal.id}"},
        {"label": "Edit"},
    ])
    context["appraisal"] = appraisal
    context["employee_options"] = get_employee_options(db)
    context["template_options"] = get_template_options(db)
    context["errors"] = {}
    context["form_data"] = None

    template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create an appraisal."""
    form = await request.form()
    errors: dict[str, str] = {}

    employee_id = _form_int(form, "employee_id")
    template_id = _form_int(form, "appraisal_template")
    start_date = _form_date(form, "start_date")
    end_date = _form_date(form, "end_date")

    if not employee_id:
        errors["employee_id"] = "Employee is required"
    if not template_id:
        errors["appraisal_template"] = "Template is required"
    if not start_date:
        errors["start_date"] = "Start date is required"
    if not end_date:
        errors["end_date"] = "End date is required"

    employee = db.query(Employee).filter(Employee.id == employee_id).first() if employee_id else None
    template_obj = (
        db.query(AppraisalTemplate).filter(AppraisalTemplate.id == template_id).first()
        if template_id
        else None
    )
    if employee_id and not employee:
        errors["employee_id"] = "Employee not found"
    if template_id and not template_obj:
        errors["appraisal_template"] = "Template not found"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Appraisal"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Appraisals", "href": "/hr/appraisal"},
            {"label": "New Appraisal"},
        ])
        context["appraisal"] = None
        context["employee_options"] = get_employee_options(db)
        context["template_options"] = get_template_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = AppraisalService(db, user)
    try:
        appraisal = service.create_appraisal(
            AppraisalCreateData(
                employee_id=employee_id,
                employee=employee.erpnext_id or str(employee.id),
                employee_name=employee.name,
                appraisal_template_id=template_id,
                appraisal_template=template_obj.template_name if template_obj else None,
                start_date=start_date,
                end_date=end_date,
                feedback=_form_str(form, "remarks") or None,
            )
        )
        db.commit()
    except (AppraisalTemplateNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["appraisal_template"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Appraisal"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Appraisals", "href": "/hr/appraisal"},
            {"label": "New Appraisal"},
        ])
        context["appraisal"] = None
        context["employee_options"] = get_employee_options(db)
        context["template_options"] = get_template_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Appraisal created successfully.", "success")
    return RedirectResponse(url=f"/hr/appraisal/{appraisal.id}", status_code=303)


@router.post("/{appraisal_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    appraisal_id: int,
):
    """Update an appraisal."""
    form = await request.form()
    errors: dict[str, str] = {}

    start_date = _form_date(form, "start_date")
    end_date = _form_date(form, "end_date")
    if not start_date:
        errors["start_date"] = "Start date is required"
    if not end_date:
        errors["end_date"] = "End date is required"

    if errors:
        service = AppraisalService(db, user)
        try:
            appraisal = service.get_appraisal(appraisal_id)
        except AppraisalNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Appraisal"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Appraisals", "href": "/hr/appraisal"},
            {"label": appraisal.employee_name or f"#{appraisal.id}"},
            {"label": "Edit"},
        ])
        context["appraisal"] = appraisal
        context["employee_options"] = get_employee_options(db)
        context["template_options"] = get_template_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = AppraisalService(db, user)
    try:
        appraisal = service.update_appraisal(
            appraisal_id,
            AppraisalUpdateData(
                start_date=start_date,
                end_date=end_date,
                feedback=_form_str(form, "remarks") or None,
            ),
        )
        db.commit()
    except (AppraisalNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["start_date"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Appraisal"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Appraisals", "href": "/hr/appraisal"},
            {"label": "Edit"},
        ])
        context["appraisal"] = None
        context["employee_options"] = get_employee_options(db)
        context["template_options"] = get_template_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/appraisal/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Appraisal updated successfully.", "success")
    return RedirectResponse(url=f"/hr/appraisal/{appraisal.id}", status_code=303)


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisals_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await appraisals_list(request, response, user, csrf_token, db, q, status, page, per_page)


@router.get("/templates", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisal_templates_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Appraisal templates list page."""
    try:
        from app.models.hr_appraisal import AppraisalTemplate
        query = db.query(AppraisalTemplate)
        if q:
            query = query.filter(AppraisalTemplate.template_name.ilike(f"%{q}%"))
        total = query.count()
        offset = (page - 1) * per_page
        appraisal_templates = query.order_by(AppraisalTemplate.template_name).offset(offset).limit(per_page).all()
    except Exception:
        appraisal_templates = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["appraisal_templates"] = appraisal_templates
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/appraisal/partials/templates_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Appraisal Templates"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisal Templates"},
    ])

    template = templates.get_template("modules/hr/templates/appraisal/pages/templates_list.html")
    return HTMLResponse(template.render(context))


@router.get("/templates/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_template_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New appraisal template form."""
    return _render_template_form(request, response, user, csrf_token)


@router.get("/templates/{template_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_template_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    template_id: int,
):
    """Edit appraisal template form."""
    service = AppraisalService(db, user)
    try:
        template_obj = service.get_template(template_id)
    except AppraisalTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _render_template_form(
        request,
        response,
        user,
        csrf_token,
        template=template_obj,
    )


@router.post("/templates", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_template_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create an appraisal template."""
    form = await request.form()
    errors: dict[str, str] = {}

    template_name = _form_str(form, "template_name")
    if not template_name:
        errors["template_name"] = "Template name is required"

    if errors:
        return _render_template_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    service = AppraisalService(db, user)
    try:
        service.create_template(
            TemplateCreateData(
                template_name=template_name,
                description=_form_str(form, "description") or None,
            )
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        errors["template_name"] = str(exc)
        return _render_template_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    set_flash(response, "Appraisal template created successfully.", "success")
    return RedirectResponse(url="/hr/appraisal/templates", status_code=303)


@router.post("/templates/{template_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def appraisal_template_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    template_id: int,
):
    """Update an appraisal template."""
    form = await request.form()
    errors: dict[str, str] = {}

    template_name = _form_str(form, "template_name")
    if not template_name:
        errors["template_name"] = "Template name is required"

    if errors:
        service = AppraisalService(db, user)
        try:
            template_obj = service.get_template(template_id)
        except AppraisalTemplateNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _render_template_form(
            request,
            response,
            user,
            csrf_token,
            template=template_obj,
            errors=errors,
            form_data=dict(form),
        )

    service = AppraisalService(db, user)
    try:
        service.update_template(
            template_id,
            TemplateUpdateData(
                template_name=template_name,
                description=_form_str(form, "description") or None,
            ),
        )
        db.commit()
    except (AppraisalTemplateNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["template_name"] = str(exc)
        return _render_template_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    set_flash(response, "Appraisal template updated successfully.", "success")
    return RedirectResponse(url="/hr/appraisal/templates", status_code=303)


@router.get("/{appraisal_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisal_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    appraisal_id: int,
):
    """Appraisal detail page."""
    try:
        from app.models.hr_appraisal import Appraisal
        appraisal = db.query(Appraisal).filter(Appraisal.id == appraisal_id).first()
    except Exception:
        appraisal = None

    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    employee_name = appraisal.employee_name or "Employee"
    context["page_title"] = f"Appraisal - {employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Appraisals", "href": "/hr/appraisal"},
        {"label": employee_name},
    ])
    context["appraisal"] = appraisal

    template = templates.get_template("modules/hr/templates/appraisal/pages/detail.html")
    return HTMLResponse(template.render(context))

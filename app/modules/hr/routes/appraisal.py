"""
HR Appraisal Routes - Performance Appraisal Management with SSR + HTMX.

Permission Requirements:
- hr:read - View appraisals, templates
- hr:write - Manage appraisals
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/appraisal", tags=["hr-appraisal"])
templates = get_template_env()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisals_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
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
        total = query.count()
        offset = (page - 1) * per_page
        appraisals = query.order_by(Appraisal.start_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        appraisals = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["appraisals"] = appraisals
    context["search_query"] = q or ""
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


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def appraisals_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await appraisals_list(request, response, user, csrf_token, db, q, page, per_page)


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

"""
HR Payroll Routes - Payroll Management with SSR + HTMX.

Permission Requirements:
- hr:read - View salary slips, structures, payroll runs
- hr:write - Process payroll
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

router = APIRouter(prefix="/payroll", tags=["hr-payroll"])
templates = get_template_env()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Salary slips list page."""
    # Import here to avoid circular imports
    try:
        from app.models.hr_payroll import SalarySlip
        query = db.query(SalarySlip)
        if q:
            query = query.filter(or_(
                SalarySlip.employee_name.ilike(f"%{q}%"),
                SalarySlip.employee.ilike(f"%{q}%"),
            ))
        total = query.count()
        offset = (page - 1) * per_page
        slips = query.order_by(SalarySlip.posting_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        slips = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["slips"] = slips
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/slips_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Salary Slips"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await payroll_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/structures", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_structures_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Salary structures list page."""
    try:
        from app.models.hr_payroll import SalaryStructure
        query = db.query(SalaryStructure)
        if q:
            query = query.filter(SalaryStructure.salary_structure_name.ilike(f"%{q}%"))
        total = query.count()
        offset = (page - 1) * per_page
        structures = query.order_by(SalaryStructure.salary_structure_name).offset(offset).limit(per_page).all()
    except Exception:
        structures = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["structures"] = structures
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/structures_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Salary Structures"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Salary Structures"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/structures_list.html")
    return HTMLResponse(template.render(context))


@router.get("/runs", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_runs_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payroll runs list page."""
    try:
        from app.models.hr_payroll import PayrollEntry
        query = db.query(PayrollEntry)
        total = query.count()
        offset = (page - 1) * per_page
        runs = query.order_by(PayrollEntry.posting_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        runs = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["runs"] = runs
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/runs_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Payroll Runs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll Runs"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/runs_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{slip_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_slip_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    slip_id: int,
):
    """Salary slip detail page."""
    try:
        from app.models.hr_payroll import SalarySlip
        slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    except Exception:
        slip = None

    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Salary Slip - {slip.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": f"Slip #{slip.id}"},
    ])
    context["slip"] = slip

    template = templates.get_template("modules/hr/templates/payroll/pages/detail.html")
    return HTMLResponse(template.render(context))

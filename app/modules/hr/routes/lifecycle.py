"""
HR Lifecycle Routes - Onboarding, Separation, Promotion, Transfer with SSR + HTMX.

Permission Requirements:
- hr:read - View lifecycle events
- hr:write - Create, update, manage lifecycle events
"""
from __future__ import annotations

from typing import Optional
from datetime import date

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
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
from app.models.employee import Employee
from app.models.hr import Department, Designation
from app.models.hr_lifecycle import (
    EmployeeOnboarding,
    EmployeeSeparation,
    EmployeePromotion,
    EmployeeTransfer,
    BoardingStatus,
)
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/lifecycle", tags=["hr-lifecycle"])
templates = get_template_env()


def get_boarding_status_options():
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in BoardingStatus
    ]


def get_employee_options(db):
    employees = db.query(Employee).filter(Employee.is_deleted == False).order_by(Employee.name).all()
    return [{"value": str(e.id), "label": e.name} for e in employees]


def get_department_options(db):
    departments = db.query(Department).order_by(Department.department_name).all()
    return [{"value": str(d.id), "label": d.department_name} for d in departments]


def get_designation_options(db):
    designations = db.query(Designation).order_by(Designation.designation_name).all()
    return [{"value": str(d.id), "label": d.designation_name} for d in designations]


# =============================================================================
# ONBOARDING
# =============================================================================

@router.get("/onboarding", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def onboarding_list(
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
    """Onboarding list page."""
    query = db.query(EmployeeOnboarding)

    if q:
        query = query.filter(or_(
            EmployeeOnboarding.employee_name.ilike(f"%{q}%"),
            EmployeeOnboarding.employee.ilike(f"%{q}%"),
        ))

    if status:
        query = query.filter(EmployeeOnboarding.boarding_status == status)

    total = query.count()
    offset = (page - 1) * per_page
    onboardings = query.order_by(EmployeeOnboarding.date_of_joining.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["onboardings"] = onboardings
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_boarding_status_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/onboarding_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Onboarding"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Onboarding"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/onboarding_list.html")
    return HTMLResponse(template.render(context))


@router.get("/onboarding/{onboarding_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def onboarding_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    onboarding_id: int,
):
    """Onboarding detail page."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()

    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Onboarding - {onboarding.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Onboarding", "href": "/hr/lifecycle/onboarding"},
        {"label": onboarding.employee_name or f"#{onboarding.id}"},
    ])
    context["onboarding"] = onboarding

    template = templates.get_template("modules/hr/templates/lifecycle/pages/onboarding_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/onboarding/{onboarding_id}/start", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def onboarding_start(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    onboarding_id: int,
):
    """Start the onboarding process."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    onboarding.boarding_status = BoardingStatus.IN_PROGRESS
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Onboarding started.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/onboarding/{onboarding_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Onboarding started.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/onboarding/{onboarding_id}", status_code=303)


@router.post("/onboarding/{onboarding_id}/complete", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def onboarding_complete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    onboarding_id: int,
):
    """Complete the onboarding process."""
    onboarding = db.query(EmployeeOnboarding).filter(EmployeeOnboarding.id == onboarding_id).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    onboarding.boarding_status = BoardingStatus.COMPLETED
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Onboarding completed.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/onboarding/{onboarding_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Onboarding completed.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/onboarding/{onboarding_id}", status_code=303)


# =============================================================================
# SEPARATION
# =============================================================================

@router.get("/separation", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def separation_list(
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
    """Separation list page."""
    query = db.query(EmployeeSeparation)

    if q:
        query = query.filter(or_(
            EmployeeSeparation.employee_name.ilike(f"%{q}%"),
            EmployeeSeparation.employee.ilike(f"%{q}%"),
        ))

    if status:
        query = query.filter(EmployeeSeparation.boarding_status == status)

    total = query.count()
    offset = (page - 1) * per_page
    separations = query.order_by(EmployeeSeparation.separation_date.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["separations"] = separations
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_boarding_status_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/separation_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Separation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Separation"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/separation_list.html")
    return HTMLResponse(template.render(context))


@router.get("/separation/{separation_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def separation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    separation_id: int,
):
    """Separation detail page."""
    separation = db.query(EmployeeSeparation).filter(EmployeeSeparation.id == separation_id).first()

    if not separation:
        raise HTTPException(status_code=404, detail="Separation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Separation - {separation.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Separation", "href": "/hr/lifecycle/separation"},
        {"label": separation.employee_name or f"#{separation.id}"},
    ])
    context["separation"] = separation

    template = templates.get_template("modules/hr/templates/lifecycle/pages/separation_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# PROMOTIONS
# =============================================================================

@router.get("/promotions", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def promotions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Promotions list page."""
    query = db.query(EmployeePromotion)

    if q:
        query = query.filter(or_(
            EmployeePromotion.employee_name.ilike(f"%{q}%"),
            EmployeePromotion.employee.ilike(f"%{q}%"),
        ))

    total = query.count()
    offset = (page - 1) * per_page
    promotions = query.order_by(EmployeePromotion.promotion_date.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["promotions"] = promotions
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/promotions_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Promotions"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Promotions"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/promotions_list.html")
    return HTMLResponse(template.render(context))


@router.get("/promotions/{promotion_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def promotion_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    promotion_id: int,
):
    """Promotion detail page."""
    promotion = db.query(EmployeePromotion).filter(EmployeePromotion.id == promotion_id).first()

    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Promotion - {promotion.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Promotions", "href": "/hr/lifecycle/promotions"},
        {"label": promotion.employee_name or f"#{promotion.id}"},
    ])
    context["promotion"] = promotion

    template = templates.get_template("modules/hr/templates/lifecycle/pages/promotion_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TRANSFERS
# =============================================================================

@router.get("/transfers", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def transfers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Transfers list page."""
    query = db.query(EmployeeTransfer)

    if q:
        query = query.filter(or_(
            EmployeeTransfer.employee_name.ilike(f"%{q}%"),
            EmployeeTransfer.employee.ilike(f"%{q}%"),
        ))

    total = query.count()
    offset = (page - 1) * per_page
    transfers = query.order_by(EmployeeTransfer.transfer_date.desc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["transfers"] = transfers
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/transfers_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Transfers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Transfers"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/transfers_list.html")
    return HTMLResponse(template.render(context))


@router.get("/transfers/{transfer_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def transfer_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    transfer_id: int,
):
    """Transfer detail page."""
    transfer = db.query(EmployeeTransfer).filter(EmployeeTransfer.id == transfer_id).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Transfer - {transfer.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Transfers", "href": "/hr/lifecycle/transfers"},
        {"label": transfer.employee_name or f"#{transfer.id}"},
    ])
    context["transfer"] = transfer

    template = templates.get_template("modules/hr/templates/lifecycle/pages/transfer_detail.html")
    return HTMLResponse(template.render(context))

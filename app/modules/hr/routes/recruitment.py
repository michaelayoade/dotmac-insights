"""
HR Recruitment Routes - Recruitment Management with SSR + HTMX.

Permission Requirements:
- hr:read - View job openings, applicants, offers, interviews
- hr:write - Manage recruitment
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

router = APIRouter(prefix="/recruitment", tags=["hr-recruitment"])
templates = get_template_env()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_openings_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job openings list page."""
    try:
        from app.models.hr_recruitment import JobOpening
        query = db.query(JobOpening)
        if q:
            query = query.filter(or_(
                JobOpening.job_title.ilike(f"%{q}%"),
                JobOpening.designation.ilike(f"%{q}%"),
            ))
        total = query.count()
        offset = (page - 1) * per_page
        openings = query.order_by(JobOpening.created_at.desc()).offset(offset).limit(per_page).all()
    except Exception:
        openings = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["openings"] = openings
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/openings_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Openings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_openings_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await job_openings_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/applicants", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def applicants_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job applicants list page."""
    try:
        from app.models.hr_recruitment import JobApplicant
        query = db.query(JobApplicant)
        if q:
            query = query.filter(or_(
                JobApplicant.applicant_name.ilike(f"%{q}%"),
                JobApplicant.email_id.ilike(f"%{q}%"),
            ))
        total = query.count()
        offset = (page - 1) * per_page
        applicants = query.order_by(JobApplicant.created_at.desc()).offset(offset).limit(per_page).all()
    except Exception:
        applicants = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["applicants"] = applicants
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/applicants_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Applicants"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Applicants"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/applicants_list.html")
    return HTMLResponse(template.render(context))


@router.get("/offers", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def offers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job offers list page."""
    try:
        from app.models.hr_recruitment import JobOffer
        query = db.query(JobOffer)
        if q:
            query = query.filter(or_(
                JobOffer.applicant_name.ilike(f"%{q}%"),
                JobOffer.designation.ilike(f"%{q}%"),
            ))
        total = query.count()
        offset = (page - 1) * per_page
        offers = query.order_by(JobOffer.offer_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        offers = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["offers"] = offers
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/offers_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Offers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Job Offers"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/offers_list.html")
    return HTMLResponse(template.render(context))


@router.get("/interviews", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def interviews_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Interviews list page."""
    try:
        from app.models.hr_recruitment import Interview
        query = db.query(Interview)
        total = query.count()
        offset = (page - 1) * per_page
        interviews = query.order_by(Interview.scheduled_date.desc()).offset(offset).limit(per_page).all()
    except Exception:
        interviews = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["interviews"] = interviews
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/interviews_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Interviews"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Interviews"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/interviews_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{opening_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_opening_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opening_id: int,
):
    """Job opening detail page."""
    try:
        from app.models.hr_recruitment import JobOpening
        opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    except Exception:
        opening = None

    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = opening.job_title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": opening.job_title},
    ])
    context["opening"] = opening

    template = templates.get_template("modules/hr/templates/recruitment/pages/detail.html")
    return HTMLResponse(template.render(context))

"""
HR Training Routes - Training Management with SSR + HTMX.

Permission Requirements:
- hr:read - View training programs, events, results
- hr:write - Manage training
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

router = APIRouter(prefix="/training", tags=["hr-training"])
templates = get_template_env()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_events_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Training events list page."""
    try:
        from app.models.hr_training import TrainingEvent
        query = db.query(TrainingEvent)
        if q:
            query = query.filter(or_(
                TrainingEvent.event_name.ilike(f"%{q}%"),
                TrainingEvent.course.ilike(f"%{q}%"),
            ))
        total = query.count()
        offset = (page - 1) * per_page
        events = query.order_by(TrainingEvent.start_time.desc()).offset(offset).limit(per_page).all()
    except Exception:
        events = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["events"] = events
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/training/partials/events_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Training Events"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training"},
    ])

    template = templates.get_template("modules/hr/templates/training/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_events_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await training_events_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/programs", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_programs_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Training programs list page."""
    try:
        from app.models.hr_training import TrainingProgram
        query = db.query(TrainingProgram)
        if q:
            query = query.filter(TrainingProgram.training_program_name.ilike(f"%{q}%"))
        total = query.count()
        offset = (page - 1) * per_page
        programs = query.order_by(TrainingProgram.training_program_name).offset(offset).limit(per_page).all()
    except Exception:
        programs = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["programs"] = programs
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/training/partials/programs_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Training Programs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training Programs"},
    ])

    template = templates.get_template("modules/hr/templates/training/pages/programs_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{event_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_event_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    event_id: int,
):
    """Training event detail page."""
    try:
        from app.models.hr_training import TrainingEvent
        event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    except Exception:
        event = None

    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = event.event_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training", "href": "/hr/training"},
        {"label": event.event_name},
    ])
    context["event"] = event

    template = templates.get_template("modules/hr/templates/training/pages/detail.html")
    return HTMLResponse(template.render(context))

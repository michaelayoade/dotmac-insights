"""
HR Training Routes - Training Management with SSR + HTMX.

Permission Requirements:
- hr:read - View training programs, events, results
- hr:write - Manage training
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime

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
from app.models.hr_training import TrainingProgram, TrainingEventStatus
from app.services.hr.training import TrainingService
from app.services.hr.training_types import (
    TrainingEventCreateData,
    TrainingEventUpdateData,
    TrainingProgramCreateData,
    TrainingProgramUpdateData,
)
from app.services.hr.errors import (
    TrainingEventNotFoundError,
    TrainingProgramNotFoundError,
    ValidationError,
)

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/training", tags=["hr-training"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_datetime(form: Any, key: str) -> Optional[datetime]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _form_int(form: Any, key: str) -> Optional[int]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_program_options(db):
    programs = db.query(TrainingProgram).order_by(TrainingProgram.training_program_name).all()
    return [{"value": str(p.id), "label": p.training_program_name} for p in programs]


def _training_status(value: str) -> Optional[TrainingEventStatus]:
    if not value:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    try:
        return TrainingEventStatus(normalized)
    except ValueError:
        return None


def _render_program_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    *,
    program: Optional[TrainingProgram] = None,
    errors: Optional[dict] = None,
    form_data: Optional[dict] = None,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Training Program"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training", "href": "/hr/training"},
        {"label": "Programs", "href": "/hr/training/programs"},
        {"label": "Program"},
    ])
    context["program"] = program
    context["errors"] = errors or {}
    context["form_data"] = form_data

    template = templates.get_template("modules/hr/templates/training/pages/program_form.html")
    return HTMLResponse(template.render(context), status_code=422 if errors else 200)


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_events_list(
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
    """Training events list page."""
    try:
        from app.models.hr_training import TrainingEvent
        query = db.query(TrainingEvent)
        if q:
            query = query.filter(or_(
                TrainingEvent.event_name.ilike(f"%{q}%"),
                TrainingEvent.course.ilike(f"%{q}%"),
            ))
        if status:
            status_enum = _training_status(status)
            if status_enum:
                query = query.filter(TrainingEvent.status == status_enum)
        total = query.count()
        offset = (page - 1) * per_page
        events = query.order_by(TrainingEvent.start_time.desc()).offset(offset).limit(per_page).all()
    except Exception:
        events = []
        total = 0

    context = get_base_context(request, response, user, csrf_token)
    context["events"] = events
    context["search_query"] = q or ""
    context["status"] = status
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


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_event_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New training event form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Training Event"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training", "href": "/hr/training"},
        {"label": "New Event"},
    ])
    context["event"] = None
    context["program_options"] = get_program_options(db)
    context["errors"] = {}
    context["form_data"] = None

    template = templates.get_template("modules/hr/templates/training/pages/form.html")
    return HTMLResponse(template.render(context))


@router.get("/{event_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_event_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    event_id: int,
):
    """Edit training event form."""
    service = TrainingService(db, user)
    try:
        event = service.get_event(event_id)
    except TrainingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit - {event.event_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training", "href": "/hr/training"},
        {"label": event.event_name},
        {"label": "Edit"},
    ])
    context["event"] = event
    context["program_options"] = get_program_options(db)
    context["errors"] = {}
    context["form_data"] = None

    template = templates.get_template("modules/hr/templates/training/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_event_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create a training event."""
    form = await request.form()
    errors: dict[str, str] = {}

    event_name = _form_str(form, "event_name")
    if not event_name:
        errors["event_name"] = "Event name is required"

    start_time = _form_datetime(form, "start_time")
    end_time = _form_datetime(form, "end_time")
    if not start_time:
        errors["start_time"] = "Start time is required"
    if not end_time:
        errors["end_time"] = "End time is required"

    program_id = _form_int(form, "training_program")
    program = None
    if program_id:
        program = db.query(TrainingProgram).filter(TrainingProgram.id == program_id).first()
        if not program:
            errors["training_program"] = "Training program not found"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Training Event"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Training", "href": "/hr/training"},
            {"label": "New Event"},
        ])
        context["event"] = None
        context["program_options"] = get_program_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/training/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = TrainingService(db, user)
    try:
        event = service.create_event(
            TrainingEventCreateData(
                event_name=event_name,
                training_program_id=program.id if program else None,
                training_program=program.training_program_name if program else None,
                type=_form_str(form, "type") or None,
                level=_form_str(form, "level") or None,
                trainer_name=_form_str(form, "trainer_name") or None,
                start_time=start_time,
                end_time=end_time,
                location=_form_str(form, "location") or None,
                introduction=_form_str(form, "introduction") or None,
            )
        )
        db.commit()
    except (TrainingProgramNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["event_name"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Training Event"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Training", "href": "/hr/training"},
            {"label": "New Event"},
        ])
        context["event"] = None
        context["program_options"] = get_program_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/training/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Training event created successfully.", "success")
    return RedirectResponse(url=f"/hr/training/{event.id}", status_code=303)


@router.post("/{event_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_event_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    event_id: int,
):
    """Update a training event."""
    form = await request.form()
    errors: dict[str, str] = {}

    event_name = _form_str(form, "event_name")
    if not event_name:
        errors["event_name"] = "Event name is required"

    start_time = _form_datetime(form, "start_time")
    end_time = _form_datetime(form, "end_time")
    if not start_time:
        errors["start_time"] = "Start time is required"
    if not end_time:
        errors["end_time"] = "End time is required"

    program_id = _form_int(form, "training_program")
    program = None
    if program_id:
        program = db.query(TrainingProgram).filter(TrainingProgram.id == program_id).first()
        if not program:
            errors["training_program"] = "Training program not found"

    if errors:
        service = TrainingService(db, user)
        try:
            event = service.get_event(event_id)
        except TrainingEventNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit - {event.event_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Training", "href": "/hr/training"},
            {"label": event.event_name},
            {"label": "Edit"},
        ])
        context["event"] = event
        context["program_options"] = get_program_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/training/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = TrainingService(db, user)
    try:
        event = service.update_event(
            event_id,
            TrainingEventUpdateData(
                event_name=event_name,
                training_program_id=program.id if program else None,
                training_program=program.training_program_name if program else None,
                type=_form_str(form, "type") or None,
                level=_form_str(form, "level") or None,
                trainer_name=_form_str(form, "trainer_name") or None,
                start_time=start_time,
                end_time=end_time,
                location=_form_str(form, "location") or None,
                introduction=_form_str(form, "introduction") or None,
            ),
        )
        db.commit()
    except (TrainingEventNotFoundError, TrainingProgramNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["event_name"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Training Event"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Training", "href": "/hr/training"},
            {"label": "Edit Event"},
        ])
        context["event"] = None
        context["program_options"] = get_program_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)
        template = templates.get_template("modules/hr/templates/training/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Training event updated successfully.", "success")
    return RedirectResponse(url=f"/hr/training/{event.id}", status_code=303)
@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def training_events_table(
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
    return await training_events_list(request, response, user, csrf_token, db, q, status, page, per_page)


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


@router.get("/programs/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_program_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New training program form."""
    return _render_program_form(request, response, user, csrf_token)


@router.get("/programs/{program_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_program_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    program_id: int,
):
    """Edit training program form."""
    service = TrainingService(db, user)
    try:
        program = service.get_program(program_id)
    except TrainingProgramNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _render_program_form(request, response, user, csrf_token, program=program)


@router.post("/programs", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_program_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create a training program."""
    form = await request.form()
    errors: dict[str, str] = {}

    name = _form_str(form, "training_program_name")
    if not name:
        errors["training_program_name"] = "Program name is required"

    if errors:
        return _render_program_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    service = TrainingService(db, user)
    try:
        program = service.create_program(
            TrainingProgramCreateData(
                training_program_name=name,
                description=_form_str(form, "description") or None,
                trainer_name=_form_str(form, "trainer_name") or None,
                trainer_email=_form_str(form, "trainer_email") or None,
                supplier=_form_str(form, "supplier") or None,
            )
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        errors["training_program_name"] = str(exc)
        return _render_program_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    set_flash(response, "Training program created successfully.", "success")
    return RedirectResponse(url="/hr/training/programs", status_code=303)


@router.post("/programs/{program_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def training_program_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    program_id: int,
):
    """Update a training program."""
    form = await request.form()
    errors: dict[str, str] = {}

    name = _form_str(form, "training_program_name")
    if not name:
        errors["training_program_name"] = "Program name is required"

    if errors:
        service = TrainingService(db, user)
        try:
            program = service.get_program(program_id)
        except TrainingProgramNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _render_program_form(
            request,
            response,
            user,
            csrf_token,
            program=program,
            errors=errors,
            form_data=dict(form),
        )

    service = TrainingService(db, user)
    try:
        service.update_program(
            program_id,
            TrainingProgramUpdateData(
                training_program_name=name,
                description=_form_str(form, "description") or None,
                trainer_name=_form_str(form, "trainer_name") or None,
                trainer_email=_form_str(form, "trainer_email") or None,
                supplier=_form_str(form, "supplier") or None,
            ),
        )
        db.commit()
    except (TrainingProgramNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["training_program_name"] = str(exc)
        return _render_program_form(
            request,
            response,
            user,
            csrf_token,
            errors=errors,
            form_data=dict(form),
        )

    set_flash(response, "Training program updated successfully.", "success")
    return RedirectResponse(url="/hr/training/programs", status_code=303)


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
    service = TrainingService(db, user)
    try:
        event = service.get_event(event_id)
    except TrainingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = event.event_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Training", "href": "/hr/training"},
        {"label": event.event_name},
    ])
    context["event"] = event
    context["employees"] = event.employees

    template = templates.get_template("modules/hr/templates/training/pages/detail.html")
    return HTMLResponse(template.render(context))

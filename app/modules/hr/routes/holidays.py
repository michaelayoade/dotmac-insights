"""
HR Holiday Routes - Holiday Lists with SSR + HTMX.

Permission Requirements:
- hr:read - View holiday lists
- hr:write - Create, update, delete holiday lists
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import date

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
from app.models.hr_leave import HolidayList, Holiday
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/holidays", tags=["hr-holidays"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def holiday_lists(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Holiday lists page."""
    query = db.query(HolidayList)

    if q:
        query = query.filter(HolidayList.holiday_list_name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * per_page
    holiday_lists = query.order_by(HolidayList.holiday_list_name).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["holiday_lists"] = holiday_lists
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/holidays/partials/holiday_lists_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Holiday Lists"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Holiday Lists"},
    ])

    template = templates.get_template("modules/hr/templates/holidays/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def holiday_list_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New holiday list form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Holiday List"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Holiday Lists", "href": "/hr/holidays"},
        {"label": "New Holiday List"},
    ])
    context["holiday_list"] = None
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/holidays/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def holiday_list_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new holiday list."""
    form = await request.form()

    errors = {}
    holiday_list_name = _form_str(form, "holiday_list_name")
    from_date_str = _form_str(form, "from_date")
    to_date_str = _form_str(form, "to_date")

    if not holiday_list_name:
        errors["holiday_list_name"] = "Holiday list name is required"

    from_date = None
    to_date = None
    if from_date_str:
        try:
            from_date = date.fromisoformat(from_date_str)
        except ValueError:
            errors["from_date"] = "Invalid date format"
    if to_date_str:
        try:
            to_date = date.fromisoformat(to_date_str)
        except ValueError:
            errors["to_date"] = "Invalid date format"

    # Check for duplicates
    existing = db.query(HolidayList).filter(
        HolidayList.holiday_list_name == holiday_list_name
    ).first()
    if existing:
        errors["holiday_list_name"] = "A holiday list with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Holiday List"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Holiday Lists", "href": "/hr/holidays"},
            {"label": "New Holiday List"},
        ])
        context["holiday_list"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/holidays/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    holiday_list = HolidayList(
        holiday_list_name=holiday_list_name,
        from_date=from_date,
        to_date=to_date,
        total_holidays=0,
    )
    db.add(holiday_list)
    db.commit()
    db.refresh(holiday_list)

    set_flash(response, "Holiday list created successfully.", "success")
    return RedirectResponse(url=f"/hr/holidays/{holiday_list.id}", status_code=303)


@router.get("/{list_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def holiday_list_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    list_id: int,
):
    """Holiday list detail page."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    # Get holidays
    holidays = db.query(Holiday).filter(Holiday.holiday_list_id == list_id).order_by(Holiday.holiday_date).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = holiday_list.holiday_list_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Holiday Lists", "href": "/hr/holidays"},
        {"label": holiday_list.holiday_list_name},
    ])
    context["holiday_list"] = holiday_list
    context["holidays"] = holidays

    template = templates.get_template("modules/hr/templates/holidays/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{list_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def holiday_list_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    list_id: int,
):
    """Edit holiday list form."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {holiday_list.holiday_list_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Holiday Lists", "href": "/hr/holidays"},
        {"label": holiday_list.holiday_list_name, "href": f"/hr/holidays/{holiday_list.id}"},
        {"label": "Edit"},
    ])
    context["holiday_list"] = holiday_list
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/holidays/pages/form.html")
    return HTMLResponse(template.render(context))


@router.put("/{list_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def holiday_list_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    list_id: int,
):
    """Update a holiday list."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    form = await request.form()
    errors = {}

    holiday_list_name = _form_str(form, "holiday_list_name")
    from_date_str = _form_str(form, "from_date")
    to_date_str = _form_str(form, "to_date")

    if not holiday_list_name:
        errors["holiday_list_name"] = "Holiday list name is required"

    from_date = None
    to_date = None
    if from_date_str:
        try:
            from_date = date.fromisoformat(from_date_str)
        except ValueError:
            errors["from_date"] = "Invalid date format"
    if to_date_str:
        try:
            to_date = date.fromisoformat(to_date_str)
        except ValueError:
            errors["to_date"] = "Invalid date format"

    # Check for duplicates (excluding self)
    existing = db.query(HolidayList).filter(
        HolidayList.holiday_list_name == holiday_list_name,
        HolidayList.id != list_id
    ).first()
    if existing:
        errors["holiday_list_name"] = "A holiday list with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {holiday_list.holiday_list_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Holiday Lists", "href": "/hr/holidays"},
            {"label": holiday_list.holiday_list_name, "href": f"/hr/holidays/{holiday_list.id}"},
            {"label": "Edit"},
        ])
        context["holiday_list"] = holiday_list
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/holidays/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    holiday_list.holiday_list_name = holiday_list_name
    holiday_list.from_date = from_date
    holiday_list.to_date = to_date
    db.commit()

    set_flash(response, "Holiday list updated successfully.", "success")
    return RedirectResponse(url=f"/hr/holidays/{holiday_list.id}", status_code=303)


@router.delete("/{list_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def holiday_list_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    list_id: int,
):
    """Delete a holiday list."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    # Delete associated holidays
    db.query(Holiday).filter(Holiday.holiday_list_id == list_id).delete()
    db.delete(holiday_list)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Holiday list deleted.", "success")
        response.headers["HX-Redirect"] = "/hr/holidays"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Holiday list deleted.", "success")
    return RedirectResponse(url="/hr/holidays", status_code=303)


# =============================================================================
# INDIVIDUAL HOLIDAYS
# =============================================================================

@router.post("/{list_id}/holidays", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def add_holiday(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    list_id: int,
):
    """Add a holiday to the list."""
    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    if not holiday_list:
        raise HTTPException(status_code=404, detail="Holiday list not found")

    form = await request.form()
    holiday_date_str = _form_str(form, "holiday_date")
    description = _form_str(form, "description")

    if not holiday_date_str:
        if is_htmx_request(request):
            htmx_toast(response, "Holiday date is required.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="Holiday date is required")

    try:
        holiday_date = date.fromisoformat(holiday_date_str)
    except ValueError:
        if is_htmx_request(request):
            htmx_toast(response, "Invalid date format.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="Invalid date format")

    holiday = Holiday(
        holiday_list_id=list_id,
        holiday_date=holiday_date,
        description=description or None,
    )
    db.add(holiday)

    # Update total holidays count
    holiday_list.total_holidays = (holiday_list.total_holidays or 0) + 1
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Holiday added.", "success")
        response.headers["HX-Redirect"] = f"/hr/holidays/{list_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Holiday added.", "success")
    return RedirectResponse(url=f"/hr/holidays/{list_id}", status_code=303)


@router.delete("/{list_id}/holidays/{holiday_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def remove_holiday(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    list_id: int,
    holiday_id: int,
):
    """Remove a holiday from the list."""
    holiday = db.query(Holiday).filter(
        Holiday.id == holiday_id,
        Holiday.holiday_list_id == list_id
    ).first()

    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    holiday_list = db.query(HolidayList).filter(HolidayList.id == list_id).first()

    db.delete(holiday)

    # Update total holidays count
    if holiday_list and holiday_list.total_holidays:
        holiday_list.total_holidays = max(0, holiday_list.total_holidays - 1)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Holiday removed.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Holiday removed.", "success")
    return RedirectResponse(url=f"/hr/holidays/{list_id}", status_code=303)

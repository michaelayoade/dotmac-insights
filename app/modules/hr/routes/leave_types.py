"""
HR Leave Types Routes - Leave Type Management with SSR + HTMX.

Permission Requirements:
- hr:read - View leave types
- hr:write - Create, update, delete leave types

Uses LeaveService for all business logic.
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
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import LeaveTypeCreateData, LeaveTypeUpdateData
from app.services.hr.errors import LeaveTypeNotFoundError, ValidationError as HRValidationError
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/leave/types", tags=["hr-leave-types"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int = 0) -> int:
    value = _form_str(form, key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


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
async def leave_types_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
):
    """Leave types list page."""
    service = LeaveService(db, user)

    leave_types = service.list_leave_types(include_inactive=include_inactive)

    # Filter by search if provided
    if q:
        q_lower = q.lower()
        leave_types = [lt for lt in leave_types if q_lower in lt.leave_type_name.lower()]

    context = get_base_context(request, response, user, csrf_token)
    context["leave_types"] = leave_types
    context["search_query"] = q or ""
    context["include_inactive"] = include_inactive

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/leave_types/partials/leave_types_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leave Types"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Types"},
    ])

    template = templates.get_template("modules/hr/templates/leave_types/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_type_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New leave type form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Leave Type"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Types", "href": "/hr/leave/types"},
        {"label": "New Leave Type"},
    ])
    context["leave_type"] = None
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_type_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new leave type."""
    service = LeaveService(db, user)
    form = await request.form()

    errors = {}
    leave_type_name = _form_str(form, "leave_type_name")

    if not leave_type_name:
        errors["leave_type_name"] = "Leave type name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Leave Type"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Types", "href": "/hr/leave/types"},
            {"label": "New Leave Type"},
        ])
        context["leave_type"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = LeaveTypeCreateData(
            leave_type_name=leave_type_name,
            max_leaves_allowed=_form_int(form, "max_leaves_allowed", 0),
            max_continuous_days_allowed=_form_int(form, "max_continuous_days_allowed") or None,
            is_carry_forward=_form_bool(form, "is_carry_forward"),
            is_lwp=_form_bool(form, "is_lwp"),
            is_optional_leave=_form_bool(form, "is_optional_leave"),
            is_compensatory=_form_bool(form, "is_compensatory"),
            allow_encashment=_form_bool(form, "allow_encashment"),
            include_holiday=_form_bool(form, "include_holiday"),
            is_earned_leave=_form_bool(form, "is_earned_leave"),
            earned_leave_frequency=_form_str(form, "earned_leave_frequency") or None,
            rounding=_form_decimal(form, "rounding", Decimal("0.5")),
        )
        leave_type = service.create_leave_type(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["leave_type_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Leave Type"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Types", "href": "/hr/leave/types"},
            {"label": "New Leave Type"},
        ])
        context["leave_type"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Leave type created successfully.", "success")
    return RedirectResponse(url=f"/hr/leave/types/{leave_type.id}", status_code=303)


@router.get("/{leave_type_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_type_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    leave_type_id: int,
):
    """Leave type detail page."""
    service = LeaveService(db, user)

    try:
        leave_type = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Leave type not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = leave_type.leave_type_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Types", "href": "/hr/leave/types"},
        {"label": leave_type.leave_type_name},
    ])
    context["leave_type"] = leave_type

    template = templates.get_template("modules/hr/templates/leave_types/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{leave_type_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_type_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    leave_type_id: int,
):
    """Edit leave type form."""
    service = LeaveService(db, user)

    try:
        leave_type = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Leave type not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {leave_type.leave_type_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Types", "href": "/hr/leave/types"},
        {"label": leave_type.leave_type_name, "href": f"/hr/leave/types/{leave_type.id}"},
        {"label": "Edit"},
    ])
    context["leave_type"] = leave_type
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{leave_type_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_type_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    leave_type_id: int,
):
    """Update a leave type."""
    service = LeaveService(db, user)

    try:
        leave_type = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Leave type not found")

    form = await request.form()
    errors = {}

    leave_type_name = _form_str(form, "leave_type_name")

    if not leave_type_name:
        errors["leave_type_name"] = "Leave type name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {leave_type.leave_type_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Types", "href": "/hr/leave/types"},
            {"label": leave_type.leave_type_name, "href": f"/hr/leave/types/{leave_type.id}"},
            {"label": "Edit"},
        ])
        context["leave_type"] = leave_type
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        data = LeaveTypeUpdateData(
            leave_type_name=leave_type_name,
            max_leaves_allowed=_form_int(form, "max_leaves_allowed", 0),
            max_continuous_days_allowed=_form_int(form, "max_continuous_days_allowed") or None,
            is_carry_forward=_form_bool(form, "is_carry_forward"),
            is_lwp=_form_bool(form, "is_lwp"),
            is_optional_leave=_form_bool(form, "is_optional_leave"),
            is_compensatory=_form_bool(form, "is_compensatory"),
            allow_encashment=_form_bool(form, "allow_encashment"),
            include_holiday=_form_bool(form, "include_holiday"),
            is_earned_leave=_form_bool(form, "is_earned_leave"),
            earned_leave_frequency=_form_str(form, "earned_leave_frequency") or None,
            rounding=_form_decimal(form, "rounding", Decimal("0.5")),
        )
        leave_type = service.update_leave_type(leave_type_id, data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["leave_type_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {leave_type.leave_type_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Types", "href": "/hr/leave/types"},
            {"label": leave_type.leave_type_name, "href": f"/hr/leave/types/{leave_type.id}"},
            {"label": "Edit"},
        ])
        context["leave_type"] = leave_type
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_types/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Leave type updated successfully.", "success")
    return RedirectResponse(url=f"/hr/leave/types/{leave_type.id}", status_code=303)


@router.delete("/{leave_type_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_type_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    leave_type_id: int,
):
    """Delete a leave type (soft delete via disable)."""
    service = LeaveService(db, user)

    try:
        leave_type = service.get_leave_type(leave_type_id)
    except LeaveTypeNotFoundError:
        raise HTTPException(status_code=404, detail="Leave type not found")

    try:
        # Soft delete by setting disabled flag
        from app.services.hr.leave_types import LeaveTypeUpdateData
        service.update_leave_type(leave_type_id, LeaveTypeUpdateData())
        # Actually mark as disabled
        leave_type.disabled = True
        db.commit()
    except HRValidationError as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail=str(e))

    if is_htmx_request(request):
        htmx_toast(response, "Leave type disabled.", "success")
        response.headers["HX-Redirect"] = "/hr/leave/types"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave type disabled.", "success")
    return RedirectResponse(url="/hr/leave/types", status_code=303)

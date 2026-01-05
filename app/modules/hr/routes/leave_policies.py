"""
HR Leave Policies Routes - Leave Policy Management with SSR + HTMX.

Permission Requirements:
- hr:read - View leave policies
- hr:write - Create, update, delete leave policies

Uses LeaveService for all business logic.
"""
from decimal import Decimal
from typing import Optional, Any, List

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.services.hr.leave import LeaveService
from app.services.hr.leave_types import (
    LeavePolicyCreateData,
    LeavePolicyUpdateData,
    LeavePolicyDetailData,
)
from app.services.hr.errors import LeavePolicyNotFoundError, ValidationError as HRValidationError
from app.core.security import is_htmx_request, htmx_toast, set_flash

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/leave/policies", tags=["hr-leave-policies"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_decimal(form: Any, key: str, default: Decimal = Decimal("0")) -> Decimal:
    value = _form_str(form, key)
    if not value:
        return default
    try:
        return Decimal(value)
    except Exception:
        return default


def _parse_policy_details(form: Any, service: LeaveService) -> List[LeavePolicyDetailData]:
    """Parse leave policy detail lines from form data."""
    details = []
    leave_types = service.list_leave_types(include_inactive=False)
    leave_type_map = {lt.id: lt.leave_type_name for lt in leave_types}

    # Form has arrays like leave_type_id[], annual_allocation[]
    leave_type_ids = form.getlist("leave_type_id")
    allocations = form.getlist("annual_allocation")

    for i, lt_id in enumerate(leave_type_ids):
        if lt_id:
            try:
                lt_id_int = int(lt_id)
                allocation = Decimal(allocations[i]) if i < len(allocations) and allocations[i] else Decimal("0")
                leave_type_name = leave_type_map.get(lt_id_int, "")
                if leave_type_name:
                    details.append(LeavePolicyDetailData(
                        leave_type=leave_type_name,
                        leave_type_id=lt_id_int,
                        annual_allocation=allocation,
                    ))
            except (ValueError, IndexError):
                continue

    return details


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_policies_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
):
    """Leave policies list page."""
    service = LeaveService(db, user)

    policies = service.list_leave_policies()

    # Filter by search if provided
    if q:
        q_lower = q.lower()
        policies = [p for p in policies if q_lower in p.leave_policy_name.lower()]

    context = get_base_context(request, response, user, csrf_token)
    context["policies"] = policies
    context["search_query"] = q or ""

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/leave_policies/partials/policies_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leave Policies"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Policies"},
    ])

    template = templates.get_template("modules/hr/templates/leave_policies/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_policy_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New leave policy form."""
    service = LeaveService(db, user)
    leave_types = service.list_leave_types(include_inactive=False)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Leave Policy"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Policies", "href": "/hr/leave/policies"},
        {"label": "New Leave Policy"},
    ])
    context["policy"] = None
    context["leave_types"] = leave_types
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_policy_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new leave policy."""
    service = LeaveService(db, user)
    form = await request.form()

    errors = {}
    leave_policy_name = _form_str(form, "leave_policy_name")

    if not leave_policy_name:
        errors["leave_policy_name"] = "Policy name is required"

    leave_types = service.list_leave_types(include_inactive=False)

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Leave Policy"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Policies", "href": "/hr/leave/policies"},
            {"label": "New Leave Policy"},
        ])
        context["policy"] = None
        context["leave_types"] = leave_types
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        details = _parse_policy_details(form, service)
        data = LeavePolicyCreateData(
            leave_policy_name=leave_policy_name,
            details=details,
        )
        policy = service.create_leave_policy(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["leave_policy_name"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Leave Policy"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Policies", "href": "/hr/leave/policies"},
            {"label": "New Leave Policy"},
        ])
        context["policy"] = None
        context["leave_types"] = leave_types
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Leave policy created successfully.", "success")
    return RedirectResponse(url=f"/hr/leave/policies/{policy.id}", status_code=303)


@router.get("/{policy_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def leave_policy_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    policy_id: int,
):
    """Leave policy detail page."""
    service = LeaveService(db, user)

    try:
        policy = service.get_leave_policy(policy_id)
    except LeavePolicyNotFoundError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = policy.leave_policy_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Policies", "href": "/hr/leave/policies"},
        {"label": policy.leave_policy_name},
    ])
    context["policy"] = policy

    template = templates.get_template("modules/hr/templates/leave_policies/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{policy_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_policy_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    policy_id: int,
):
    """Edit leave policy form."""
    service = LeaveService(db, user)

    try:
        policy = service.get_leave_policy(policy_id)
    except LeavePolicyNotFoundError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    leave_types = service.list_leave_types(include_inactive=False)

    # Build a map of existing allocations
    existing_allocations = {}
    if policy.details:
        for detail in policy.details:
            existing_allocations[detail.leave_type_id] = detail.annual_allocation

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {policy.leave_policy_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Leave", "href": "/hr/leave"},
        {"label": "Leave Policies", "href": "/hr/leave/policies"},
        {"label": policy.leave_policy_name, "href": f"/hr/leave/policies/{policy.id}"},
        {"label": "Edit"},
    ])
    context["policy"] = policy
    context["leave_types"] = leave_types
    context["existing_allocations"] = existing_allocations
    context["errors"] = {}

    template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{policy_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_policy_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    policy_id: int,
):
    """Update a leave policy."""
    service = LeaveService(db, user)

    try:
        policy = service.get_leave_policy(policy_id)
    except LeavePolicyNotFoundError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    form = await request.form()
    errors = {}

    leave_policy_name = _form_str(form, "leave_policy_name")
    leave_types = service.list_leave_types(include_inactive=False)

    if not leave_policy_name:
        errors["leave_policy_name"] = "Policy name is required"

    if errors:
        existing_allocations = {}
        if policy.details:
            for detail in policy.details:
                existing_allocations[detail.leave_type_id] = detail.annual_allocation

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {policy.leave_policy_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Policies", "href": "/hr/leave/policies"},
            {"label": policy.leave_policy_name, "href": f"/hr/leave/policies/{policy.id}"},
            {"label": "Edit"},
        ])
        context["policy"] = policy
        context["leave_types"] = leave_types
        context["existing_allocations"] = existing_allocations
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        details = _parse_policy_details(form, service)
        data = LeavePolicyUpdateData(
            leave_policy_name=leave_policy_name,
            details=details,
        )
        policy = service.update_leave_policy(policy_id, data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        errors["leave_policy_name"] = str(e)

        existing_allocations = {}
        if policy.details:
            for detail in policy.details:
                existing_allocations[detail.leave_type_id] = detail.annual_allocation

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {policy.leave_policy_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr"},
            {"label": "Leave", "href": "/hr/leave"},
            {"label": "Leave Policies", "href": "/hr/leave/policies"},
            {"label": policy.leave_policy_name, "href": f"/hr/leave/policies/{policy.id}"},
            {"label": "Edit"},
        ])
        context["policy"] = policy
        context["leave_types"] = leave_types
        context["existing_allocations"] = existing_allocations
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/hr/templates/leave_policies/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, "Leave policy updated successfully.", "success")
    return RedirectResponse(url=f"/hr/leave/policies/{policy.id}", status_code=303)


@router.delete("/{policy_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def leave_policy_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    policy_id: int,
):
    """Delete a leave policy."""
    service = LeaveService(db, user)

    try:
        policy = service.get_leave_policy(policy_id)
    except LeavePolicyNotFoundError:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    try:
        # Delete policy (this will cascade delete details)
        db.delete(policy)
        db.commit()
    except Exception as e:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail=str(e))

    if is_htmx_request(request):
        htmx_toast(response, "Leave policy deleted.", "success")
        response.headers["HX-Redirect"] = "/hr/leave/policies"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Leave policy deleted.", "success")
    return RedirectResponse(url="/hr/leave/policies", status_code=303)

"""
CRM Activities Routes - SSR + HTMX

Provides web routes for managing activities (calls, meetings, emails, tasks).
Uses service layer via CRMWebService for all operations.
"""
from ._deps import (
    # FastAPI
    APIRouter, Request, Response, Query, Depends,
    HTMLResponse, RedirectResponse,
    # Types
    Optional, date, datetime,
    # Context helpers
    get_base_context, build_breadcrumbs, build_pagination_context,
    # Dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireCRMRead, RequireCRMWrite,
    # Templates
    templates,
    # Helpers
    is_htmx_request, htmx_toast, set_flash,
    _form_str, _form_int, _form_date,
    # Models
    Activity, ActivityType, ActivityStatus,
    # Service
    CRMWebService,
    # Options
    get_activity_type_options, get_activity_status_options, get_priority_options,
    get_owner_options, get_customer_options,
)

router = APIRouter(prefix="/crm/activities", tags=["crm-activities"])


# =============================================================================
# ACTIVITIES LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def activities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = None,
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=5, le=100),
    sort: str = "scheduled_at",
    dir: str = "desc",
):
    """List activities with filtering and search."""
    service = CRMWebService(db, user_id=user.id)

    # Parse date strings
    parsed_start_date = None
    parsed_end_date = None
    if start_date:
        try:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    if end_date:
        try:
            parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    result = service.list_activities(
        q=q,
        activity_type=activity_type,
        status=status,
        lead_id=lead_id,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        page=page,
        per_page=per_page,
        sort=sort,
        dir=dir,
    )

    summary = service.get_activities_summary()

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": "Activities",
        "breadcrumbs": build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Activities"},
        ]),
        # Data
        "activities": result["items"],
        "summary": summary,
        # Pagination
        "pagination": build_pagination_context(result["page"], per_page, result["total"]),
        "pagination_base_url": "/crm/activities",
        # Filter state
        "q": q or "",
        "activity_type": activity_type or "",
        "status": status or "",
        "start_date": start_date or "",
        "end_date": end_date or "",
        # Options
        "type_options": get_activity_type_options(),
        "status_options": get_activity_status_options(),
    }

    if is_htmx_request(request):
        template = templates.get_template("modules/crm/activities/partials/activities_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/crm/activities/pages/list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ACTIVITY DETAIL
# =============================================================================

@router.get("/{activity_id}", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def activity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    activity_id: int,
):
    """View activity details."""
    service = CRMWebService(db, user_id=user.id)
    activity = service.get_activity(activity_id)

    if not activity:
        set_flash(response, "Activity not found", "error")
        return RedirectResponse("/crm/activities", status_code=303)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": activity.subject,
        "breadcrumbs": build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Activities", "url": "/crm/activities"},
            {"label": activity.subject},
        ]),
        "activity": activity,
    }

    template = templates.get_template("modules/crm/activities/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# CREATE ACTIVITY
# =============================================================================

@router.get("/new", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def activity_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    activity_type: Optional[str] = None,
):
    """Show new activity form."""
    service = CRMWebService(db, user_id=user.id)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": "New Activity",
        "breadcrumbs": build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Activities", "url": "/crm/activities"},
            {"label": "New Activity"},
        ]),
        "activity": None,
        "errors": {},
        "form_data": {
            "lead_id": lead_id,
            "customer_id": customer_id,
            "opportunity_id": opportunity_id,
            "activity_type": activity_type or "task",
        },
        # Options
        "type_options": get_activity_type_options(),
        "status_options": get_activity_status_options(),
        "priority_options": get_priority_options(),
        "owner_options": get_owner_options(db),
        "customer_options": get_customer_options(db),
        "lead_options": service.get_lead_options(),
        "opportunity_options": service.get_opportunity_options(),
    }

    template = templates.get_template("modules/crm/activities/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def activity_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    _csrf: CSRFProtect,
    db: DB,
):
    """Create a new activity."""
    form = await request.form()
    service = CRMWebService(db, user_id=user.id)

    errors = {}
    subject = _form_str(form, "subject")
    if not subject:
        errors["subject"] = "Subject is required"

    if errors:
        context = {
            **get_base_context(request, response, user, csrf_token),
            "page_title": "New Activity",
            "breadcrumbs": build_breadcrumbs([
                {"label": "CRM"},
                {"label": "Activities", "url": "/crm/activities"},
                {"label": "New Activity"},
            ]),
            "activity": None,
            "errors": errors,
            "form_data": dict(form),
            "type_options": get_activity_type_options(),
            "status_options": get_activity_status_options(),
            "priority_options": get_priority_options(),
            "owner_options": get_owner_options(db),
            "customer_options": get_customer_options(db),
            "lead_options": service.get_lead_options(),
            "opportunity_options": service.get_opportunity_options(),
        }
        template = templates.get_template("modules/crm/activities/pages/form.html")
        return HTMLResponse(template.render(context))

    # Parse scheduled_at datetime
    scheduled_at = None
    sched_date = _form_str(form, "scheduled_date")
    sched_time = _form_str(form, "scheduled_time")
    if sched_date:
        try:
            if sched_time:
                scheduled_at = datetime.strptime(f"{sched_date} {sched_time}", "%Y-%m-%d %H:%M")
            else:
                scheduled_at = datetime.strptime(sched_date, "%Y-%m-%d")
        except ValueError:
            pass

    data = {
        "activity_type": _form_str(form, "activity_type", "task"),
        "subject": subject,
        "description": _form_str(form, "description") or None,
        "lead_id": _form_int(form, "lead_id"),
        "customer_id": _form_int(form, "customer_id"),
        "opportunity_id": _form_int(form, "opportunity_id"),
        "scheduled_at": scheduled_at,
        "duration_minutes": _form_int(form, "duration_minutes"),
        "assigned_to_id": _form_int(form, "assigned_to_id"),
        "priority": _form_str(form, "priority", "medium"),
        "call_direction": _form_str(form, "call_direction") or None,
        "owner_id": user.id,
    }

    activity = service.create_activity(data)

    set_flash(response, f"Activity '{activity.subject}' created successfully", "success")
    return RedirectResponse(f"/crm/activities/{activity.id}", status_code=303)


# =============================================================================
# EDIT ACTIVITY
# =============================================================================

@router.get("/{activity_id}/edit", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def activity_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    activity_id: int,
):
    """Show edit activity form."""
    service = CRMWebService(db, user_id=user.id)
    activity = service.get_activity(activity_id)

    if not activity:
        set_flash(response, "Activity not found", "error")
        return RedirectResponse("/crm/activities", status_code=303)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": f"Edit: {activity.subject}",
        "breadcrumbs": build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Activities", "url": "/crm/activities"},
            {"label": activity.subject, "url": f"/crm/activities/{activity_id}"},
            {"label": "Edit"},
        ]),
        "activity": activity,
        "errors": {},
        "form_data": None,
        # Options
        "type_options": get_activity_type_options(),
        "status_options": get_activity_status_options(),
        "priority_options": get_priority_options(),
        "owner_options": get_owner_options(db),
        "customer_options": get_customer_options(db),
        "lead_options": service.get_lead_options(),
        "opportunity_options": service.get_opportunity_options(),
    }

    template = templates.get_template("modules/crm/activities/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{activity_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def activity_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    _csrf: CSRFProtect,
    db: DB,
    activity_id: int,
):
    """Update an existing activity."""
    form = await request.form()
    service = CRMWebService(db, user_id=user.id)

    activity = service.get_activity(activity_id)
    if not activity:
        set_flash(response, "Activity not found", "error")
        return RedirectResponse("/crm/activities", status_code=303)

    errors = {}
    subject = _form_str(form, "subject")
    if not subject:
        errors["subject"] = "Subject is required"

    if errors:
        context = {
            **get_base_context(request, response, user, csrf_token),
            "page_title": f"Edit: {activity.subject}",
            "breadcrumbs": build_breadcrumbs([
                {"label": "CRM"},
                {"label": "Activities", "url": "/crm/activities"},
                {"label": activity.subject, "url": f"/crm/activities/{activity_id}"},
                {"label": "Edit"},
            ]),
            "activity": activity,
            "errors": errors,
            "form_data": dict(form),
            "type_options": get_activity_type_options(),
            "status_options": get_activity_status_options(),
            "priority_options": get_priority_options(),
            "owner_options": get_owner_options(db),
            "customer_options": get_customer_options(db),
            "lead_options": service.get_lead_options(),
            "opportunity_options": service.get_opportunity_options(),
        }
        template = templates.get_template("modules/crm/activities/pages/form.html")
        return HTMLResponse(template.render(context))

    # Parse scheduled_at datetime
    scheduled_at = None
    sched_date = _form_str(form, "scheduled_date")
    sched_time = _form_str(form, "scheduled_time")
    if sched_date:
        try:
            if sched_time:
                scheduled_at = datetime.strptime(f"{sched_date} {sched_time}", "%Y-%m-%d %H:%M")
            else:
                scheduled_at = datetime.strptime(sched_date, "%Y-%m-%d")
        except ValueError:
            pass

    data = {
        "activity_type": _form_str(form, "activity_type", "task"),
        "subject": subject,
        "description": _form_str(form, "description") or None,
        "lead_id": _form_int(form, "lead_id"),
        "customer_id": _form_int(form, "customer_id"),
        "opportunity_id": _form_int(form, "opportunity_id"),
        "scheduled_at": scheduled_at,
        "duration_minutes": _form_int(form, "duration_minutes"),
        "assigned_to_id": _form_int(form, "assigned_to_id"),
        "priority": _form_str(form, "priority", "medium"),
        "call_direction": _form_str(form, "call_direction") or None,
    }

    service.update_activity(activity_id, data)

    set_flash(response, f"Activity '{subject}' updated successfully", "success")
    return RedirectResponse(f"/crm/activities/{activity_id}", status_code=303)


# =============================================================================
# ACTIVITY ACTIONS
# =============================================================================

@router.post("/{activity_id}/complete", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def activity_complete(
    request: Request,
    response: Response,
    user: SessionUser,
    _csrf: CSRFProtect,
    db: DB,
    activity_id: int,
):
    """Mark an activity as completed."""
    form = await request.form()
    service = CRMWebService(db, user_id=user.id)

    outcome = _form_str(form, "outcome") or None
    notes = _form_str(form, "notes") or None

    activity = service.complete_activity(activity_id, outcome=outcome, notes=notes)

    if not activity:
        if is_htmx_request(request):
            htmx_toast(response, "Activity not found", "error")
            return Response(status_code=204)
        set_flash(response, "Activity not found", "error")
        return RedirectResponse("/crm/activities", status_code=303)

    if is_htmx_request(request):
        htmx_toast(response, f"Activity '{activity.subject}' marked as completed", "success")
        response.headers["HX-Refresh"] = "true"
        return Response(status_code=204)

    set_flash(response, f"Activity '{activity.subject}' marked as completed", "success")
    return RedirectResponse(f"/crm/activities/{activity_id}", status_code=303)


@router.post("/{activity_id}/cancel", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def activity_cancel(
    request: Request,
    response: Response,
    user: SessionUser,
    _csrf: CSRFProtect,
    db: DB,
    activity_id: int,
):
    """Cancel an activity."""
    service = CRMWebService(db, user_id=user.id)

    activity = service.cancel_activity(activity_id)

    if not activity:
        if is_htmx_request(request):
            htmx_toast(response, "Activity not found", "error")
            return Response(status_code=204)
        set_flash(response, "Activity not found", "error")
        return RedirectResponse("/crm/activities", status_code=303)

    if is_htmx_request(request):
        htmx_toast(response, f"Activity '{activity.subject}' cancelled", "success")
        response.headers["HX-Refresh"] = "true"
        return Response(status_code=204)

    set_flash(response, f"Activity '{activity.subject}' cancelled", "success")
    return RedirectResponse(f"/crm/activities/{activity_id}", status_code=303)


@router.post("/{activity_id}/delete", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def activity_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    _csrf: CSRFProtect,
    db: DB,
    activity_id: int,
):
    """Delete an activity."""
    service = CRMWebService(db, user_id=user.id)

    activity = service.get_activity(activity_id)
    if activity:
        subject = activity.subject
        service.delete_activity(activity_id)
    else:
        subject = None

    if is_htmx_request(request):
        if subject:
            htmx_toast(response, f"Activity '{subject}' deleted", "success")
        else:
            htmx_toast(response, "Activity not found", "error")
        response.headers["HX-Redirect"] = "/crm/activities"
        return Response(status_code=204)

    if subject:
        set_flash(response, f"Activity '{subject}' deleted", "success")
    else:
        set_flash(response, "Activity not found", "error")

    return RedirectResponse("/crm/activities", status_code=303)


# =============================================================================
# ACTIVITY ROW PARTIAL (for HTMX updates)
# =============================================================================

@router.get("/{activity_id}/row", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def activity_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    activity_id: int,
):
    """Return a single activity row for HTMX updates."""
    service = CRMWebService(db, user_id=user.id)
    activity = service.get_activity(activity_id)

    if not activity:
        return Response(status_code=404)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "activity": activity,
    }

    template = templates.get_template("modules/crm/activities/partials/activity_row.html")
    return HTMLResponse(template.render(context))

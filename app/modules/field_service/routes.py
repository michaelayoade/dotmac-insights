"""
Field Service Routes - Service Order Management with SSR + HTMX.

Permission Requirements:
- field_service:read - View service orders and technician assignments
- field_service:write - Create, update, delete service orders
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, date

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
from app.models.field_service import (
    ServiceOrderType, ServiceOrderStatus, ServiceOrderPriority,
)
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.field_service import (
    ServiceOrderService,
    TeamService,
    FieldServiceLookupService,
    ServiceOrderFilters,
    ServiceOrderCreateData,
    ServiceOrderUpdateData,
    TeamFilters,
    TeamCreateData,
    TeamUpdateData,
    TeamMemberData,
    TechnicianFilters,
    TechnicianSkillData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

# Permission dependencies
RequireFieldServiceRead = Depends(require_scope("field_service:read"))
RequireFieldServiceWrite = Depends(require_scope("field_service:write"))

router = APIRouter(prefix="/field-service", tags=["field_service"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _form_enum(enum_cls: type, form: Any, key: str, default: Any) -> Any:
    default_value = str(getattr(default, "value", default))
    value = _form_str(form, key, default_value)
    try:
        return enum_cls(value)
    except ValueError:
        return default


def _get_order_form_options(lookup: FieldServiceLookupService):
    customers = lookup.list_customers(limit=100)
    technicians = lookup.list_employees(limit=100, active_only=False)
    teams = lookup.list_teams(active_only=True)
    return customers, technicians, teams


def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ServiceOrderStatus
    ]


def get_priority_options():
    """Get priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in ServiceOrderPriority
    ]


def get_type_options():
    """Get type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.title()}
        for t in ServiceOrderType
    ]


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def field_service_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Field Service Dashboard with overview stats."""
    today = date.today()
    order_service = ServiceOrderService(db)
    team_service = TeamService(db)

    # Get order stats from service
    stats = order_service.get_stats()

    # Orders by status distribution
    status_distribution = [
        {"status": status, "count": count}
        for status, count in stats.by_status.items()
    ]

    # Orders by priority distribution
    priority_distribution = [
        {"priority": priority, "count": count}
        for priority, count in stats.by_priority.items()
    ]

    # Today's schedule
    today_filters = ServiceOrderFilters(
        scheduled_date_from=today,
        scheduled_date_to=today,
    )
    today_result = order_service.list_orders(today_filters, PaginationParams(limit=10))
    todays_orders = today_result.items

    # Active teams with stats
    team_filters = TeamFilters(is_active=True)
    teams_result = team_service.list_teams(team_filters)
    team_stats = []
    for team in teams_result.items:
        team_counts = team_service.get_team_stats(team.id)
        team_stats.append({
            "id": team.id,
            "name": team.name,
            "members": team_service.count_team_members(team.id),
            "active_orders": team_counts["active_orders"],
        })

    # Recent completions
    completed_filters = ServiceOrderFilters(status="completed")
    completed_result = order_service.list_orders(completed_filters, PaginationParams(limit=5))
    recent_completions = completed_result.items

    # Calculate today counts
    today_scheduled = len(todays_orders)
    in_progress = stats.by_status.get("en_route", 0) + stats.by_status.get("on_site", 0) + stats.by_status.get("in_progress", 0)
    pending_dispatch = stats.by_status.get("draft", 0) + stats.by_status.get("scheduled", 0)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Field Service Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service"},
    ])

    context["stats"] = {
        "total_orders": stats.total,
        "today_scheduled": today_scheduled,
        "in_progress": in_progress,
        "pending_dispatch": pending_dispatch,
        "completed_today": stats.completed_today,
    }
    context["status_distribution"] = status_distribution
    context["priority_distribution"] = priority_distribution
    context["todays_orders"] = todays_orders
    context["team_stats"] = team_stats
    context["recent_completions"] = recent_completions
    context["today"] = today

    template = templates.get_template("modules/field_service/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def service_orders_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("scheduled_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Service orders list page."""
    service = ServiceOrderService(db)

    # Build filters
    filters = ServiceOrderFilters(
        search=q,
        status=status,
        priority=priority,
        order_type=type,
        sort_by=sort,
        sort_dir=dir,
    )

    # Paginate
    offset = (page - 1) * per_page
    pagination = PaginationParams(limit=per_page, offset=offset)
    result = service.list_orders(filters, pagination)
    orders_with_coords = [
        order
        for order in result.items
        if getattr(order, "latitude", None)
        and getattr(order, "longitude", None)
    ]

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["orders"] = result.items
    context["orders_with_coords"] = orders_with_coords
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_type"] = type
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/orders_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Field Service"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service"},
    ])

    template = templates.get_template("modules/field_service/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def service_orders_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("scheduled_date"),
    dir: str = Query("desc"),
):
    """Service orders table partial for HTMX updates."""
    return await service_orders_list(
        request, response, user, csrf_token, db,
        q, status, priority, type, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def service_order_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New service order form page."""
    lookup = FieldServiceLookupService(db)
    customers, technicians, teams = _get_order_form_options(lookup)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Service Order"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "New Order"},
    ])
    context["order"] = None
    context["customers"] = customers
    context["technicians"] = technicians
    context["teams"] = teams
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/field_service/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def service_order_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new service order."""
    form = await request.form()

    # Basic validation
    errors = {}
    title = _form_str(form, "title")
    service_address = _form_str(form, "service_address")
    customer_account_id = _form_int(form, "customer_account_id")

    if not title:
        errors["title"] = "Title is required"
    if not service_address:
        errors["service_address"] = "Service address is required"
    if customer_account_id is None:
        errors["customer_account_id"] = "Customer is required"

    if errors:
        lookup = FieldServiceLookupService(db)
        customers, technicians, teams = _get_order_form_options(lookup)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Service Order"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": "New Order"},
        ])
        context["order"] = None
        context["customers"] = customers
        context["technicians"] = technicians
        context["teams"] = teams
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/field_service/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse scheduled date
    scheduled_date = date.today()
    scheduled_date_str = _form_str(form, "scheduled_date")
    if scheduled_date_str:
        try:
            scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Build create data
    order_type = _form_enum(ServiceOrderType, form, "order_type", ServiceOrderType.REPAIR)
    priority = _form_enum(ServiceOrderPriority, form, "priority", ServiceOrderPriority.MEDIUM)

    data = ServiceOrderCreateData(
        customer_account_id=customer_account_id,
        order_type=order_type.value,
        title=title,
        service_address=service_address,
        scheduled_date=scheduled_date,
        description=_form_str(form, "description") or None,
        priority=priority.value,
        city=_form_str(form, "city") or None,
        state=_form_str(form, "state") or None,
        postal_code=_form_str(form, "postal_code") or None,
        customer_contact_name=_form_str(form, "customer_contact_name") or None,
        customer_contact_phone=_form_str(form, "customer_contact_phone") or None,
        assigned_technician_id=_form_int(form, "assigned_technician_id"),
        assigned_team_id=_form_int(form, "assigned_team_id"),
    )

    service = ServiceOrderService(db)
    try:
        order = service.create_order(data)
        db.commit()
        db.refresh(order)
        set_flash(response, f"Service order '{order.order_number}' created successfully.", "success")
        return RedirectResponse(url=f"/field-service/{order.id}", status_code=303)
    except ValidationError as e:
        errors["general"] = str(e)
        lookup = FieldServiceLookupService(db)
        customers, technicians, teams = _get_order_form_options(lookup)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Service Order"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": "New Order"},
        ])
        context["order"] = None
        context["customers"] = customers
        context["technicians"] = technicians
        context["teams"] = teams
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/field_service/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)


# =============================================================================
# TEAMS MANAGEMENT
# =============================================================================

@router.get("/teams", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def teams_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Field teams list page."""
    service = TeamService(db)
    filters = TeamFilters(search=q)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_teams(filters, pagination)

    # Get member counts for each team
    teams_with_counts = []
    for team in result.items:
        teams_with_counts.append({
            "team": team,
            "member_count": service.count_team_members(team.id),
        })

    context = get_base_context(request, response, user, csrf_token)
    context["teams"] = teams_with_counts
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/teams_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Field Teams"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Teams"},
    ])

    template = templates.get_template("modules/field_service/templates/pages/teams_list.html")
    return HTMLResponse(template.render(context))


@router.get("/teams/new", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New team form page."""
    lookup = FieldServiceLookupService(db)
    supervisors = lookup.list_employees(limit=100, active_only=True)
    zones = lookup.list_zones(active_only=True)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Field Team"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Teams", "href": "/field-service/teams"},
        {"label": "New Team"},
    ])
    context["team"] = None
    context["supervisors"] = supervisors
    context["zones"] = zones
    context["errors"] = {}

    template = templates.get_template("modules/field_service/templates/pages/team_form.html")
    return HTMLResponse(template.render(context))


@router.post("/teams", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new field team."""
    form = await request.form()

    errors = {}
    name = _form_str(form, "name")
    if not name:
        errors["name"] = "Team name is required"

    if errors:
        lookup = FieldServiceLookupService(db)
        supervisors = lookup.list_employees(limit=100, active_only=True)
        zones = lookup.list_zones(active_only=True)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Field Team"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": "Teams", "href": "/field-service/teams"},
            {"label": "New Team"},
        ])
        context["team"] = None
        context["supervisors"] = supervisors
        context["zones"] = zones
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/field_service/templates/pages/team_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = TeamService(db)
    data = TeamCreateData(
        name=name,
        description=_form_str(form, "description") or None,
        contact_phone=_form_str(form, "contact_phone") or None,
        contact_email=_form_str(form, "contact_email") or None,
        max_daily_orders=_form_int(form, "max_daily_orders", 10) or 10,
        supervisor_id=_form_int(form, "supervisor_id"),
    )

    team = service.create_team(data)
    team.is_active = form.get("is_active") == "on"
    db.commit()

    set_flash(response, f"Team '{team.name}' created successfully.", "success")
    return RedirectResponse(url=f"/field-service/teams/{team.id}", status_code=303)


@router.get("/teams/{team_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def team_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
):
    """Team detail page."""
    service = TeamService(db)
    try:
        team = service.get_team(team_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    members = service.list_team_members(team_id)
    available_employees = service.list_available_employees(team_id)

    order_service = ServiceOrderService(db)
    active_orders = order_service.list_active_orders_for_team(team_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = team.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Teams", "href": "/field-service/teams"},
        {"label": team.name},
    ])
    context["team"] = team
    context["members"] = members
    context["available_employees"] = available_employees
    context["active_orders"] = active_orders

    template = templates.get_template("modules/field_service/templates/pages/team_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/teams/{team_id}/edit", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
):
    """Team edit form page."""
    service = TeamService(db)
    try:
        team = service.get_team(team_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    lookup = FieldServiceLookupService(db)
    supervisors = lookup.list_employees(limit=100, active_only=True)
    zones = lookup.list_zones(active_only=True)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {team.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Teams", "href": "/field-service/teams"},
        {"label": team.name, "href": f"/field-service/teams/{team.id}"},
        {"label": "Edit"},
    ])
    context["team"] = team
    context["supervisors"] = supervisors
    context["zones"] = zones
    context["errors"] = {}

    template = templates.get_template("modules/field_service/templates/pages/team_form.html")
    return HTMLResponse(template.render(context))


@router.post("/teams/{team_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    team_id: int,
):
    """Update a field team."""
    service = TeamService(db)
    try:
        team = service.get_team(team_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    form = await request.form()

    errors = {}
    name = _form_str(form, "name")
    if not name:
        errors["name"] = "Team name is required"

    if errors:
        lookup = FieldServiceLookupService(db)
        supervisors = lookup.list_employees(limit=100, active_only=True)
        zones = lookup.list_zones(active_only=True)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {team.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": "Teams", "href": "/field-service/teams"},
            {"label": team.name, "href": f"/field-service/teams/{team.id}"},
            {"label": "Edit"},
        ])
        context["team"] = team
        context["supervisors"] = supervisors
        context["zones"] = zones
        context["errors"] = errors

        template = templates.get_template("modules/field_service/templates/pages/team_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = TeamUpdateData(
        name=name,
        description=_form_str(form, "description") or None,
        contact_phone=_form_str(form, "contact_phone") or None,
        contact_email=_form_str(form, "contact_email") or None,
        max_daily_orders=_form_int(form, "max_daily_orders", 10) or 10,
        is_active=form.get("is_active") == "on",
        supervisor_id=_form_int(form, "supervisor_id"),
    )

    team = service.update_team(team_id, data)
    db.commit()

    set_flash(response, f"Team '{team.name}' updated successfully.", "success")
    return RedirectResponse(url=f"/field-service/teams/{team.id}", status_code=303)


@router.delete("/teams/{team_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    team_id: int,
):
    """Deactivate a field team."""
    service = TeamService(db)
    try:
        team = service.deactivate_team(team_id)
        name = team.name
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Team '{name}' deactivated.", "success")
        response.headers["HX-Redirect"] = "/field-service/teams"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Team '{name}' deactivated.", "success")
    return RedirectResponse(url="/field-service/teams", status_code=303)


@router.post("/teams/{team_id}/members", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_add_member(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    team_id: int,
):
    """Add a member to a team."""
    form = await request.form()
    employee_id = _form_int(form, "employee_id")
    role = _form_str(form, "role", "technician")

    if employee_id is None:
        set_flash(response, "Please select an employee.", "error")
        return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)

    service = TeamService(db)
    try:
        data = TeamMemberData(employee_id=employee_id, role=role)
        service.add_member(team_id, data)
        db.commit()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError:
        set_flash(response, "Employee is already a team member.", "error")
        return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)

    set_flash(response, "Team member added.", "success")
    return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)


@router.delete("/teams/{team_id}/members/{member_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def team_remove_member(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    team_id: int,
    member_id: int,
):
    """Remove a member from a team."""
    service = TeamService(db)
    member = service.get_team_member(team_id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if not member.employee:
        raise HTTPException(status_code=400, detail="Member has no linked employee")
    service.remove_member(team_id, member.employee.id)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Team member removed.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Team member removed.", "success")
    return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)


# =============================================================================
# TECHNICIANS
# =============================================================================

@router.get("/technicians", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def technicians_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Technicians list page - employees with field team memberships."""
    service = TeamService(db)
    filters = TechnicianFilters(search=q)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_technicians(filters, pagination)

    # Get team memberships and skills for each technician
    technicians_with_info = []
    order_service = ServiceOrderService(db)
    for tech in result.items:
        memberships = service.get_technician_teams(tech.id)
        skills = service.get_technician_skills(tech.id)
        active_orders = order_service.count_active_orders_for_technician(tech.id)

        technicians_with_info.append({
            "employee": tech,
            "memberships": memberships,
            "skills": skills,
            "active_orders": active_orders,
        })

    context = get_base_context(request, response, user, csrf_token)
    context["technicians"] = technicians_with_info
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/field_service/templates/partials/technicians_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Technicians"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Technicians"},
    ])

    template = templates.get_template("modules/field_service/templates/pages/technicians_list.html")
    return HTMLResponse(template.render(context))


@router.get("/technicians/{employee_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def technician_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    employee_id: int,
):
    """Technician detail page."""
    service = TeamService(db)
    try:
        employee = service.get_technician(employee_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Technician not found")

    # Get team memberships and skills from service
    memberships = service.get_technician_teams(employee_id)
    skills = service.get_technician_skills(employee_id)

    order_service = ServiceOrderService(db)
    recent_orders = order_service.list_recent_orders_for_technician(employee_id)

    completed_orders = order_service.count_completed_orders_for_technician(employee_id)
    active_orders = order_service.count_active_orders_for_technician(employee_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = employee.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": "Technicians", "href": "/field-service/technicians"},
        {"label": employee.name},
    ])
    context["employee"] = employee
    context["memberships"] = memberships
    context["skills"] = skills
    context["recent_orders"] = recent_orders
    context["completed_orders"] = completed_orders
    context["active_orders"] = active_orders

    template = templates.get_template("modules/field_service/templates/pages/technician_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/technicians/{employee_id}/skills", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def technician_add_skill(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    employee_id: int,
):
    """Add a skill to a technician."""
    form = await request.form()
    skill_type = _form_str(form, "skill_type")
    proficiency_level = _form_str(form, "proficiency_level", "intermediate")

    if not skill_type:
        set_flash(response, "Skill type is required.", "error")
        return RedirectResponse(url=f"/field-service/technicians/{employee_id}", status_code=303)

    service = TeamService(db)
    try:
        data = TechnicianSkillData(
            skill_type=skill_type,
            proficiency_level=proficiency_level,
            certification=_form_str(form, "certification") or None,
        )
        service.add_skill(employee_id, data)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Technician not found")

    set_flash(response, "Skill added.", "success")
    return RedirectResponse(url=f"/field-service/technicians/{employee_id}", status_code=303)


@router.delete("/technicians/{employee_id}/skills/{skill_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def technician_remove_skill(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    employee_id: int,
    skill_id: int,
):
    """Remove a skill from a technician."""
    service = TeamService(db)
    try:
        service.remove_skill(employee_id, skill_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")

    if is_htmx_request(request):
        htmx_toast(response, "Skill removed.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Skill removed.", "success")
    return RedirectResponse(url=f"/field-service/technicians/{employee_id}", status_code=303)


# =============================================================================
# SERVICE ORDER DETAIL ROUTES (must be after /teams and /technicians)
# =============================================================================

@router.get("/{order_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def service_order_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Service order detail page."""
    service = ServiceOrderService(db)

    try:
        order = service.get_order(order_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service order not found")

    lookup = FieldServiceLookupService(db)

    customer = order.customer
    technician = order.technician
    team = order.team

    related_project = (
        lookup.get_project(order.project_id) if order.project_id else None
    )
    related_ticket = (
        lookup.get_unified_ticket(order.ticket_id) if order.ticket_id else None
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = order.order_number
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": order.order_number},
    ])
    context["order"] = order
    context["customer"] = customer
    context["technician"] = technician
    context["team"] = team
    context["related_project"] = related_project
    context["related_ticket"] = related_ticket

    template = templates.get_template("modules/field_service/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{order_id}/edit", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def service_order_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Service order edit form page."""
    service = ServiceOrderService(db)

    try:
        order = service.get_order(order_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service order not found")

    lookup = FieldServiceLookupService(db)
    customers, technicians, teams = _get_order_form_options(lookup)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {order.order_number}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service", "href": "/field-service"},
        {"label": order.order_number, "href": f"/field-service/{order.id}"},
        {"label": "Edit"},
    ])
    context["order"] = order
    context["customers"] = customers
    context["technicians"] = technicians
    context["teams"] = teams
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/field_service/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{order_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def service_order_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    order_id: int,
):
    """Update a service order."""
    service = ServiceOrderService(db)

    try:
        order = service.get_order(order_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service order not found")

    form = await request.form()

    # Basic validation
    errors = {}
    title = _form_str(form, "title")
    service_address = _form_str(form, "service_address")

    if not title:
        errors["title"] = "Title is required"
    if not service_address:
        errors["service_address"] = "Service address is required"

    if errors:
        lookup = FieldServiceLookupService(db)
        customers, technicians, teams = _get_order_form_options(lookup)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {order.order_number}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": order.order_number, "href": f"/field-service/{order.id}"},
            {"label": "Edit"},
        ])
        context["order"] = order
        context["customers"] = customers
        context["technicians"] = technicians
        context["teams"] = teams
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors

        template = templates.get_template("modules/field_service/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse scheduled date
    scheduled_date = None
    scheduled_date_str = _form_str(form, "scheduled_date")
    if scheduled_date_str:
        try:
            scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Build update data
    order_type = _form_enum(ServiceOrderType, form, "order_type", order.order_type)
    priority = _form_enum(ServiceOrderPriority, form, "priority", order.priority)

    data = ServiceOrderUpdateData(
        title=title,
        description=_form_str(form, "description") or None,
        order_type=order_type.value,
        priority=priority.value,
        service_address=service_address,
        city=_form_str(form, "city") or None,
        state=_form_str(form, "state") or None,
        postal_code=_form_str(form, "postal_code") or None,
        scheduled_date=scheduled_date,
        customer_contact_name=_form_str(form, "customer_contact_name") or None,
        customer_contact_phone=_form_str(form, "customer_contact_phone") or None,
        assigned_technician_id=_form_int(form, "assigned_technician_id"),
        assigned_team_id=_form_int(form, "assigned_team_id"),
    )

    try:
        order = service.update_order(order_id, data)
        db.commit()
        set_flash(response, f"Service order '{order.order_number}' updated successfully.", "success")
        return RedirectResponse(url=f"/field-service/{order.id}", status_code=303)
    except ValidationError as e:
        errors["general"] = str(e)
        lookup = FieldServiceLookupService(db)
        customers, technicians, teams = _get_order_form_options(lookup)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {order.order_number}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Field Service", "href": "/field-service"},
            {"label": order.order_number, "href": f"/field-service/{order.id}"},
            {"label": "Edit"},
        ])
        context["order"] = order
        context["customers"] = customers
        context["technicians"] = technicians
        context["teams"] = teams
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors

        template = templates.get_template("modules/field_service/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.delete("/{order_id}", response_class=HTMLResponse, dependencies=[RequireFieldServiceWrite])
async def service_order_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    order_id: int,
):
    """Delete a service order."""
    service = ServiceOrderService(db)

    try:
        order = service.get_order(order_id)
        order_number = order.order_number
        service.cancel(order_id, "Deleted via web UI")
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service order not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Service order '{order_number}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Service order '{order_number}' deleted.", "success")
    return RedirectResponse(url="/field-service", status_code=303)


@router.get("/{order_id}/row", response_class=HTMLResponse, dependencies=[RequireFieldServiceRead])
async def service_order_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Single service order row partial for HTMX updates."""
    service = ServiceOrderService(db)

    try:
        order = service.get_order(order_id)
    except NotFoundError:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["order"] = order

    template = templates.get_template("modules/field_service/templates/partials/order_row.html")
    return HTMLResponse(template.render(context))

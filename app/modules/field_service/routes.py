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
from sqlalchemy import func, or_, true

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.field_service import (
    ServiceOrder, ServiceOrderType, ServiceOrderStatus, ServiceOrderPriority,
    FieldTeam, FieldTeamMember, ServiceZone, TechnicianSkill
)
from app.models.party import CustomerAccount, Party
from app.models.employee import Employee, EmploymentStatus
from app.core.security import is_htmx_request, htmx_toast, set_flash

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


def generate_order_number(db) -> str:
    """Generate a unique order number."""
    today = date.today()
    prefix = f"SO-{today.strftime('%Y%m%d')}"

    # Count existing orders today
    count = db.query(ServiceOrder).filter(
        ServiceOrder.order_number.like(f"{prefix}%")
    ).count()

    return f"{prefix}-{count + 1:04d}"


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

    # Order Stats
    total_orders = db.query(func.count(ServiceOrder.id)).scalar() or 0

    today_scheduled = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.scheduled_date == today
    ).scalar() or 0

    in_progress = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([
            ServiceOrderStatus.EN_ROUTE,
            ServiceOrderStatus.ON_SITE,
            ServiceOrderStatus.IN_PROGRESS
        ])
    ).scalar() or 0

    pending_dispatch = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status.in_([ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED])
    ).scalar() or 0

    completed_today = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
        func.date(ServiceOrder.actual_end_time) == today
    ).scalar() or 0

    # Orders by status
    status_counts = db.query(
        ServiceOrder.status,
        func.count(ServiceOrder.id).label("count")
    ).group_by(ServiceOrder.status).all()

    status_distribution = [
        {"status": s[0].value, "count": s[1]}
        for s in status_counts
    ]

    # Orders by priority
    priority_counts = db.query(
        ServiceOrder.priority,
        func.count(ServiceOrder.id).label("count")
    ).group_by(ServiceOrder.priority).all()

    priority_distribution = [
        {"priority": p[0].value, "count": p[1]}
        for p in priority_counts
    ]

    # Today's schedule
    todays_orders = db.query(ServiceOrder).filter(
        ServiceOrder.scheduled_date == today
    ).order_by(ServiceOrder.scheduled_start_time).limit(10).all()

    # Active teams
    teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()
    team_stats = []
    for team in teams:
        member_count = db.query(func.count(FieldTeamMember.id)).filter(
            FieldTeamMember.team_id == team.id,
            FieldTeamMember.is_active == True
        ).scalar() or 0
        active_orders = db.query(func.count(ServiceOrder.id)).filter(
            ServiceOrder.assigned_team_id == team.id,
            ServiceOrder.status.in_([
                ServiceOrderStatus.SCHEDULED,
                ServiceOrderStatus.DISPATCHED,
                ServiceOrderStatus.EN_ROUTE,
                ServiceOrderStatus.ON_SITE,
                ServiceOrderStatus.IN_PROGRESS
            ])
        ).scalar() or 0
        team_stats.append({
            "id": team.id,
            "name": team.name,
            "members": member_count,
            "active_orders": active_orders
        })

    # Recent completions
    recent_completions = db.query(ServiceOrder).filter(
        ServiceOrder.status == ServiceOrderStatus.COMPLETED
    ).order_by(ServiceOrder.actual_end_time.desc()).limit(5).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Field Service Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Field Service"},
    ])

    context["stats"] = {
        "total_orders": total_orders,
        "today_scheduled": today_scheduled,
        "in_progress": in_progress,
        "pending_dispatch": pending_dispatch,
        "completed_today": completed_today,
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
    query = db.query(ServiceOrder)

    # Search
    if q:
        search_filter = or_(
            ServiceOrder.order_number.ilike(f"%{q}%"),
            ServiceOrder.title.ilike(f"%{q}%"),
            ServiceOrder.service_address.ilike(f"%{q}%"),
            ServiceOrder.city.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(ServiceOrder.status == status)
    if priority:
        query = query.filter(ServiceOrder.priority == priority)
    if type:
        query = query.filter(ServiceOrder.order_type == type)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(ServiceOrder, sort, ServiceOrder.scheduled_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    orders = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["orders"] = orders
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_type"] = type
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    customers = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .limit(100)
        .all()
    )
    technicians = db.query(Employee).filter(Employee.is_deleted == False).limit(100).all()
    teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()

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
    customer_account_id = _form_int(form, "customer_id")

    if not title:
        errors["title"] = "Title is required"
    if not service_address:
        errors["service_address"] = "Service address is required"
    if customer_account_id is None:
        errors["customer_id"] = "Customer is required"

    if errors:
        customers = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(100)
            .all()
        )
        technicians = db.query(Employee).filter(Employee.is_deleted == False).limit(100).all()
        teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()

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

    # Create service order
    order = ServiceOrder(
        order_number=generate_order_number(db),
        title=title,
        description=_form_str(form, "description") or None,
        order_type=_form_enum(ServiceOrderType, form, "order_type", ServiceOrderType.REPAIR),
        status=_form_enum(ServiceOrderStatus, form, "status", ServiceOrderStatus.DRAFT),
        priority=_form_enum(ServiceOrderPriority, form, "priority", ServiceOrderPriority.MEDIUM),
        customer_account_id=customer_account_id,
        service_address=service_address,
        city=_form_str(form, "city") or None,
        state=_form_str(form, "state") or None,
        postal_code=_form_str(form, "postal_code") or None,
        scheduled_date=scheduled_date,
        customer_contact_name=_form_str(form, "customer_contact_name") or None,
        customer_contact_phone=_form_str(form, "customer_contact_phone") or None,
        created_by=user.email if user else None,
    )

    # Assign technician if provided
    technician_id = _form_int(form, "assigned_technician_id")
    if technician_id is not None:
        order.assigned_technician_id = technician_id

    # Assign team if provided
    team_id = _form_int(form, "assigned_team_id")
    if team_id is not None:
        order.assigned_team_id = team_id

    db.add(order)
    db.commit()
    db.refresh(order)

    set_flash(response, f"Service order '{order.order_number}' created successfully.", "success")
    return RedirectResponse(url=f"/field-service/{order.id}", status_code=303)


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
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Service order not found")

    # Load customer details
    customer = None
    if order.customer_account_id:
        customer = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .filter(CustomerAccount.id == order.customer_account_id)
            .first()
        )

    # Load technician (employee) details
    technician = None
    if order.assigned_technician_id:
        technician = db.query(Employee).filter(Employee.id == order.assigned_technician_id).first()

    # Load team details
    team = None
    if order.assigned_team_id:
        team = db.query(FieldTeam).filter(FieldTeam.id == order.assigned_team_id).first()

    # Load related project
    from app.models.project import Project
    related_project = None
    if order.project_id:
        related_project = db.query(Project).filter(Project.id == order.project_id).first()

    # Load related ticket
    from app.models.unified_ticket import UnifiedTicket
    related_ticket = None
    if order.ticket_id:
        related_ticket = db.query(UnifiedTicket).filter(UnifiedTicket.id == order.ticket_id).first()

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
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Service order not found")

    customers = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .limit(100)
        .all()
    )
    technicians = db.query(Employee).filter(Employee.is_deleted == False).limit(100).all()
    teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()

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
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
    ).first()

    if not order:
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
        customers = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(100)
            .all()
        )
        technicians = db.query(Employee).filter(Employee.is_deleted == False).limit(100).all()
        teams = db.query(FieldTeam).filter(FieldTeam.is_active == True).all()

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
    scheduled_date_str = _form_str(form, "scheduled_date")
    if scheduled_date_str:
        try:
            order.scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Update order
    order.title = title
    order.description = _form_str(form, "description") or None
    order.order_type = _form_enum(ServiceOrderType, form, "order_type", order.order_type)
    order.status = _form_enum(ServiceOrderStatus, form, "status", order.status)
    order.priority = _form_enum(ServiceOrderPriority, form, "priority", order.priority)
    order.service_address = service_address
    order.city = _form_str(form, "city") or None
    order.state = _form_str(form, "state") or None
    order.postal_code = _form_str(form, "postal_code") or None
    order.customer_contact_name = _form_str(form, "customer_contact_name") or None
    order.customer_contact_phone = _form_str(form, "customer_contact_phone") or None

    # Assign technician
    technician_id = _form_int(form, "assigned_technician_id")
    order.assigned_technician_id = technician_id

    # Assign team
    team_id = _form_int(form, "assigned_team_id")
    order.assigned_team_id = team_id

    db.commit()

    set_flash(response, f"Service order '{order.order_number}' updated successfully.", "success")
    return RedirectResponse(url=f"/field-service/{order.id}", status_code=303)


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
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Service order not found")

    order_number = order.order_number
    db.delete(order)
    db.commit()

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
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
    ).first()

    if not order:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["order"] = order

    template = templates.get_template("modules/field_service/templates/partials/order_row.html")
    return HTMLResponse(template.render(context))


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
    query = db.query(FieldTeam)

    if q:
        query = query.filter(FieldTeam.name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * per_page
    teams = query.order_by(FieldTeam.name).offset(offset).limit(per_page).all()

    # Get member counts for each team
    teams_with_counts = []
    for team in teams:
        member_count = db.query(func.count(FieldTeamMember.id)).filter(
            FieldTeamMember.team_id == team.id,
            FieldTeamMember.is_active == True
        ).scalar() or 0
        teams_with_counts.append({
            "team": team,
            "member_count": member_count
        })

    context = get_base_context(request, response, user, csrf_token)
    context["teams"] = teams_with_counts
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    supervisors = db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE
    ).limit(100).all()
    zones = db.query(ServiceZone).filter(ServiceZone.is_active == True).all()

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
        supervisors = db.query(Employee).filter(
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE
        ).limit(100).all()
        zones = db.query(ServiceZone).filter(ServiceZone.is_active == True).all()

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

    team = FieldTeam(
        name=name,
        description=_form_str(form, "description") or None,
        contact_phone=_form_str(form, "contact_phone") or None,
        contact_email=_form_str(form, "contact_email") or None,
        max_daily_orders=_form_int(form, "max_daily_orders", 10) or 10,
        is_active=form.get("is_active") == "on",
    )

    supervisor_id = _form_int(form, "supervisor_id")
    if supervisor_id is not None:
        team.supervisor_id = supervisor_id

    db.add(team)
    db.commit()
    db.refresh(team)

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
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get members with employee info
    members = db.query(FieldTeamMember).filter(
        FieldTeamMember.team_id == team_id
    ).all()

    # Get available employees to add
    member_employee_ids = [m.employee_id for m in members]
    available_employees = db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE,
        ~Employee.id.in_(member_employee_ids) if member_employee_ids else true()
    ).limit(50).all()

    # Get team's active orders
    active_orders = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_team_id == team_id,
        ServiceOrder.status.in_([
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.EN_ROUTE,
            ServiceOrderStatus.ON_SITE,
            ServiceOrderStatus.IN_PROGRESS
        ])
    ).order_by(ServiceOrder.scheduled_date).limit(10).all()

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
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    supervisors = db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE
    ).limit(100).all()
    zones = db.query(ServiceZone).filter(ServiceZone.is_active == True).all()

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
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    form = await request.form()

    errors = {}
    name = _form_str(form, "name")
    if not name:
        errors["name"] = "Team name is required"

    if errors:
        supervisors = db.query(Employee).filter(
            Employee.is_deleted == False,
            Employee.status == EmploymentStatus.ACTIVE
        ).limit(100).all()
        zones = db.query(ServiceZone).filter(ServiceZone.is_active == True).all()

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

    team.name = name
    team.description = _form_str(form, "description") or None
    team.contact_phone = _form_str(form, "contact_phone") or None
    team.contact_email = _form_str(form, "contact_email") or None
    team.max_daily_orders = _form_int(form, "max_daily_orders", 10) or 10
    team.is_active = form.get("is_active") == "on"

    supervisor_id = _form_int(form, "supervisor_id")
    team.supervisor_id = supervisor_id

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
    """Delete a field team."""
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    name = team.name
    db.delete(team)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Team '{name}' deleted.", "success")
        response.headers["HX-Redirect"] = "/field-service/teams"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Team '{name}' deleted.", "success")
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
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    form = await request.form()
    employee_id = _form_int(form, "employee_id")
    role = form.get("role", "technician")

    if employee_id is None:
        set_flash(response, "Please select an employee.", "error")
        return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)

    # Check if already a member
    existing = db.query(FieldTeamMember).filter(
        FieldTeamMember.team_id == team_id,
        FieldTeamMember.employee_id == employee_id
    ).first()

    if existing:
        set_flash(response, "Employee is already a team member.", "error")
        return RedirectResponse(url=f"/field-service/teams/{team_id}", status_code=303)

    member = FieldTeamMember(
        team_id=team_id,
        employee_id=employee_id,
        role=role,
        is_active=True
    )
    db.add(member)
    db.commit()

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
    member = db.query(FieldTeamMember).filter(
        FieldTeamMember.id == member_id,
        FieldTeamMember.team_id == team_id
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
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
    # Get employees who are field team members
    query = db.query(Employee).join(
        FieldTeamMember, FieldTeamMember.employee_id == Employee.id
    ).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE
    ).distinct()

    if q:
        query = query.filter(Employee.name.ilike(f"%{q}%"))

    total = query.count()
    offset = (page - 1) * per_page
    technicians = query.order_by(Employee.name).offset(offset).limit(per_page).all()

    # Get team memberships and skills for each technician
    technicians_with_info = []
    for tech in technicians:
        memberships = db.query(FieldTeamMember).filter(
            FieldTeamMember.employee_id == tech.id,
            FieldTeamMember.is_active == True
        ).all()

        skills = db.query(TechnicianSkill).filter(
            TechnicianSkill.employee_id == tech.id,
            TechnicianSkill.is_active == True
        ).all()

        active_orders = db.query(func.count(ServiceOrder.id)).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.status.in_([
                ServiceOrderStatus.SCHEDULED,
                ServiceOrderStatus.DISPATCHED,
                ServiceOrderStatus.EN_ROUTE,
                ServiceOrderStatus.ON_SITE,
                ServiceOrderStatus.IN_PROGRESS
            ])
        ).scalar() or 0

        technicians_with_info.append({
            "employee": tech,
            "memberships": memberships,
            "skills": skills,
            "active_orders": active_orders
        })

    context = get_base_context(request, response, user, csrf_token)
    context["technicians"] = technicians_with_info
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.is_deleted == False
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Technician not found")

    # Get team memberships
    memberships = db.query(FieldTeamMember).filter(
        FieldTeamMember.employee_id == employee_id
    ).all()

    # Get skills
    skills = db.query(TechnicianSkill).filter(
        TechnicianSkill.employee_id == employee_id
    ).all()

    # Get recent orders
    recent_orders = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_technician_id == employee_id
    ).order_by(ServiceOrder.scheduled_date.desc()).limit(10).all()

    # Stats
    completed_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.assigned_technician_id == employee_id,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED
    ).scalar() or 0

    active_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.assigned_technician_id == employee_id,
        ServiceOrder.status.in_([
            ServiceOrderStatus.SCHEDULED,
            ServiceOrderStatus.DISPATCHED,
            ServiceOrderStatus.EN_ROUTE,
            ServiceOrderStatus.ON_SITE,
            ServiceOrderStatus.IN_PROGRESS
        ])
    ).scalar() or 0

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
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Technician not found")

    form = await request.form()
    skill_type = _form_str(form, "skill_type")
    proficiency_level = _form_str(form, "proficiency_level", "intermediate")

    if not skill_type:
        set_flash(response, "Skill type is required.", "error")
        return RedirectResponse(url=f"/field-service/technicians/{employee_id}", status_code=303)

    skill = TechnicianSkill(
        employee_id=employee_id,
        skill_type=skill_type,
        proficiency_level=proficiency_level,
        certification=_form_str(form, "certification") or None,
        is_active=True
    )
    db.add(skill)
    db.commit()

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
    skill = db.query(TechnicianSkill).filter(
        TechnicianSkill.id == skill_id,
        TechnicianSkill.employee_id == employee_id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    db.delete(skill)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Skill removed.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Skill removed.", "success")
    return RedirectResponse(url=f"/field-service/technicians/{employee_id}", status_code=303)

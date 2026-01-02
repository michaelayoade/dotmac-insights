"""
Support Routes - Ticket Management with SSR + HTMX.

This module provides SSR pages for support ticket management:
- Ticket list with filtering/search
- Ticket detail with conversation view
- Create/edit ticket forms

Permission Requirements:
- support:read - View tickets and ticket details
- support:write - Create, update, delete tickets
"""
from __future__ import annotations

# Import shared dependencies from _deps.py
from ._deps import (
    # FastAPI
    APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile,
    HTMLResponse, RedirectResponse,
    # SQLAlchemy
    func, or_, and_, joinedload,
    # Web dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    # Templates
    templates,
    # Core utilities
    is_htmx_request, htmx_toast, set_flash,
    # Models
    UnifiedTicket, TicketStatus, TicketPriority, TicketType, TicketChannel, TicketSource,
    Agent, Team, TeamMember,
    CannedResponse, CannedResponseScope,
    SLAPolicy, SLATarget, BusinessCalendar,
    Employee, EmploymentStatus,
    Contact,
    # Permission dependencies
    RequireSupportRead, RequireSupportWrite,
    # Helper functions
    _form_str, _form_int,
    # Enum options
    get_status_options, get_priority_options, get_type_options,
    get_channel_options, get_source_options,
    get_agent_options, get_team_options, get_sla_policy_options,
    # Entity lists for forms
    get_agents, get_teams,
    # Date utilities
    datetime, timedelta,
    # Typing
    Optional, Any,
)

# Import service layer
from ._services import SupportWebService

# Routers
router = APIRouter(prefix="/support/tickets", tags=["support"])
dashboard_router = APIRouter(prefix="/support", tags=["support-dashboard"])
agents_router = APIRouter(prefix="/support/agents", tags=["support-agents"])
canned_router = APIRouter(prefix="/support/canned-responses", tags=["support-canned"])
sla_router = APIRouter(prefix="/support/sla", tags=["support-sla"])


# =============================================================================
# SUPPORT DASHBOARD
# =============================================================================

@dashboard_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def support_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support Dashboard with ticket overview stats."""
    service = SupportWebService(db, user_id=user.id)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get stats from service
    stats = service.get_dashboard_stats()
    agent_stats = service.get_agent_stats(limit=10)

    # Get recent and unassigned tickets from service
    recent_tickets = service.get_recent_tickets(limit=10)
    unassigned_tickets = service.list_tickets(
        status="open",
        page=1,
        per_page=5,
    )["items"]

    # Format distributions for template
    status_distribution = [
        {"status": status, "count": count}
        for status, count in stats["status_distribution"].items()
    ]
    priority_distribution = [
        {"priority": priority, "count": count}
        for priority, count in stats["priority_distribution"].items()
    ]

    # Created today (additional stat not in service)
    created_today = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.is_deleted == False,
        UnifiedTicket.created_at >= today
    ).scalar() or 0

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
    ])

    context["stats"] = {
        "total_open": stats["total_open"],
        "urgent_tickets": stats["urgent_tickets"],
        "resolved_today": stats["resolved_today"],
        "created_today": created_today,
    }
    context["status_distribution"] = status_distribution
    context["priority_distribution"] = priority_distribution
    context["recent_tickets"] = recent_tickets
    context["unassigned_tickets"] = unassigned_tickets
    context["agent_stats"] = agent_stats
    context["today"] = today

    template = templates.get_template("modules/support/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TICKET LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def tickets_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    assigned: Optional[str] = Query(None, description="Filter by assignment"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Ticket list page.

    Returns full page for normal requests, table partial for HTMX requests.
    """
    service = SupportWebService(db, user_id=user.id)

    # Handle special assignment filter
    assigned_to_id = None
    if assigned == "unassigned":
        # Will be handled in service - pass None and filter after
        pass

    # Get tickets using service
    result = service.list_tickets(
        q=q,
        status=status,
        priority=priority,
        page=page,
        per_page=per_page,
        sort=sort,
        dir=dir,
    )

    tickets = result["items"]
    total = result["total"]

    # Filter unassigned if needed (service doesn't handle this special case)
    if assigned == "unassigned":
        tickets = [t for t in tickets if t.assigned_to_id is None]

    # Get dashboard stats for the quick filters
    dashboard_stats = service.get_dashboard_stats()
    stats = {
        "open": dashboard_stats["status_distribution"].get("open", 0),
        "in_progress": dashboard_stats["status_distribution"].get("in_progress", 0),
        "urgent": dashboard_stats["urgent_tickets"],
        "resolved_today": dashboard_stats["resolved_today"],
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["tickets"] = tickets
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_assigned"] = assigned
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/tickets_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Tickets"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets"},
    ])

    template = templates.get_template("modules/support/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def tickets_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Ticket table partial for HTMX updates."""
    return await tickets_list(
        request, response, user, csrf_token, db,
        q, status, priority, assigned, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New ticket form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Ticket"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": "New Ticket"},
    ])
    context["ticket"] = None
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["channel_options"] = get_channel_options()
    context["agents"] = get_agents(db)
    context["teams"] = get_teams(db)
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new ticket."""
    form = await request.form()

    # Basic validation
    errors = {}
    subject = _form_str(form, "subject")
    description = _form_str(form, "description")

    if not subject:
        errors["subject"] = "Subject is required"
    if len(subject) > 500:
        errors["subject"] = "Subject must be 500 characters or less"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Ticket"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/tickets"},
            {"label": "Tickets", "href": "/support/tickets"},
            {"label": "New Ticket"},
        ])
        context["ticket"] = None
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["channel_options"] = get_channel_options()
        context["agents"] = get_agents(db)
        context["teams"] = get_teams(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/support/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Handle FK fields
    unified_contact_id = _form_str(form, "unified_contact_id")
    assigned_to_id = _form_str(form, "assigned_to_id")
    assigned_team = _form_str(form, "assigned_team")

    # Create ticket using service
    service = SupportWebService(db, user_id=user.id)
    ticket_data = {
        "subject": subject,
        "description": description or None,
        "ticket_type": form.get("ticket_type", TicketType.SUPPORT.value),
        "priority": form.get("priority", TicketPriority.MEDIUM.value),
        "status": TicketStatus.OPEN.value if hasattr(TicketStatus.OPEN, 'value') else "open",
        "source": TicketSource.INTERNAL.value if hasattr(TicketSource.INTERNAL, 'value') else "internal",
        "channel": form.get("channel") or None,
        "contact_name": _form_str(form, "contact_name") or None,
        "contact_email": _form_str(form, "contact_email") or None,
        "contact_phone": _form_str(form, "contact_phone") or None,
        "unified_contact_id": int(unified_contact_id) if unified_contact_id else None,
        "assigned_to_id": int(assigned_to_id) if assigned_to_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.create_ticket(ticket_data)

    set_flash(response, f"Ticket '{ticket.ticket_number}' created successfully.", "success")
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@router.get("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def ticket_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Ticket detail page."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Load related project
    from app.models.project import Project
    related_project = None
    project_id = getattr(ticket, "project_id", None)
    if project_id:
        related_project = db.query(Project).filter(
            Project.id == project_id,
            Project.is_deleted == False,
        ).first()

    # Load assigned employee
    assigned_employee = None
    if ticket.assigned_to_id:
        assigned_employee = db.query(Employee).filter(
            Employee.id == ticket.assigned_to_id
        ).first()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Ticket {ticket.ticket_number}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": ticket.ticket_number or f"#{ticket.id}"},
    ])
    context["ticket"] = ticket
    context["related_project"] = related_project
    context["assigned_employee"] = assigned_employee
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{ticket_id}/edit", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Ticket edit form page."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    ticket_label = ticket.ticket_number or f"#{ticket.id}"
    context["page_title"] = f"Edit Ticket {ticket_label}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": ticket_label, "href": f"/support/tickets/{ticket.id}"},
        {"label": "Edit"},
    ])
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["channel_options"] = get_channel_options()
    context["agents"] = get_agents(db)
    context["teams"] = get_teams(db)
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Update a ticket."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()

    # Basic validation
    errors = {}
    subject = _form_str(form, "subject")

    if not subject:
        errors["subject"] = "Subject is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        ticket_label = ticket.ticket_number or f"#{ticket.id}"
        context["page_title"] = f"Edit Ticket {ticket_label}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/tickets"},
            {"label": "Tickets", "href": "/support/tickets"},
            {"label": ticket_label, "href": f"/support/tickets/{ticket.id}"},
            {"label": "Edit"},
        ])
        context["ticket"] = ticket
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["channel_options"] = get_channel_options()
        context["agents"] = get_agents(db)
        context["teams"] = get_teams(db)
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Handle FK fields
    unified_contact_id = _form_str(form, "unified_contact_id")
    assigned_to_id = _form_str(form, "assigned_to_id")
    assigned_team = _form_str(form, "assigned_team")

    # Update ticket using service
    update_data = {
        "subject": subject,
        "description": _form_str(form, "description") or None,
        "ticket_type": form.get("ticket_type"),
        "priority": form.get("priority"),
        "status": form.get("status"),
        "channel": form.get("channel") or None,
        "contact_name": _form_str(form, "contact_name") or None,
        "contact_email": _form_str(form, "contact_email") or None,
        "contact_phone": _form_str(form, "contact_phone") or None,
        "resolution": _form_str(form, "resolution") or None,
        "unified_contact_id": int(unified_contact_id) if unified_contact_id else None,
        "assigned_to_id": int(assigned_to_id) if assigned_to_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.update_ticket(ticket_id, update_data)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    set_flash(response, f"Ticket '{ticket.ticket_number}' updated successfully.", "success")
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@router.delete("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Delete a ticket (soft delete)."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_number = ticket.ticket_number
    service.delete_ticket(ticket_id)

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Ticket '{ticket_number}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Ticket '{ticket_number}' deleted.", "success")
    return RedirectResponse(url="/support/tickets", status_code=303)


@router.post("/{ticket_id}/status", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_update_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Quick status update via HTMX."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        ticket = service.update_ticket(ticket_id, {"status": new_status})
        htmx_toast(response, f"Status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated ticket row
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


@router.get("/{ticket_id}/row", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def ticket_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Single ticket row partial for HTMX updates."""
    service = SupportWebService(db, user_id=user.id)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# KNOWLEDGE BASE ROUTES
# =============================================================================

from app.models.support_kb import KBArticle, KBCategory, ArticleStatus, ArticleVisibility

kb_router = APIRouter(prefix="/support/kb", tags=["support-kb"])


def get_article_status_options():
    """Get article status options for select dropdown."""
    return [
        {"value": s.value, "label": s.name.replace('_', ' ').title()}
        for s in ArticleStatus
    ]


def get_visibility_options():
    """Get visibility options for select dropdown."""
    return [
        {"value": v.value, "label": v.name.replace('_', ' ').title()}
        for v in ArticleVisibility
    ]


def get_kb_categories(db):
    """Get active KB categories for select dropdown."""
    return db.query(KBCategory).filter(
        KBCategory.is_active == True
    ).order_by(KBCategory.display_order, KBCategory.name).all()


@kb_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def kb_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("updated_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Knowledge base articles list page."""
    query = db.query(KBArticle)

    # Search
    if q:
        search_filter = or_(
            KBArticle.title.ilike(f"%{q}%"),
            KBArticle.content.ilike(f"%{q}%"),
            KBArticle.search_keywords.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(KBArticle.status == status)
    if category_id:
        query = query.filter(KBArticle.category_id == category_id)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(KBArticle, sort, KBArticle.updated_at)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    articles = query.offset(offset).limit(per_page).all()

    # Get categories for filter
    categories = get_kb_categories(db)

    # Stats
    stats = {
        "published": db.query(func.count(KBArticle.id)).filter(
            KBArticle.status == ArticleStatus.PUBLISHED.value
        ).scalar() or 0,
        "draft": db.query(func.count(KBArticle.id)).filter(
            KBArticle.status == ArticleStatus.DRAFT.value
        ).scalar() or 0,
        "total_views": db.query(func.sum(KBArticle.view_count)).scalar() or 0,
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["articles"] = articles
    context["stats"] = stats
    context["categories"] = categories
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_category_id"] = category_id
    context["status_options"] = get_article_status_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/kb_articles_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Knowledge Base"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
        {"label": "Knowledge Base"},
    ])

    template = templates.get_template("modules/support/templates/pages/kb_list.html")
    return HTMLResponse(template.render(context))


@kb_router.get("/table", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def kb_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("updated_at"),
    dir: str = Query("desc"),
):
    """KB articles table partial for HTMX updates."""
    return await kb_list(
        request, response, user, csrf_token, db,
        q, status, category_id, page, per_page, sort, dir
    )


@kb_router.get("/new", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def kb_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New KB article form page."""
    categories = get_kb_categories(db)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Article"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
        {"label": "Knowledge Base", "href": "/support/kb"},
        {"label": "New Article"},
    ])
    context["article"] = None
    context["categories"] = categories
    context["status_options"] = get_article_status_options()
    context["visibility_options"] = get_visibility_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/kb_form.html")
    return HTMLResponse(template.render(context))


@kb_router.post("", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def kb_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new KB article."""
    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    slug = _form_str(form, "slug")
    content = _form_str(form, "content")

    if not name:
        errors["name"] = "Title is required"
    if not slug:
        # Auto-generate slug from name
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not content:
        errors["content"] = "Content is required"

    # Check for duplicate slug
    existing = db.query(KBArticle).filter(KBArticle.slug == slug).first()
    if existing:
        errors["slug"] = "An article with this slug already exists"

    if errors:
        categories = get_kb_categories(db)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Article"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support"},
            {"label": "Knowledge Base", "href": "/support/kb"},
            {"label": "New Article"},
        ])
        context["article"] = None
        context["categories"] = categories
        context["status_options"] = get_article_status_options()
        context["visibility_options"] = get_visibility_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/support/templates/pages/kb_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Get category
    category_id = _form_str(form, "category_id")

    # Create article
    article = KBArticle(
        title=name,
        slug=slug,
        content=content,
        excerpt=_form_str(form, "excerpt") or None,
        category_id=int(category_id) if category_id else None,
        status=_form_str(form, "status", ArticleStatus.DRAFT.value),
        visibility=_form_str(form, "visibility", ArticleVisibility.PUBLIC.value),
        search_keywords=_form_str(form, "search_keywords") or None,
        created_by_id=user.id,
        updated_by_id=user.id,
    )

    # Set published_at if publishing
    if article.status == ArticleStatus.PUBLISHED.value:
        from datetime import datetime
        article.published_at = datetime.utcnow()

    db.add(article)
    db.commit()
    db.refresh(article)

    set_flash(response, f"Article '{article.title}' created successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/support/kb/{article.id}", status_code=303)


@kb_router.get("/categories", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def kb_categories(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """KB categories management page."""
    categories = db.query(KBCategory).order_by(
        KBCategory.display_order, KBCategory.name
    ).all()

    # Get article counts per category
    category_counts = {}
    for cat in categories:
        count = db.query(func.count(KBArticle.id)).filter(
            KBArticle.category_id == cat.id
        ).scalar() or 0
        category_counts[cat.id] = count

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "KB Categories"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
        {"label": "Knowledge Base", "href": "/support/kb"},
        {"label": "Categories"},
    ])
    context["categories"] = categories
    context["category_counts"] = category_counts
    context["visibility_options"] = get_visibility_options()

    template = templates.get_template("modules/support/templates/pages/kb_categories.html")
    return HTMLResponse(template.render(context))


@kb_router.get("/{article_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def kb_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    article_id: int,
):
    """KB article detail page."""
    article = db.query(KBArticle).options(
        joinedload(KBArticle.category)
    ).filter(KBArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Increment view count
    article.view_count += 1
    db.commit()

    # Get related articles
    related_articles = []
    if article.related_article_ids:
        related_articles = db.query(KBArticle).filter(
            KBArticle.id.in_(article.related_article_ids),
            KBArticle.status == ArticleStatus.PUBLISHED.value
        ).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = article.title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
        {"label": "Knowledge Base", "href": "/support/kb"},
        {"label": article.title},
    ])
    context["article"] = article
    context["related_articles"] = related_articles

    template = templates.get_template("modules/support/templates/pages/kb_detail.html")
    return HTMLResponse(template.render(context))


@kb_router.get("/{article_id}/edit", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def kb_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    article_id: int,
):
    """KB article edit form page."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    categories = get_kb_categories(db)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit: {article.title}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
        {"label": "Knowledge Base", "href": "/support/kb"},
        {"label": article.title, "href": f"/support/kb/{article.id}"},
        {"label": "Edit"},
    ])
    context["article"] = article
    context["categories"] = categories
    context["status_options"] = get_article_status_options()
    context["visibility_options"] = get_visibility_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/kb_form.html")
    return HTMLResponse(template.render(context))


@kb_router.post("/{article_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def kb_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    article_id: int,
):
    """Update a KB article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    slug = _form_str(form, "slug")
    content = _form_str(form, "content")

    if not name:
        errors["name"] = "Title is required"
    if not content:
        errors["content"] = "Content is required"

    # Check for duplicate slug (excluding current)
    if slug and slug != article.slug:
        existing = db.query(KBArticle).filter(
            KBArticle.slug == slug,
            KBArticle.id != article_id
        ).first()
        if existing:
            errors["slug"] = "An article with this slug already exists"

    if errors:
        categories = get_kb_categories(db)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit: {article.title}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support"},
            {"label": "Knowledge Base", "href": "/support/kb"},
            {"label": article.title, "href": f"/support/kb/{article.id}"},
            {"label": "Edit"},
        ])
        context["article"] = article
        context["categories"] = categories
        context["status_options"] = get_article_status_options()
        context["visibility_options"] = get_visibility_options()
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/kb_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Track if we're publishing for the first time
    was_not_published = article.status != ArticleStatus.PUBLISHED.value
    new_status = _form_str(form, "status", article.status)

    # Get category
    category_id = _form_str(form, "category_id")

    # Update article
    article.title = name
    if slug:
        article.slug = slug
    article.content = content
    article.excerpt = _form_str(form, "excerpt") or None
    article.category_id = int(category_id) if category_id else None
    article.status = new_status
    article.visibility = _form_str(form, "visibility", article.visibility)
    article.search_keywords = _form_str(form, "search_keywords") or None
    article.updated_by_id = user.id
    article.version += 1

    # Set published_at if publishing for the first time
    if was_not_published and new_status == ArticleStatus.PUBLISHED.value:
        from datetime import datetime
        article.published_at = datetime.utcnow()

    db.commit()

    set_flash(response, f"Article '{article.title}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/support/kb/{article.id}", status_code=303)


@kb_router.post("/{article_id}/delete", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def kb_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    article_id: int,
):
    """Delete a KB article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    name = article.title
    db.delete(article)
    db.commit()

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Article '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Article '{name}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/support/kb", status_code=303)


@kb_router.get("/{article_id}/row", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def kb_article_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    article_id: int,
):
    """Single KB article row partial for HTMX updates."""
    article = db.query(KBArticle).options(
        joinedload(KBArticle.category)
    ).filter(KBArticle.id == article_id).first()

    if not article:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["article"] = article

    template = templates.get_template("modules/support/templates/partials/kb_article_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# AGENTS MANAGEMENT
# =============================================================================

@agents_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def agents_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Support agents list page."""
    service = SupportWebService(db, user_id=user.id)

    # Use service to list agents
    active_only = status != "inactive" if status else None
    result = service.list_agents(
        active_only=active_only if active_only is not None else True,
        page=page,
        per_page=per_page,
    )

    agents = result["items"]
    total = result["total"]

    # Apply search filter (service doesn't support search yet)
    if q:
        agents = [a for a in agents if (
            (a.display_name and q.lower() in a.display_name.lower()) or
            (a.email and q.lower() in a.email.lower())
        )]
        total = len(agents)

    # Get agent stats from service
    agent_stats_list = service.get_agent_stats(limit=100)
    agent_stats = {
        stat["id"]: {"open_tickets": stat["open_tickets"]}
        for stat in agent_stats_list
    }

    # Stats
    all_agents = service.list_agents(active_only=False, page=1, per_page=1000)
    active_count = sum(1 for a in all_agents["items"] if a.is_active)
    stats = {
        "total": all_agents["total"],
        "active": active_count,
        "online": active_count,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["agents"] = agents
    context["agent_stats"] = agent_stats
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/agents_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Agents"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Agents"},
    ])

    template = templates.get_template("modules/support/templates/pages/agents_list.html")
    return HTMLResponse(template.render(context))


@agents_router.get("/{agent_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def agent_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    agent_id: int,
):
    """Agent detail page."""
    service = SupportWebService(db, user_id=user.id)
    agent = service.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get agent's tickets using service
    open_tickets_result = service.list_tickets(
        assigned_to_id=agent.employee_id,
        page=1,
        per_page=10,
        sort="created_at",
        dir="desc",
    )
    # Filter out closed/resolved tickets
    open_tickets = [t for t in open_tickets_result["items"]
                    if t.status not in ["closed", "resolved"]]

    # Get agent's team memberships (still using db for now - relationship data)
    team_memberships = db.query(TeamMember).options(
        joinedload(TeamMember.team)
    ).filter(TeamMember.agent_id == agent_id).all()

    # Stats
    open_count = len([t for t in service.list_tickets(
        assigned_to_id=agent.employee_id, page=1, per_page=1000
    )["items"] if t.status not in ["closed", "resolved"]])

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    all_tickets = service.list_tickets(
        assigned_to_id=agent.employee_id, page=1, per_page=1000
    )["items"]
    resolved_today = len([t for t in all_tickets
                          if t.status == "resolved" and t.updated_at and t.updated_at >= today])

    stats = {
        "open_tickets": open_count,
        "resolved_today": resolved_today,
        "teams": len(team_memberships),
    }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = agent.display_name or f"Agent {agent.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Agents", "href": "/support/agents"},
        {"label": agent.display_name or f"Agent {agent.id}"},
    ])
    context["agent"] = agent
    context["open_tickets"] = open_tickets
    context["team_memberships"] = team_memberships
    context["stats"] = stats

    template = templates.get_template("modules/support/templates/pages/agent_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# CANNED RESPONSES
# =============================================================================

def get_canned_scope_options():
    """Get scope options for canned responses."""
    return [
        {"value": s.value, "label": s.name.replace('_', ' ').title()}
        for s in CannedResponseScope
    ]


@canned_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def canned_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Canned responses list page."""
    service = SupportWebService(db, user_id=user.id)

    # Use service to list canned responses
    result = service.list_canned_responses(
        active_only=True,
        page=page,
        per_page=per_page,
    )

    responses = result["items"]
    total = result["total"]

    # Apply search filter (service doesn't support search yet)
    if q:
        q_lower = q.lower()
        responses = [r for r in responses if (
            (r.name and q_lower in r.name.lower()) or
            (r.shortcode and q_lower in r.shortcode.lower()) or
            (r.content and q_lower in r.content.lower())
        )]
        total = len(responses)

    # Apply scope filter (service doesn't support scope filter yet)
    if scope:
        responses = [r for r in responses if r.scope == scope]
        total = len(responses)

    # Stats - get all canned responses for counting
    all_responses = service.list_canned_responses(active_only=True, page=1, per_page=1000)["items"]
    stats = {
        "total": len(all_responses),
        "personal": len([r for r in all_responses if r.scope == CannedResponseScope.PERSONAL.value]),
        "team": len([r for r in all_responses if r.scope == CannedResponseScope.TEAM.value]),
        "global": len([r for r in all_responses if r.scope == CannedResponseScope.GLOBAL.value]),
    }

    context = get_base_context(request, response, user, csrf_token)
    context["responses"] = responses
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_scope"] = scope
    context["scope_options"] = get_canned_scope_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/canned_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Canned Responses"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Canned Responses"},
    ])

    template = templates.get_template("modules/support/templates/pages/canned_list.html")
    return HTMLResponse(template.render(context))


@canned_router.get("/new", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def canned_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New canned response form page."""
    # Get teams for scope selection
    teams = db.query(Team).filter(Team.is_active == True).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Canned Response"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Canned Responses", "href": "/support/canned-responses"},
        {"label": "New"},
    ])
    context["canned"] = None
    context["teams"] = teams
    context["scope_options"] = get_canned_scope_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/canned_form.html")
    return HTMLResponse(template.render(context))


@canned_router.post("", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def canned_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new canned response."""
    form = await request.form()
    teams = db.query(Team).filter(Team.is_active == True).all()

    # Validation
    errors = {}
    name = _form_str(form, "name")
    content = _form_str(form, "content")
    shortcode = _form_str(form, "shortcode")

    if not name:
        errors["name"] = "Title is required"
    if not content:
        errors["content"] = "Content is required"

    # Check for duplicate shortcode
    if shortcode:
        existing = db.query(CannedResponse).filter(
            CannedResponse.shortcode == shortcode,
            CannedResponse.is_active == True
        ).first()
        if existing:
            errors["shortcode"] = "This shortcode is already in use"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Canned Response"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/dashboard"},
            {"label": "Canned Responses", "href": "/support/canned-responses"},
            {"label": "New"},
        ])
        context["canned"] = None
        context["teams"] = teams
        context["scope_options"] = get_canned_scope_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/support/templates/pages/canned_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create canned response
    scope = _form_str(form, "scope") or CannedResponseScope.PERSONAL.value
    team_id = _form_str(form, "team_id")

    canned = CannedResponse(
        name=name,
        content=content,
        shortcode=shortcode or None,
        scope=scope,
        team_id=int(team_id) if team_id else None,
        created_by_id=user.id,
        is_active=True,
    )

    db.add(canned)
    db.commit()
    db.refresh(canned)

    set_flash(response, f"Canned response '{canned.name}' created successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/support/canned-responses", status_code=303)


@canned_router.get("/{canned_id}/edit", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def canned_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    canned_id: int,
):
    """Edit canned response form page."""
    canned = db.query(CannedResponse).filter(CannedResponse.id == canned_id).first()

    if not canned:
        raise HTTPException(status_code=404, detail="Canned response not found")

    teams = db.query(Team).filter(Team.is_active == True).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit: {canned.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Canned Responses", "href": "/support/canned-responses"},
        {"label": "Edit"},
    ])
    context["canned"] = canned
    context["teams"] = teams
    context["scope_options"] = get_canned_scope_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/canned_form.html")
    return HTMLResponse(template.render(context))


@canned_router.post("/{canned_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def canned_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    canned_id: int,
):
    """Update a canned response."""
    canned = db.query(CannedResponse).filter(CannedResponse.id == canned_id).first()

    if not canned:
        raise HTTPException(status_code=404, detail="Canned response not found")

    form = await request.form()
    teams = db.query(Team).filter(Team.is_active == True).all()

    # Validation
    errors = {}
    name = _form_str(form, "name")
    content = _form_str(form, "content")
    shortcode = _form_str(form, "shortcode")

    if not name:
        errors["name"] = "Title is required"
    if not content:
        errors["content"] = "Content is required"

    # Check for duplicate shortcode (excluding current)
    if shortcode and shortcode != canned.shortcode:
        existing = db.query(CannedResponse).filter(
            CannedResponse.shortcode == shortcode,
            CannedResponse.is_active == True,
            CannedResponse.id != canned_id
        ).first()
        if existing:
            errors["shortcode"] = "This shortcode is already in use"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit: {canned.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/dashboard"},
            {"label": "Canned Responses", "href": "/support/canned-responses"},
            {"label": "Edit"},
        ])
        context["canned"] = canned
        context["teams"] = teams
        context["scope_options"] = get_canned_scope_options()
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/canned_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update canned response
    team_id = _form_str(form, "team_id")

    canned.name = name
    canned.content = content
    canned.shortcode = shortcode or None
    canned.scope = _form_str(form, "scope") or canned.scope
    canned.team_id = int(team_id) if team_id else None

    db.commit()

    set_flash(response, f"Canned response '{canned.name}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/support/canned-responses", status_code=303)


@canned_router.delete("/{canned_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def canned_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    canned_id: int,
):
    """Delete a canned response (soft delete)."""
    canned = db.query(CannedResponse).filter(CannedResponse.id == canned_id).first()

    if not canned:
        raise HTTPException(status_code=404, detail="Canned response not found")

    name = canned.name
    canned.is_active = False
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Canned response '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Canned response '{name}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/support/canned-responses", status_code=303)


# =============================================================================
# SLA POLICIES
# =============================================================================

@sla_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def sla_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """SLA policies list page."""
    service = SupportWebService(db, user_id=user.id)

    # Use service to list SLA policies
    result = service.list_sla_policies(
        active_only=False,  # Show all policies
        page=page,
        per_page=per_page,
    )

    policies = result["items"]
    total = result["total"]

    # Apply search filter (service doesn't support search yet)
    if q:
        q_lower = q.lower()
        policies = [p for p in policies if (
            (p.name and q_lower in p.name.lower()) or
            (p.description and q_lower in p.description.lower())
        )]
        total = len(policies)

    # Sort by priority desc, name
    policies = sorted(policies, key=lambda p: (-getattr(p, 'priority', 0), p.name or ""))

    # Get targets per policy (still using db for relationship data)
    policy_targets = {}
    for policy in policies:
        targets = db.query(SLATarget).filter(SLATarget.policy_id == policy.id).all()
        policy_targets[policy.id] = targets

    # Stats - get all policies for counting
    all_policies = service.list_sla_policies(active_only=False, page=1, per_page=1000)["items"]
    stats = {
        "total": len(all_policies),
        "active": len([p for p in all_policies if p.is_active]),
    }

    context = get_base_context(request, response, user, csrf_token)
    context["policies"] = policies
    context["policy_targets"] = policy_targets
    context["stats"] = stats
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/sla_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "SLA Policies"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "SLA Policies"},
    ])

    template = templates.get_template("modules/support/templates/pages/sla_list.html")
    return HTMLResponse(template.render(context))


@sla_router.get("/{policy_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def sla_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    policy_id: int,
):
    """SLA policy detail page."""
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()

    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")

    # Get targets
    targets = db.query(SLATarget).filter(SLATarget.policy_id == policy_id).order_by(SLATarget.priority).all()

    # Get business calendar if assigned
    calendar = None
    if policy.calendar_id:
        calendar = db.query(BusinessCalendar).filter(
            BusinessCalendar.id == policy.calendar_id
        ).first()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = policy.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "SLA Policies", "href": "/support/sla"},
        {"label": policy.name},
    ])
    context["policy"] = policy
    context["targets"] = targets
    context["calendar"] = calendar

    template = templates.get_template("modules/support/templates/pages/sla_detail.html")
    return HTMLResponse(template.render(context))


@sla_router.get("/calendars", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def sla_calendars(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Business calendars list page."""
    calendars = db.query(BusinessCalendar).order_by(BusinessCalendar.name).all()

    # Get policy counts per calendar
    calendar_usage = {}
    for cal in calendars:
        count = db.query(func.count(SLAPolicy.id)).filter(
            SLAPolicy.calendar_id == cal.id
        ).scalar() or 0
        calendar_usage[cal.id] = count

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Business Calendars"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "SLA Policies", "href": "/support/sla"},
        {"label": "Calendars"},
    ])
    context["calendars"] = calendars
    context["calendar_usage"] = calendar_usage

    template = templates.get_template("modules/support/templates/pages/sla_calendars.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# AUTOMATION RULES
# =============================================================================

automation_router = APIRouter(prefix="/support/automation", tags=["support-automation"])


@automation_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def automation_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    trigger: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    """Automation rules list page."""
    from app.models.support_automation import (
        AutomationRule,
        AutomationLog,
        AutomationTrigger,
        AutomationActionType,
    )

    # Build query
    query = db.query(AutomationRule)

    if trigger:
        query = query.filter(AutomationRule.trigger == trigger)
    if active_only:
        query = query.filter(AutomationRule.is_active == True)

    rules = query.order_by(AutomationRule.priority, AutomationRule.name).all()

    # Get execution stats
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    execution_stats = db.query(
        AutomationLog.rule_id,
        func.count(AutomationLog.id).label("total"),
        func.sum(func.cast(AutomationLog.success, func.literal(1).type)).label("success"),
    ).filter(
        AutomationLog.created_at >= thirty_days_ago
    ).group_by(AutomationLog.rule_id).all()

    stats_map = {
        row.rule_id: {"total": row.total, "success": row.success or 0}
        for row in execution_stats
    }

    # Summary stats
    total_rules = len(rules)
    active_rules = sum(1 for r in rules if r.is_active)
    total_executions = sum(s["total"] for s in stats_map.values())

    # Trigger options
    trigger_options = [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in AutomationTrigger
    ]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Automation Rules"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Automation"},
    ])

    context["rules"] = rules
    context["stats_map"] = stats_map
    context["summary"] = {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "total_executions": total_executions,
    }
    context["trigger_options"] = trigger_options
    context["trigger_filter"] = trigger or ""
    context["active_only"] = active_only

    template = templates.get_template("modules/support/templates/pages/automation_list.html")
    return HTMLResponse(template.render(context))


@automation_router.get("/{rule_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def automation_detail(
    rule_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Automation rule detail page."""
    from app.models.support_automation import (
        AutomationRule,
        AutomationLog,
        AutomationTrigger,
        AutomationActionType,
    )

    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()

    if not rule:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Automation rule not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get recent logs
    recent_logs = db.query(AutomationLog).filter(
        AutomationLog.rule_id == rule_id
    ).order_by(AutomationLog.created_at.desc()).limit(20).all()

    # Get execution stats for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats = db.query(
        func.count(AutomationLog.id).label("total"),
        func.sum(func.cast(AutomationLog.success, func.literal(1).type)).label("success"),
        func.avg(AutomationLog.execution_time_ms).label("avg_time"),
    ).filter(
        AutomationLog.rule_id == rule_id,
        AutomationLog.created_at >= thirty_days_ago,
    ).first()

    # Reference data for display
    trigger_labels = {t.value: t.value.replace("_", " ").title() for t in AutomationTrigger}
    action_labels = {a.value: a.value.replace("_", " ").title() for a in AutomationActionType}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Rule: {rule.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Automation", "href": "/support/automation"},
        {"label": rule.name},
    ])

    context["rule"] = rule
    context["recent_logs"] = recent_logs
    context["stats"] = {
        "total": stats.total if stats else 0,
        "success": stats.success or 0 if stats else 0,
        "success_rate": round((stats.success or 0) / stats.total * 100, 1) if stats and stats.total > 0 else 0,
        "avg_time_ms": round(float(stats.avg_time or 0), 1) if stats else 0,
    }
    context["trigger_labels"] = trigger_labels
    context["action_labels"] = action_labels

    template = templates.get_template("modules/support/templates/pages/automation_detail.html")
    return HTMLResponse(template.render(context))


@automation_router.post("/{rule_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def automation_toggle(
    rule_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Toggle automation rule active status."""
    from app.models.support_automation import AutomationRule

    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()

    if not rule:
        htmx_toast(response, "Rule not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

    rule.is_active = not rule.is_active
    db.commit()

    status_text = "enabled" if rule.is_active else "disabled"

    # Return HTMX response to refresh the page
    return HTMLResponse(
        "",
        headers={
            "HX-Redirect": f"/support/automation/{rule_id}",
            "HX-Trigger": f'{{"showToast": {{"message": "Rule {status_text}", "type": "success"}}}}'
        }
    )


# =============================================================================
# CSAT SURVEYS
# =============================================================================

csat_router = APIRouter(prefix="/support/csat", tags=["support-csat"])


@csat_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def csat_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    active_only: bool = Query(True),
):
    """CSAT surveys list page."""
    from app.models.support_csat import CSATSurvey, CSATResponse, SurveyType, SurveyTrigger

    # Build query
    query = db.query(CSATSurvey)
    if active_only:
        query = query.filter(CSATSurvey.is_active == True)

    surveys = query.order_by(CSATSurvey.name).all()

    # Get response stats for each survey
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats_query = db.query(
        CSATResponse.survey_id,
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
        func.sum(func.cast(CSATResponse.rating >= 4, func.literal(1).type)).label("positive"),
    ).filter(
        CSATResponse.responded_at >= thirty_days_ago,
        CSATResponse.rating.isnot(None),
    ).group_by(CSATResponse.survey_id).all()

    stats_map = {
        row.survey_id: {
            "total": row.total,
            "avg_rating": round(float(row.avg_rating or 0), 2),
            "positive": row.positive or 0,
        }
        for row in stats_query
    }

    # Overall stats
    overall_stats = db.query(
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).filter(
        CSATResponse.responded_at >= thirty_days_ago,
        CSATResponse.rating.isnot(None),
    ).first()

    # Sent vs responded (response rate)
    sent_count = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.sent_at >= thirty_days_ago
    ).scalar() or 0
    responded_count = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.responded_at >= thirty_days_ago
    ).scalar() or 0

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CSAT Surveys"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "CSAT"},
    ])

    context["surveys"] = surveys
    context["stats_map"] = stats_map
    context["summary"] = {
        "total_surveys": len(surveys),
        "active_surveys": sum(1 for s in surveys if s.is_active),
        "total_responses": overall_stats.total if overall_stats else 0,
        "avg_rating": round(float(overall_stats.avg_rating or 0), 2) if overall_stats else 0,
        "response_rate": round(responded_count / sent_count * 100, 1) if sent_count > 0 else 0,
    }
    context["active_only"] = active_only

    # Type labels
    context["type_labels"] = {t.value: t.value.upper() for t in SurveyType}
    context["trigger_labels"] = {t.value: t.value.replace("_", " ").title() for t in SurveyTrigger}

    template = templates.get_template("modules/support/templates/pages/csat_list.html")
    return HTMLResponse(template.render(context))


@csat_router.get("/{survey_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def csat_detail(
    survey_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """CSAT survey detail page with responses."""
    from app.models.support_csat import CSATSurvey, CSATResponse, SurveyType, SurveyTrigger

    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()

    if not survey:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Survey not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get responses
    responses = db.query(CSATResponse).filter(
        CSATResponse.survey_id == survey_id,
        CSATResponse.responded_at.isnot(None),
    ).order_by(CSATResponse.responded_at.desc()).limit(50).all()

    # Get stats
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats = db.query(
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
        func.sum(func.cast(CSATResponse.rating >= 4, func.literal(1).type)).label("positive"),
        func.sum(func.cast(CSATResponse.rating <= 2, func.literal(1).type)).label("negative"),
    ).filter(
        CSATResponse.survey_id == survey_id,
        CSATResponse.responded_at >= thirty_days_ago,
        CSATResponse.rating.isnot(None),
    ).first()

    # Rating distribution
    rating_dist = db.query(
        CSATResponse.rating,
        func.count(CSATResponse.id).label("count"),
    ).filter(
        CSATResponse.survey_id == survey_id,
        CSATResponse.responded_at >= thirty_days_ago,
        CSATResponse.rating.isnot(None),
    ).group_by(CSATResponse.rating).all()

    rating_distribution = {row.rating: row.count for row in rating_dist}

    # Reference labels
    type_labels = {t.value: t.value.upper() for t in SurveyType}
    trigger_labels = {t.value: t.value.replace("_", " ").title() for t in SurveyTrigger}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Survey: {survey.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "CSAT", "href": "/support/csat"},
        {"label": survey.name},
    ])

    context["survey"] = survey
    context["responses"] = responses
    context["stats"] = {
        "total": stats.total if stats else 0,
        "avg_rating": round(float(stats.avg_rating or 0), 2) if stats else 0,
        "positive": stats.positive or 0 if stats else 0,
        "negative": stats.negative or 0 if stats else 0,
        "satisfaction_pct": round((stats.positive or 0) / stats.total * 100, 1) if stats and stats.total > 0 else 0,
    }
    context["rating_distribution"] = rating_distribution
    context["type_labels"] = type_labels
    context["trigger_labels"] = trigger_labels

    template = templates.get_template("modules/support/templates/pages/csat_detail.html")
    return HTMLResponse(template.render(context))


@csat_router.post("/{survey_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def csat_toggle(
    survey_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Toggle CSAT survey active status."""
    from app.models.support_csat import CSATSurvey

    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()

    if not survey:
        htmx_toast(response, "Survey not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

    survey.is_active = not survey.is_active
    db.commit()

    status_text = "enabled" if survey.is_active else "disabled"

    return HTMLResponse(
        "",
        headers={
            "HX-Redirect": f"/support/csat/{survey_id}",
            "HX-Trigger": f'{{"showToast": {{"message": "Survey {status_text}", "type": "success"}}}}'
        }
    )


# =============================================================================
# ROUTING RULES SSR ROUTER
# =============================================================================

routing_router = APIRouter(prefix="/support/routing", tags=["support-routing"])


@routing_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def routing_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    active_only: bool = Query(False),
    team_id: Optional[int] = Query(None),
):
    """Routing configuration page with rules, workload, and queue health."""
    from app.models.support_sla import RoutingRule, RoutingStrategy
    from app.models.agent import Agent, Team, TeamMember
    from app.models.unified_ticket import UnifiedTicket

    # Get routing rules
    query = db.query(RoutingRule)
    if active_only:
        query = query.filter(RoutingRule.is_active == True)
    if team_id:
        query = query.filter(RoutingRule.team_id == team_id)

    rules = query.order_by(RoutingRule.priority, RoutingRule.name).all()

    # Get teams for filter
    teams = db.query(Team).filter(Team.is_active == True).order_by(Team.name).all()

    # Get agent workload
    agents = db.query(Agent).filter(Agent.is_active == True).all()
    agent_workload: list[dict[str, Any]] = []
    for agent in agents:
        name = agent.display_name or agent.email
        capacity = agent.capacity or 10
        open_count = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
        ).scalar() or 0
        agent_workload.append({
            "id": agent.id,
            "name": agent.display_name or agent.email,
            "email": agent.email,
            "capacity": capacity,
            "load": open_count,
            "utilization": round(open_count / capacity * 100, 1) if capacity > 0 else 0,
            "available": max(0, capacity - open_count),
        })
    agent_workload.sort(key=lambda x: -float(x.get("utilization") or 0))

    # Queue health
    unassigned = db.query(func.count(Ticket.id)).filter(
        Ticket.assigned_to.is_(None),
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
    ).scalar() or 0

    total_open = db.query(func.count(Ticket.id)).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
    ).scalar() or 0

    total_capacity = sum(float(a.get("capacity") or 0) for a in agent_workload)
    total_load = sum(float(a.get("load") or 0) for a in agent_workload)

    queue_health = {
        "unassigned": unassigned,
        "total_open": total_open,
        "total_agents": len(agents),
        "total_capacity": total_capacity,
        "total_load": total_load,
        "utilization": round(total_load / total_capacity * 100, 1) if total_capacity > 0 else 0,
    }

    # Strategy labels
    strategy_options = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in RoutingStrategy
    ]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Routing Configuration"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Routing"},
    ])

    context["rules"] = rules
    context["teams"] = teams
    context["agent_workload"] = agent_workload
    context["queue_health"] = queue_health
    context["strategy_options"] = strategy_options
    context["active_only"] = active_only
    context["team_filter"] = team_id
    context["summary"] = {
        "total_rules": len(rules),
        "active_rules": sum(1 for r in rules if r.is_active),
    }

    template = templates.get_template("modules/support/templates/pages/routing.html")
    return HTMLResponse(template.render(context))


@routing_router.get("/{rule_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def routing_detail(
    rule_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Routing rule detail page."""
    from app.models.support_sla import RoutingRule, RoutingStrategy

    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()

    if not rule:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Routing rule not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Strategy labels
    strategy_labels = {s.value: s.value.replace("_", " ").title() for s in RoutingStrategy}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Rule: {rule.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Routing", "href": "/support/routing"},
        {"label": rule.name},
    ])

    context["rule"] = rule
    context["strategy_labels"] = strategy_labels

    template = templates.get_template("modules/support/templates/pages/routing_detail.html")
    return HTMLResponse(template.render(context))


@routing_router.post("/{rule_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def routing_toggle(
    rule_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Toggle routing rule active status."""
    from app.models.support_sla import RoutingRule

    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()

    if not rule:
        htmx_toast(response, "Rule not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

    rule.is_active = not rule.is_active
    db.commit()

    status_text = "enabled" if rule.is_active else "disabled"

    return HTMLResponse(
        "",
        headers={
            "HX-Redirect": f"/support/routing/{rule_id}",
            "HX-Trigger": f'{{"showToast": {{"message": "Rule {status_text}", "type": "success"}}}}'
        }
    )


# =============================================================================
# CONVERSATIONS SSR ROUTER
# =============================================================================

conversations_router = APIRouter(prefix="/support/conversations", tags=["support-conversations"])


@conversations_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def conversations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Conversations list page."""
    from app.models.conversation import Conversation, ConversationStatus, ConversationPriority

    offset = (page - 1) * per_page

    # Build query
    query = db.query(Conversation)

    if status:
        try:
            status_enum = ConversationStatus(status)
            query = query.filter(Conversation.status == status_enum)
        except ValueError:
            pass

    if channel:
        query = query.filter(Conversation.channel == channel)

    if q:
        search = f"%{q}%"
        query = query.filter(Conversation.subject.ilike(search))

    total = query.count()
    conversations = query.order_by(Conversation.last_activity_at.desc().nullslast()).offset(offset).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    # Get stats
    status_counts = {}
    for s in ConversationStatus:
        count = db.query(func.count(Conversation.id)).filter(Conversation.status == s).scalar() or 0
        status_counts[s.value] = count

    # Channel options
    channels = db.query(Conversation.channel).distinct().filter(Conversation.channel.isnot(None)).all()
    channel_options = [c[0] for c in channels if c[0]]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Conversations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Conversations"},
    ])

    context["conversations"] = conversations
    context["status_filter"] = status
    context["channel_filter"] = channel
    context["search_query"] = q or ""
    context["status_counts"] = status_counts
    context["channel_options"] = channel_options
    context["status_options"] = [{"value": s.value, "label": s.value.title()} for s in ConversationStatus]
    context["pagination"] = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }
    context["summary"] = {
        "total": total,
        "open": status_counts.get("open", 0),
        "pending": status_counts.get("pending", 0),
        "resolved": status_counts.get("resolved", 0),
    }

    template = templates.get_template("modules/support/templates/pages/conversations_list.html")
    return HTMLResponse(template.render(context))


@conversations_router.get("/{conversation_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def conversation_detail(
    conversation_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Conversation detail page."""
    from app.models.conversation import Conversation, ConversationStatus
    from app.models.customer import Customer

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Conversation not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get customer if linked
    customer = None
    if conversation.customer_id:
        customer = db.query(Customer).filter(Customer.id == conversation.customer_id).first()

    # Status labels
    status_labels = {s.value: s.value.title() for s in ConversationStatus}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Conversation #{conversation.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Conversations", "href": "/support/conversations"},
        {"label": f"#{conversation.id}"},
    ])

    context["conversation"] = conversation
    context["customer"] = customer
    context["status_labels"] = status_labels

    template = templates.get_template("modules/support/templates/pages/conversation_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# CSAT ANALYTICS
# =============================================================================

@csat_router.get("/analytics", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def csat_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    days: int = Query(30, ge=7, le=90),
):
    """CSAT Analytics - trends, by agent, satisfaction metrics."""
    from app.models.support_csat import CSATSurvey, CSATResponse, SurveyType
    from app.models.agent import Agent
    from sqlalchemy import extract

    start_dt = datetime.utcnow() - timedelta(days=days)
    six_months_ago = datetime.utcnow() - timedelta(days=180)

    # Overall stats
    overall = db.query(
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
        func.sum(func.cast(CSATResponse.rating >= 4, func.literal(1).type)).label("positive"),
        func.sum(func.cast(CSATResponse.rating <= 2, func.literal(1).type)).label("negative"),
    ).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
    ).first()

    # Response rate
    sent_count = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.sent_at >= start_dt
    ).scalar() or 0
    responded_count = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.responded_at >= start_dt
    ).scalar() or 0

    # Trends - monthly for last 6 months
    trends = db.query(
        extract('year', CSATResponse.responded_at).label('year'),
        extract('month', CSATResponse.responded_at).label('month'),
        func.count(CSATResponse.id).label('count'),
        func.avg(CSATResponse.rating).label('avg_rating'),
    ).filter(
        CSATResponse.responded_at >= six_months_ago,
        CSATResponse.rating.isnot(None),
    ).group_by(
        extract('year', CSATResponse.responded_at),
        extract('month', CSATResponse.responded_at)
    ).order_by(
        extract('year', CSATResponse.responded_at),
        extract('month', CSATResponse.responded_at)
    ).all()

    # By agent
    by_agent = db.query(
        CSATResponse.agent_id,
        Agent.display_name,
        func.count(CSATResponse.id).label("count"),
        func.avg(CSATResponse.rating).label("avg_rating"),
        func.sum(func.cast(CSATResponse.rating >= 4, func.literal(1).type)).label("positive"),
    ).join(Agent, Agent.id == CSATResponse.agent_id, isouter=True).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
        CSATResponse.agent_id.isnot(None),
    ).group_by(CSATResponse.agent_id, Agent.display_name).order_by(
        func.avg(CSATResponse.rating).desc()
    ).all()

    # By survey type
    by_type = db.query(
        CSATSurvey.survey_type,
        func.count(CSATResponse.id).label("count"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).join(CSATSurvey, CSATSurvey.id == CSATResponse.survey_id).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
    ).group_by(CSATSurvey.survey_type).all()

    # Recent feedback with comments
    recent_feedback = db.query(CSATResponse).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.feedback_text.isnot(None),
        CSATResponse.feedback_text != "",
    ).order_by(CSATResponse.responded_at.desc()).limit(20).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CSAT Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "CSAT", "href": "/support/csat"},
        {"label": "Analytics"},
    ])

    context["period_days"] = days
    context["stats"] = {
        "total_responses": overall.total if overall else 0,
        "avg_rating": round(float(overall.avg_rating or 0), 2) if overall else 0,
        "positive": overall.positive or 0 if overall else 0,
        "negative": overall.negative or 0 if overall else 0,
        "satisfaction_pct": round((overall.positive or 0) / overall.total * 100, 1) if overall and overall.total > 0 else 0,
        "response_rate": round(responded_count / sent_count * 100, 1) if sent_count > 0 else 0,
    }

    context["trends"] = [
        {
            "period": f"{int(t.year)}-{int(t.month):02d}",
            "count": t.count,
            "avg_rating": round(float(t.avg_rating or 0), 2),
        }
        for t in trends
    ]

    context["by_agent"] = [
        {
            "agent_id": a.agent_id,
            "agent_name": a.display_name or "Unknown",
            "count": a.count,
            "avg_rating": round(float(a.avg_rating or 0), 2),
            "satisfaction_pct": round((a.positive or 0) / a.count * 100, 1) if a.count > 0 else 0,
        }
        for a in by_agent
    ]

    context["by_type"] = [
        {
            "type": t.survey_type.upper() if t.survey_type else "Unknown",
            "count": t.count,
            "avg_rating": round(float(t.avg_rating or 0), 2),
        }
        for t in by_type
    ]

    context["recent_feedback"] = recent_feedback

    template = templates.get_template("modules/support/templates/pages/csat_analytics.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SLA BREACHES
# =============================================================================

@sla_router.get("/breaches", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def sla_breaches(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    days: int = Query(30, ge=7, le=90),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """SLA breaches list - tickets that breached SLA targets."""
    from app.models.ticket import Ticket, TicketStatus

    start_dt = datetime.utcnow() - timedelta(days=days)
    offset = (page - 1) * per_page

    # Get tickets that breached SLA (first response or resolution)
    breached_query = db.query(UnifiedTicket).filter(
        UnifiedTicket.created_at >= start_dt,
        or_(
            UnifiedTicket.response_sla_breached.is_(True),
            UnifiedTicket.resolution_sla_breached.is_(True),
        ),
    )

    total = breached_query.count()
    breached_tickets = breached_query.order_by(UnifiedTicket.created_at.desc()).offset(offset).limit(per_page).all()

    # Breach stats
    first_response_breaches = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.response_sla_breached == True,
        UnifiedTicket.created_at >= start_dt,
    ).scalar() or 0

    resolution_breaches = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.resolution_sla_breached == True,
        UnifiedTicket.created_at >= start_dt,
    ).scalar() or 0

    # Total tickets in period
    total_tickets = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.created_at >= start_dt
    ).scalar() or 1

    # By priority (if available)
    by_priority = db.query(
        UnifiedTicket.priority,
        func.count(UnifiedTicket.id).label("count"),
    ).filter(
        UnifiedTicket.created_at >= start_dt,
        or_(
            UnifiedTicket.response_sla_breached.is_(True),
            UnifiedTicket.resolution_sla_breached.is_(True),
        ),
    ).group_by(UnifiedTicket.priority).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "SLA Breaches"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "SLA", "href": "/support/sla"},
        {"label": "Breaches"},
    ])

    context["period_days"] = days
    context["tickets"] = breached_tickets
    context["pagination"] = build_pagination_context(page, per_page, total)

    context["stats"] = {
        "total_breaches": total,
        "first_response_breaches": first_response_breaches,
        "resolution_breaches": resolution_breaches,
        "breach_rate": round(total / total_tickets * 100, 2) if total_tickets > 0 else 0,
    }

    context["by_priority"] = [
        {"priority": p.priority or "Unknown", "count": p.count}
        for p in by_priority
    ]

    template = templates.get_template("modules/support/templates/pages/sla_breaches.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TEAMS
# =============================================================================

teams_router = APIRouter(prefix="/support/teams", tags=["support-teams"])


@teams_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def teams_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support teams list."""
    from app.models.agent import Agent, Team, TeamMember

    teams = db.query(Team).order_by(Team.name).all()

    # Get member counts and stats
    team_stats: dict[int, dict[str, Any]] = {}
    for team in teams:
        members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        member_count = len(members)
        agent_ids = [m.agent_id for m in members]
        agents = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
        active_agents = sum(1 for a in agents if a.is_active)
        total_capacity = sum(a.capacity or 0 for a in agents if a.is_active)
        team_stats[team.id] = {
            "member_count": member_count,
            "active_agents": active_agents,
            "total_capacity": total_capacity,
        }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Teams"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Teams"},
    ])

    context["teams"] = teams
    context["team_stats"] = team_stats
    context["summary"] = {
        "total_teams": len(teams),
        "active_teams": sum(1 for t in teams if t.is_active),
    }

    template = templates.get_template("modules/support/templates/pages/teams_list.html")
    return HTMLResponse(template.render(context))


@teams_router.get("/{team_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def team_detail(
    team_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Team detail page with members."""
    from app.models.agent import Agent, Team, TeamMember
    from app.models.ticket import Ticket, TicketStatus

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get members with agent details
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    agent_ids = [m.agent_id for m in members]
    agents = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []

    # Agent workload
    agent_workload: list[dict[str, Any]] = []
    for agent in agents:
        name = agent.display_name or agent.email
        open_tickets = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
        ).scalar() or 0
        agent_workload.append({
            "agent": agent,
            "open_tickets": open_tickets,
            "capacity": agent.capacity or 10,
            "utilization": round(open_tickets / (agent.capacity or 10) * 100, 1) if agent.capacity else 0,
        })

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = team.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Teams", "href": "/support/teams"},
        {"label": team.name},
    ])

    context["team"] = team
    context["agents"] = agent_workload
    context["stats"] = {
        "member_count": len(members),
        "active_agents": sum(1 for a in agents if a.is_active),
        "total_capacity": sum(a.capacity or 0 for a in agents if a.is_active),
    }

    template = templates.get_template("modules/support/templates/pages/team_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TAGS
# =============================================================================

tags_router = APIRouter(prefix="/support/tags", tags=["support-tags"])


@tags_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def tags_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support tags list."""
    from app.models.support import Tag, TicketTag
    from app.models.ticket import Ticket

    tags = db.query(Tag).order_by(Tag.name).all()

    # Get usage counts
    tag_usage: dict[int, int] = {}
    for tag in tags:
        count = db.query(func.count(TicketTag.ticket_id)).filter(
            TicketTag.tag_id == tag.id
        ).scalar() or 0
        tag_usage[tag.id] = count

    # Recent usage (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_usage_query = db.query(
        TicketTag.tag_id,
        func.count(TicketTag.ticket_id).label("count"),
    ).join(Ticket, Ticket.id == TicketTag.ticket_id).filter(
        Ticket.created_at >= thirty_days_ago
    ).group_by(TicketTag.tag_id).all()

    recent_usage = {row.tag_id: row.count for row in recent_usage_query}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Ticket Tags"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Tags"},
    ])

    context["tags"] = tags
    context["tag_usage"] = tag_usage
    context["recent_usage"] = recent_usage
    context["summary"] = {
        "total_tags": len(tags),
        "active_tags": sum(1 for t in tags if tag_usage.get(t.id, 0) > 0),
    }

    template = templates.get_template("modules/support/templates/pages/tags_list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# AUTOMATION LOGS
# =============================================================================

@automation_router.get("/logs", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def automation_logs(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    rule_id: Optional[int] = Query(None),
    success: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Automation execution logs."""
    from app.models.support_automation import AutomationRule, AutomationLog

    offset = (page - 1) * per_page

    query = db.query(AutomationLog)

    if rule_id:
        query = query.filter(AutomationLog.rule_id == rule_id)
    if success is not None:
        query = query.filter(AutomationLog.success == success)

    total = query.count()
    logs = query.order_by(AutomationLog.created_at.desc()).offset(offset).limit(per_page).all()

    # Get rules for filter dropdown
    rules = db.query(AutomationRule).order_by(AutomationRule.name).all()

    # Stats
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats_query = db.query(
        func.count(AutomationLog.id).label("total"),
        func.sum(func.cast(AutomationLog.success, func.literal(1).type)).label("success"),
        func.avg(AutomationLog.execution_time_ms).label("avg_time"),
    ).filter(AutomationLog.created_at >= thirty_days_ago)

    stats = stats_query.first()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Automation Logs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Automation", "href": "/support/automation"},
        {"label": "Logs"},
    ])

    context["logs"] = logs
    context["rules"] = rules
    context["rule_filter"] = rule_id
    context["success_filter"] = success
    context["pagination"] = build_pagination_context(page, per_page, total)

    context["stats"] = {
        "total_30d": stats.total if stats else 0,
        "success_30d": stats.success or 0 if stats else 0,
        "success_rate": round((stats.success or 0) / stats.total * 100, 1) if stats and stats.total > 0 else 0,
        "avg_time_ms": round(float(stats.avg_time or 0), 1) if stats else 0,
    }

    template = templates.get_template("modules/support/templates/pages/automation_logs.html")
    return HTMLResponse(template.render(context))

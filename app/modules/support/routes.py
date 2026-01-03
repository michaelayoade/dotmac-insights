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
    Party,
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
    # Party resolution
    resolve_party_for_ticket,
    # Date utilities
    datetime, timedelta,
    # Typing
    Optional, Any,
)

# Import service layer
from ._services import SupportWebService
from app.services.support import SupportAnalyticsService, AnalyticsFilters

# In-memory TTL cache for analytics
import time
from typing import Dict, Tuple

# Simple TTL cache for dashboard analytics (60 second TTL)
_analytics_cache: Dict[int, Tuple[float, dict]] = {}
_ANALYTICS_CACHE_TTL = 60  # seconds


def _get_cached_analytics(company_id: int) -> dict | None:
    """Get cached analytics if not expired."""
    if company_id in _analytics_cache:
        timestamp, data = _analytics_cache[company_id]
        if time.time() - timestamp < _ANALYTICS_CACHE_TTL:
            return data
        del _analytics_cache[company_id]
    return None


def _set_cached_analytics(company_id: int, data: dict) -> None:
    """Cache analytics data with TTL."""
    # Limit cache size to prevent memory issues
    if len(_analytics_cache) > 100:
        # Remove oldest entries
        oldest = sorted(_analytics_cache.items(), key=lambda x: x[1][0])[:50]
        for key, _ in oldest:
            del _analytics_cache[key]
    _analytics_cache[company_id] = (time.time(), data)

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
    """Support Dashboard with comprehensive analytics."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    analytics = SupportAnalyticsService(db, principal=user)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get basic stats from web service (for ticket lists)
    basic_stats = service.get_dashboard_stats()
    recent_tickets = service.get_recent_tickets(limit=10)
    unassigned_tickets = service.list_tickets(
        status="open",
        page=1,
        per_page=5,
    )["items"]

    # Get rich analytics from SupportAnalyticsService with graceful degradation
    # Check cache first for performance (60 second TTL per company)
    company_id = user.company_id if hasattr(user, "company_id") else 0
    cached_analytics = _get_cached_analytics(company_id)

    if cached_analytics:
        # Use cached data
        overview = cached_analytics["overview"]
        resolution_stats = cached_analytics["resolution_stats"]
        first_response_stats = cached_analytics["first_response_stats"]
        agent_performance = cached_analytics["agent_performance"]
        team_performance = cached_analytics["team_performance"]
        channel_breakdown = cached_analytics["channel_breakdown"]
        category_breakdown = cached_analytics["category_breakdown"]
        backlog_aging = cached_analytics["backlog_aging"]
        sla_performance = cached_analytics["sla_performance"]
        patterns = cached_analytics["patterns"]
    else:
        # Fetch fresh analytics data
        filters_30d = AnalyticsFilters(days=30)

        # Import default types for fallback
        from app.services.support.types import (
            OverviewStats, ResolutionTimeStats, FirstResponseStats,
            PatternInsights,
        )

        # Fetch with graceful degradation
        try:
            overview = analytics.get_overview(filters_30d)
        except Exception:
            overview = OverviewStats(
                total_tickets=0, open_tickets=0, resolved_tickets=0,
                closed_tickets=0, pending_tickets=0, avg_resolution_hours=0,
                avg_first_response_hours=0, sla_attainment_pct=0,
                csat_score=None, period_days=30,
            )

        try:
            resolution_stats = analytics.get_resolution_stats(filters_30d)
        except Exception:
            resolution_stats = ResolutionTimeStats(
                avg_hours=0, median_hours=0, p90_hours=0, p95_hours=0,
                min_hours=0, max_hours=0, sample_size=0,
            )

        try:
            first_response_stats = analytics.get_first_response_stats(filters_30d)
        except Exception:
            first_response_stats = FirstResponseStats(
                avg_hours=0, median_hours=0, p90_hours=0,
                within_sla_pct=0, sample_size=0,
            )

        try:
            agent_performance = analytics.get_agent_performance(filters_30d, limit=10)
        except Exception:
            agent_performance = []

        try:
            team_performance = analytics.get_team_performance(filters_30d)
        except Exception:
            team_performance = []

        try:
            channel_breakdown = analytics.get_channel_breakdown(filters_30d)
        except Exception:
            channel_breakdown = []

        try:
            category_breakdown = analytics.get_category_breakdown(filters_30d, category_field="ticket_type")
        except Exception:
            category_breakdown = []

        try:
            backlog_aging = analytics.get_backlog_aging(filters_30d)
        except Exception:
            backlog_aging = []

        try:
            sla_performance = analytics.get_sla_performance(filters_30d)
        except Exception:
            sla_performance = []

        try:
            patterns = analytics.get_pattern_insights(filters_30d)
        except Exception:
            patterns = PatternInsights(
                peak_hours=[], peak_days=[], busiest_period="N/A",
                quietest_period="N/A", by_region=[], seasonal_factors=[],
            )

        # Cache the results
        _set_cached_analytics(company_id, {
            "overview": overview,
            "resolution_stats": resolution_stats,
            "first_response_stats": first_response_stats,
            "agent_performance": agent_performance,
            "team_performance": team_performance,
            "channel_breakdown": channel_breakdown,
            "category_breakdown": category_breakdown,
            "backlog_aging": backlog_aging,
            "sla_performance": sla_performance,
            "patterns": patterns,
        })

    # Format distributions for template
    status_distribution = [
        {"status": status, "count": count}
        for status, count in basic_stats["status_distribution"].items()
    ]
    priority_distribution = [
        {"priority": priority, "count": count}
        for priority, count in basic_stats["priority_distribution"].items()
    ]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support"},
    ])

    # Basic ticket stats
    context["stats"] = {
        "total_open": basic_stats["total_open"],
        "urgent_tickets": basic_stats["urgent_tickets"],
        "resolved_today": basic_stats["resolved_today"],
        "created_today": basic_stats["created_today"],
        "response_overdue": basic_stats["response_overdue"],
        "resolution_overdue": basic_stats["resolution_overdue"],
    }

    # Rich analytics overview
    context["overview"] = {
        "total_tickets": overview.total_tickets,
        "open_tickets": overview.open_tickets,
        "resolved_tickets": overview.resolved_tickets,
        "closed_tickets": overview.closed_tickets,
        "pending_tickets": overview.pending_tickets,
        "avg_resolution_hours": overview.avg_resolution_hours,
        "avg_first_response_hours": overview.avg_first_response_hours,
        "sla_attainment_pct": overview.sla_attainment_pct,
        "csat_score": overview.csat_score,
    }

    # Resolution and response time stats
    context["resolution_stats"] = {
        "avg_hours": resolution_stats.avg_hours,
        "median_hours": resolution_stats.median_hours,
        "p90_hours": resolution_stats.p90_hours,
        "p95_hours": resolution_stats.p95_hours,
    }
    context["first_response_stats"] = {
        "avg_hours": first_response_stats.avg_hours,
        "median_hours": first_response_stats.median_hours,
        "p90_hours": first_response_stats.p90_hours,
        "within_sla_pct": first_response_stats.within_sla_pct,
    }

    # Agent performance with CSAT
    context["agent_performance"] = [
        {
            "agent_id": a.agent_id,
            "agent_name": a.agent_name,
            "team_name": a.team_name,
            "total_tickets": a.total_tickets,
            "resolved_tickets": a.resolved_tickets,
            "resolution_rate": a.resolution_rate,
            "avg_resolution_hours": a.avg_resolution_hours,
            "sla_attainment_pct": a.sla_attainment_pct,
            "csat_score": a.csat_score,
            "current_open": a.current_open,
            "capacity": a.capacity,
            "utilization_pct": a.utilization_pct,
        }
        for a in agent_performance
    ]

    # Team performance
    context["team_performance"] = [
        {
            "team_id": t.team_id,
            "team_name": t.team_name,
            "total_agents": t.total_agents,
            "active_agents": t.active_agents,
            "total_tickets": t.total_tickets,
            "resolution_rate": t.resolution_rate,
            "avg_resolution_hours": t.avg_resolution_hours,
            "sla_attainment_pct": t.sla_attainment_pct,
            "csat_score": t.csat_score,
            "utilization_pct": t.utilization_pct,
            "top_performers": t.top_performers,
        }
        for t in team_performance
    ]

    # Channel breakdown
    context["channel_breakdown"] = [
        {
            "channel": c.channel,
            "total_tickets": c.total_tickets,
            "resolution_rate": c.resolution_rate,
            "avg_resolution_hours": c.avg_resolution_hours,
            "pct_of_total": c.pct_of_total,
        }
        for c in channel_breakdown
    ]

    # Category breakdown
    context["category_breakdown"] = [
        {
            "category": c.category,
            "total_tickets": c.total_tickets,
            "resolution_rate": c.resolution_rate,
            "pct_of_total": c.pct_of_total,
        }
        for c in category_breakdown
    ]

    # Backlog aging
    context["backlog_aging"] = [
        {
            "age_bucket": b.age_bucket,
            "count": b.count,
            "pct_of_backlog": b.pct_of_backlog,
            "sla_at_risk": b.sla_at_risk,
        }
        for b in backlog_aging
    ]

    # SLA performance trend (last few periods)
    context["sla_trend"] = [
        {
            "period": s.period,
            "response_attainment_pct": s.response_attainment_pct,
            "resolution_attainment_pct": s.resolution_attainment_pct,
        }
        for s in sla_performance[-6:]  # Last 6 periods
    ]

    # Pattern insights
    context["patterns"] = {
        "peak_hours": patterns.peak_hours[:3],  # Top 3 peak hours
        "peak_days": patterns.peak_days[:3],  # Top 3 peak days
        "busiest_period": patterns.busiest_period,
        "quietest_period": patterns.quietest_period,
    }

    # Legacy context for existing template sections
    context["status_distribution"] = status_distribution
    context["priority_distribution"] = priority_distribution
    context["recent_tickets"] = recent_tickets
    context["unassigned_tickets"] = unassigned_tickets
    context["agent_stats"] = service.get_agent_stats(limit=10)  # Legacy format
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
    service = SupportWebService(db, user_id=user.id, principal=user)

    # Get tickets using service - unassigned filter handled at DB level for correct pagination
    result = service.list_tickets(
        q=q,
        status=status,
        priority=priority,
        unassigned_only=(assigned == "unassigned"),
        page=page,
        per_page=per_page,
        sort=sort,
        dir=dir,
    )

    tickets = result["items"]
    total = result["total"]

    # Get dashboard stats for the quick filters
    dashboard_stats = service.get_dashboard_stats()
    stats = {
        "open": dashboard_stats["status_distribution"].get("open", 0),
        "in_progress": dashboard_stats["status_distribution"].get("in_progress", 0),
        "waiting": dashboard_stats["status_distribution"].get("waiting", 0),
        "on_hold": dashboard_stats["status_distribution"].get("on_hold", 0),
        "reopened": dashboard_stats["status_distribution"].get("reopened", 0),
        "urgent": dashboard_stats["urgent_tickets"],
        "resolved_today": dashboard_stats["resolved_today"],
        "response_overdue": dashboard_stats["response_overdue"],
        "resolution_overdue": dashboard_stats["resolution_overdue"],
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
    party_id = _form_int(form, "party_id")
    contact_email = _form_str(form, "contact_email")
    contact_phone = _form_str(form, "contact_phone")
    contact_name = _form_str(form, "contact_name")

    # Create service early for party resolution
    service = SupportWebService(db, user_id=user.id, principal=user)

    # Resolve party - either from explicit ID or auto-resolve from contact info
    party = None
    if party_id:
        party = service.get_party(party_id)
    elif contact_email or contact_phone:
        # Auto-resolve party from contact email/phone
        party = resolve_party_for_ticket(db, email=contact_email, phone=contact_phone, name=contact_name)

    if not subject:
        errors["subject"] = "Subject is required"
    if len(subject) > 500:
        errors["subject"] = "Subject must be 500 characters or less"
    if not party and not party_id and not contact_email:
        errors["party_id"] = "Party or contact email is required"
    elif party_id and not party:
        errors["party_id"] = "Party not found"

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
    assigned_to_id = _form_str(form, "assigned_to_id")
    assigned_team = _form_str(form, "assigned_team")

    # Create ticket using service (service already created above for party resolution)
    ticket_data = {
        "subject": subject,
        "description": description or None,
        "ticket_type": form.get("ticket_type", TicketType.SUPPORT.value),
        "priority": form.get("priority", TicketPriority.MEDIUM.value),
        "status": TicketStatus.OPEN.value if hasattr(TicketStatus.OPEN, 'value') else "open",
        "source": TicketSource.INTERNAL.value if hasattr(TicketSource.INTERNAL, 'value') else "internal",
        "channel": form.get("channel") or None,
        "party_id": party.id if party else None,
        "contact_name": contact_name or (party.name if party else None),
        "contact_email": contact_email or (party.primary_email if party else None),
        "contact_phone": contact_phone or (party.primary_phone if party else None),
        "assigned_to_id": int(assigned_to_id) if assigned_to_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.create_ticket(ticket_data)
    db.commit()

    set_flash(response, f"Ticket '{ticket.ticket_number}' created successfully.", "success")
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@router.get("/parties/search", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def party_search(
    user: SessionUser,
    db: DB,
    q: str = Query(default=""),
):
    """Search parties for ticket contact linking."""
    query = (q or "").strip()
    parties = []
    if len(query) >= 2:
        service = SupportWebService(db, user_id=user.id, principal=user)
        parties = service.search_parties(query, limit=10)

    template = templates.get_template("modules/support/templates/partials/party_search_results.html")
    return HTMLResponse(template.render({"parties": parties, "query": query}))


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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()

    # Basic validation
    errors = {}
    subject = _form_str(form, "subject")
    party_id = _form_int(form, "party_id")
    party = None
    if party_id:
        party = db.query(Party).filter(Party.id == party_id).first()

    if not subject:
        errors["subject"] = "Subject is required"
    if not party_id:
        errors["party_id"] = "Party is required"
    elif not party:
        errors["party_id"] = "Party not found"

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
        "party_id": party.id if party else None,
        "contact_name": _form_str(form, "contact_name") or (party.name if party else None),
        "contact_email": _form_str(form, "contact_email") or (party.primary_email if party else None),
        "contact_phone": _form_str(form, "contact_phone") or (party.primary_phone if party else None),
        "resolution": _form_str(form, "resolution") or None,
        "assigned_to_id": int(assigned_to_id) if assigned_to_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.update_ticket(ticket_id, update_data)
    db.commit()

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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_number = ticket.ticket_number
    service.delete_ticket(ticket_id)
    db.commit()

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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        # Validate status value
        valid_statuses = [s.value for s in TicketStatus]
        if new_status not in valid_statuses:
            htmx_toast(response, f"Invalid status: {new_status}", "error")
            return HTMLResponse("", status_code=400, headers=dict(response.headers))

        ticket = service.update_ticket(ticket_id, {"status": new_status})
        db.commit()
        htmx_toast(response, f"Status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated ticket row
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

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
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context))


@router.patch("/{ticket_id}/inline/{field}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_inline_update(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    ticket_id: int,
    field: str,
):
    """Inline field update via HTMX PATCH - returns just the updated inline component."""
    from app.services.errors import NotFoundError, ValidationError as SvcValidationError

    service = SupportWebService(db, user_id=user.id, principal=user)

    # Get the new value from form data
    form = await request.form()
    new_value = _form_str(form, field)

    if not new_value:
        raise HTTPException(status_code=400, detail=f"Missing {field} value")

    # Use service layer for inline field update with validation
    try:
        ticket = service.update_field(ticket_id, field, new_value)
        db.commit()
    except SvcValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    htmx_toast(response, f"{field.title()} updated", "success")

    # Return the updated inline component
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template(f"modules/support/templates/partials/inline_{field}.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.post("/bulk-status", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def tickets_bulk_status(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    status: str = Query(..., description="Target status"),
):
    """Bulk update ticket status."""
    import json
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
        ids = data.get("ids", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not ids:
        raise HTTPException(status_code=400, detail="No ticket IDs provided")

    # Validate status
    try:
        target_status = TicketStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Use service layer for bulk update
    service = SupportWebService(db, user_id=user.id, principal=user)
    updated = service.bulk_update_status(ids, target_status)
    db.commit()

    htmx_toast(response, f"Updated {updated} tickets to {status.replace('_', ' ').title()}", "success")
    return HTMLResponse("", headers=dict(response.headers))


@router.delete("/bulk", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def tickets_bulk_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
):
    """Bulk delete tickets."""
    import json
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
        ids = data.get("ids", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not ids:
        raise HTTPException(status_code=400, detail="No ticket IDs provided")

    # Use service layer for bulk delete
    service = SupportWebService(db, user_id=user.id, principal=user)
    deleted = service.bulk_delete(ids)
    db.commit()

    htmx_toast(response, f"Deleted {deleted} tickets", "success")
    return HTMLResponse("", headers=dict(response.headers))


@router.get("/export", dependencies=[RequireSupportRead])
async def tickets_export(
    request: Request,
    db: DB,
    ids: list[int] = Query(None, description="Ticket IDs to export"),
):
    """Export tickets to CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    # Build query
    query = db.query(UnifiedTicket)
    if ids:
        query = query.filter(UnifiedTicket.id.in_(ids))
    tickets = query.order_by(UnifiedTicket.created_at.desc()).all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket Number", "Subject", "Status", "Priority", "Party ID", "Contact", "Assigned To", "Created At"])

    for ticket in tickets:
        writer.writerow([
            ticket.ticket_number,
            ticket.subject,
            ticket.status.value if ticket.status else "",
            ticket.priority.value if ticket.priority else "",
            ticket.party_id or "",
            ticket.contact_name or "",
            f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}" if ticket.assigned_to else "",
            ticket.created_at.isoformat() if ticket.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tickets.csv"}
    )


# =============================================================================
# TICKET ASSIGNMENT ROUTES
# =============================================================================


@router.get("/{ticket_id}/assign-modal", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_assign_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Return assignment modal content with agent/team selects."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get available agents and teams
    agents = get_agents(db)
    teams = get_teams(db)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket
    context["agents"] = agents
    context["teams"] = teams

    template = templates.get_template("modules/support/templates/partials/assign_modal.html")
    return HTMLResponse(template.render(context))


@router.post("/{ticket_id}/assign", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_assign(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Assign ticket to an agent and/or team."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    agent_id = _form_int(form, "agent_id")
    team_id = _form_int(form, "team_id")

    # Update assignment
    update_data = {}
    if agent_id is not None:
        update_data["assigned_to_id"] = agent_id if agent_id > 0 else None
    if team_id is not None:
        update_data["assigned_team_id"] = team_id if team_id > 0 else None

    if update_data:
        ticket = service.update_ticket(ticket_id, update_data)
        db.commit()

        # Get agent name for toast message
        if agent_id and agent_id > 0:
            agent = service.get_agent(agent_id)
            name = agent.display_name if agent else "an agent"
        else:
            name = "a team" if team_id else "unassigned"
        htmx_toast(response, f"Ticket assigned to {name}", "success")

    # Return updated ticket row
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


@router.post("/{ticket_id}/unassign", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_unassign(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Unassign ticket from agent and team."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = service.update_ticket(ticket_id, {
        "assigned_to_id": None,
        "assigned_team_id": None,
    })
    db.commit()

    htmx_toast(response, "Ticket unassigned", "success")

    # Return updated ticket row
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


# =============================================================================
# TICKET COMMENT/REPLY ROUTES
# =============================================================================


@router.post("/{ticket_id}/comment", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_add_comment(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Add a comment/reply to a ticket."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    body = _form_str(form, "body")
    is_public = _form_str(form, "is_public") == "true"

    if not body or not body.strip():
        htmx_toast(response, "Comment body is required", "error")
        return HTMLResponse("", status_code=400, headers=dict(response.headers))

    # Create comment using service
    service.add_comment(ticket_id, body.strip(), is_public=is_public)
    db.commit()

    htmx_toast(response, "Comment added", "success")

    # Return updated activity timeline
    return await ticket_activity(request, response, user, "", db, ticket_id)


@router.get("/{ticket_id}/comments", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def ticket_comments(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Get ticket comments as HTML partial."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    comments = service.get_comments(ticket_id)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket
    context["comments"] = comments

    template = templates.get_template("modules/support/templates/partials/comment_list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TICKET ACTIVITY TIMELINE
# =============================================================================


@router.get("/{ticket_id}/activity", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def ticket_activity(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Get ticket activity timeline as HTML partial."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get unified timeline from service
    timeline = service.get_activity_timeline(ticket_id)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket
    context["timeline"] = timeline

    template = templates.get_template("modules/support/templates/partials/activity_timeline.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# BULK PRIORITY UPDATE
# =============================================================================


@router.post("/bulk-priority", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def tickets_bulk_priority(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    priority: str = Query(..., description="Target priority"),
):
    """Bulk update ticket priority."""
    import json
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
        ids = data.get("ids", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not ids:
        raise HTTPException(status_code=400, detail="No ticket IDs provided")

    # Validate priority
    try:
        target_priority = TicketPriority(priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    # Use service layer for bulk update
    service = SupportWebService(db, user_id=user.id, principal=user)
    updated = service.bulk_update_priority(ids, target_priority)
    db.commit()

    htmx_toast(response, f"Updated {updated} tickets to {priority.replace('_', ' ').title()} priority", "success")
    return HTMLResponse("", headers=dict(response.headers))


# =============================================================================
# TICKET TAGS ROUTES
# =============================================================================


@router.get("/{ticket_id}/tags", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def ticket_tags(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Get ticket tags as HTML partial."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket
    context["tags"] = ticket.tags or []

    template = templates.get_template("modules/support/templates/partials/ticket_tags.html")
    return HTMLResponse(template.render(context))


@router.post("/{ticket_id}/tags", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_add_tag(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Add a tag to a ticket."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    tag = _form_str(form, "tag")

    if not tag or not tag.strip():
        htmx_toast(response, "Tag name is required", "error")
        return HTMLResponse("", status_code=400, headers=dict(response.headers))

    tag = tag.strip().lower()

    # Add tag if not exists
    current_tags = ticket.tags or []
    if tag not in current_tags:
        ticket = service.update_ticket(ticket_id, {"tags": current_tags + [tag]})
        db.commit()
        htmx_toast(response, f"Tag '{tag}' added", "success")

    # Return updated tags partial
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["tags"] = ticket.tags or []

    template = templates.get_template("modules/support/templates/partials/ticket_tags.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


@router.delete("/{ticket_id}/tags/{tag_name}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_remove_tag(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    ticket_id: int,
    tag_name: str,
):
    """Remove a tag from a ticket."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Remove tag if exists
    current_tags = ticket.tags or []
    if tag_name in current_tags:
        new_tags = [t for t in current_tags if t != tag_name]
        ticket = service.update_ticket(ticket_id, {"tags": new_tags})
        db.commit()
        htmx_toast(response, f"Tag '{tag_name}' removed", "success")

    # Return updated tags partial
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["tags"] = ticket.tags or []

    template = templates.get_template("modules/support/templates/partials/ticket_tags.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


# =============================================================================
# SLA OVERRIDE ROUTES
# =============================================================================


@router.get("/{ticket_id}/sla-modal", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_sla_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Return SLA override modal content."""
    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/sla_modal.html")
    return HTMLResponse(template.render(context))


@router.post("/{ticket_id}/sla", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def ticket_update_sla(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Override ticket SLA dates."""
    from dateutil.parser import parse as parse_date

    service = SupportWebService(db, user_id=user.id, principal=user)
    ticket = service.get_ticket_or_none(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    response_by_str = _form_str(form, "response_by")
    resolution_by_str = _form_str(form, "resolution_by")
    reason = _form_str(form, "reason")

    update_data = {}

    try:
        if response_by_str:
            update_data["response_by"] = parse_date(response_by_str)
        if resolution_by_str:
            update_data["resolution_by"] = parse_date(resolution_by_str)
    except Exception:
        htmx_toast(response, "Invalid date format", "error")
        return HTMLResponse("", status_code=400, headers=dict(response.headers))

    if update_data:
        ticket = service.update_ticket(ticket_id, update_data)
        db.commit()
        htmx_toast(response, "SLA dates updated", "success")

    # Return updated ticket detail SLA section
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/ticket_sla.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


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
    service = SupportWebService(db, user_id=user.id, principal=user)

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
    service = SupportWebService(db, user_id=user.id, principal=user)
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
    service = SupportWebService(db, user_id=user.id, principal=user)

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
    service = SupportWebService(db, user_id=user.id, principal=user)

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
    open_statuses = [
        TicketStatus.OPEN.value,
        TicketStatus.IN_PROGRESS.value,
        TicketStatus.WAITING.value,
        TicketStatus.ON_HOLD.value,
        TicketStatus.REOPENED.value,
    ]
    agents = db.query(Agent).filter(Agent.is_active == True).all()
    agent_workload: list[dict[str, Any]] = []
    for agent in agents:
        name = agent.display_name or agent.email
        capacity = agent.capacity or 10
        if agent.employee_id:
            open_count = db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.assigned_to_id == agent.employee_id,
                UnifiedTicket.status.in_(open_statuses),
            ).scalar() or 0
        else:
            open_count = 0
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
    unassigned = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.is_deleted == False,
        UnifiedTicket.assigned_to_id.is_(None),
        UnifiedTicket.status.in_(open_statuses),
    ).scalar() or 0

    total_open = db.query(func.count(UnifiedTicket.id)).filter(
        UnifiedTicket.is_deleted == False,
        UnifiedTicket.status.in_(open_statuses),
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

    ticket_ids = [c.unified_ticket_id for c in conversations if c.unified_ticket_id]
    ticket_map = {}
    if ticket_ids:
        tickets = db.query(UnifiedTicket).filter(UnifiedTicket.id.in_(ticket_ids)).all()
        ticket_map = {t.id: t for t in tickets}

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
    context["linked_tickets"] = ticket_map
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
    from app.models.party import CustomerAccount, Party

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Conversation not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get customer if linked
    customer = None
    if conversation.customer_account_id:
        customer = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .filter(CustomerAccount.id == conversation.customer_account_id)
            .first()
        )

    ticket = None
    if conversation.unified_ticket_id:
        ticket = db.query(UnifiedTicket).filter(
            UnifiedTicket.id == conversation.unified_ticket_id
        ).first()

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
    context["linked_ticket"] = ticket

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
    from app.models.unified_ticket import UnifiedTicket

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get members with agent details
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    agent_ids = [m.agent_id for m in members]
    agents = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []

    # Agent workload
    open_statuses = [
        TicketStatus.OPEN.value,
        TicketStatus.IN_PROGRESS.value,
        TicketStatus.WAITING.value,
        TicketStatus.ON_HOLD.value,
        TicketStatus.REOPENED.value,
    ]
    agent_workload: list[dict[str, Any]] = []
    for agent in agents:
        name = agent.display_name or agent.email
        if agent.employee_id:
            open_tickets = db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.assigned_to_id == agent.employee_id,
                UnifiedTicket.status.in_(open_statuses),
            ).scalar() or 0
        else:
            open_tickets = 0
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
queues_router = APIRouter(prefix="/support/queues", tags=["support-queues"])
escalations_router = APIRouter(prefix="/support/escalations", tags=["support-escalations"])
channels_router = APIRouter(prefix="/support/channels", tags=["support-channels"])
webhooks_router = APIRouter(prefix="/support/webhooks", tags=["support-webhooks"])


@tags_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def tags_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support tags list."""
    from app.services.support.tags import TagService

    service = TagService(db, principal=user)
    tags, tag_usage, recent_usage = service.list_with_usage(days=30)

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
# QUEUES
# =============================================================================

@queues_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def queues_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    queue_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Support queues overview."""
    from app.services.support.queues import QueueService

    service = QueueService(db, principal=user)
    queues = service.list(active_only=True, include_private=True)
    queue_counts = {q.id: service.get_ticket_count(q.id) for q in queues}

    selected_queue = None
    tickets = []
    total = 0
    if queues:
        selected_queue_id = queue_id or queues[0].id
        selected_queue = service.get(selected_queue_id)
        total = service.get_ticket_count(selected_queue_id)
        offset = (page - 1) * per_page
        tickets = service.get_tickets(selected_queue_id, limit=per_page, offset=offset)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Queues"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Queues"},
    ])

    context["queues"] = queues
    context["queue_counts"] = queue_counts
    context["selected_queue"] = selected_queue
    context["tickets"] = tickets
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/support/templates/pages/queues.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ESCALATIONS
# =============================================================================

@escalations_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def escalations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Escalation policies overview."""
    from app.services.support.escalation import EscalationService
    from app.models.unified_ticket import UnifiedTicket
    from sqlalchemy import or_, and_

    def _apply_conditions(query, conditions):
        for condition in conditions or []:
            field = condition.get("field")
            operator = condition.get("operator", "equals")
            value = condition.get("value")

            if not field or not hasattr(UnifiedTicket, field):
                continue
            column = getattr(UnifiedTicket, field)

            if operator == "equals":
                query = query.filter(column == value)
            elif operator == "not_equals":
                query = query.filter(column != value)
            elif operator == "in":
                if isinstance(value, list):
                    query = query.filter(column.in_(value))
            elif operator == "not_in":
                if isinstance(value, list):
                    query = query.filter(~column.in_(value))
            elif operator == "is_empty":
                query = query.filter(or_(column.is_(None), column == ""))
            elif operator == "is_not_empty":
                query = query.filter(and_(column.isnot(None), column != ""))

        return query

    service = EscalationService(db, principal=user)
    policies = service.list_policies(active_only=False)
    for policy in policies:
        _ = policy.levels

    now = datetime.utcnow()
    overdue_filter = or_(
        and_(
            UnifiedTicket.response_by.isnot(None),
            UnifiedTicket.first_response_at.is_(None),
            UnifiedTicket.response_by < now,
        ),
        and_(
            UnifiedTicket.resolution_by.isnot(None),
            UnifiedTicket.resolved_at.is_(None),
            UnifiedTicket.resolution_by < now,
        ),
    )

    candidate_counts: dict[int, int] = {}
    for policy in policies:
        query = db.query(UnifiedTicket).filter(
            UnifiedTicket.is_deleted == False,
        )
        query = _apply_conditions(query, policy.conditions)
        count = query.filter(overdue_filter).count()
        candidate_counts[policy.id] = count

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Escalations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Escalations"},
    ])

    context["policies"] = policies
    context["candidate_counts"] = candidate_counts

    template = templates.get_template("modules/support/templates/pages/escalations.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# CHANNELS
# =============================================================================

@channels_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def channels_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Channel configuration list."""
    from app.services.support.channels import ChannelService

    service = ChannelService(db, principal=user)
    channels = service.list(active_only=False)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Channels"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Channels"},
    ])

    context["channels"] = channels

    template = templates.get_template("modules/support/templates/pages/channels.html")
    return HTMLResponse(template.render(context))


@channels_router.get("/new", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def channels_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New channel form."""
    from app.models.omni import OmniChannelType

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Channel"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Channels", "href": "/support/channels"},
        {"label": "New"},
    ])
    context["channel_types"] = [t.value for t in OmniChannelType]
    context["form_data"] = {}
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/channel_form.html")
    return HTMLResponse(template.render(context))


@channels_router.post("", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def channels_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new channel."""
    import json
    from app.services.support.channels import ChannelService
    from app.services.support.types import ChannelCreate

    form = await request.form()
    name = _form_str(form, "name")
    channel_type = _form_str(form, "type")
    webhook_secret = _form_str(form, "webhook_secret") or None
    config_raw = _form_str(form, "config_json")
    is_active = bool(form.get("is_active"))

    errors = {}
    config = None
    if not name:
        errors["name"] = "Name is required"
    if not channel_type:
        errors["type"] = "Type is required"
    else:
        try:
            OmniChannelType(channel_type)
        except ValueError:
            errors["type"] = "Invalid channel type"

    if config_raw:
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            errors["config_json"] = "Config must be valid JSON"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Channel"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/dashboard"},
            {"label": "Channels", "href": "/support/channels"},
            {"label": "New"},
        ])
        context["channel_types"] = [t.value for t in OmniChannelType]
        context["form_data"] = {
            "name": name,
            "type": channel_type,
            "webhook_secret": webhook_secret or "",
            "config_json": config_raw,
            "is_active": is_active,
        }
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/channel_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = ChannelService(db, principal=user)
    channel = service.create(ChannelCreate(
        name=name,
        type=channel_type,
        config=config or {},
        webhook_secret=webhook_secret,
        is_active=is_active,
    ))
    db.commit()

    set_flash(response, f"Channel '{channel.name}' created.", "success")
    return RedirectResponse(url="/support/channels", status_code=303)


@channels_router.get("/{channel_id}/edit", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def channels_edit(
    channel_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Edit channel form."""
    import json
    from app.models.omni import OmniChannelType
    from app.services.support.channels import ChannelService
    from app.services.errors import NotFoundError

    service = ChannelService(db, principal=user)
    try:
        channel = service.get(channel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Channel not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit Channel {channel.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Channels", "href": "/support/channels"},
        {"label": channel.name},
    ])
    context["channel"] = channel
    context["channel_types"] = [t.value for t in OmniChannelType]
    context["form_data"] = {
        "name": channel.name,
        "type": channel.type,
        "webhook_secret": channel.webhook_secret or "",
        "config_json": json.dumps(channel.config or {}, indent=2, sort_keys=True),
        "is_active": channel.is_active,
    }
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/channel_form.html")
    return HTMLResponse(template.render(context))


@channels_router.post("/{channel_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def channels_update(
    channel_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Update a channel."""
    import json
    from app.models.omni import OmniChannelType
    from app.services.support.channels import ChannelService
    from app.services.support.types import ChannelUpdate
    from app.services.errors import NotFoundError

    service = ChannelService(db, principal=user)
    try:
        channel = service.get(channel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Channel not found")

    form = await request.form()
    name = _form_str(form, "name")
    channel_type = channel.type
    webhook_secret = _form_str(form, "webhook_secret") or None
    config_raw = _form_str(form, "config_json")
    is_active = bool(form.get("is_active"))

    errors = {}
    config = None
    if not name:
        errors["name"] = "Name is required"
    if not channel_type:
        errors["type"] = "Type is required"

    if config_raw:
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            errors["config_json"] = "Config must be valid JSON"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit Channel {channel.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/dashboard"},
            {"label": "Channels", "href": "/support/channels"},
            {"label": channel.name},
        ])
        context["channel"] = channel
        context["channel_types"] = [t.value for t in OmniChannelType]
        context["form_data"] = {
            "name": name,
            "type": channel_type,
            "webhook_secret": webhook_secret or "",
            "config_json": config_raw,
            "is_active": is_active,
        }
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/channel_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service.update(channel_id, ChannelUpdate(
        name=name,
        config=config,
        webhook_secret=webhook_secret,
        is_active=is_active,
    ))
    db.commit()

    set_flash(response, f"Channel '{channel.name}' updated.", "success")
    return RedirectResponse(url="/support/channels", status_code=303)


@channels_router.post("/{channel_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def channels_toggle(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    channel_id: int,
):
    """Toggle channel active state."""
    from app.services.support.channels import ChannelService
    from app.services.support.types import ChannelUpdate
    from app.services.errors import NotFoundError

    service = ChannelService(db, principal=user)
    try:
        channel = service.get(channel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Channel not found")

    service.update(channel_id, ChannelUpdate(is_active=not channel.is_active))
    db.commit()

    status_text = "enabled" if channel.is_active else "disabled"
    htmx_toast(response, f"Channel {status_text}", "success")
    return HTMLResponse("", headers=dict(response.headers))


# =============================================================================
# WEBHOOK EVENTS
# =============================================================================

@webhooks_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def webhooks_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    channel_id: Optional[int] = Query(None),
    processed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Webhook event log."""
    from app.services.support.webhooks import WebhookService
    from app.services.support.channels import ChannelService

    webhook_service = WebhookService(db, principal=user)
    events, total = webhook_service.list_events(
        channel_id=channel_id,
        processed=processed,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    channel_service = ChannelService(db, principal=user)
    channels = channel_service.list(active_only=False)
    channel_map = {c.id: c for c in channels}

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Webhook Events"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Webhooks"},
    ])

    context["events"] = events
    context["channel_filter"] = channel_id
    context["processed_filter"] = processed
    context["channel_options"] = channels
    context["channel_map"] = channel_map
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/support/templates/pages/webhooks.html")
    return HTMLResponse(template.render(context))


@webhooks_router.get("/{event_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
async def webhook_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    event_id: int,
):
    """Webhook event detail."""
    from app.services.support.webhooks import WebhookService
    from app.services.support.channels import ChannelService

    webhook_service = WebhookService(db, principal=user)
    event = webhook_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found")
    channel = None
    if event.channel_id:
        channel_service = ChannelService(db, principal=user)
        try:
            channel = channel_service.get(event.channel_id)
        except Exception:
            channel = None

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Webhook Event #{event.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Webhooks", "href": "/support/webhooks"},
        {"label": f"#{event.id}"},
    ])

    context["event"] = event
    context["channel"] = channel

    template = templates.get_template("modules/support/templates/pages/webhook_detail.html")
    return HTMLResponse(template.render(context))


@webhooks_router.post("/{event_id}/retry", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
async def webhook_retry(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    event_id: int,
):
    """Retry processing a webhook event."""
    from app.services.support.webhooks import WebhookService

    service = WebhookService(db, principal=user)
    try:
        service.retry_event(event_id)
        db.commit()
        htmx_toast(response, "Webhook reprocessed", "success")
    except Exception as exc:
        db.rollback()
        htmx_toast(response, f"Retry failed: {exc}", "error")

    return RedirectResponse(url=f"/support/webhooks/{event_id}", status_code=303)


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
    trigger: Optional[str] = Query(None),
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
    if trigger:
        query = query.filter(AutomationLog.trigger == trigger)

    total = query.count()
    logs = query.order_by(AutomationLog.created_at.desc()).offset(offset).limit(per_page).all()

    # Get rules for filter dropdown
    rules = db.query(AutomationRule).order_by(AutomationRule.name).all()
    trigger_rows = db.query(AutomationLog.trigger).distinct().order_by(AutomationLog.trigger).all()
    trigger_options = [row[0] for row in trigger_rows if row[0]]

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
    context["trigger_filter"] = trigger
    context["trigger_options"] = trigger_options
    context["pagination"] = build_pagination_context(page, per_page, total)

    context["stats"] = {
        "total_30d": stats.total if stats else 0,
        "success_30d": stats.success or 0 if stats else 0,
        "success_rate": round((stats.success or 0) / stats.total * 100, 1) if stats and stats.total > 0 else 0,
        "avg_time_ms": round(float(stats.avg_time or 0), 1) if stats else 0,
    }

    template = templates.get_template("modules/support/templates/pages/automation_logs.html")
    return HTMLResponse(template.render(context))

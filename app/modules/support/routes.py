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
    Team, TeamMember, PartyRole,
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
# Base router for the support module - all other routers are included into this
# No prefix here since all sub-routers have their full /support/... paths
router = APIRouter(tags=["support"])
tickets_router = APIRouter(prefix="/support/tickets", tags=["support-tickets"])
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
    try:
        basic_stats = service.get_dashboard_stats()
    except Exception:
        basic_stats = {
            "total_open": 0,
            "urgent_tickets": 0,
            "created_today": 0,
            "resolved_today": 0,
            "response_overdue": 0,
            "resolution_overdue": 0,
            "status_distribution": {},
            "priority_distribution": {},
        }

    try:
        recent_tickets = service.get_recent_tickets(limit=10)
    except Exception:
        recent_tickets = []

    try:
        unassigned_tickets = service.list_tickets(
            status="open",
            page=1,
            per_page=5,
        )["items"]
    except Exception:
        unassigned_tickets = []

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
        tag_breakdown = cached_analytics.get("tag_breakdown", [])
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

        try:
            tag_breakdown = analytics.get_tag_breakdown(filters_30d, limit=10)
        except Exception:
            tag_breakdown = []

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
            "tag_breakdown": tag_breakdown,
        })

    # Format distributions for template
    status_distribution = [
        {"status": status, "count": count}
        for status, count in basic_stats.get("status_distribution", {}).items()
    ]
    priority_distribution = [
        {"priority": priority, "count": count}
        for priority, count in basic_stats.get("priority_distribution", {}).items()
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

    # Tag breakdown (top tags with growth indicators)
    context["tag_breakdown"] = [
        {
            "tag_id": t.tag_id,
            "tag_name": t.tag_name,
            "color": t.color,
            "ticket_count": t.ticket_count,
            "pct_of_total": t.pct_of_total,
            "growth_pct": t.growth_pct,
            "prior_period_count": t.prior_period_count,
        }
        for t in tag_breakdown
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

@tickets_router.get("", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.get("/table", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.get("/new", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.post("", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
    if not description:
        errors["description"] = "Description is required"
    if party_id and not party:
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
    assigned_to_party_id = _form_str(form, "assigned_to_party_id") or _form_str(form, "assigned_to_id")
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
        "assigned_to_party_id": int(assigned_to_party_id) if assigned_to_party_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.create_ticket(ticket_data)
    db.commit()
    redirect = RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)
    set_flash(redirect, f"Ticket '{ticket.ticket_number}' created successfully.", "success")
    return redirect


@tickets_router.get("/parties/search", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.get("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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
    from app.services.projects import ProjectService
    from app.services.projects.errors import ProjectNotFoundError

    related_project = None
    project_id = getattr(ticket, "project_id", None)
    if project_id:
        project_service = ProjectService(db, principal=user)
        try:
            related_project = project_service.get_project(project_id)
        except ProjectNotFoundError:
            related_project = None

    # Load assigned party (support agent)
    assigned_party = None
    if ticket.assigned_to_party_id:
        from app.services.identity import PartyService

        party_service = PartyService(db)
        assigned_party = party_service.get_party(ticket.assigned_to_party_id)

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
    context["assigned_party"] = assigned_party
    context["agents"] = get_agents(db)
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["timeline"] = service.get_activity_timeline(ticket_id)

    template = templates.get_template("modules/support/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@tickets_router.get("/{ticket_id}/edit", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.post("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
        from app.services.identity import PartyService
        from app.services.errors import NotFoundError as PartyNotFoundError

        party_service = PartyService(db, principal=user)
        try:
            party = party_service.get_party(party_id)
        except PartyNotFoundError:
            party = None

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
    assigned_to_party_id = _form_str(form, "assigned_to_party_id") or _form_str(form, "assigned_to_id")
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
        "assigned_to_party_id": int(assigned_to_party_id) if assigned_to_party_id else None,
        "assigned_team": assigned_team or None,
    }
    ticket = service.update_ticket(ticket_id, update_data)
    db.commit()

    set_flash(response, f"Ticket '{ticket.ticket_number}' updated successfully.", "success")
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@tickets_router.delete("/{ticket_id}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.post("/{ticket_id}/status", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
    return_type = _form_str(form, "return")

    if new_status:
        # Validate status value
        valid_statuses = [s.value for s in TicketStatus]
        if new_status not in valid_statuses:
            htmx_toast(response, f"Invalid status: {new_status}", "error")
            return HTMLResponse("", status_code=400, headers=dict(response.headers))

        ticket = service.update_ticket(ticket_id, {"status": new_status})
        db.commit()
        htmx_toast(response, f"Status updated to {new_status.replace('_', ' ').title()}", "success")

    if return_type == "badge":
        context = get_base_context(request, response, user, "")
        context["ticket"] = ticket
        template = templates.get_template("modules/support/templates/partials/status_badge.html")
        return HTMLResponse(template.render(context), headers=dict(response.headers))

    # Return updated ticket row
    context = get_base_context(request, response, user, "")
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


@tickets_router.get("/{ticket_id}/row", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.patch("/{ticket_id}/inline/{field}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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

@tickets_router.post("/bulk-status", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.delete("/bulk", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.get("/export", dependencies=[RequireSupportRead])
async def tickets_export(
    request: Request,
    db: DB,
    ids: list[int] = Query(None, description="Ticket IDs to export"),
):
    """Export tickets to CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    service = SupportWebService(db)
    tickets = service.list_tickets_for_export(ids=ids)

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


@tickets_router.get("/{ticket_id}/assign-modal", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.post("/{ticket_id}/assign", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
    # Accept party_id (new) or agent_id (legacy) from form
    party_id = _form_int(form, "party_id") or _form_int(form, "agent_id")
    if party_id is None:
        party_id = _form_int(form, "assigned_to")
    team_id = _form_int(form, "team_id")

    # Update assignment
    update_data = {}
    if party_id is not None:
        update_data["assigned_to_party_id"] = party_id if party_id > 0 else None
    if team_id is not None:
        update_data["assigned_team_id"] = team_id if team_id > 0 else None

    if update_data:
        ticket = service.update_ticket(ticket_id, update_data)
        db.commit()

        # Get agent name for toast message (get_agent returns Party now)
        if party_id and party_id > 0:
            agent = service.get_agent(party_id)
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


@tickets_router.post("/{ticket_id}/unassign", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
        "assigned_to_party_id": None,
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


@tickets_router.post("/{ticket_id}/comment", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
@tickets_router.post("/{ticket_id}/comments", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
@tickets_router.post("/{ticket_id}/reply", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
    body = _form_str(form, "body") or _form_str(form, "message")
    is_internal = _form_str(form, "is_internal") in ["1", "true", "yes", "on"]
    if is_internal:
        is_public = False
    else:
        is_public_raw = _form_str(form, "is_public")
        is_public = True if is_public_raw in [None, ""] else is_public_raw == "true"

    if not body or not body.strip():
        htmx_toast(response, "Comment body is required", "error")
        return HTMLResponse("", status_code=400, headers=dict(response.headers))

    # Create comment using service
    service.add_comment(ticket_id, body.strip(), is_public=is_public)
    db.commit()

    htmx_toast(response, "Comment added", "success")

    # Return updated activity timeline
    return await ticket_activity(request, response, user, "", db, ticket_id)


@tickets_router.get("/{ticket_id}/comments", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.get("/{ticket_id}/activity", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.post("/bulk-priority", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.get("/{ticket_id}/tags", response_class=HTMLResponse, dependencies=[RequireSupportRead])
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


@tickets_router.post("/{ticket_id}/tags", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.delete("/{ticket_id}/tags/{tag_name}", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.get("/{ticket_id}/sla-modal", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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


@tickets_router.post("/{ticket_id}/sla", response_class=HTMLResponse, dependencies=[RequireSupportWrite])
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
from app.services.support import KnowledgeBaseService, KBArticleFilters
from app.services.base import PaginationParams

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
    service = KnowledgeBaseService(db)
    return service.list_categories_flat(active_only=True)


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
    # Use service for filtering, pagination, and stats (single optimized query)
    service = KnowledgeBaseService(db, user)
    filters = KBArticleFilters(search=q, status=status, category_id=category_id)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_articles_with_stats(
        filters=filters,
        pagination=pagination,
        sort_by=sort,
        sort_dir=dir,
    )

    # Map stats to template format
    stats = {
        "published": result.stats.published_count,
        "draft": result.stats.draft_count,
        "total_views": result.stats.total_views,
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["articles"] = result.items
    context["stats"] = stats
    context["categories"] = result.categories
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_category_id"] = category_id
    context["status_options"] = get_article_status_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    service = KnowledgeBaseService(db, user)
    existing = service.get_article_by_slug(slug)
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

    # Create article via service
    from app.services.support import KBArticleCreate

    article = service.create_article(KBArticleCreate(
        title=name,
        slug=slug,
        content=content,
        excerpt=_form_str(form, "excerpt") or None,
        category_id=int(category_id) if category_id else None,
        visibility=_form_str(form, "visibility", ArticleVisibility.PUBLIC.value),
        search_keywords=_form_str(form, "search_keywords") or None,
    ))

    article.status = _form_str(form, "status", ArticleStatus.DRAFT.value)
    article.updated_by_id = user.id

    # Set published_at if publishing
    if article.status == ArticleStatus.PUBLISHED.value:
        from datetime import datetime
        article.published_at = datetime.utcnow()

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
    # Use service to get categories with counts in single query (avoids N+1)
    service = KnowledgeBaseService(db, user)
    categories_with_counts = service.get_categories_with_counts()

    # Separate for template compatibility
    categories = [cat for cat, _ in categories_with_counts]
    category_counts = {cat.id: count for cat, count in categories_with_counts}

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
    from app.services.support import KBArticleNotFoundError

    service = KnowledgeBaseService(db, user)

    try:
        article, related_articles = service.get_article_with_related(
            article_id, increment_view=True
        )
        db.commit()
    except KBArticleNotFoundError:
        raise HTTPException(status_code=404, detail="Article not found")

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
    service = KnowledgeBaseService(db, user)
    from app.services.support import KBArticleNotFoundError
    try:
        article = service.get_article(article_id)
    except KBArticleNotFoundError:
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
    service = KnowledgeBaseService(db, user)
    from app.services.support import KBArticleNotFoundError, KBArticleUpdate
    try:
        article = service.get_article(article_id)
    except KBArticleNotFoundError:
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
        existing = service.get_article_by_slug(slug)
        if existing and existing.id != article_id:
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

    # Update article via service
    service.update_article(article_id, KBArticleUpdate(
        title=name,
        slug=slug or None,
        content=content,
        excerpt=_form_str(form, "excerpt") or None,
        category_id=int(category_id) if category_id else None,
        visibility=_form_str(form, "visibility", article.visibility),
        search_keywords=_form_str(form, "search_keywords") or None,
    ))

    article.status = new_status
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
    service = KnowledgeBaseService(db, user)
    from app.services.support import KBArticleNotFoundError
    try:
        article = service.get_article(article_id)
    except KBArticleNotFoundError:
        raise HTTPException(status_code=404, detail="Article not found")

    name = article.title
    service.delete_article(article_id)
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
    service = KnowledgeBaseService(db, user)
    from app.services.support import KBArticleNotFoundError
    try:
        article, _ = service.get_article_with_related(
            article_id, increment_view=False
        )
    except KBArticleNotFoundError:
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
    """Support agents list page with comprehensive analytics."""
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
    available_count = sum(1 for a in all_agents["items"] if a.is_active and a.is_available)

    # Get agent performance analytics (30 days)
    analytics = SupportAnalyticsService(db, principal=user)
    filters = AnalyticsFilters(days=30)
    agent_performance = analytics.get_agent_performance(filters, limit=100)

    # Build performance lookup by agent_id for table enhancement
    perf_by_agent = {p.agent_id: p for p in agent_performance}

    # Calculate aggregate stats from performance data
    avg_resolution_hours = 0.0
    avg_sla_pct = 0.0
    avg_csat = 0.0
    csat_count = 0

    if agent_performance:
        total_resolution = sum(p.avg_resolution_hours for p in agent_performance)
        avg_resolution_hours = total_resolution / len(agent_performance) if agent_performance else 0

        total_sla = sum(p.sla_attainment_pct for p in agent_performance)
        avg_sla_pct = total_sla / len(agent_performance) if agent_performance else 0

        csat_scores = [p.csat_score for p in agent_performance if p.csat_score is not None]
        if csat_scores:
            avg_csat = sum(csat_scores) / len(csat_scores)
            csat_count = len(csat_scores)

    # Top performers (top 10 by resolution rate, min 5 tickets)
    top_performers = sorted(
        [p for p in agent_performance if p.total_tickets >= 5],
        key=lambda x: (x.sla_attainment_pct, x.resolution_rate, -x.avg_resolution_hours),
        reverse=True
    )[:10]

    # Workload distribution (by utilization tier)
    workload_tiers = {
        "available": {"label": "Available (<50%)", "agents": [], "color": "emerald"},
        "moderate": {"label": "Moderate (50-75%)", "agents": [], "color": "amber"},
        "high": {"label": "High Load (75-100%)", "agents": [], "color": "orange"},
        "overloaded": {"label": "Overloaded (>100%)", "agents": [], "color": "red"},
    }
    for p in agent_performance:
        if p.utilization_pct < 50:
            workload_tiers["available"]["agents"].append(p)
        elif p.utilization_pct < 75:
            workload_tiers["moderate"]["agents"].append(p)
        elif p.utilization_pct <= 100:
            workload_tiers["high"]["agents"].append(p)
        else:
            workload_tiers["overloaded"]["agents"].append(p)

    # Agents at capacity (utilization >= 90%)
    at_capacity = [p for p in agent_performance if p.utilization_pct >= 90]

    stats = {
        "total": all_agents["total"],
        "active": active_count,
        "available": available_count,
        "avg_resolution_hours": round(avg_resolution_hours, 1),
        "avg_sla_pct": round(avg_sla_pct, 1),
        "avg_csat": round(avg_csat, 1) if csat_count > 0 else None,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["agents"] = agents
    context["agent_stats"] = agent_stats
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)
    # Enhanced analytics context
    context["agent_performance"] = perf_by_agent
    context["top_performers"] = top_performers
    context["workload_tiers"] = workload_tiers
    context["at_capacity"] = at_capacity

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
    """Agent detail page with comprehensive performance metrics."""
    from app.services.support import AgentService, AgentNotFoundError

    service = AgentService(db, user)

    try:
        result = service.get_agent_detail(agent_id, recent_ticket_limit=10)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get agent performance analytics (30 days)
    analytics = SupportAnalyticsService(db, principal=user)
    filters = AnalyticsFilters(days=30, agent_id=agent_id)
    agent_perf_list = analytics.get_agent_performance(filters, limit=1)
    agent_perf = agent_perf_list[0] if agent_perf_list else None

    # Map stats to template format with enhanced metrics
    stats = {
        "open_tickets": result.stats.open_tickets,
        "resolved_today": result.stats.resolved_today,
        "teams": result.stats.team_count,
        # Enhanced stats from performance analytics
        "total_30d": agent_perf.total_tickets if agent_perf else 0,
        "resolved_30d": agent_perf.resolved_tickets if agent_perf else 0,
        "resolution_rate": agent_perf.resolution_rate if agent_perf else 0,
        "avg_resolution_hours": agent_perf.avg_resolution_hours if agent_perf else 0,
        "avg_first_response_hours": agent_perf.avg_first_response_hours if agent_perf else 0,
        "sla_attainment_pct": agent_perf.sla_attainment_pct if agent_perf else 0,
        "csat_score": agent_perf.csat_score if agent_perf else None,
        "csat_responses": agent_perf.csat_responses if agent_perf else 0,
        "capacity": agent_perf.capacity if agent_perf else (result.agent.agent_capacity or 10),
        "utilization_pct": agent_perf.utilization_pct if agent_perf else 0,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = result.agent.display_name or f"Agent {result.agent.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Agents", "href": "/support/agents"},
        {"label": result.agent.display_name or f"Agent {result.agent.id}"},
    ])
    context["agent"] = result.agent
    context["open_tickets"] = result.recent_tickets
    context["team_memberships"] = result.team_memberships
    context["stats"] = stats
    context["performance"] = agent_perf

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
    from app.services.support import CannedResponseService, CannedResponseFilters

    # Use CannedResponseService for filtering, pagination, and stats (single optimized query)
    service = CannedResponseService(db, user)
    filters = CannedResponseFilters(search=q, scope=scope, active_only=True)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_with_stats(filters=filters, pagination=pagination)

    # Map stats to template format
    stats = {
        "total": result.stats.total,
        "personal": result.stats.personal_count,
        "team": result.stats.team_count,
        "global": result.stats.global_count,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["responses"] = result.items
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_scope"] = scope
    context["scope_options"] = get_canned_scope_options()
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    from app.services.support import AgentService
    teams = AgentService(db, user).list_teams(active_only=True)

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
    from app.services.support import AgentService, CannedResponseService, CannedResponseCreate, DuplicateShortcodeError
    teams = AgentService(db, user).list_teams(active_only=True)

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
    service = CannedResponseService(db, user)
    if shortcode:
        existing = service.get_by_shortcode(shortcode)
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

    try:
        canned = service.create(CannedResponseCreate(
            name=name,
            content=content,
            shortcode=shortcode or None,
            scope=scope,
            team_id=int(team_id) if team_id else None,
        ))
        db.commit()
    except DuplicateShortcodeError:
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
        context["errors"] = {"shortcode": "This shortcode is already in use"}
        context["form_data"] = dict(form)

        template = templates.get_template("modules/support/templates/pages/canned_form.html")
        return HTMLResponse(template.render(context), status_code=422)

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
    from app.services.support import AgentService, CannedResponseService, CannedResponseNotFoundError
    service = CannedResponseService(db, user)
    try:
        canned = service.get(canned_id)
    except CannedResponseNotFoundError:
        raise HTTPException(status_code=404, detail="Canned response not found")

    teams = AgentService(db, user).list_teams(active_only=True)

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
    from app.services.support import AgentService, CannedResponseService, CannedResponseUpdate, CannedResponseNotFoundError, DuplicateShortcodeError
    service = CannedResponseService(db, user)
    try:
        canned = service.get(canned_id)
    except CannedResponseNotFoundError:
        raise HTTPException(status_code=404, detail="Canned response not found")

    form = await request.form()
    teams = AgentService(db, user).list_teams(active_only=True)

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
        existing = service.get_by_shortcode(shortcode)
        if existing and existing.id != canned_id:
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

    try:
        canned = service.update(canned_id, CannedResponseUpdate(
            name=name,
            content=content,
            shortcode=shortcode or None,
            scope=_form_str(form, "scope") or canned.scope,
            team_id=int(team_id) if team_id else None,
        ))
        db.commit()
    except DuplicateShortcodeError:
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
        context["errors"] = {"shortcode": "This shortcode is already in use"}

        template = templates.get_template("modules/support/templates/pages/canned_form.html")
        return HTMLResponse(template.render(context), status_code=422)

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
    from app.services.support import CannedResponseService, CannedResponseUpdate, CannedResponseNotFoundError
    service = CannedResponseService(db, user)
    try:
        canned = service.get(canned_id)
    except CannedResponseNotFoundError:
        raise HTTPException(status_code=404, detail="Canned response not found")

    name = canned.name
    service.update(canned_id, CannedResponseUpdate(is_active=False))
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
async def sla_analytics_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    days: int = Query(30, ge=7, le=365, description="Period in days"),
):
    """SLA Analytics Dashboard - comprehensive SLA performance analytics."""
    from app.services.support import SLAService
    analytics = SupportAnalyticsService(db, principal=user)
    filters = AnalyticsFilters(days=days)

    # Get SLA analytics summary
    try:
        summary = analytics.get_sla_analytics_summary(filters)
        summary_data = {
            "overall_attainment_pct": summary.overall_attainment_pct,
            "response_attainment_pct": summary.response_attainment_pct,
            "resolution_attainment_pct": summary.resolution_attainment_pct,
            "total_breaches": summary.total_breaches,
            "response_breaches": summary.response_breaches,
            "resolution_breaches": summary.resolution_breaches,
            "total_tracked": summary.total_tracked,
        }
    except Exception:
        summary_data = {
            "overall_attainment_pct": 0,
            "response_attainment_pct": 0,
            "resolution_attainment_pct": 0,
            "total_breaches": 0,
            "response_breaches": 0,
            "resolution_breaches": 0,
            "total_tracked": 0,
        }

    # Get SLA trends for chart
    try:
        trends = analytics.get_sla_trends(filters, periods=6)
        trends_data = [
            {
                "period": t.period,
                "response_attainment_pct": t.response_attainment_pct,
                "resolution_attainment_pct": t.resolution_attainment_pct,
                "overall_attainment_pct": t.overall_attainment_pct,
                "total_tickets": t.total_tickets,
            }
            for t in trends
        ]
    except Exception:
        trends_data = []

    # Get agent SLA performance
    try:
        agent_stats = analytics.get_sla_attainment_by_agent(filters, limit=20)
        agent_stats_data = [
            {
                "agent_id": a.agent_id,
                "agent_name": a.agent_name,
                "team_name": a.team_name,
                "total_tickets": a.total_tickets,
                "response_attainment_pct": a.response_attainment_pct,
                "resolution_attainment_pct": a.resolution_attainment_pct,
                "overall_attainment_pct": a.overall_attainment_pct,
                "avg_response_hours": a.avg_response_hours,
                "avg_resolution_hours": a.avg_resolution_hours,
            }
            for a in agent_stats
        ]
    except Exception:
        agent_stats_data = []

    # Get team SLA performance
    try:
        team_stats = analytics.get_sla_attainment_by_team(filters)
        team_stats_data = [
            {
                "team_id": t.team_id,
                "team_name": t.team_name,
                "total_tickets": t.total_tickets,
                "response_attainment_pct": t.response_attainment_pct,
                "resolution_attainment_pct": t.resolution_attainment_pct,
                "overall_attainment_pct": t.overall_attainment_pct,
            }
            for t in team_stats
        ]
    except Exception:
        team_stats_data = []

    # Get SLA by category
    try:
        category_stats = analytics.get_sla_by_category(filters)
        category_stats_data = [
            {
                "category": c.category,
                "total_tickets": c.total_tickets,
                "response_attainment_pct": c.response_attainment_pct,
                "resolution_attainment_pct": c.resolution_attainment_pct,
                "total_breaches": c.total_breaches,
            }
            for c in category_stats
        ]
    except Exception:
        category_stats_data = []

    # Get SLA by priority
    try:
        priority_stats = analytics.get_sla_by_priority(filters)
        priority_stats_data = [
            {
                "priority": p.priority,
                "total_tickets": p.total_tickets,
                "response_attainment_pct": p.response_attainment_pct,
                "resolution_attainment_pct": p.resolution_attainment_pct,
                "total_breaches": p.total_breaches,
            }
            for p in priority_stats
        ]
    except Exception:
        priority_stats_data = []

    # Get near misses
    try:
        near_misses = analytics.get_sla_near_misses(filters, threshold_pct=0.9, limit=10)
        near_misses_data = [
            {
                "ticket_id": n.ticket_id,
                "ticket_number": n.ticket_number,
                "subject": n.subject,
                "sla_type": n.sla_type,
                "target_time": n.target_time.isoformat() if n.target_time else None,
                "actual_time": n.actual_time.isoformat() if n.actual_time else None,
                "margin_pct": n.margin_pct,
            }
            for n in near_misses
        ]
    except Exception:
        near_misses_data = []

    # Get SLA policy count for "Configure" link
    sla_service = SLAService(db, user)
    all_policies, _ = sla_service.list_policies(is_active=None, skip=0, limit=1000)
    policy_count = len(all_policies)
    active_policy_count = len([p for p in all_policies if p.is_active])

    context = get_base_context(request, response, user, csrf_token)
    context["summary"] = summary_data
    context["trends"] = trends_data
    context["agent_stats"] = agent_stats_data
    context["team_stats"] = team_stats_data
    context["category_stats"] = category_stats_data
    context["priority_stats"] = priority_stats_data
    context["near_misses"] = near_misses_data
    context["policy_count"] = policy_count
    context["active_policy_count"] = active_policy_count
    context["selected_days"] = days

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "SLA Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "SLA Analytics"},
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
    from app.services.support import SLAService
    service = SLAService(db, user)

    policy = service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")

    targets = service.list_targets(policy_id)

    calendar = None
    if policy.calendar_id:
        calendar = service.get_calendar(policy.calendar_id)

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
    from app.services.support import SLAService
    service = SLAService(db, user)
    calendars, _ = service.list_calendars()

    calendar_usage = service.get_calendar_usage([c.id for c in calendars])

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
        AutomationTrigger,
        AutomationActionType,
    )
    from app.services.support import AutomationService

    service = AutomationService(db, principal=user)
    rules, _ = service.list_db_rules(
        trigger=trigger,
        is_active=True if active_only else None,
        skip=0,
        limit=1000,
    )

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats_map = service.get_rule_execution_stats(thirty_days_ago)

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
        AutomationTrigger,
        AutomationActionType,
    )
    from app.services.support import AutomationService
    from app.services.support.types import AutomationLogFilters

    service = AutomationService(db, principal=user)
    rule = service.get_db_rule(rule_id)

    if not rule:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Automation rule not found"
        return HTMLResponse(template.render(context), status_code=404)

    recent_logs, _ = service.list_logs(
        filters=AutomationLogFilters(rule_id=rule_id),
        skip=0,
        limit=20,
    )

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats = service.get_rule_log_stats(rule_id, start_date=thirty_days_ago)

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
    total = stats.get("total", 0)
    success = stats.get("success", 0)
    avg_time_ms = stats.get("avg_time_ms", 0)
    context["stats"] = {
        "total": total,
        "success": success,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "avg_time_ms": round(float(avg_time_ms or 0), 1),
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
    from app.services.support import AutomationService

    service = AutomationService(db, principal=user)
    rule = service.toggle_db_rule(rule_id)

    if not rule:
        htmx_toast(response, "Rule not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

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
    from app.models.support_csat import SurveyType, SurveyTrigger
    from app.services.support import CSATService

    service = CSATService(db, principal=user)
    surveys = service.list_surveys(active_only=active_only)

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats_map = service.get_survey_stats(thirty_days_ago)
    overall_stats = service.get_overall_stats(thirty_days_ago)
    response_counts = service.get_response_counts(thirty_days_ago)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CSAT Surveys"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "CSAT"},
    ])

    context["surveys"] = surveys
    context["stats_map"] = stats_map
    sent_count = response_counts.get("sent", 0)
    responded_count = response_counts.get("responded", 0)
    context["summary"] = {
        "total_surveys": len(surveys),
        "active_surveys": sum(1 for s in surveys if s.is_active),
        "total_responses": overall_stats.get("total", 0),
        "avg_rating": overall_stats.get("avg_rating", 0),
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
    from app.models.support_csat import SurveyType, SurveyTrigger
    from app.services.support import CSATService, CSATSurveyNotFoundError

    service = CSATService(db, principal=user)
    try:
        survey = service.get_survey(survey_id)
    except CSATSurveyNotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Survey not found"
        return HTMLResponse(template.render(context), status_code=404)

    responses = service.list_responses(
        survey_id=survey_id,
        responded_only=True,
        limit=50,
        offset=0,
    )

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats = service.get_survey_period_stats(survey_id, thirty_days_ago)
    rating_distribution = stats.get("rating_distribution", {})

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
    total = stats.get("total", 0)
    positive = stats.get("positive", 0)
    context["stats"] = {
        "total": total,
        "avg_rating": stats.get("avg_rating", 0),
        "positive": positive,
        "negative": stats.get("negative", 0),
        "satisfaction_pct": round(positive / total * 100, 1) if total > 0 else 0,
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
    from app.services.support import CSATService, CSATSurveyNotFoundError, CSATSurveyUpdate

    service = CSATService(db, principal=user)
    try:
        survey = service.get_survey(survey_id)
    except CSATSurveyNotFoundError:
        htmx_toast(response, "Survey not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

    service.update_survey(survey_id, CSATSurveyUpdate(is_active=not survey.is_active))
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
    from app.models.support_sla import RoutingStrategy
    from app.services.support import AgentService, RoutingService

    routing_service = RoutingService(db, principal=user)
    rules = routing_service.list_ticket_routing_rules(
        team_id=team_id,
        active_only=active_only,
    )

    teams = AgentService(db, user).list_teams(active_only=True)

    agent_workload = routing_service.get_unified_agent_workloads()
    queue_health = routing_service.get_ticket_queue_health()

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
    from app.models.support_sla import RoutingStrategy
    from app.services.support import RoutingService, RoutingRuleNotFoundError

    service = RoutingService(db, principal=user)
    try:
        rule = service.get_ticket_routing_rule(rule_id)
    except RoutingRuleNotFoundError:
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
    from app.services.support import RoutingService, RoutingRuleNotFoundError, TicketRoutingRuleUpdate

    service = RoutingService(db, principal=user)
    try:
        rule = service.get_ticket_routing_rule(rule_id)
    except RoutingRuleNotFoundError:
        htmx_toast(response, "Rule not found", "error")
        return HTMLResponse(
            "",
            status_code=404,
            headers={"HX-Reswap": "none", **dict(response.headers)},
        )

    service.update_ticket_routing_rule(rule_id, TicketRoutingRuleUpdate(is_active=not rule.is_active))
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
    from app.models.conversation import ConversationStatus, ConversationPriority
    from app.services.support import LegacyConversationService

    offset = (page - 1) * per_page
    service = LegacyConversationService(db)

    conversations, total = service.list_conversations(
        status=status,
        channel=channel,
        search=q,
        offset=offset,
        limit=per_page,
    )

    ticket_ids = [c.unified_ticket_id for c in conversations if c.unified_ticket_id]
    ticket_map = service.get_ticket_map(ticket_ids)

    total_pages = (total + per_page - 1) // per_page
    status_counts = service.get_status_counts()
    channel_options = service.list_channels()

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
    from app.models.conversation import ConversationStatus
    from app.services.support import LegacyConversationService

    service = LegacyConversationService(db)
    conversation = service.get_conversation(conversation_id)

    if not conversation:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Conversation not found"
        return HTMLResponse(template.render(context), status_code=404)

    customer = service.get_customer_for_conversation(conversation.customer_account_id)
    ticket = None
    if conversation.unified_ticket_id:
        ticket_map = service.get_ticket_map([conversation.unified_ticket_id])
        ticket = ticket_map.get(conversation.unified_ticket_id)

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
    from app.models.support_csat import SurveyType
    from app.services.support import CSATService

    start_dt = datetime.utcnow() - timedelta(days=days)
    six_months_ago = datetime.utcnow() - timedelta(days=180)

    service = CSATService(db, principal=user)
    overall = service.get_overall_stats(start_dt)
    response_counts = service.get_response_counts(start_dt)
    trends = service.get_trends(six_months_ago)
    by_agent = service.get_agent_stats(start_dt)
    by_type = service.get_type_stats(start_dt)
    recent_feedback = service.list_recent_feedback(start_dt, limit=20)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "CSAT Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "CSAT", "href": "/support/csat"},
        {"label": "Analytics"},
    ])

    context["period_days"] = days
    sent_count = response_counts.get("sent", 0)
    responded_count = response_counts.get("responded", 0)
    total = overall.get("total", 0)
    positive = overall.get("positive", 0)
    context["stats"] = {
        "total_responses": total,
        "avg_rating": overall.get("avg_rating", 0),
        "positive": positive,
        "negative": overall.get("negative", 0),
        "satisfaction_pct": round(positive / total * 100, 1) if total > 0 else 0,
        "response_rate": round(responded_count / sent_count * 100, 1) if sent_count > 0 else 0,
    }

    context["trends"] = [
        {
            "period": f"{t['year']}-{t['month']:02d}",
            "count": t["count"],
            "avg_rating": t["avg_rating"],
        }
        for t in trends
    ]

    context["by_agent"] = [
        {
            "agent_id": a["agent_id"],
            "agent_name": a["agent_name"],
            "count": a["count"],
            "avg_rating": a["avg_rating"],
            "satisfaction_pct": round(a["positive"] / a["count"] * 100, 1) if a["count"] > 0 else 0,
        }
        for a in by_agent
    ]

    context["by_type"] = [
        {
            "type": t["type"].upper() if t["type"] else "Unknown",
            "count": t["count"],
            "avg_rating": t["avg_rating"],
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
    start_dt = datetime.utcnow() - timedelta(days=days)
    offset = (page - 1) * per_page

    service = SupportWebService(db, user_id=user.id, principal=user)
    result = service.list_sla_breaches(
        start_dt=start_dt,
        offset=offset,
        limit=per_page,
    )
    breached_tickets = result["items"]
    total = result["total"]
    first_response_breaches = result["first_response_breaches"]
    resolution_breaches = result["resolution_breaches"]
    total_tickets = result["total_tickets"]
    by_priority = result["by_priority"]

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
    """Support teams list with comprehensive analytics."""
    from app.services.support import AgentService

    service = AgentService(db, user)
    teams, team_stats = service.list_teams_with_stats(active_only=None)

    # Get team performance analytics (30 days)
    analytics = SupportAnalyticsService(db, principal=user)
    filters = AnalyticsFilters(days=30)
    team_performance = analytics.get_team_performance(filters)

    # Build performance lookup by team_id
    perf_by_team = {p.team_id: p for p in team_performance}

    # Calculate aggregate stats
    total_capacity = sum(s["total_capacity"] for s in team_stats.values())
    avg_sla_pct = 0.0
    avg_csat = 0.0
    csat_count = 0

    if team_performance:
        total_sla = sum(p.sla_attainment_pct for p in team_performance)
        avg_sla_pct = total_sla / len(team_performance) if team_performance else 0

        csat_scores = [p.csat_score for p in team_performance if p.csat_score is not None]
        if csat_scores:
            avg_csat = sum(csat_scores) / len(csat_scores)
            csat_count = len(csat_scores)

    # Team rankings by SLA
    teams_by_sla = sorted(
        [p for p in team_performance if p.total_tickets >= 5],
        key=lambda x: x.sla_attainment_pct,
        reverse=True
    )

    # Team rankings by utilization
    teams_by_util = sorted(
        team_performance,
        key=lambda x: x.utilization_pct,
        reverse=True
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Teams"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/dashboard"},
        {"label": "Teams"},
    ])

    context["teams"] = teams
    context["team_stats"] = team_stats
    context["team_performance"] = perf_by_team
    context["teams_by_sla"] = teams_by_sla[:5]
    context["teams_by_util"] = teams_by_util[:5]
    context["summary"] = {
        "total_teams": len(teams),
        "active_teams": sum(1 for t in teams if t.is_active),
        "total_capacity": total_capacity,
        "avg_sla_pct": round(avg_sla_pct, 1),
        "avg_csat": round(avg_csat, 1) if csat_count > 0 else None,
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
    """Team detail page with comprehensive performance metrics."""
    from app.services.support import AgentService, TeamNotFoundError

    service = AgentService(db, user)
    try:
        result = service.get_team_detail(team_id)
    except TeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    team = result["team"]
    agent_workload = result["agents"]
    stats = result["stats"]

    # Get team performance analytics (30 days)
    analytics = SupportAnalyticsService(db, principal=user)
    filters = AnalyticsFilters(days=30, team_id=team_id)
    team_perf_list = analytics.get_team_performance(filters)
    team_perf = team_perf_list[0] if team_perf_list else None

    # Get agent performance for this team
    agent_filters = AnalyticsFilters(days=30, team_id=team_id)
    agent_performance = analytics.get_agent_performance(agent_filters, limit=50)
    agent_perf_by_id = {p.agent_id: p for p in agent_performance}

    # Get organization-wide averages for comparison
    org_filters = AnalyticsFilters(days=30)
    all_teams = analytics.get_team_performance(org_filters)
    org_avg_sla = sum(t.sla_attainment_pct for t in all_teams) / len(all_teams) if all_teams else 0
    org_avg_resolution = sum(t.avg_resolution_hours for t in all_teams) / len(all_teams) if all_teams else 0
    csat_scores = [t.csat_score for t in all_teams if t.csat_score is not None]
    org_avg_csat = sum(csat_scores) / len(csat_scores) if csat_scores else None

    # Enhanced stats with performance metrics
    enhanced_stats = {
        **stats,
        "total_30d": team_perf.total_tickets if team_perf else 0,
        "resolved_30d": team_perf.resolved_tickets if team_perf else 0,
        "resolution_rate": team_perf.resolution_rate if team_perf else 0,
        "avg_resolution_hours": team_perf.avg_resolution_hours if team_perf else 0,
        "avg_first_response_hours": team_perf.avg_first_response_hours if team_perf else 0,
        "sla_attainment_pct": team_perf.sla_attainment_pct if team_perf else 0,
        "csat_score": team_perf.csat_score if team_perf else None,
        "utilization_pct": team_perf.utilization_pct if team_perf else 0,
        "current_open": team_perf.current_open if team_perf else 0,
        # Organization comparison
        "org_avg_sla": round(org_avg_sla, 1),
        "org_avg_resolution": round(org_avg_resolution, 1),
        "org_avg_csat": round(org_avg_csat, 1) if org_avg_csat else None,
    }

    # Top 3 performers in this team
    top_performers = sorted(
        [p for p in agent_performance if p.total_tickets >= 3],
        key=lambda x: (x.sla_attainment_pct, x.resolution_rate),
        reverse=True
    )[:3]

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
    context["stats"] = enhanced_stats
    context["agent_performance"] = agent_perf_by_id
    context["top_performers"] = top_performers
    context["team_perf"] = team_perf

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


@tags_router.get("", dependencies=[RequireSupportRead])
async def tags_list_redirect():
    """Redirect to tags settings page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/support/tags", status_code=301)


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
    service = EscalationService(db, principal=user)
    policies = service.list_policies(active_only=False)
    for policy in policies:
        _ = policy.levels

    candidate_counts = service.get_candidate_counts(policies)

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
    from app.services.support import AutomationService
    from app.services.support.types import AutomationLogFilters

    offset = (page - 1) * per_page
    service = AutomationService(db, principal=user)

    logs, total = service.list_logs(
        filters=AutomationLogFilters(
            rule_id=rule_id,
            success=success,
            trigger=trigger,
        ),
        skip=offset,
        limit=per_page,
    )

    rules, _ = service.list_db_rules(skip=0, limit=1000)
    trigger_options = service.list_distinct_triggers()

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stats = service.get_logs_stats(start_date=thirty_days_ago)

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

    total_30d = stats.get("total", 0)
    success_30d = stats.get("success", 0)
    context["stats"] = {
        "total_30d": total_30d,
        "success_30d": success_30d,
        "success_rate": round(success_30d / total_30d * 100, 1) if total_30d > 0 else 0,
        "avg_time_ms": round(float(stats.get("avg_time_ms", 0) or 0), 1),
    }

    template = templates.get_template("modules/support/templates/pages/automation_logs.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ROUTER CONSOLIDATION
# =============================================================================
# Include all sub-routers into the main router for module discovery
# Main router has no prefix; sub-routers have their full /support/xxx paths

router.include_router(dashboard_router)
router.include_router(tickets_router)
router.include_router(agents_router)
router.include_router(canned_router)
router.include_router(sla_router)
router.include_router(kb_router)
router.include_router(automation_router)
router.include_router(csat_router)
router.include_router(routing_router)
router.include_router(conversations_router)
router.include_router(teams_router)
router.include_router(tags_router)
router.include_router(queues_router)
router.include_router(escalations_router)
router.include_router(channels_router)
router.include_router(webhooks_router)

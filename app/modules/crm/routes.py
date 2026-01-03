"""
CRM Module Routes - Leads, Opportunities, Activities, Campaigns.

HTMX-powered routes for CRM management.
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Request, Response, Query, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Import models
from app.models.party import Party, PartyRole
from app.models.crm import Opportunity, OpportunityStage, Activity, Campaign

router = APIRouter()
templates = get_template_env()


# =============================================================================
# Leads Routes
# =============================================================================

@router.get("/crm/leads", response_class=HTMLResponse)
async def leads_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    qualification: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List leads (Party + PartyRole)."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leads"
    context["now"] = datetime.utcnow()

    company_id = user.company_id
    per_page = 25

    # Base query - leads are parties with "lead" role
    query = db.query(Party).join(
        PartyRole, and_(
            PartyRole.party_id == Party.id,
            PartyRole.role == "lead",
        )
    ).filter(Party.company_id == company_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Party.name.ilike(search_term),
                Party.email.ilike(search_term),
                Party.phone.ilike(search_term),
            )
        )

    if status:
        query = query.filter(PartyRole.status == status)

    # Get stats for filters
    total_leads = query.count()

    # Paginate
    leads = query.order_by(Party.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["leads"] = leads
    context["total"] = total_leads
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total_leads + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status
    context["qualification_filter"] = qualification

    # Status options for filter
    context["status_options"] = [
        {"value": "active", "label": "Active"},
        {"value": "qualified", "label": "Qualified"},
        {"value": "disqualified", "label": "Disqualified"},
        {"value": "converted", "label": "Converted"},
    ]

    # Qualification options
    context["qualification_options"] = [
        {"value": "hot", "label": "Hot"},
        {"value": "warm", "label": "Warm"},
        {"value": "cold", "label": "Cold"},
    ]

    template = templates.get_template("modules/crm/templates/leads/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/leads/table", response_class=HTMLResponse)
async def leads_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - leads table."""
    context = get_base_context(request, response, user, csrf_token)
    company_id = user.company_id
    per_page = 25

    query = db.query(Party).join(
        PartyRole, and_(
            PartyRole.party_id == Party.id,
            PartyRole.role == "lead",
        )
    ).filter(Party.company_id == company_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Party.name.ilike(search_term),
                Party.email.ilike(search_term),
            )
        )

    if status:
        query = query.filter(PartyRole.status == status)

    total = query.count()
    leads = query.order_by(Party.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["leads"] = leads
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/leads/partials/leads_table.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Lead detail page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    company_id = user.company_id

    lead = db.query(Party).filter(
        Party.id == lead_id,
        Party.company_id == company_id,
    ).first()

    if not lead:
        context["error"] = "Lead not found"
        template = templates.get_template("modules/crm/templates/leads/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    # Get lead role
    lead_role = db.query(PartyRole).filter(
        PartyRole.party_id == lead_id,
        PartyRole.role == "lead",
    ).first()

    # Get activities for this lead
    activities = db.query(Activity).filter(
        Activity.party_id == lead_id,
    ).order_by(Activity.scheduled_at.desc()).limit(10).all()

    context["lead"] = lead
    context["lead_role"] = lead_role
    context["activities"] = activities
    context["page_title"] = f"Lead: {lead.display_name or lead.name}"

    template = templates.get_template("modules/crm/templates/leads/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Opportunities Routes
# =============================================================================

@router.get("/crm/opportunities", response_class=HTMLResponse)
async def opportunities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    stage_id: Optional[int] = None,
    view: str = "list",  # list or kanban
    page: int = Query(1, ge=1),
):
    """List opportunities."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Opportunities"
    context["now"] = datetime.utcnow()

    company_id = user.company_id
    per_page = 25

    # Get stages for kanban/filter
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.company_id == company_id,
    ).order_by(OpportunityStage.order).all()
    context["stages"] = stages

    # Base query
    query = db.query(Opportunity).filter(
        Opportunity.company_id == company_id,
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(Opportunity.name.ilike(search_term))

    if status:
        query = query.filter(Opportunity.status == status)

    if stage_id:
        query = query.filter(Opportunity.stage_id == stage_id)

    total = query.count()

    if view == "kanban":
        # For kanban, get all open opportunities grouped by stage
        opportunities_by_stage = {}
        for stage in stages:
            stage_opps = db.query(Opportunity).filter(
                Opportunity.company_id == company_id,
                Opportunity.stage_id == stage.id,
                Opportunity.status == "open",
            ).order_by(Opportunity.updated_at.desc()).all()
            opportunities_by_stage[stage.id] = stage_opps
        context["opportunities_by_stage"] = opportunities_by_stage
    else:
        # List view with pagination
        opportunities = query.order_by(Opportunity.updated_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        context["opportunities"] = opportunities

    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status
    context["stage_filter"] = stage_id
    context["view"] = view

    context["status_options"] = [
        {"value": "open", "label": "Open"},
        {"value": "won", "label": "Won"},
        {"value": "lost", "label": "Lost"},
    ]

    template_name = "modules/crm/templates/opportunities/pages/kanban.html" if view == "kanban" else "modules/crm/templates/opportunities/pages/list.html"
    template = templates.get_template(template_name)
    return HTMLResponse(template.render(context))


@router.get("/crm/opportunities/table", response_class=HTMLResponse)
async def opportunities_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - opportunities table."""
    context = get_base_context(request, response, user, csrf_token)
    company_id = user.company_id
    per_page = 25

    query = db.query(Opportunity).filter(
        Opportunity.company_id == company_id,
    )

    if search:
        query = query.filter(Opportunity.name.ilike(f"%{search}%"))

    if status:
        query = query.filter(Opportunity.status == status)

    total = query.count()
    opportunities = query.order_by(Opportunity.updated_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["opportunities"] = opportunities
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/opportunities/partials/opportunities_table.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/opportunities/{opp_id}", response_class=HTMLResponse)
async def opportunity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opp_id: int,
):
    """Opportunity detail page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    company_id = user.company_id

    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.company_id == company_id,
    ).first()

    if not opportunity:
        context["error"] = "Opportunity not found"
        template = templates.get_template("modules/crm/templates/opportunities/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    # Get stage
    stage = db.query(OpportunityStage).filter(
        OpportunityStage.id == opportunity.stage_id,
    ).first()

    # Get all stages for stage selector
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.company_id == company_id,
    ).order_by(OpportunityStage.order).all()

    # Get party
    party = None
    if opportunity.party_id:
        party = db.query(Party).filter(Party.id == opportunity.party_id).first()

    # Get activities
    activities = db.query(Activity).filter(
        Activity.opportunity_id == opp_id,
    ).order_by(Activity.scheduled_at.desc()).limit(10).all()

    context["opportunity"] = opportunity
    context["stage"] = stage
    context["stages"] = stages
    context["party"] = party
    context["activities"] = activities
    context["page_title"] = f"Opportunity: {opportunity.name}"

    template = templates.get_template("modules/crm/templates/opportunities/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Activities Routes
# =============================================================================

@router.get("/crm/activities", response_class=HTMLResponse)
async def activities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    date_filter: Optional[str] = None,  # today, week, overdue
    page: int = Query(1, ge=1),
):
    """List activities."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Activities"
    context["now"] = datetime.utcnow()

    company_id = user.company_id
    per_page = 25

    query = db.query(Activity).filter(
        Activity.company_id == company_id,
    )

    if search:
        query = query.filter(Activity.subject.ilike(f"%{search}%"))

    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    if status:
        query = query.filter(Activity.status == status)

    today = date.today()
    if date_filter == "today":
        query = query.filter(func.date(Activity.scheduled_at) == today)
    elif date_filter == "week":
        week_end = today + timedelta(days=7)
        query = query.filter(
            func.date(Activity.scheduled_at) >= today,
            func.date(Activity.scheduled_at) <= week_end,
        )
    elif date_filter == "overdue":
        query = query.filter(
            Activity.scheduled_at < datetime.utcnow(),
            Activity.status.in_(["scheduled", "pending"]),
        )

    total = query.count()
    activities = query.order_by(Activity.scheduled_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["activities"] = activities
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["search"] = search or ""
    context["type_filter"] = activity_type
    context["status_filter"] = status
    context["date_filter"] = date_filter

    context["type_options"] = [
        {"value": "call", "label": "Call", "icon": "phone"},
        {"value": "meeting", "label": "Meeting", "icon": "users"},
        {"value": "email", "label": "Email", "icon": "mail"},
        {"value": "task", "label": "Task", "icon": "check-square"},
        {"value": "note", "label": "Note", "icon": "file-text"},
    ]

    context["status_options"] = [
        {"value": "scheduled", "label": "Scheduled"},
        {"value": "in_progress", "label": "In Progress"},
        {"value": "completed", "label": "Completed"},
        {"value": "cancelled", "label": "Cancelled"},
    ]

    template = templates.get_template("modules/crm/templates/activities/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/activities/table", response_class=HTMLResponse)
async def activities_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - activities table."""
    context = get_base_context(request, response, user, csrf_token)
    company_id = user.company_id
    per_page = 25

    query = db.query(Activity).filter(
        Activity.company_id == company_id,
    )

    if search:
        query = query.filter(Activity.subject.ilike(f"%{search}%"))

    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    total = query.count()
    activities = query.order_by(Activity.scheduled_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["activities"] = activities
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/activities/partials/activities_table.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/activities/{activity_id}", response_class=HTMLResponse)
async def activity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    activity_id: int,
):
    """Activity detail page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    company_id = user.company_id

    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.company_id == company_id,
    ).first()

    if not activity:
        context["error"] = "Activity not found"
        template = templates.get_template("modules/crm/templates/activities/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    # Get related party
    party = None
    if activity.party_id:
        party = db.query(Party).filter(Party.id == activity.party_id).first()

    # Get related opportunity
    opportunity = None
    if activity.opportunity_id:
        opportunity = db.query(Opportunity).filter(
            Opportunity.id == activity.opportunity_id
        ).first()

    context["activity"] = activity
    context["party"] = party
    context["opportunity"] = opportunity
    context["page_title"] = f"Activity: {activity.subject}"

    template = templates.get_template("modules/crm/templates/activities/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Campaigns Routes
# =============================================================================

@router.get("/crm/campaigns", response_class=HTMLResponse)
async def campaigns_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List campaigns."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Campaigns"
    context["now"] = datetime.utcnow()

    company_id = user.company_id
    per_page = 25

    query = db.query(Campaign).filter(
        Campaign.company_id == company_id,
    )

    if search:
        query = query.filter(Campaign.name.ilike(f"%{search}%"))

    if status:
        query = query.filter(Campaign.status == status)

    total = query.count()
    campaigns = query.order_by(Campaign.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context["campaigns"] = campaigns
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status

    context["status_options"] = [
        {"value": "draft", "label": "Draft"},
        {"value": "active", "label": "Active"},
        {"value": "paused", "label": "Paused"},
        {"value": "completed", "label": "Completed"},
    ]

    template = templates.get_template("modules/crm/templates/campaigns/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    campaign_id: int,
):
    """Campaign detail page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    company_id = user.company_id

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.company_id == company_id,
    ).first()

    if not campaign:
        context["error"] = "Campaign not found"
        template = templates.get_template("modules/crm/templates/campaigns/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    context["campaign"] = campaign
    context["page_title"] = f"Campaign: {campaign.name}"

    template = templates.get_template("modules/crm/templates/campaigns/pages/detail.html")
    return HTMLResponse(template.render(context))

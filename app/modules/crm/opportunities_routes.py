"""
CRM Opportunities Routes - Sales Pipeline Management with SSR + HTMX.

Permission Requirements:
- crm:read - View opportunities and pipeline
- crm:write - Create, update, delete opportunities
"""
from __future__ import annotations

from typing import Optional, Any, cast
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.crm import Opportunity, OpportunityStage, OpportunityStatus
from app.models.contact import Contact
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Permission dependencies
RequireCRMRead = Depends(require_scope("crm:read"))
RequireCRMWrite = Depends(require_scope("crm:write"))

router = APIRouter(prefix="/crm", tags=["crm-opportunities"])
templates = get_template_env()

def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value in ("", None):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.title()}
        for s in OpportunityStatus
    ]


def get_stages(db) -> list[OpportunityStage]:
    """Get all active pipeline stages ordered by sequence."""
    return cast(
        list[OpportunityStage],
        db.query(OpportunityStage).filter(
            OpportunityStage.is_active == True
        ).order_by(OpportunityStage.sequence).all(),
    )


def get_pipeline_stats(db) -> dict:
    """Calculate pipeline statistics."""
    result = db.query(
        func.count(Opportunity.id).label("total_count"),
        func.sum(Opportunity.deal_value).label("total_value"),
        func.sum(Opportunity.weighted_value).label("weighted_value"),
        func.avg(Opportunity.deal_value).label("avg_deal_value"),
    ).filter(Opportunity.status == OpportunityStatus.OPEN).first()

    return {
        "total_count": result.total_count or 0,
        "total_value": result.total_value or Decimal("0"),
        "weighted_value": result.weighted_value or Decimal("0"),
        "avg_deal_value": result.avg_deal_value or Decimal("0"),
    }


# =============================================================================
# OPPORTUNITIES LIST
# =============================================================================

@router.get("/opportunities", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def opportunities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    stage: Optional[int] = Query(None, description="Filter by stage"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Opportunities list page."""
    # Build query
    query = db.query(Opportunity)

    # Search
    if q:
        search_filter = or_(
            Opportunity.name.ilike(f"%{q}%"),
            Opportunity.description.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Opportunity.status == status)
    if stage:
        query = query.filter(Opportunity.stage_id == stage)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Opportunity, sort, Opportunity.created_at)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    opportunities = query.offset(offset).limit(per_page).all()

    # Get stages for filter dropdown
    stages = get_stages(db)

    # Get stats
    stats = get_pipeline_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["opportunities"] = opportunities
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_stage"] = stage
    context["status_options"] = get_status_options()
    context["stages"] = stages
    context["stats"] = stats
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/crm/templates/opportunities/partials/opportunities_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Opportunities"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Opportunities"},
    ])

    template = templates.get_template("modules/crm/templates/opportunities/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/opportunities/table", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def opportunities_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stage: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Opportunities table partial for HTMX updates."""
    return await opportunities_list(
        request, response, user, csrf_token, db,
        q, status, stage, page, per_page, sort, dir
    )


# =============================================================================
# OPPORTUNITY CRUD
# =============================================================================

@router.get("/opportunities/new", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New opportunity form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Opportunity"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Opportunities", "href": "/crm/opportunities"},
        {"label": "New Opportunity"},
    ])
    context["opportunity"] = None
    context["status_options"] = get_status_options()
    context["stages"] = get_stages(db)
    context["contacts"] = db.query(Contact).order_by(Contact.name).limit(100).all()
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/opportunities/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/opportunities", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new opportunity."""
    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    deal_value_str = _form_str(form, "deal_value", "0")

    if not name:
        errors["name"] = "Name is required"

    try:
        deal_value = Decimal(deal_value_str) if deal_value_str else Decimal("0")
        if deal_value < 0:
            errors["deal_value"] = "Deal value must be positive"
    except:
        errors["deal_value"] = "Invalid deal value"
        deal_value = Decimal("0")

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Opportunity"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Opportunities", "href": "/crm/opportunities"},
            {"label": "New Opportunity"},
        ])
        context["opportunity"] = None
        context["status_options"] = get_status_options()
        context["stages"] = get_stages(db)
        context["contacts"] = db.query(Contact).order_by(Contact.name).limit(100).all()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/crm/templates/opportunities/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse optional fields
    probability = _form_int(form, "probability", 50)
    stage_id = _form_int(form, "stage_id", 0) or None
    unified_contact_id = _form_int(form, "unified_contact_id", 0) or None

    expected_close_date_str = _form_str(form, "expected_close_date")
    expected_close_date = None
    if expected_close_date_str:
        try:
            expected_close_date = date.fromisoformat(expected_close_date_str)
        except ValueError:
            pass

    # Create opportunity
    opportunity = Opportunity(
        name=name,
        description=_form_str(form, "description") or None,
        deal_value=deal_value,
        probability=probability,
        weighted_value=deal_value * Decimal(probability) / Decimal("100"),
        status=OpportunityStatus(
            _form_str(form, "status", OpportunityStatus.OPEN.value)
        ),
        stage_id=stage_id,
        unified_contact_id=unified_contact_id,
        expected_close_date=expected_close_date,
        source=_form_str(form, "source") or None,
        campaign=_form_str(form, "campaign") or None,
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)

    set_flash(response, f"Opportunity '{opportunity.name}' created successfully.", "success")
    return RedirectResponse(url=f"/crm/opportunities/{opportunity.id}", status_code=303)


@router.get("/opportunities/{opportunity_id}", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def opportunity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opportunity_id: int,
):
    """Opportunity detail page."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = opportunity.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Opportunities", "href": "/crm/opportunities"},
        {"label": opportunity.name},
    ])
    context["opportunity"] = opportunity
    context["stages"] = get_stages(db)

    template = templates.get_template("modules/crm/templates/opportunities/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/opportunities/{opportunity_id}/edit", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opportunity_id: int,
):
    """Opportunity edit form page."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {opportunity.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Opportunities", "href": "/crm/opportunities"},
        {"label": opportunity.name, "href": f"/crm/opportunities/{opportunity.id}"},
        {"label": "Edit"},
    ])
    context["opportunity"] = opportunity
    context["status_options"] = get_status_options()
    context["stages"] = get_stages(db)
    context["contacts"] = db.query(Contact).order_by(Contact.name).limit(100).all()
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/opportunities/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/opportunities/{opportunity_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    opportunity_id: int,
):
    """Update an opportunity."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    form = await request.form()

    # Basic validation
    errors = {}
    name = _form_str(form, "name")
    deal_value_str = _form_str(form, "deal_value", "0")

    if not name:
        errors["name"] = "Name is required"

    try:
        deal_value = Decimal(deal_value_str) if deal_value_str else Decimal("0")
        if deal_value < 0:
            errors["deal_value"] = "Deal value must be positive"
    except:
        errors["deal_value"] = "Invalid deal value"
        deal_value = Decimal("0")

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {opportunity.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Opportunities", "href": "/crm/opportunities"},
            {"label": opportunity.name, "href": f"/crm/opportunities/{opportunity.id}"},
            {"label": "Edit"},
        ])
        context["opportunity"] = opportunity
        context["status_options"] = get_status_options()
        context["stages"] = get_stages(db)
        context["contacts"] = db.query(Contact).order_by(Contact.name).limit(100).all()
        context["errors"] = errors

        template = templates.get_template("modules/crm/templates/opportunities/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse optional fields
    probability = _form_int(form, "probability", 50)
    stage_id = _form_int(form, "stage_id", 0) or None
    unified_contact_id = _form_int(form, "unified_contact_id", 0) or None

    expected_close_date_str = _form_str(form, "expected_close_date")
    expected_close_date = None
    if expected_close_date_str:
        try:
            expected_close_date = date.fromisoformat(expected_close_date_str)
        except ValueError:
            pass

    # Update opportunity
    opportunity.name = name
    opportunity.description = _form_str(form, "description") or None
    opportunity.deal_value = deal_value
    opportunity.probability = probability
    opportunity.weighted_value = deal_value * Decimal(probability) / Decimal("100")
    status_value = _form_str(
        form,
        "status",
        opportunity.status.value if opportunity.status else OpportunityStatus.OPEN.value,
    )
    try:
        opportunity.status = OpportunityStatus(status_value)
    except ValueError:
        pass
    opportunity.stage_id = stage_id
    opportunity.unified_contact_id = unified_contact_id
    opportunity.expected_close_date = expected_close_date
    opportunity.source = _form_str(form, "source") or None
    opportunity.campaign = _form_str(form, "campaign") or None
    db.commit()

    set_flash(response, f"Opportunity '{opportunity.name}' updated successfully.", "success")
    return RedirectResponse(url=f"/crm/opportunities/{opportunity.id}", status_code=303)


@router.delete("/opportunities/{opportunity_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    opportunity_id: int,
):
    """Delete an opportunity."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    name = opportunity.name
    db.delete(opportunity)
    db.commit()

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Opportunity '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Opportunity '{name}' deleted.", "success")
    return RedirectResponse(url="/crm/opportunities", status_code=303)


@router.get("/opportunities/{opportunity_id}/row", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def opportunity_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opportunity_id: int,
):
    """Single opportunity row partial for HTMX updates."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["opp"] = opportunity

    template = templates.get_template("modules/crm/templates/opportunities/partials/opportunity_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# OPPORTUNITY ACTIONS
# =============================================================================

@router.post("/opportunities/{opportunity_id}/stage", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_update_stage(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    opportunity_id: int,
):
    """Update opportunity stage (for Kanban drag-drop)."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Get stage_id from JSON body
    import json
    body = await request.body()
    try:
        data = json.loads(body)
        stage_id = data.get("stage_id")
    except:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if stage_id:
        stage = db.query(OpportunityStage).filter(OpportunityStage.id == stage_id).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Invalid stage")

        opportunity.stage_id = stage_id
        # Update probability to match stage if not manually overridden
        opportunity.probability = stage.probability
        opportunity.update_weighted_value()
        db.commit()

    return HTMLResponse(status_code=200)


@router.post("/opportunities/{opportunity_id}/won", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_mark_won(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    opportunity_id: int,
):
    """Mark opportunity as won."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opportunity.status = OpportunityStatus.WON
    opportunity.probability = 100
    opportunity.update_weighted_value()
    opportunity.actual_close_date = date.today()
    db.commit()

    set_flash(response, f"Congratulations! Deal '{opportunity.name}' marked as won.", "success")
    return RedirectResponse(url=f"/crm/opportunities/{opportunity.id}", status_code=303)


@router.post("/opportunities/{opportunity_id}/lost", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def opportunity_mark_lost(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    opportunity_id: int,
):
    """Mark opportunity as lost."""
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    form = await request.form()
    lost_reason = _form_str(form, "lost_reason")
    competitor = _form_str(form, "competitor")

    opportunity.status = OpportunityStatus.LOST
    opportunity.probability = 0
    opportunity.update_weighted_value()
    opportunity.actual_close_date = date.today()
    opportunity.lost_reason = lost_reason or None
    opportunity.competitor = competitor or None
    db.commit()

    set_flash(response, f"Deal '{opportunity.name}' marked as lost.", "info")
    return RedirectResponse(url=f"/crm/opportunities/{opportunity.id}", status_code=303)


# =============================================================================
# PIPELINE KANBAN VIEW
# =============================================================================

@router.get("/pipeline", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def pipeline_kanban(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Pipeline Kanban board view."""
    # Get all active stages with their opportunities
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.is_active == True,
        OpportunityStage.is_won == False,
        OpportunityStage.is_lost == False,
    ).order_by(OpportunityStage.sequence).all()

    # For each stage, load opportunities
    for stage in stages:
        stage.opportunities = db.query(Opportunity).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN,
        ).order_by(Opportunity.expected_close_date.asc().nullslast()).all()

        # Calculate stage total value for templates
        setattr(stage, "total_value", sum(opp.deal_value for opp in stage.opportunities))

    # Get won opportunities (recent)
    won_opportunities = db.query(Opportunity).filter(
        Opportunity.status == OpportunityStatus.WON,
    ).order_by(Opportunity.actual_close_date.desc()).limit(10).all()

    won_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.status == OpportunityStatus.WON,
    ).scalar() or Decimal("0")

    # Get lost opportunities (recent)
    lost_opportunities = db.query(Opportunity).filter(
        Opportunity.status == OpportunityStatus.LOST,
    ).order_by(Opportunity.actual_close_date.desc()).limit(10).all()

    lost_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.status == OpportunityStatus.LOST,
    ).scalar() or Decimal("0")

    # Get stats
    stats = get_pipeline_stats(db)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Pipeline"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Pipeline"},
    ])
    context["stages"] = stages
    context["won_opportunities"] = won_opportunities
    context["won_value"] = won_value
    context["lost_opportunities"] = lost_opportunities
    context["lost_value"] = lost_value
    context["stats"] = stats

    template = templates.get_template("modules/crm/templates/pipeline/kanban.html")
    return HTMLResponse(template.render(context))

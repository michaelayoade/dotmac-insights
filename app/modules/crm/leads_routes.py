"""
CRM Leads Routes - Lead Management with SSR + HTMX.

This module provides SSR pages for lead management:
- Lead list with filtering/search
- Lead detail with conversion options
- Create/edit lead forms

Permission Requirements:
- crm:read - View leads and lead details
- crm:write - Create, update, convert leads
"""
from __future__ import annotations

from ._deps import (
    # FastAPI
    APIRouter, Request, Response, Query, HTTPException, Depends,
    HTMLResponse, RedirectResponse,
    # SQLAlchemy
    func, or_,
    # Web dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    # Templates
    templates,
    # Core utilities
    is_htmx_request, htmx_toast, set_flash,
    # Models
    ERPNextLead, ERPNextLeadStatus,
    # Permission dependencies
    RequireCRMRead, RequireCRMWrite,
    # Helper functions
    _form_str, _form_int,
    # Enum options
    get_lead_status_options, get_lead_source_options, get_territory_options, get_industry_options,
    get_owner_options,
    # Service
    CRMWebService,
    # Typing
    Optional,
)

router = APIRouter(prefix="/crm/leads", tags=["crm-leads"])


# =============================================================================
# LEADS LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def leads_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
    converted: Optional[str] = Query(None, description="Filter by converted status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Lead list page.

    Returns full page for normal requests, table partial for HTMX requests.
    """
    service = CRMWebService(db, user_id=user.id)

    # Parse converted filter
    converted_bool = None
    if converted == "yes":
        converted_bool = True
    elif converted == "no":
        converted_bool = False

    # Get leads using service
    result = service.list_leads(
        q=q,
        status=status,
        source=source,
        territory=territory,
        converted=converted_bool,
        page=page,
        per_page=per_page,
        sort=sort,
        dir=dir,
    )

    leads = result["items"]
    total = result["total"]

    # Get summary stats
    stats = service.get_leads_summary()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["leads"] = leads
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_source"] = source
    context["current_territory"] = territory
    context["current_converted"] = converted
    context["status_options"] = get_lead_status_options()
    context["source_options"] = get_lead_source_options()
    context["territory_options"] = get_territory_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/crm/templates/leads/partials/leads_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leads"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Leads"},
    ])

    template = templates.get_template("modules/crm/templates/leads/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def leads_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    territory: Optional[str] = Query(None),
    converted: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Lead table partial for HTMX updates."""
    return await leads_list(
        request, response, user, csrf_token, db,
        q, status, source, territory, converted, page, per_page, sort, dir
    )


# =============================================================================
# LEAD CRUD
# =============================================================================

@router.get("/new", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New lead form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Lead"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Leads", "href": "/crm/leads"},
        {"label": "New Lead"},
    ])
    context["lead"] = None
    context["status_options"] = get_lead_status_options()
    context["source_options"] = get_lead_source_options()
    context["territory_options"] = get_territory_options()
    context["industry_options"] = get_industry_options()
    context["owner_options"] = get_owner_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/leads/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new lead."""
    form = await request.form()

    # Basic validation
    errors = {}
    lead_name = _form_str(form, "lead_name")

    if not lead_name:
        errors["lead_name"] = "Lead name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Lead"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Leads", "href": "/crm/leads"},
            {"label": "New Lead"},
        ])
        context["lead"] = None
        context["status_options"] = get_lead_status_options()
        context["source_options"] = get_lead_source_options()
        context["territory_options"] = get_territory_options()
        context["industry_options"] = get_industry_options()
        context["owner_options"] = get_owner_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/crm/templates/leads/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create lead using service
    service = CRMWebService(db, user_id=user.id)
    lead_data = {
        "lead_name": lead_name,
        "company_name": _form_str(form, "company_name") or None,
        "email_id": _form_str(form, "email_id") or None,
        "phone": _form_str(form, "phone") or None,
        "mobile_no": _form_str(form, "mobile_no") or None,
        "website": _form_str(form, "website") or None,
        "source": _form_str(form, "source") or None,
        "lead_owner": _form_str(form, "lead_owner") or None,
        "territory": _form_str(form, "territory") or None,
        "industry": _form_str(form, "industry") or None,
        "market_segment": _form_str(form, "market_segment") or None,
        "city": _form_str(form, "city") or None,
        "state": _form_str(form, "state") or None,
        "country": _form_str(form, "country") or None,
        "notes": _form_str(form, "notes") or None,
    }
    lead = service.create_lead(lead_data)

    set_flash(response, f"Lead '{lead.lead_name}' created successfully.", "success")
    return RedirectResponse(url=f"/crm/leads/{lead.id}", status_code=303)


@router.get("/{lead_id}", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def lead_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Lead detail page."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = lead.lead_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Leads", "href": "/crm/leads"},
        {"label": lead.lead_name},
    ])
    context["lead"] = lead
    context["status_options"] = get_lead_status_options()

    template = templates.get_template("modules/crm/templates/leads/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{lead_id}/edit", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Lead edit form page."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {lead.lead_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Leads", "href": "/crm/leads"},
        {"label": lead.lead_name, "href": f"/crm/leads/{lead.id}"},
        {"label": "Edit"},
    ])
    context["lead"] = lead
    context["status_options"] = get_lead_status_options()
    context["source_options"] = get_lead_source_options()
    context["territory_options"] = get_territory_options()
    context["industry_options"] = get_industry_options()
    context["owner_options"] = get_owner_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/leads/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{lead_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    lead_id: int,
):
    """Update a lead."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    form = await request.form()

    # Basic validation
    errors = {}
    lead_name = _form_str(form, "lead_name")

    if not lead_name:
        errors["lead_name"] = "Lead name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {lead.lead_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Leads", "href": "/crm/leads"},
            {"label": lead.lead_name, "href": f"/crm/leads/{lead.id}"},
            {"label": "Edit"},
        ])
        context["lead"] = lead
        context["status_options"] = get_lead_status_options()
        context["source_options"] = get_lead_source_options()
        context["territory_options"] = get_territory_options()
        context["industry_options"] = get_industry_options()
        context["owner_options"] = get_owner_options(db)
        context["errors"] = errors

        template = templates.get_template("modules/crm/templates/leads/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update lead using service
    update_data = {
        "lead_name": lead_name,
        "company_name": _form_str(form, "company_name") or None,
        "email_id": _form_str(form, "email_id") or None,
        "phone": _form_str(form, "phone") or None,
        "mobile_no": _form_str(form, "mobile_no") or None,
        "website": _form_str(form, "website") or None,
        "source": _form_str(form, "source") or None,
        "lead_owner": _form_str(form, "lead_owner") or None,
        "territory": _form_str(form, "territory") or None,
        "industry": _form_str(form, "industry") or None,
        "market_segment": _form_str(form, "market_segment") or None,
        "city": _form_str(form, "city") or None,
        "state": _form_str(form, "state") or None,
        "country": _form_str(form, "country") or None,
        "notes": _form_str(form, "notes") or None,
        "status": _form_str(form, "status") or None,
    }
    lead = service.update_lead(lead_id, update_data)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    set_flash(response, f"Lead '{lead.lead_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/crm/leads/{lead.id}", status_code=303)


# =============================================================================
# LEAD ACTIONS
# =============================================================================

@router.post("/{lead_id}/qualify", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_qualify(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    lead_id: int,
):
    """Mark a lead as qualified."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.qualify_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Lead '{lead.lead_name}' qualified.", "success")
        # Return updated row
        context = get_base_context(request, response, user, "")
        context["lead"] = lead
        template = templates.get_template("modules/crm/templates/leads/partials/lead_row.html")
        return HTMLResponse(template.render(context), headers=dict(response.headers))

    set_flash(response, f"Lead '{lead.lead_name}' qualified.", "success")
    return RedirectResponse(url=f"/crm/leads/{lead.id}", status_code=303)


@router.post("/{lead_id}/disqualify", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_disqualify(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    lead_id: int,
):
    """Mark a lead as disqualified."""
    form = await request.form()
    reason = _form_str(form, "reason")

    service = CRMWebService(db, user_id=user.id)
    lead = service.disqualify_lead(lead_id, reason)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Lead '{lead.lead_name}' disqualified.", "warning")
        context = get_base_context(request, response, user, "")
        context["lead"] = lead
        template = templates.get_template("modules/crm/templates/leads/partials/lead_row.html")
        return HTMLResponse(template.render(context), headers=dict(response.headers))

    set_flash(response, f"Lead '{lead.lead_name}' disqualified.", "warning")
    return RedirectResponse(url=f"/crm/leads/{lead.id}", status_code=303)


@router.get("/{lead_id}/convert", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_convert_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Show lead conversion form."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.converted:
        set_flash(response, "This lead has already been converted.", "warning")
        return RedirectResponse(url=f"/crm/leads/{lead.id}", status_code=303)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Convert Lead: {lead.lead_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Leads", "href": "/crm/leads"},
        {"label": lead.lead_name, "href": f"/crm/leads/{lead.id}"},
        {"label": "Convert"},
    ])
    context["lead"] = lead
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/leads/pages/convert.html")
    return HTMLResponse(template.render(context))


@router.post("/{lead_id}/convert", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def lead_convert(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    lead_id: int,
):
    """Convert a lead to a customer."""
    form = await request.form()

    customer_name = _form_str(form, "customer_name")
    customer_type = _form_str(form, "customer_type", "business")
    create_opportunity = _form_str(form, "create_opportunity") == "on"
    opportunity_name = _form_str(form, "opportunity_name")
    deal_value_str = _form_str(form, "deal_value")
    deal_value = float(deal_value_str) if deal_value_str else None

    service = CRMWebService(db, user_id=user.id)
    result = service.convert_lead(
        lead_id,
        customer_name=customer_name or None,
        customer_type=customer_type,
        create_opportunity=create_opportunity,
        opportunity_name=opportunity_name or None,
        deal_value=deal_value,
    )

    if not result["success"]:
        if is_htmx_request(request):
            htmx_toast(response, result.get("error", "Conversion failed"), "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, result.get("error", "Conversion failed"), "error")
        return RedirectResponse(url=f"/crm/leads/{lead_id}", status_code=303)

    if is_htmx_request(request):
        htmx_toast(response, result["message"], "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, result["message"], "success")
    return RedirectResponse(url=f"/crm/contacts", status_code=303)


@router.get("/{lead_id}/row", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def lead_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Single lead row partial for HTMX updates."""
    service = CRMWebService(db, user_id=user.id)
    lead = service.get_lead(lead_id)

    if not lead:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["lead"] = lead

    template = templates.get_template("modules/crm/templates/leads/partials/lead_row.html")
    return HTMLResponse(template.render(context))

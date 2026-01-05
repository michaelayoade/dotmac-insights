"""
Subscriptions Routes - Service Subscription Management with SSR + HTMX.

Permission Requirements:
- subscriptions:read - View subscriptions and tariffs
- subscriptions:write - Create, update, delete, status changes
- network:write - Network assignment and provisioning
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Query, HTTPException, Path

from ._deps import (
    # Types
    Optional, Any, Decimal, datetime, date,
    # FastAPI
    HTMLResponse, RedirectResponse,
    # Dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireSubscriptionsRead, RequireSubscriptionsWrite, RequireNetworkWrite,
    # Context helpers
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    # Template
    templates,
    # Security helpers
    is_htmx_request, htmx_toast, set_flash,
    # Models
    Subscription, SubscriptionStatus, SubscriptionType,
    Tariff, TariffType, Party, Router,
    # Services and errors
    NotFoundError, ValidationError, ConflictError,
    SubscriptionService, ServiceTypeConfigService, SubscriptionFilters,
    SubscriptionCreateData, SubscriptionUpdateData, NetworkAssignmentData, ProvisioningConfigData,
    PartyService,
    # Form helpers
    _form_str, _form_int, _form_decimal, _form_bool, _form_date,
    # Option helpers
    get_status_options, get_service_type_options, get_billing_cycle_options,
    get_router_options, get_tariff_options, get_party_options, get_access_method_options,
    # Status helpers
    get_status_style, get_available_transitions, can_transition,
    # Formatting helpers
    format_speed, format_currency,
    # Stats
    compute_subscription_stats,
    # Pagination
    PaginationParams,
)

from ._services import SubscriptionWebService
from app.services.subscriptions.web_services import SubscriptionCommitService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# =============================================================================
# SUBSCRIPTION LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service_type: Optional[str] = Query(None, description="Filter by service type"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Subscriptions list page with stats and filters."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    # Build filters
    filters = SubscriptionFilters(
        search=q,
        status=status,
        service_type=service_type,
        party_id=party_id,
    )
    # Convert page/per_page to offset/limit
    offset = (page - 1) * per_page
    pagination = PaginationParams(offset=offset, limit=per_page)

    # Get subscriptions with pagination
    result = svc.list_subscriptions(
        filters=filters,
        pagination=pagination,
    )

    # Compute stats
    stats = compute_subscription_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["subscriptions"] = result.items
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_service_type"] = service_type
    context["current_party_id"] = party_id
    context["status_options"] = get_status_options()
    context["service_type_options"] = get_service_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)
    context["format_speed"] = format_speed
    context["get_status_style"] = get_status_style

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/subscriptions/templates/partials/subscriptions_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Subscriptions"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions"},
    ])

    template = templates.get_template("modules/subscriptions/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    party_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Subscriptions table partial for HTMX updates."""
    return await subscriptions_list(
        request, response, user, csrf_token, db,
        q, status, service_type, party_id, page, per_page, sort, dir
    )


# =============================================================================
# SUBSCRIPTION DETAIL
# =============================================================================

@router.get("/{subscription_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscription_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Subscription detail page with usage stats and actions."""
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get configuration and lifecycle info
    config_service = ServiceTypeConfigService(db, principal=user)
    config = config_service.get_config()
    grace_period_days = config_service.get_grace_period_days(
        subscription.service_type.value
    )
    early_termination_fee = svc._subscription_svc.calculate_early_termination_fee(subscription.id)

    # Get available status transitions
    transitions = svc.get_status_transitions(subscription_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = subscription.plan_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": subscription.plan_name},
    ])
    context["subscription"] = subscription
    context["format_speed"] = format_speed
    context["format_currency"] = format_currency
    context["get_status_style"] = get_status_style
    context["plan_change_settings"] = config.plan_changes
    context["lifecycle_settings"] = config.lifecycle
    context["grace_period_days"] = grace_period_days
    context["early_termination_fee"] = early_termination_fee
    context["status_transitions"] = transitions

    template = templates.get_template("modules/subscriptions/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SUBSCRIPTION CREATE/EDIT
# =============================================================================

@router.get("/new", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    party_id: Optional[int] = Query(None),
):
    """New subscription form page."""
    # Get options for dropdowns
    tariffs = get_tariff_options(db)
    routers = get_router_options(db)
    customers = get_party_options(db)

    # Pre-selected party if provided
    selected_customer = None
    if party_id:
        party_service = PartyService(db, principal=user)
        try:
            selected_customer = party_service.get_party(party_id)
        except NotFoundError:
            selected_customer = None

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Subscription"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": "New Subscription"},
    ])
    context["subscription"] = None
    context["tariffs"] = tariffs
    context["routers"] = routers
    context["customers"] = customers
    context["selected_customer"] = selected_customer
    context["service_type_options"] = get_service_type_options()
    context["billing_cycle_options"] = get_billing_cycle_options()
    context["access_method_options"] = get_access_method_options()
    context["errors"] = {}

    template = templates.get_template("modules/subscriptions/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new subscription."""
    form = await request.form()
    svc = SubscriptionWebService(db, principal=user)

    # Validation
    errors = {}
    party_id = _form_str(form, "party_id")
    plan_name = _form_str(form, "plan_name")
    price = _form_decimal(form, "price")

    if not party_id or not party_id.isdigit():
        errors["party_id"] = "Customer is required"

    if not plan_name:
        errors["plan_name"] = "Plan name is required"

    if price is None:
        errors["price"] = "Price is required"
    elif price < 0:
        errors["price"] = "Price must be positive"

    if errors:
        # Return form with errors
        tariffs = get_tariff_options(db)
        routers = get_router_options(db)
        customers = get_party_options(db)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Subscription"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Services"},
            {"label": "Subscriptions", "href": "/subscriptions"},
            {"label": "New Subscription"},
        ])
        context["subscription"] = None
        context["tariffs"] = tariffs
        context["routers"] = routers
        context["customers"] = customers
        context["selected_customer"] = None
        context["service_type_options"] = get_service_type_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["access_method_options"] = get_access_method_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/subscriptions/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Build create data
    create_data = SubscriptionCreateData(
        party_id=int(party_id),
        tariff_id=_form_int(form, "tariff_id"),
        service_type=_form_str(form, "service_type", "internet"),
        plan_name=plan_name,
        plan_code=_form_str(form, "plan_code") or None,
        description=_form_str(form, "description") or None,
        price=price,
        currency=_form_str(form, "currency", "NGN"),
        billing_cycle=_form_str(form, "billing_cycle", "monthly"),
        download_speed=_form_int(form, "download_speed"),
        upload_speed=_form_int(form, "upload_speed"),
        router_id=_form_int(form, "router_id"),
        ipv4_address=_form_str(form, "ipv4_address") or None,
        ipv6_address=_form_str(form, "ipv6_address") or None,
        mac_address=_form_str(form, "mac_address") or None,
        access_method=_form_str(form, "access_method") or None,
        ppp_username=_form_str(form, "ppp_username") or None,
        ppp_password=_form_str(form, "ppp_password") or None,
        start_date=_form_date(form, "start_date"),
        end_date=_form_date(form, "end_date"),
    )

    try:
        subscription = commit_svc.create_subscription(create_data)
    except ValidationError as exc:
        errors["_general"] = str(exc)
        # Return form with errors
        tariffs = get_tariff_options(db)
        routers = get_router_options(db)
        customers = get_party_options(db)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Subscription"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Services"},
            {"label": "Subscriptions", "href": "/subscriptions"},
            {"label": "New Subscription"},
        ])
        context["subscription"] = None
        context["tariffs"] = tariffs
        context["routers"] = routers
        context["customers"] = customers
        context["selected_customer"] = None
        context["service_type_options"] = get_service_type_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["access_method_options"] = get_access_method_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/subscriptions/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, f"Subscription '{subscription.plan_name}' created successfully.", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


@router.get("/{subscription_id:int}/edit", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Subscription edit form page."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get options for dropdowns
    tariffs = get_tariff_options(db)
    routers = get_router_options(db)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {subscription.plan_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": subscription.plan_name, "href": f"/subscriptions/{subscription.id}"},
        {"label": "Edit"},
    ])
    context["subscription"] = subscription
    context["tariffs"] = tariffs
    context["routers"] = routers
    context["customers"] = []  # Not changeable on edit
    context["selected_customer"] = subscription.party
    context["service_type_options"] = get_service_type_options()
    context["billing_cycle_options"] = get_billing_cycle_options()
    context["access_method_options"] = get_access_method_options()
    context["status_options"] = get_status_options()
    context["errors"] = {}

    template = templates.get_template("modules/subscriptions/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscription_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Update a subscription."""
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()

    # Validation
    errors = {}
    plan_name = _form_str(form, "plan_name")
    price = _form_decimal(form, "price")

    if not plan_name:
        errors["plan_name"] = "Plan name is required"

    if price is None:
        errors["price"] = "Price is required"
    elif price < 0:
        errors["price"] = "Price must be positive"

    if errors:
        tariffs = get_tariff_options(db)
        routers = get_router_options(db)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {subscription.plan_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Services"},
            {"label": "Subscriptions", "href": "/subscriptions"},
            {"label": subscription.plan_name, "href": f"/subscriptions/{subscription.id}"},
            {"label": "Edit"},
        ])
        context["subscription"] = subscription
        context["tariffs"] = tariffs
        context["routers"] = routers
        context["customers"] = []
        context["selected_customer"] = subscription.party
        context["service_type_options"] = get_service_type_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["access_method_options"] = get_access_method_options()
        context["status_options"] = get_status_options()
        context["errors"] = errors

        template = templates.get_template("modules/subscriptions/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Build update data
    update_data = SubscriptionUpdateData(
        tariff_id=_form_int(form, "tariff_id"),
        service_type=_form_str(form, "service_type") or None,
        plan_name=plan_name,
        plan_code=_form_str(form, "plan_code") or None,
        description=_form_str(form, "description") or None,
        price=price,
        currency=_form_str(form, "currency", "NGN"),
        billing_cycle=_form_str(form, "billing_cycle", "monthly"),
        download_speed=_form_int(form, "download_speed"),
        upload_speed=_form_int(form, "upload_speed"),
        router_id=_form_int(form, "router_id"),
        ipv4_address=_form_str(form, "ipv4_address") or None,
        ipv6_address=_form_str(form, "ipv6_address") or None,
        mac_address=_form_str(form, "mac_address") or None,
        access_method=_form_str(form, "access_method") or None,
        ppp_username=_form_str(form, "ppp_username") or None,
        ppp_password=_form_str(form, "ppp_password") or None,
        start_date=_form_date(form, "start_date"),
        end_date=_form_date(form, "end_date"),
    )

    try:
        subscription = commit_svc.update_subscription(subscription_id, update_data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    set_flash(response, f"Subscription '{subscription.plan_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# STATUS CHANGE
# =============================================================================

@router.get("/{subscription_id:int}/status-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_status_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
    target_status: str = Query(...),
):
    """Status change confirmation modal."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        new_status = SubscriptionStatus(target_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Validate transition
    if not can_transition(subscription.status, new_status):
        raise HTTPException(status_code=400, detail=f"Cannot transition from {subscription.status.value} to {target_status}")

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["target_status"] = target_status
    context["target_status_label"] = target_status.replace("_", " ").title()
    context["get_status_style"] = get_status_style

    template = templates.get_template("modules/subscriptions/templates/partials/status_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id:int}/status", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_status_change(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Change subscription status."""
    svc = SubscriptionWebService(db, principal=user)
    form = await request.form()
    new_status_str = _form_str(form, "status")

    if not new_status_str:
        raise HTTPException(status_code=400, detail="Status is required")

    try:
        new_status = SubscriptionStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    try:
        subscription = svc.get_subscription(subscription_id)
        old_status = subscription.status

        if new_status == SubscriptionStatus.ACTIVE:
            if old_status == SubscriptionStatus.SUSPENDED:
                subscription = commit_svc.reactivate(subscription_id)
            else:
                subscription = commit_svc.activate(subscription_id)
        elif new_status == SubscriptionStatus.SUSPENDED:
            subscription = commit_svc.suspend(subscription_id)
        elif new_status == SubscriptionStatus.CANCELLED:
            subscription = commit_svc.cancel(subscription_id)
        else:
            subscription = commit_svc.change_status(subscription_id, new_status.value)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Status changed from {old_status.value.replace('_', ' ').title()} to {new_status.value.replace('_', ' ').title()}", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Status changed to {new_status.value.replace('_', ' ').title()}", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# LIFECYCLE ACTIONS (PLAN CHANGES, RENEWALS, GRACE)
# =============================================================================

@router.get("/{subscription_id:int}/plan-change-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_plan_change_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
    mode: str = Query("upgrade", description="upgrade or downgrade"),
):
    """Plan change modal (upgrade/downgrade)."""
    if mode not in {"upgrade", "downgrade"}:
        mode = "upgrade"

    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Use service methods to get plan change options (avoids direct db queries)
    upgrade_tariffs = svc.get_tariffs_for_upgrade(subscription_id)
    downgrade_tariffs = svc.get_tariffs_for_downgrade(subscription_id)

    config = svc.get_service_type_config()

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["mode"] = mode
    context["upgrade_tariffs"] = upgrade_tariffs
    context["downgrade_tariffs"] = downgrade_tariffs
    context["plan_change_settings"] = config.plan_changes
    context["format_currency"] = format_currency

    template = templates.get_template("modules/subscriptions/templates/partials/plan_change_modal.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscription_id:int}/upgrade", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_upgrade(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Upgrade a subscription to a higher plan."""
    form = await request.form()
    new_tariff_id = _form_int(form, "new_tariff_id")

    if not new_tariff_id:
        raise HTTPException(status_code=400, detail="Valid plan is required")

    config_service = ServiceTypeConfigService(db, principal=user)
    config = config_service.get_config()

    effective = _form_str(form, "effective") or config.plan_changes.upgrade_effective
    prorate = _form_bool(form, "prorate")

    svc = SubscriptionWebService(db, principal=user)
    try:
        result = commit_svc.execute_upgrade(
            subscription_id=subscription_id,
            new_tariff_id=new_tariff_id,
            effective=effective,
            prorate=prorate,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    message = f"Upgraded from {result.old_plan} to {result.new_plan}"
    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return RedirectResponse(url=f"/subscriptions/{subscription_id}", status_code=303)


@router.post("/{subscription_id:int}/downgrade", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_downgrade(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Downgrade a subscription to a lower plan."""
    form = await request.form()
    new_tariff_id = _form_int(form, "new_tariff_id")

    if not new_tariff_id:
        raise HTTPException(status_code=400, detail="Valid plan is required")

    config_service = ServiceTypeConfigService(db, principal=user)
    config = config_service.get_config()

    effective = _form_str(form, "effective") or config.plan_changes.downgrade_effective
    prorate = _form_bool(form, "prorate")

    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)
    try:
        result = commit_svc.execute_downgrade(
            subscription_id=subscription_id,
            new_tariff_id=new_tariff_id,
            effective=effective,
            prorate=prorate,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    message = f"Downgraded from {result.old_plan} to {result.new_plan}"
    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return RedirectResponse(url=f"/subscriptions/{subscription_id}", status_code=303)


@router.get("/{subscription_id:int}/renew-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_renew_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Renewal modal for subscriptions."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    renewal_info = svc.get_renewal_info(subscription_id)

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["renewal_info"] = renewal_info
    context["format_currency"] = format_currency

    template = templates.get_template("modules/subscriptions/templates/partials/renew_modal.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscription_id:int}/renew", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_renew(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Renew a subscription for additional periods."""
    form = await request.form()
    periods = _form_int(form, "periods", 1)
    new_end_date = _form_date(form, "new_end_date")

    if periods < 1:
        periods = 1

    svc = SubscriptionWebService(db, principal=user)
    try:
        result = commit_svc.execute_renewal(
            subscription_id=subscription_id,
            periods=periods,
            new_end_date=new_end_date,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    message = f"Renewed for {result.periods} period(s)"
    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return RedirectResponse(url=f"/subscriptions/{subscription_id}", status_code=303)


@router.get("/{subscription_id:int}/grace-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_grace_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Grace period extension modal."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    config_service = ServiceTypeConfigService(db, principal=user)
    grace_period_days = config_service.get_grace_period_days(
        subscription.service_type.value
    )

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["grace_period_days"] = grace_period_days

    template = templates.get_template("modules/subscriptions/templates/partials/grace_modal.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscription_id:int}/grace", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_extend_grace(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Extend grace period for a suspended subscription."""
    form = await request.form()
    days = _form_int(form, "days", 0)
    reason = _form_str(form, "reason")

    if days <= 0:
        raise HTTPException(status_code=400, detail="Grace period must be greater than zero")

    svc = SubscriptionWebService(db, principal=user)
    try:
        commit_svc.extend_grace_period(
            subscription_id=subscription_id,
            days=days,
            reason=reason,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    message = f"Extended grace period by {days} day(s)"
    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return RedirectResponse(url=f"/subscriptions/{subscription_id}", status_code=303)


# =============================================================================
# NETWORK ASSIGNMENT
# =============================================================================

@router.get("/{subscription_id:int}/network-modal", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_network_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Network assignment modal."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    routers = get_router_options(db)

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["routers"] = routers

    template = templates.get_template("modules/subscriptions/templates/partials/network_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id:int}/network", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_network_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Update subscription network assignment."""
    form = await request.form()
    svc = SubscriptionWebService(db, principal=user)

    network_data = NetworkAssignmentData(
        router_id=_form_int(form, "router_id"),
        ipv4_address=_form_str(form, "ipv4_address") or None,
        ipv6_address=_form_str(form, "ipv6_address") or None,
        mac_address=_form_str(form, "mac_address") or None,
    )

    try:
        subscription = commit_svc.assign_network(subscription_id, network_data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, "Network assignment updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Network assignment updated", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# DELETE
# =============================================================================

@router.delete("/{subscription_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Delete a subscription (cancel and mark as deleted)."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    name = subscription.plan_name
    try:
        if subscription.status != SubscriptionStatus.CANCELLED:
            commit_svc.cancel(subscription_id)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Subscription '{name}' cancelled.", "success")
        response.headers["HX-Redirect"] = "/subscriptions"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Subscription '{name}' cancelled.", "success")
    return RedirectResponse(url="/subscriptions", status_code=303)


# =============================================================================
# ROW PARTIAL
# =============================================================================

@router.get("/{subscription_id:int}/row", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscription_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Single subscription row partial for HTMX updates."""
    svc = SubscriptionWebService(db, principal=user)
    commit_svc = SubscriptionCommitService(db, svc)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["format_speed"] = format_speed
    context["get_status_style"] = get_status_style

    template = templates.get_template("modules/subscriptions/templates/partials/subscription_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# MIKROTIK PROVISIONING
# =============================================================================

@router.post("/{subscription_id:int}/provision", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_provision(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """
    Manually trigger provisioning for a subscription.

    This queues a Celery task to provision the subscription on its assigned router.
    """
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot provision.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    if not subscription.access_method:
        if is_htmx_request(request):
            htmx_toast(response, "No access method set. Cannot provision.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No access method configured")

    try:
        task_id = svc.queue_provision(subscription_id, triggered_by=user.name or "manual", force=True)

        if is_htmx_request(request):
            htmx_toast(response, f"Provisioning task queued (task_id: {task_id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Provisioning task queued (task_id: {task_id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue provisioning: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue provisioning: {str(e)}")


@router.post("/{subscription_id:int}/disconnect", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_disconnect(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """
    Force disconnect an active session for a subscription.

    This disconnects any active PPPoE/Hotspot session, forcing the customer to reconnect.
    """
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot disconnect.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    try:
        result = svc.disconnect_subscription_sessions(subscription_id, triggered_by=user.name or "manual")

        if is_htmx_request(request):
            htmx_toast(response, f"Disconnect task queued (task_id: {result[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Disconnect task queued (task_id: {result})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue disconnect: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue disconnect: {str(e)}")


@router.post("/{subscription_id:int}/deprovision", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_deprovision(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """
    Remove subscription provisioning from router.

    This removes PPPoE secrets, Hotspot users, DHCP bindings, etc.
    """
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot deprovision.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    try:
        task_id = svc.queue_deprovision(subscription_id, triggered_by=user.name or "manual")

        if is_htmx_request(request):
            htmx_toast(response, f"Deprovisioning task queued (task_id: {task_id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Deprovisioning task queued (task_id: {task_id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue deprovisioning: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue deprovisioning: {str(e)}")


@router.post("/{subscription_id:int}/provision-update", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_provision_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """
    Queue a provisioning update for a subscription.

    Used when speed/IP details change for a provisioned service.
    """
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot update provisioning.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    try:
        task_id = svc.queue_provision_update(subscription_id, triggered_by=user.name or "manual")

        if is_htmx_request(request):
            htmx_toast(response, f"Update task queued (task_id: {task_id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Update task queued (task_id: {task_id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue update: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue update: {str(e)}")


@router.get("/{subscription_id:int}/provisioning-modal", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_provisioning_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Provisioning configuration modal."""
    svc = SubscriptionWebService(db, principal=user)

    try:
        subscription = svc.get_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")

    routers = get_router_options(db)

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["routers"] = routers
    context["access_method_options"] = get_access_method_options()

    template = templates.get_template("modules/subscriptions/templates/partials/provisioning_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id:int}/provisioning", response_class=HTMLResponse, dependencies=[RequireNetworkWrite])
async def subscription_provisioning_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Update subscription provisioning configuration."""
    form = await request.form()
    svc = SubscriptionWebService(db, principal=user)

    provisioning_data = ProvisioningConfigData(
        access_method=_form_str(form, "access_method") or None,
        ppp_username=_form_str(form, "ppp_username") or None,
        ppp_password=_form_str(form, "ppp_password") or None,
        router_id=_form_int(form, "router_id"),
    )

    try:
        subscription = commit_svc.configure_provisioning(subscription_id, provisioning_data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, "Provisioning configuration updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Provisioning configuration updated", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

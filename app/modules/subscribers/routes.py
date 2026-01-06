"""
Subscribers Routes - Subscriber Management with SSR + HTMX.

Permission Requirements:
- crm:read - View subscribers
- crm:write - Create, update, delete subscribers
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Query, HTTPException, Path

from ._deps import (
    # Types
    Optional, Any, Decimal,
    # FastAPI
    HTMLResponse, RedirectResponse,
    # Dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireSubscribersRead, RequireSubscribersWrite,
    # Context helpers
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    # Template
    templates,
    # Security helpers
    is_htmx_request, htmx_toast, set_flash,
    # Services and errors
    NotFoundError, ValidationError, ConflictError,
    SubscriberFilters, SubscriberCreateData, SubscriberUpdateData,
    # Form helpers
    _form_str, _form_int, _form_decimal, _form_bool, _form_date, _form_list,
    # Option helpers
    get_status_options, get_party_type_options, get_account_tier_options, get_billing_cycle_options,
    # Status helpers
    get_status_style, get_subscription_status_style,
    # Formatting helpers
    format_currency, format_phone, format_date, format_datetime,
    # Pagination
    PaginationParams,
)

from ._services import SubscriberWebService

router = APIRouter(prefix="/subscribers", tags=["subscribers"])


# =============================================================================
# SUBSCRIBER LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def subscribers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    party_type: Optional[str] = Query(None, description="Filter by party type"),
    has_active_subscription: Optional[bool] = Query(None, description="Filter by active subscription"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Subscribers list page with stats and filters."""
    svc = SubscriberWebService(db, principal=user)

    # Build filters
    filters = SubscriberFilters(
        search=q,
        status=status,
        party_type=party_type,
        has_active_subscription=has_active_subscription,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get subscribers with pagination
    result = svc.list_subscribers(filters=filters, pagination=pagination)

    # Get stats
    stats = svc.get_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["subscribers"] = result.items
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_party_type"] = party_type
    context["current_has_active"] = has_active_subscription
    context["status_options"] = get_status_options()
    context["party_type_options"] = get_party_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)
    context["get_status_style"] = get_status_style
    context["format_currency"] = format_currency
    context["format_phone"] = format_phone

    # Get subscriber account lookup for list view
    subscriber_accounts = {}
    for sub in result.items:
        account = svc.get_customer_account(sub.id)
        if account:
            subscriber_accounts[sub.id] = account
    context["subscriber_accounts"] = subscriber_accounts

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/subscribers/templates/partials/subscribers_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Subscribers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM"},
        {"label": "Subscribers"},
    ])

    template = templates.get_template("modules/subscribers/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def subscribers_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    party_type: Optional[str] = Query(None),
    has_active_subscription: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name"),
    dir: str = Query("asc"),
):
    """Subscribers table partial for HTMX updates."""
    return await subscribers_list(
        request, response, user, csrf_token, db,
        q, status, party_type, has_active_subscription, page, per_page, sort, dir
    )


# =============================================================================
# SUBSCRIBER 360 DETAIL
# =============================================================================

@router.get("/{subscriber_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def subscriber_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Subscriber 360 detail page."""
    svc = SubscriberWebService(db, principal=user)

    try:
        data_360 = svc.get_subscriber_360(subscriber_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = data_360.party.name or "Subscriber"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM"},
        {"label": "Subscribers", "href": "/subscribers"},
        {"label": data_360.party.name or f"#{subscriber_id}"},
    ])

    # Core data
    context["subscriber"] = data_360.party
    context["roles"] = data_360.roles
    context["account"] = data_360.customer_account

    # Services
    context["subscriptions"] = data_360.subscriptions
    context["payment_subscriptions"] = data_360.payment_subscriptions
    context["service_summary"] = data_360.service_summary

    # Financial
    context["invoices"] = data_360.invoices
    context["financial_summary"] = data_360.financial_summary

    # Support
    context["tickets"] = data_360.tickets
    context["support_summary"] = data_360.support_summary

    # Usage
    context["active_sessions"] = data_360.active_sessions
    context["usage_summary"] = data_360.usage_summary

    # Activity
    context["recent_transactions"] = data_360.recent_transactions
    context["recent_activity"] = data_360.recent_activity

    # Helpers
    context["get_status_style"] = get_status_style
    context["get_subscription_status_style"] = get_subscription_status_style
    context["format_currency"] = format_currency
    context["format_phone"] = format_phone
    context["format_date"] = format_date
    context["format_datetime"] = format_datetime

    template = templates.get_template("modules/subscribers/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SUBSCRIBER CREATE/EDIT
# =============================================================================

@router.get("/new", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New subscriber form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Subscriber"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM"},
        {"label": "Subscribers", "href": "/subscribers"},
        {"label": "New Subscriber"},
    ])
    context["subscriber"] = None
    context["account"] = None
    context["party_type_options"] = get_party_type_options()
    context["account_tier_options"] = get_account_tier_options()
    context["billing_cycle_options"] = get_billing_cycle_options()
    context["errors"] = {}

    template = templates.get_template("modules/subscribers/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new subscriber."""
    form = await request.form()
    svc = SubscriberWebService(db, principal=user)

    # Validation
    errors = {}
    name = _form_str(form, "name")
    party_type = _form_str(form, "party_type", "person")

    if not name:
        errors["name"] = "Name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Subscriber"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Subscribers", "href": "/subscribers"},
            {"label": "New Subscriber"},
        ])
        context["subscriber"] = None
        context["account"] = None
        context["party_type_options"] = get_party_type_options()
        context["account_tier_options"] = get_account_tier_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/subscribers/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Build email list
    emails = []
    email = _form_str(form, "email")
    if email:
        emails.append({"address": email, "is_primary": True, "label": "main"})

    # Build phone list
    phones = []
    phone = _form_str(form, "phone")
    if phone:
        phones.append({"number": phone, "is_primary": True, "label": "main"})

    # Build address list
    addresses = []
    address_line1 = _form_str(form, "address_line1")
    if address_line1:
        addresses.append({
            "type": "primary",
            "line1": address_line1,
            "line2": _form_str(form, "address_line2"),
            "city": _form_str(form, "city"),
            "state": _form_str(form, "state"),
            "postal_code": _form_str(form, "postal_code"),
            "country": _form_str(form, "country", "Nigeria"),
            "is_primary": True,
        })

    # Build create data
    create_data = SubscriberCreateData(
        party_type=party_type,
        name=name,
        first_name=_form_str(form, "first_name") or None,
        last_name=_form_str(form, "last_name") or None,
        legal_name=_form_str(form, "legal_name") or None,
        trading_name=_form_str(form, "trading_name") or None,
        emails=emails,
        phones=phones,
        addresses=addresses,
        tax_id=_form_str(form, "tax_id") or None,
        notes=_form_str(form, "notes") or None,
        create_account=_form_bool(form, "create_account"),
        account_tier=_form_str(form, "account_tier", "standard"),
        billing_email=_form_str(form, "billing_email") or email or None,
        billing_cycle=_form_str(form, "billing_cycle", "monthly"),
        payment_terms=_form_str(form, "payment_terms") or None,
        credit_limit=_form_decimal(form, "credit_limit"),
        currency=_form_str(form, "currency", "NGN"),
    )

    try:
        subscriber = svc.create_subscriber(create_data)
        db.commit()
    except ConflictError as exc:
        errors["email"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Subscriber"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Subscribers", "href": "/subscribers"},
            {"label": "New Subscriber"},
        ])
        context["subscriber"] = None
        context["account"] = None
        context["party_type_options"] = get_party_type_options()
        context["account_tier_options"] = get_account_tier_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/subscribers/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    set_flash(response, f"Subscriber '{subscriber.name}' created successfully.", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber.id}", status_code=303)


@router.get("/{subscriber_id:int}/edit", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Subscriber edit form page."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.get_subscriber(subscriber_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    account = svc.get_customer_account(subscriber_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {subscriber.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM"},
        {"label": "Subscribers", "href": "/subscribers"},
        {"label": subscriber.name, "href": f"/subscribers/{subscriber.id}"},
        {"label": "Edit"},
    ])
    context["subscriber"] = subscriber
    context["account"] = account
    context["party_type_options"] = get_party_type_options()
    context["status_options"] = get_status_options()
    context["account_tier_options"] = get_account_tier_options()
    context["billing_cycle_options"] = get_billing_cycle_options()
    context["errors"] = {}

    template = templates.get_template("modules/subscribers/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscriber_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Update a subscriber."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.get_subscriber(subscriber_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    form = await request.form()

    # Validation
    errors = {}
    name = _form_str(form, "name")

    if not name:
        errors["name"] = "Name is required"

    if errors:
        account = svc.get_customer_account(subscriber_id)

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {subscriber.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM"},
            {"label": "Subscribers", "href": "/subscribers"},
            {"label": subscriber.name, "href": f"/subscribers/{subscriber.id}"},
            {"label": "Edit"},
        ])
        context["subscriber"] = subscriber
        context["account"] = account
        context["party_type_options"] = get_party_type_options()
        context["status_options"] = get_status_options()
        context["account_tier_options"] = get_account_tier_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["errors"] = errors

        template = templates.get_template("modules/subscribers/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Build email list
    emails = []
    email = _form_str(form, "email")
    if email:
        emails.append({"address": email, "is_primary": True, "label": "main"})

    # Build phone list
    phones = []
    phone = _form_str(form, "phone")
    if phone:
        phones.append({"number": phone, "is_primary": True, "label": "main"})

    # Build update data
    update_data = SubscriberUpdateData(
        status=_form_str(form, "status") or None,
        name=name,
        first_name=_form_str(form, "first_name") or None,
        last_name=_form_str(form, "last_name") or None,
        legal_name=_form_str(form, "legal_name") or None,
        trading_name=_form_str(form, "trading_name") or None,
        emails=emails if emails else None,
        phones=phones if phones else None,
        tax_id=_form_str(form, "tax_id") or None,
        notes=_form_str(form, "notes") or None,
        account_tier=_form_str(form, "account_tier") or None,
        billing_email=_form_str(form, "billing_email") or None,
        billing_cycle=_form_str(form, "billing_cycle") or None,
        payment_terms=_form_str(form, "payment_terms") or None,
        credit_limit=_form_decimal(form, "credit_limit"),
    )

    try:
        subscriber = svc.update_subscriber(subscriber_id, update_data)
        db.commit()
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    set_flash(response, f"Subscriber '{subscriber.name}' updated successfully.", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber.id}", status_code=303)


# =============================================================================
# QUICK ACTIONS
# =============================================================================

@router.patch("/{subscriber_id:int}/block", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_block(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Block a subscriber."""
    svc = SubscriberWebService(db, principal=user)
    form = await request.form()
    reason = _form_str(form, "reason")

    try:
        subscriber = svc.block_subscriber(subscriber_id, reason=reason)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Subscriber '{subscriber.name}' blocked.", "warning")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Subscriber '{subscriber.name}' blocked.", "warning")
    return RedirectResponse(url=f"/subscribers/{subscriber.id}", status_code=303)


@router.patch("/{subscriber_id:int}/unblock", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_unblock(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Unblock a subscriber."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.unblock_subscriber(subscriber_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Subscriber '{subscriber.name}' unblocked.", "success")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Subscriber '{subscriber.name}' unblocked.", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber.id}", status_code=303)


@router.delete("/{subscriber_id:int}", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def subscriber_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Delete (deactivate) a subscriber."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.get_subscriber(subscriber_id)
        name = subscriber.name
        svc.delete_subscriber(subscriber_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    except ValidationError as exc:
        if is_htmx_request(request):
            htmx_toast(response, str(exc), "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Subscriber '{name}' deactivated.", "success")
        response.headers["HX-Redirect"] = "/subscribers"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Subscriber '{name}' deactivated.", "success")
    return RedirectResponse(url="/subscribers", status_code=303)


# =============================================================================
# ROW PARTIAL
# =============================================================================

@router.get("/{subscriber_id:int}/row", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def subscriber_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
):
    """Single subscriber row partial for HTMX updates."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.get_subscriber(subscriber_id)
    except NotFoundError:
        return HTMLResponse("", status_code=404)

    account = svc.get_customer_account(subscriber_id)

    context = get_base_context(request, response, user, csrf_token)
    context["subscriber"] = subscriber
    context["account"] = account
    context["get_status_style"] = get_status_style
    context["format_currency"] = format_currency
    context["format_phone"] = format_phone

    template = templates.get_template("modules/subscribers/templates/partials/subscriber_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SERVICE LIFECYCLE ACTIONS
# =============================================================================

@router.get("/{subscriber_id:int}/services/{subscription_id:int}/lifecycle", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def service_lifecycle_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Get lifecycle detail for a service."""
    svc = SubscriberWebService(db, principal=user)

    try:
        subscriber = svc.get_subscriber(subscriber_id)
        lifecycle = svc.get_service_lifecycle(subscription_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    context = get_base_context(request, response, user, csrf_token)
    context["subscriber"] = subscriber
    context["lifecycle"] = lifecycle
    context["suspension_reasons"] = svc.get_suspension_reasons()
    context["termination_reasons"] = svc.get_termination_reasons()

    # Return partial for HTMX or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/subscribers/templates/partials/service_lifecycle.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/subscribers/templates/pages/service_lifecycle.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscriber_id:int}/services/{subscription_id:int}/suspend", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def service_suspend(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Suspend a service."""
    from app.services.subscribers import SuspensionReason

    svc = SubscriberWebService(db, principal=user)
    form = await request.form()

    reason_str = _form_str(form, "reason") or "admin_action"
    notes = _form_str(form, "notes")
    apply_grace = _form_bool(form, "apply_grace_period")
    grace_days = _form_int(form, "grace_period_days")

    try:
        reason = SuspensionReason(reason_str)
    except ValueError:
        reason = SuspensionReason.ADMIN_ACTION

    try:
        result = svc.suspend_service(
            subscription_id,
            reason=reason,
            notes=notes,
            apply_grace_period=apply_grace if apply_grace is not None else True,
            grace_period_days=grace_days,
        )
        if result.success:
            db.commit()
        else:
            db.rollback()
            if is_htmx_request(request):
                htmx_toast(response, result.error or "Failed to suspend service", "error")
                return HTMLResponse("")
            raise HTTPException(status_code=400, detail=result.error)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")

    if is_htmx_request(request):
        state_label = "grace period" if apply_grace else "suspended"
        htmx_toast(response, f"Service suspended ({state_label})", "warning")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber_id}"
        return HTMLResponse("")

    set_flash(response, "Service suspended", "warning")
    return RedirectResponse(url=f"/subscribers/{subscriber_id}", status_code=303)


@router.post("/{subscriber_id:int}/services/{subscription_id:int}/reactivate", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def service_reactivate(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Reactivate a suspended service."""
    svc = SubscriberWebService(db, principal=user)
    form = await request.form()

    notes = _form_str(form, "notes")
    waive_outstanding = _form_bool(form, "waive_outstanding") or False
    waive_fee = _form_bool(form, "waive_reconnection_fee") or False
    force = _form_bool(form, "force") or False

    try:
        result = svc.reactivate_service(
            subscription_id,
            notes=notes,
            waive_outstanding=waive_outstanding,
            waive_reconnection_fee=waive_fee,
            force=force,
        )
        if result.success:
            db.commit()
        else:
            db.rollback()
            if is_htmx_request(request):
                htmx_toast(response, result.error or "Failed to reactivate service", "error")
                return HTMLResponse("")
            raise HTTPException(status_code=400, detail=result.error)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")

    if is_htmx_request(request):
        htmx_toast(response, "Service reactivated", "success")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber_id}"
        return HTMLResponse("")

    set_flash(response, "Service reactivated", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber_id}", status_code=303)


@router.post("/{subscriber_id:int}/services/{subscription_id:int}/terminate", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def service_terminate(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Terminate a service permanently."""
    from app.services.subscribers import TerminationReason

    svc = SubscriberWebService(db, principal=user)
    form = await request.form()

    reason_str = _form_str(form, "reason") or "admin_action"
    notes = _form_str(form, "notes")

    try:
        reason = TerminationReason(reason_str)
    except ValueError:
        reason = TerminationReason.ADMIN_ACTION

    try:
        result = svc.terminate_service(
            subscription_id,
            reason=reason,
            notes=notes,
        )
        if result.success:
            db.commit()
        else:
            db.rollback()
            if is_htmx_request(request):
                htmx_toast(response, result.error or "Failed to terminate service", "error")
                return HTMLResponse("")
            raise HTTPException(status_code=400, detail=result.error)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")

    if is_htmx_request(request):
        htmx_toast(response, "Service terminated", "warning")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber_id}"
        return HTMLResponse("")

    set_flash(response, "Service terminated", "warning")
    return RedirectResponse(url=f"/subscribers/{subscriber_id}", status_code=303)


@router.post("/{subscriber_id:int}/services/{subscription_id:int}/extend-grace", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def service_extend_grace(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Extend grace period for a service."""
    svc = SubscriberWebService(db, principal=user)
    form = await request.form()

    days = _form_int(form, "days") or 7
    reason = _form_str(form, "reason") or ""

    try:
        result = svc.extend_grace_period(
            subscription_id,
            days=days,
            reason=reason,
        )
        if result.success:
            db.commit()
        else:
            db.rollback()
            if is_htmx_request(request):
                htmx_toast(response, result.error or "Failed to extend grace period", "error")
                return HTMLResponse("")
            raise HTTPException(status_code=400, detail=result.error)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Grace period extended by {days} days", "success")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber_id}"
        return HTMLResponse("")

    set_flash(response, f"Grace period extended by {days} days", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber_id}", status_code=303)


@router.post("/{subscriber_id:int}/services/{subscription_id:int}/activate", response_class=HTMLResponse, dependencies=[RequireSubscribersWrite])
async def service_activate(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscriber_id: int = Path(..., description="Subscriber ID"),
    subscription_id: int = Path(..., description="Subscription ID"),
):
    """Activate a pending service."""
    svc = SubscriberWebService(db, principal=user)
    form = await request.form()
    notes = _form_str(form, "notes")

    try:
        result = svc.activate_service(subscription_id, notes=notes)
        if result.success:
            db.commit()
        else:
            db.rollback()
            if is_htmx_request(request):
                htmx_toast(response, result.error or "Failed to activate service", "error")
                return HTMLResponse("")
            raise HTTPException(status_code=400, detail=result.error)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")

    if is_htmx_request(request):
        htmx_toast(response, "Service activated", "success")
        response.headers["HX-Redirect"] = f"/subscribers/{subscriber_id}"
        return HTMLResponse("")

    set_flash(response, "Service activated", "success")
    return RedirectResponse(url=f"/subscribers/{subscriber_id}", status_code=303)


# =============================================================================
# LIFECYCLE STATS & REPORTS
# =============================================================================

@router.get("/lifecycle/stats", response_class=HTMLResponse, dependencies=[RequireSubscribersRead])
async def lifecycle_stats(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Get lifecycle statistics."""
    svc = SubscriberWebService(db, principal=user)
    stats = svc.get_lifecycle_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["stats"] = stats

    if is_htmx_request(request):
        template = templates.get_template("modules/subscribers/templates/partials/lifecycle_stats.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Service Lifecycle Statistics"
    template = templates.get_template("modules/subscribers/templates/pages/lifecycle_stats.html")
    return HTMLResponse(template.render(context))

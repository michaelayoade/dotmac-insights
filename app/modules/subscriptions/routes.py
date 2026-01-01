"""
Subscriptions Routes - Service Subscription Management with SSR + HTMX.

Permission Requirements:
- subscriptions:read - View subscriptions and tariffs
- subscriptions:write - Create, update, delete, status changes
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.tariff import Tariff, TariffType
from app.models.customer import Customer
from app.models.router import Router
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.integrations.mikrotik.access_methods import ACCESS_METHODS, get_access_method_options

# Permission dependencies
RequireSubscriptionsRead = Depends(require_scope("subscriptions:read"))
RequireSubscriptionsWrite = Depends(require_scope("subscriptions:write"))

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def get_status_options():
    """Get subscription status options for filter dropdown."""
    return [
        {"value": s.value, "label": s.value.title()}
        for s in SubscriptionStatus
    ]


def get_service_type_options():
    """Get service type options for filter dropdown."""
    return [
        {"value": t.value, "label": t.value.title()}
        for t in SubscriptionType
    ]


def get_billing_cycle_options():
    """Get billing cycle options."""
    return [
        {"value": "monthly", "label": "Monthly"},
        {"value": "quarterly", "label": "Quarterly"},
        {"value": "yearly", "label": "Yearly"},
    ]


def format_speed(speed: Optional[int]) -> str:
    """Format speed in Mbps or Gbps."""
    if not speed:
        return "-"
    if speed >= 1000:
        return f"{speed / 1000:.0f} Gbps"
    return f"{speed} Mbps"


def compute_stats(db, status_filter=None, service_type_filter=None) -> dict:
    """Compute subscription stats for dashboard cards."""
    base_query = db.query(Subscription)

    active = base_query.filter(Subscription.status == SubscriptionStatus.ACTIVE).count()
    suspended = base_query.filter(Subscription.status == SubscriptionStatus.SUSPENDED).count()
    pending = base_query.filter(Subscription.status == SubscriptionStatus.PENDING).count()
    total = base_query.count()

    # MRR calculation (sum of active subscriptions)
    mrr_result = db.query(func.sum(Subscription.price)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "monthly"
    ).scalar() or Decimal("0")

    # Quarterly and yearly contributions to MRR
    quarterly_mrr = db.query(func.sum(Subscription.price / 3)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "quarterly"
    ).scalar() or Decimal("0")

    yearly_mrr = db.query(func.sum(Subscription.price / 12)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "yearly"
    ).scalar() or Decimal("0")

    total_mrr = float(mrr_result) + float(quarterly_mrr) + float(yearly_mrr)

    # New this month
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = base_query.filter(Subscription.created_at >= start_of_month).count()

    return {
        "active": active,
        "suspended": suspended,
        "pending": pending,
        "total": total,
        "mrr": total_mrr,
        "new_this_month": new_this_month,
    }


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
    customer_id: Optional[int] = Query(None, description="Filter by customer"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Subscriptions list page with stats and filters."""
    query = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.tariff),
        joinedload(Subscription.router),
    )

    # Search
    if q:
        search_filter = or_(
            Subscription.plan_name.ilike(f"%{q}%"),
            Subscription.ipv4_address.ilike(f"%{q}%"),
            Subscription.mac_address.ilike(f"%{q}%"),
            Subscription.customer.has(Customer.name.ilike(f"%{q}%")),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        try:
            status_enum = SubscriptionStatus(status)
            query = query.filter(Subscription.status == status_enum)
        except ValueError:
            pass

    if service_type:
        try:
            type_enum = SubscriptionType(service_type)
            query = query.filter(Subscription.service_type == type_enum)
        except ValueError:
            pass

    if customer_id:
        query = query.filter(Subscription.customer_id == customer_id)

    # Count total
    total = query.count()

    # Sort
    sort_mapping = {
        "created_at": Subscription.created_at,
        "plan_name": Subscription.plan_name,
        "price": Subscription.price,
        "status": Subscription.status,
        "start_date": Subscription.start_date,
    }
    sort_column = sort_mapping.get(sort, Subscription.created_at)
    order_column = sort_column.desc() if dir == "desc" else sort_column.asc()
    query = query.order_by(order_column)

    # Paginate
    offset = (page - 1) * per_page
    subscriptions = query.offset(offset).limit(per_page).all()

    # Stats
    stats = compute_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["subscriptions"] = subscriptions
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_service_type"] = service_type
    context["current_customer_id"] = customer_id
    context["status_options"] = get_status_options()
    context["service_type_options"] = get_service_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["format_speed"] = format_speed

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
    customer_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Subscriptions table partial for HTMX updates."""
    return await subscriptions_list(
        request, response, user, csrf_token, db,
        q, status, service_type, customer_id, page, per_page, sort, dir
    )


# =============================================================================
# SUBSCRIPTION DETAIL
# =============================================================================

@router.get("/{subscription_id}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscription_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Subscription detail page with usage stats and actions."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.tariff),
        joinedload(Subscription.router),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

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

    # Available status transitions
    transitions = get_available_transitions(subscription.status)
    context["status_transitions"] = transitions

    template = templates.get_template("modules/subscriptions/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


def get_available_transitions(current_status: SubscriptionStatus) -> list:
    """Get available status transitions for a subscription."""
    transitions = {
        SubscriptionStatus.PENDING: [
            {"status": "active", "label": "Activate", "color": "emerald"},
            {"status": "cancelled", "label": "Cancel", "color": "red"},
        ],
        SubscriptionStatus.ACTIVE: [
            {"status": "suspended", "label": "Suspend", "color": "amber"},
            {"status": "cancelled", "label": "Cancel", "color": "red"},
        ],
        SubscriptionStatus.SUSPENDED: [
            {"status": "active", "label": "Reactivate", "color": "emerald"},
            {"status": "cancelled", "label": "Cancel", "color": "red"},
        ],
        SubscriptionStatus.CANCELLED: [],
    }
    return transitions.get(current_status, [])


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
    customer_id: Optional[int] = Query(None),
):
    """New subscription form page."""
    # Get tariffs for selection
    tariffs = db.query(Tariff).filter(
        Tariff.enabled == True,
        Tariff.available_for_services == True,
    ).order_by(Tariff.title).all()

    # Get routers for network assignment
    routers = db.query(Router).filter(
        Router.status == "active",
    ).order_by(Router.title).all()

    # Get customers for selection
    customers = db.query(Customer).filter(
        Customer.status == "active",
    ).order_by(Customer.name).limit(100).all()

    # Pre-selected customer if provided
    selected_customer = None
    if customer_id:
        selected_customer = db.query(Customer).filter(Customer.id == customer_id).first()

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

    # Validation
    errors = {}
    customer_id = _form_str(form, "customer_id")
    plan_name = _form_str(form, "plan_name")
    price_str = _form_str(form, "price")

    if not customer_id:
        errors["customer_id"] = "Customer is required"
    elif not customer_id.isdigit():
        errors["customer_id"] = "Invalid customer"

    if not plan_name:
        errors["plan_name"] = "Plan name is required"

    if not price_str:
        errors["price"] = "Price is required"
    else:
        try:
            price = Decimal(price_str)
            if price < 0:
                errors["price"] = "Price must be positive"
        except:
            errors["price"] = "Invalid price format"

    if errors:
        # Get form context again
        tariffs = db.query(Tariff).filter(
            Tariff.enabled == True,
            Tariff.available_for_services == True,
        ).order_by(Tariff.title).all()

        routers = db.query(Router).filter(
            Router.status == "active",
        ).order_by(Router.title).all()

        customers = db.query(Customer).filter(
            Customer.status == "active",
        ).order_by(Customer.name).limit(100).all()

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

    # Parse service type
    service_type_str = form.get("service_type", "internet")
    try:
        service_type = SubscriptionType(service_type_str)
    except ValueError:
        service_type = SubscriptionType.INTERNET

    # Parse dates
    start_date = None
    start_date_str = _form_str(form, "start_date")
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    # Parse tariff_id
    tariff_id = None
    tariff_id_str = _form_str(form, "tariff_id")
    if tariff_id_str and tariff_id_str.isdigit():
        tariff_id = int(tariff_id_str)

    # Parse router_id
    router_id = None
    router_id_str = _form_str(form, "router_id")
    if router_id_str and router_id_str.isdigit():
        router_id = int(router_id_str)

    # Parse speeds
    download_speed = None
    download_str = _form_str(form, "download_speed")
    if download_str and download_str.isdigit():
        download_speed = int(download_str)

    upload_speed = None
    upload_str = _form_str(form, "upload_speed")
    if upload_str and upload_str.isdigit():
        upload_speed = int(upload_str)

    # Parse access method and PPP credentials
    access_method = _form_str(form, "access_method") or None
    if access_method and access_method not in ACCESS_METHODS:
        access_method = None

    ppp_username = _form_str(form, "ppp_username") or None
    ppp_password = _form_str(form, "ppp_password") or None

    # Create subscription
    subscription = Subscription(
        customer_id=int(customer_id),
        tariff_id=tariff_id,
        service_type=service_type,
        plan_name=plan_name,
        plan_code=_form_str(form, "plan_code") or None,
        description=_form_str(form, "description") or None,
        price=Decimal(price_str),
        currency=_form_str(form, "currency", "NGN") or "NGN",
        billing_cycle=_form_str(form, "billing_cycle", "monthly") or "monthly",
        download_speed=download_speed,
        upload_speed=upload_speed,
        router_id=router_id,
        ipv4_address=_form_str(form, "ipv4_address") or None,
        ipv6_address=_form_str(form, "ipv6_address") or None,
        mac_address=_form_str(form, "mac_address") or None,
        access_method=access_method,
        ppp_username=ppp_username,
        ppp_password=ppp_password,
        status=SubscriptionStatus.PENDING,
        start_date=start_date,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    set_flash(response, f"Subscription '{subscription.plan_name}' created successfully.", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


@router.get("/{subscription_id}/edit", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Subscription edit form page."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.tariff),
        joinedload(Subscription.router),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get tariffs for selection
    tariffs = db.query(Tariff).filter(
        Tariff.enabled == True,
        Tariff.available_for_services == True,
    ).order_by(Tariff.title).all()

    # Get routers for network assignment
    routers = db.query(Router).filter(
        Router.status == "active",
    ).order_by(Router.title).all()

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
    context["selected_customer"] = subscription.customer
    context["service_type_options"] = get_service_type_options()
    context["billing_cycle_options"] = get_billing_cycle_options()
    context["access_method_options"] = get_access_method_options()
    context["status_options"] = get_status_options()
    context["errors"] = {}

    template = templates.get_template("modules/subscriptions/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{subscription_id}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Update a subscription."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()

    # Validation
    errors = {}
    plan_name = _form_str(form, "plan_name")
    price_str = _form_str(form, "price")

    if not plan_name:
        errors["plan_name"] = "Plan name is required"

    if not price_str:
        errors["price"] = "Price is required"
    else:
        try:
            price = Decimal(price_str)
            if price < 0:
                errors["price"] = "Price must be positive"
        except:
            errors["price"] = "Invalid price format"

    if errors:
        tariffs = db.query(Tariff).filter(
            Tariff.enabled == True,
            Tariff.available_for_services == True,
        ).order_by(Tariff.title).all()

        routers = db.query(Router).filter(
            Router.status == "active",
        ).order_by(Router.title).all()

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
        context["selected_customer"] = subscription.customer
        context["service_type_options"] = get_service_type_options()
        context["billing_cycle_options"] = get_billing_cycle_options()
        context["access_method_options"] = get_access_method_options()
        context["status_options"] = get_status_options()
        context["errors"] = errors

        template = templates.get_template("modules/subscriptions/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse service type
    service_type_str = form.get("service_type", subscription.service_type.value)
    try:
        service_type = SubscriptionType(service_type_str)
    except ValueError:
        service_type = subscription.service_type

    # Parse dates
    start_date = subscription.start_date
    start_date_str = _form_str(form, "start_date")
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    # Parse tariff_id
    tariff_id = subscription.tariff_id
    tariff_id_str = _form_str(form, "tariff_id")
    if tariff_id_str and tariff_id_str.isdigit():
        tariff_id = int(tariff_id_str)

    # Parse router_id
    router_id = subscription.router_id
    router_id_str = _form_str(form, "router_id")
    if router_id_str and router_id_str.isdigit():
        router_id = int(router_id_str)
    elif router_id_str == "":
        router_id = None

    # Parse speeds
    download_speed = subscription.download_speed
    download_str = _form_str(form, "download_speed")
    if download_str and download_str.isdigit():
        download_speed = int(download_str)

    upload_speed = subscription.upload_speed
    upload_str = _form_str(form, "upload_speed")
    if upload_str and upload_str.isdigit():
        upload_speed = int(upload_str)

    # Parse access method and PPP credentials
    access_method = _form_str(form, "access_method")
    if access_method and access_method in ACCESS_METHODS:
        subscription.access_method = access_method
    elif access_method == "":
        subscription.access_method = None

    ppp_username = _form_str(form, "ppp_username")
    ppp_password = _form_str(form, "ppp_password")
    if ppp_username:
        subscription.ppp_username = ppp_username
    if ppp_password:  # Only update if a new password is provided
        subscription.ppp_password = ppp_password

    # Update subscription
    subscription.tariff_id = tariff_id
    subscription.service_type = service_type
    subscription.plan_name = plan_name
    subscription.plan_code = _form_str(form, "plan_code") or None
    subscription.description = _form_str(form, "description") or None
    subscription.price = Decimal(price_str)
    subscription.currency = _form_str(form, "currency", "NGN") or "NGN"
    subscription.billing_cycle = _form_str(form, "billing_cycle", "monthly") or "monthly"
    subscription.download_speed = download_speed
    subscription.upload_speed = upload_speed
    subscription.router_id = router_id
    subscription.ipv4_address = _form_str(form, "ipv4_address") or None
    subscription.ipv6_address = _form_str(form, "ipv6_address") or None
    subscription.mac_address = _form_str(form, "mac_address") or None
    subscription.start_date = start_date
    db.commit()

    set_flash(response, f"Subscription '{subscription.plan_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# STATUS CHANGE
# =============================================================================

@router.get("/{subscription_id}/status-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_status_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
    target_status: str = Query(...),
):
    """Status change confirmation modal."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        new_status = SubscriptionStatus(target_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["target_status"] = target_status
    context["target_status_label"] = target_status.title()

    template = templates.get_template("modules/subscriptions/templates/partials/status_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id}/status", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_status_change(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Change subscription status."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()
    new_status_str = _form_str(form, "status")

    if not new_status_str:
        raise HTTPException(status_code=400, detail="Status is required")

    try:
        new_status = SubscriptionStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Validate transition
    allowed = get_available_transitions(subscription.status)
    allowed_statuses = [t["status"] for t in allowed]
    if new_status.value not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    old_status = subscription.status
    subscription.status = new_status

    # Set cancelled date if cancelling
    if new_status == SubscriptionStatus.CANCELLED:
        subscription.cancelled_date = datetime.utcnow()

    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Status changed from {old_status.value.title()} to {new_status.value.title()}", "success")
        # Return updated row or redirect
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Status changed to {new_status.value.title()}", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# NETWORK ASSIGNMENT
# =============================================================================

@router.get("/{subscription_id}/network-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_network_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Network assignment modal."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.router),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get routers
    routers = db.query(Router).filter(
        Router.status == "active",
    ).order_by(Router.title).all()

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["routers"] = routers

    template = templates.get_template("modules/subscriptions/templates/partials/network_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id}/network", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_network_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Update subscription network assignment."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()

    # Parse router_id
    router_id = subscription.router_id
    router_id_str = _form_str(form, "router_id")
    if router_id_str and router_id_str.isdigit():
        router_id = int(router_id_str)
    elif router_id_str == "":
        router_id = None

    # Update network fields
    subscription.router_id = router_id
    subscription.ipv4_address = _form_str(form, "ipv4_address") or None
    subscription.ipv6_address = _form_str(form, "ipv6_address") or None
    subscription.mac_address = _form_str(form, "mac_address") or None
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Network assignment updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Network assignment updated", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)


# =============================================================================
# DELETE
# =============================================================================

@router.delete("/{subscription_id}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Delete a subscription (cancel and mark as deleted)."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    name = subscription.plan_name
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_date = datetime.utcnow()
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Subscription '{name}' cancelled.", "success")
        response.headers["HX-Redirect"] = "/subscriptions"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Subscription '{name}' cancelled.", "success")
    return RedirectResponse(url="/subscriptions", status_code=303)


# =============================================================================
# ROW PARTIAL
# =============================================================================

@router.get("/{subscription_id}/row", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscription_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Single subscription row partial for HTMX updates."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.tariff),
        joinedload(Subscription.router),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["format_speed"] = format_speed

    template = templates.get_template("modules/subscriptions/templates/partials/subscription_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# MIKROTIK PROVISIONING
# =============================================================================

@router.post("/{subscription_id}/provision", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_provision(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """
    Manually trigger provisioning for a subscription.

    This queues a Celery task to provision the subscription on its assigned router.
    """
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
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

    # Queue provisioning task
    try:
        from app.tasks.provisioning_tasks import provision_subscription

        result = provision_subscription.delay(
            subscription_id=subscription.id,
            triggered_by=user.name or "manual",
            force=True,
        )

        if is_htmx_request(request):
            htmx_toast(response, f"Provisioning task queued (task_id: {result.id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Provisioning task queued (task_id: {result.id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue provisioning: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue provisioning: {str(e)}")


@router.post("/{subscription_id}/disconnect", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_disconnect(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """
    Force disconnect an active session for a subscription.

    This disconnects any active PPPoE/Hotspot session, forcing the customer to reconnect.
    """
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot disconnect.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    # Queue disconnect task
    try:
        from app.tasks.provisioning_tasks import disconnect_subscription_session

        result = disconnect_subscription_session.delay(
            subscription_id=subscription.id,
            triggered_by=user.name or "manual",
        )

        if is_htmx_request(request):
            htmx_toast(response, f"Disconnect task queued (task_id: {result.id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Disconnect task queued (task_id: {result.id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue disconnect: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue disconnect: {str(e)}")


@router.post("/{subscription_id}/deprovision", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_deprovision(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """
    Remove subscription provisioning from router.

    This removes PPPoE secrets, Hotspot users, DHCP bindings, etc.
    """
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.router_id:
        if is_htmx_request(request):
            htmx_toast(response, "No router assigned. Cannot deprovision.", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=400, detail="No router assigned")

    # Queue deprovisioning task
    try:
        from app.tasks.provisioning_tasks import deprovision_subscription

        result = deprovision_subscription.delay(
            subscription_id=subscription.id,
            triggered_by=user.name or "manual",
        )

        if is_htmx_request(request):
            htmx_toast(response, f"Deprovisioning task queued (task_id: {result.id[:8]}...)", "info")
            response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
            return HTMLResponse("", headers=dict(response.headers))

        set_flash(response, f"Deprovisioning task queued (task_id: {result.id})", "info")
        return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

    except Exception as e:
        if is_htmx_request(request):
            htmx_toast(response, f"Failed to queue deprovisioning: {str(e)}", "error")
            return HTMLResponse("", headers=dict(response.headers))
        raise HTTPException(status_code=500, detail=f"Failed to queue deprovisioning: {str(e)}")


@router.get("/{subscription_id}/provisioning-modal", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_provisioning_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Provisioning configuration modal."""
    subscription = db.query(Subscription).options(
        joinedload(Subscription.customer),
        joinedload(Subscription.router),
    ).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get routers for selection
    routers = db.query(Router).filter(
        Router.status == "active",
    ).order_by(Router.title).all()

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["routers"] = routers
    context["access_method_options"] = get_access_method_options()

    template = templates.get_template("modules/subscriptions/templates/partials/provisioning_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id}/provisioning", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def subscription_provisioning_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Update subscription provisioning configuration."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    form = await request.form()

    # Update provisioning fields
    access_method = _form_str(form, "access_method")
    if access_method and access_method in ACCESS_METHODS:
        subscription.access_method = access_method
    elif access_method == "":
        subscription.access_method = None

    # Update PPP credentials if provided
    ppp_username = _form_str(form, "ppp_username")
    ppp_password = _form_str(form, "ppp_password")

    if ppp_username:
        subscription.ppp_username = ppp_username
    if ppp_password:
        subscription.ppp_password = ppp_password

    # Update router if provided
    router_id_str = _form_str(form, "router_id")
    if router_id_str and router_id_str.isdigit():
        subscription.router_id = int(router_id_str)
    elif router_id_str == "":
        subscription.router_id = None

    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Provisioning configuration updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Provisioning configuration updated", "success")
    return RedirectResponse(url=f"/subscriptions/{subscription.id}", status_code=303)

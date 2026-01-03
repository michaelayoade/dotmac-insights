"""
Payment Subscription Routes - Recurring Payment Management with SSR + HTMX.

Permission Requirements:
- payments:read - View payment subscriptions
- payments:write - Manage payment subscriptions (pause, resume, cancel)
"""
from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.payment_subscription import (
    PaymentSubscription,
    PaymentSubscriptionStatus,
    PaymentSubscriptionInterval,
)
from app.models.gateway_transaction import GatewayProvider, GatewayTransaction
from app.models.party import CustomerAccount
from app.models.subscription import Subscription
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.subscriptions import (
    PaymentSubscriptionService,
    PaymentSubscriptionFilters,
)
from app.services.types import PaginationParams

# Permission dependencies
RequirePaymentsRead = Depends(require_scope("payments:read"))
RequirePaymentsWrite = Depends(require_scope("payments:write"))

router = APIRouter(prefix="/subscriptions/payments", tags=["payment-subscriptions"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def get_status_options():
    """Get payment subscription status options."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PaymentSubscriptionStatus
    ]


def get_provider_options():
    """Get payment provider options."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in GatewayProvider
    ]


def get_interval_options():
    """Get billing interval options."""
    return [
        {"value": i.value, "label": i.value.title()}
        for i in PaymentSubscriptionInterval
    ]


def get_available_actions(status: PaymentSubscriptionStatus) -> list:
    """Get available actions for a payment subscription based on status."""
    actions = {
        PaymentSubscriptionStatus.ACTIVE: [
            {"action": "pause", "label": "Pause", "color": "amber", "icon": "pause"},
            {"action": "cancel", "label": "Cancel", "color": "red", "icon": "x"},
        ],
        PaymentSubscriptionStatus.PAUSED: [
            {"action": "resume", "label": "Resume", "color": "emerald", "icon": "play"},
            {"action": "cancel", "label": "Cancel", "color": "red", "icon": "x"},
        ],
        PaymentSubscriptionStatus.PAST_DUE: [
            {"action": "retry", "label": "Retry Charge", "color": "blue", "icon": "refresh"},
            {"action": "pause", "label": "Pause", "color": "amber", "icon": "pause"},
            {"action": "cancel", "label": "Cancel", "color": "red", "icon": "x"},
        ],
        PaymentSubscriptionStatus.CANCELLED: [],
        PaymentSubscriptionStatus.COMPLETED: [],
        PaymentSubscriptionStatus.EXPIRED: [],
    }
    return actions.get(status, [])


# =============================================================================
# PAYMENT SUBSCRIPTION LIST
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def payment_subscriptions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    party_id: Optional[int] = Query(None, description="Filter by party"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Payment subscriptions list page."""
    svc = PaymentSubscriptionService(db, principal=user)

    # Build filters
    filters = PaymentSubscriptionFilters(
        search=q,
        status=status,
        provider=provider,
        party_id=party_id,
    )
    pagination = PaginationParams(page=page, per_page=per_page)

    # Get payment subscriptions using service
    result = svc.list_payment_subscriptions(
        filters=filters,
        pagination=pagination,
        include_relations=True,
    )

    # Get stats using service
    stats = svc.get_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["subscriptions"] = result.items
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_provider"] = provider
    context["current_party_id"] = party_id
    context["status_options"] = get_status_options()
    context["provider_options"] = get_provider_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/subscriptions/templates/partials/payment_subscriptions_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Payment Subscriptions"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": "Payment Subscriptions"},
    ])

    template = templates.get_template("modules/subscriptions/templates/pages/payment_subscriptions_list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def payment_subscriptions_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    party_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Payment subscriptions table partial for HTMX updates."""
    return await payment_subscriptions_list(
        request, response, user, csrf_token, db,
        q, status, provider, party_id, page, per_page, sort, dir
    )


# =============================================================================
# PAYMENT SUBSCRIPTION DETAIL
# =============================================================================

@router.get("/{subscription_id}", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def payment_subscription_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Payment subscription detail page with transaction history."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.get_payment_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    # Get linked service subscription if any
    service_subscription = None
    if subscription.service_subscription_id:
        service_subscription = db.query(Subscription).filter(
            Subscription.id == subscription.service_subscription_id
        ).first()

    # Get recent transactions for this payment subscription
    customer_account = db.query(CustomerAccount).filter(
        CustomerAccount.party_id == subscription.party_id
    ).first()
    transactions_query = db.query(GatewayTransaction).filter(
        GatewayTransaction.provider == subscription.provider,
    )
    if customer_account:
        transactions_query = transactions_query.filter(
            GatewayTransaction.customer_account_id == customer_account.id
        )
    transactions = (
        transactions_query.order_by(GatewayTransaction.created_at.desc())
        .limit(20)
        .all()
    )

    # Available actions based on status
    actions = get_available_actions(subscription.status)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = subscription.plan_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": "Payment Subscriptions", "href": "/subscriptions/payments"},
        {"label": subscription.plan_name},
    ])
    context["subscription"] = subscription
    context["service_subscription"] = service_subscription
    context["transactions"] = transactions
    context["actions"] = actions

    template = templates.get_template("modules/subscriptions/templates/pages/payment_subscription_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# PAYMENT SUBSCRIPTION ACTIONS
# =============================================================================

@router.get("/{subscription_id}/action-modal", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_action_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
    action: str = Query(...),
):
    """Action confirmation modal."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.get_payment_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    valid_actions = ["pause", "resume", "cancel", "retry"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail="Invalid action")

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["action"] = action

    template = templates.get_template("modules/subscriptions/templates/partials/payment_action_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id}/pause", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_pause(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Pause a payment subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.pause(subscription_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")
    except (ValidationError, ConflictError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Payment subscription '{subscription.plan_name}' paused", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Payment subscription '{subscription.plan_name}' paused", "success")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)


@router.patch("/{subscription_id}/resume", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_resume(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Resume a paused payment subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.resume(subscription_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")
    except (ValidationError, ConflictError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Payment subscription '{subscription.plan_name}' resumed", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Payment subscription '{subscription.plan_name}' resumed", "success")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)


@router.patch("/{subscription_id}/cancel", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_cancel(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Cancel a payment subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    form = await request.form()
    reason = _form_str(form, "reason") or None

    try:
        subscription = svc.cancel(subscription_id, reason=reason)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")
    except (ValidationError, ConflictError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, f"Payment subscription '{subscription.plan_name}' cancelled", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Payment subscription '{subscription.plan_name}' cancelled", "success")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)


@router.post("/{subscription_id}/retry", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_retry(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Retry a failed charge for a payment subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.get_payment_subscription(subscription_id)
        svc.record_charge_attempt(subscription_id, success=False, reference=None, amount=subscription.amount)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")
    except (ValidationError, ConflictError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, "Charge retry initiated. Check transaction history for results.", "info")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Charge retry initiated. Check transaction history for results.", "info")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)


# =============================================================================
# LINK TO SERVICE SUBSCRIPTION
# =============================================================================

@router.get("/{subscription_id}/link-modal", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_link_modal(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: int,
):
    """Modal to link payment subscription to service subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.get_payment_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    # Get service subscriptions for the same customer
    service_subscriptions = db.query(Subscription).filter(
        Subscription.party_id == subscription.party_id,
    ).order_by(Subscription.plan_name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["subscription"] = subscription
    context["service_subscriptions"] = service_subscriptions

    template = templates.get_template("modules/subscriptions/templates/partials/payment_link_modal.html")
    return HTMLResponse(template.render(context))


@router.patch("/{subscription_id}/link", response_class=HTMLResponse, dependencies=[RequirePaymentsWrite])
async def payment_subscription_link(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    subscription_id: int,
):
    """Link payment subscription to a service subscription."""
    svc = PaymentSubscriptionService(db, principal=user)

    try:
        subscription = svc.get_payment_subscription(subscription_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    form = await request.form()
    service_subscription_id = _form_str(form, "service_subscription_id")

    try:
        if service_subscription_id and service_subscription_id.isdigit():
            subscription = svc.link_to_service_subscription(
                subscription_id,
                int(service_subscription_id),
            )
        else:
            # Unlink
            subscription = svc.unlink_service_subscription(subscription_id)
        db.commit()
    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, "Service subscription link updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Service subscription link updated", "success")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)

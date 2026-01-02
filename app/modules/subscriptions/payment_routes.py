"""
Payment Subscription Routes - Recurring Payment Management with SSR + HTMX.

Permission Requirements:
- payments:read - View payment subscriptions
- payments:write - Manage payment subscriptions (pause, resume, cancel)
"""
from __future__ import annotations

from typing import Optional, Any, cast
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import ColumnElement

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


def compute_stats(db) -> dict:
    """Compute payment subscription stats."""
    base = db.query(PaymentSubscription)

    active = base.filter(PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE).count()
    paused = base.filter(PaymentSubscription.status == PaymentSubscriptionStatus.PAUSED).count()
    past_due = base.filter(PaymentSubscription.status == PaymentSubscriptionStatus.PAST_DUE).count()
    total = base.count()

    # Monthly revenue (from active monthly subscriptions)
    monthly_revenue = db.query(func.sum(PaymentSubscription.amount)).filter(
        PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE,
        PaymentSubscription.interval == PaymentSubscriptionInterval.MONTHLY,
    ).scalar() or Decimal("0")

    # Total collected all-time
    total_collected = db.query(func.sum(PaymentSubscription.total_collected)).scalar() or Decimal("0")

    return {
        "active": active,
        "paused": paused,
        "past_due": past_due,
        "total": total,
        "monthly_revenue": float(monthly_revenue),
        "total_collected": float(total_collected),
    }


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
    query = db.query(PaymentSubscription).options(
        joinedload(PaymentSubscription.party),
    )

    # Search
    if q:
        search_filter = or_(
            PaymentSubscription.plan_name.ilike(f"%{q}%"),
            PaymentSubscription.customer_email.ilike(f"%{q}%"),
            PaymentSubscription.provider_subscription_code.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        try:
            status_enum = PaymentSubscriptionStatus(status)
            query = query.filter(PaymentSubscription.status == status_enum)
        except ValueError:
            pass

    if provider:
        try:
            provider_enum = GatewayProvider(provider)
            query = query.filter(PaymentSubscription.provider == provider_enum)
        except ValueError:
            pass

    if party_id:
        query = query.filter(PaymentSubscription.party_id == party_id)

    # Count total
    total = query.count()

    # Sort
    sort_mapping = {
        "created_at": PaymentSubscription.created_at,
        "plan_name": PaymentSubscription.plan_name,
        "amount": PaymentSubscription.amount,
        "status": PaymentSubscription.status,
        "next_billing_date": PaymentSubscription.next_billing_date,
    }
    order_column: ColumnElement[Any] = cast(ColumnElement[Any], sort_mapping.get(sort, PaymentSubscription.created_at))
    if dir == "desc":
        order_column = order_column.desc()
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
    context["current_provider"] = provider
    context["current_party_id"] = party_id
    context["status_options"] = get_status_options()
    context["provider_options"] = get_provider_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    subscription = db.query(PaymentSubscription).options(
        joinedload(PaymentSubscription.party),
    ).filter(PaymentSubscription.id == subscription_id).first()

    if not subscription:
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
    subscription = db.query(PaymentSubscription).options(
        joinedload(PaymentSubscription.party),
    ).filter(PaymentSubscription.id == subscription_id).first()

    if not subscription:
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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    if subscription.status not in [PaymentSubscriptionStatus.ACTIVE, PaymentSubscriptionStatus.PAST_DUE]:
        raise HTTPException(status_code=400, detail="Cannot pause this subscription")

    subscription.status = PaymentSubscriptionStatus.PAUSED
    subscription.paused_at = datetime.utcnow()
    db.commit()

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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    if subscription.status != PaymentSubscriptionStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Can only resume paused subscriptions")

    subscription.status = PaymentSubscriptionStatus.ACTIVE
    subscription.paused_at = None
    subscription.retry_count = 0  # Reset retry count
    db.commit()

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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    if subscription.status in [PaymentSubscriptionStatus.CANCELLED, PaymentSubscriptionStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="Subscription already cancelled or completed")

    form = await request.form()
    reason = _form_str(form, "reason")

    subscription.status = PaymentSubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()
    subscription.cancellation_reason = reason if reason else None
    subscription.ended_at = datetime.utcnow()
    db.commit()

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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    if subscription.status not in [PaymentSubscriptionStatus.PAST_DUE, PaymentSubscriptionStatus.ACTIVE]:
        raise HTTPException(status_code=400, detail="Cannot retry charge for this subscription")

    # Note: In production, this would trigger an actual charge via the payment gateway
    # For now, we'll just update the retry count and log the attempt
    subscription.retry_count += 1
    subscription.last_charge_date = datetime.utcnow()
    db.commit()

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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
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
    subscription = db.query(PaymentSubscription).filter(
        PaymentSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Payment subscription not found")

    form = await request.form()
    service_subscription_id = _form_str(form, "service_subscription_id")

    if service_subscription_id and service_subscription_id.isdigit():
        # Verify the service subscription belongs to the same customer
        service_sub = db.query(Subscription).filter(
            Subscription.id == int(service_subscription_id),
            Subscription.party_id == subscription.party_id,
        ).first()

        if not service_sub:
            raise HTTPException(status_code=400, detail="Invalid service subscription")

        subscription.service_subscription_id = int(service_subscription_id)
    else:
        # Unlink
        subscription.service_subscription_id = None

    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Service subscription link updated", "success")
        response.headers["HX-Redirect"] = f"/subscriptions/payments/{subscription.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Service subscription link updated", "success")
    return RedirectResponse(url=f"/subscriptions/payments/{subscription.id}", status_code=303)

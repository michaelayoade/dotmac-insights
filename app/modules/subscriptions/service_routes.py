"""
Subscription Service Routes - Comprehensive lifecycle + ops UI.

Pages covered:
- Dashboard / analytics
- Usage monitoring
- Session monitoring
- Provisioning logs
- Service transactions
- Billing overview
- Finance summary
- Settings (service type, billing config, RADIUS)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Request, Response, Depends, Query, HTTPException, UploadFile
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
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.services.types import PaginationParams
from app.services.subscriptions import (
    SubscriptionReportsService,
    UsageService,
    SessionService,
    ProvisioningService,
    ServiceTransactionService,
    BillingService,
    BillingConfigService,
    SubscriptionFinanceService,
    ServiceTypeConfigService,
    RADIUSSettingsService,
    RADIUSCredentialConfigService,
    ServiceTypeConfig,
)
from app.services.subscriptions.subscription_types import (
    UsageFilters,
    SessionFilters,
    ProvisioningLogFilters,
    DisconnectRequest,
)
from app.services.subscriptions import ServiceTransactionFilters
from app.services.subscriptions.radius_settings_types import (
    NASConfigFilters,
    AttributeMappingFilters,
    DictionaryFilters,
    RADIUSSettingsUpdate,
    AttributeMappingData,
    NASConfigData,
)

RequireSubscriptionsRead = Depends(require_scope("subscriptions:read"))
RequireSubscriptionsWrite = Depends(require_scope("subscriptions:write"))

router = APIRouter(prefix="/subscriptions", tags=["subscriptions-services"])
templates = get_template_env()

SERVICE_NAV = [
    {"id": "dashboard", "label": "Dashboard", "href": "/subscriptions/dashboard"},
    {"id": "usage", "label": "Usage", "href": "/subscriptions/usage"},
    {"id": "sessions", "label": "Sessions", "href": "/subscriptions/sessions"},
    {"id": "provisioning", "label": "Provisioning", "href": "/subscriptions/provisioning"},
    {"id": "transactions", "label": "Transactions", "href": "/subscriptions/transactions"},
    {"id": "billing", "label": "Billing", "href": "/subscriptions/billing"},
    {"id": "finance", "label": "Finance", "href": "/subscriptions/finance"},
    {"id": "settings", "label": "Settings", "href": "/subscriptions/settings"},
]


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int = 0) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_bool(form: Any, key: str) -> bool:
    value = form.get(key)
    if isinstance(value, UploadFile):
        return False
    return value in ("true", "on", "1", True)


def _build_service_context(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    current_id: str,
    title: str,
    breadcrumb_label: str,
) -> dict:
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Services"},
        {"label": "Subscriptions", "href": "/subscriptions"},
        {"label": breadcrumb_label},
    ])
    context["service_nav"] = [
        {**item, "is_current": item["id"] == current_id}
        for item in SERVICE_NAV
    ]
    return context


@router.get("/dashboard", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Comprehensive subscription analytics dashboard."""
    reports = SubscriptionReportsService(db, principal=user)
    summary = reports.get_dashboard_summary()
    mrr_summary = reports.get_mrr_summary()
    churn_summary = reports.get_churn_summary()
    revenue_summary = reports.get_revenue_summary()

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "dashboard",
        "Subscriptions Dashboard",
        "Dashboard",
    )
    context["summary"] = summary
    context["mrr_summary"] = mrr_summary
    context["churn_summary"] = churn_summary
    context["revenue_summary"] = revenue_summary

    template = templates.get_template("modules/subscriptions/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/usage", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_usage(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: Optional[int] = Query(None),
    party_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Usage monitoring and reporting."""
    filters = UsageFilters(
        subscription_id=subscription_id,
        party_id=party_id,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    service = UsageService(db, principal=user)
    result = service.list_usage(filters, pagination)

    subscription_ids = {item.subscription_id for item in result.items}
    subscriptions = {}
    if subscription_ids:
        subs = (
            db.query(Subscription)
            .options(joinedload(Subscription.party))
            .filter(Subscription.id.in_(subscription_ids))
            .all()
        )
        subscriptions = {sub.id: sub for sub in subs}

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "usage",
        "Usage Monitoring",
        "Usage",
    )
    context["usage_records"] = result.items
    context["subscriptions_lookup"] = subscriptions
    context["filters"] = {
        "subscription_id": subscription_id,
        "party_id": party_id,
        "date_from": date_from or "",
        "date_to": date_to or "",
    }
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/subscriptions/templates/pages/usage.html")
    return HTMLResponse(template.render(context))


@router.get("/sessions", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_sessions(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    mode: str = Query("active", description="active or history"),
    username: Optional[str] = Query(None),
    nas_ip: Optional[str] = Query(None),
    framed_ip: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Session monitoring (active and historical)."""
    filters = SessionFilters(
        username=username or None,
        nas_ip=nas_ip or None,
        framed_ip=framed_ip or None,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    service = SessionService(db, principal=user)
    stats = service.get_session_stats()

    active_sessions = []
    session_history = []
    if mode == "history":
        session_history = service.get_session_history(filters, pagination)
    else:
        active_sessions = service.list_active_sessions(filters, pagination)

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "sessions",
        "Session Monitoring",
        "Sessions",
    )
    context["mode"] = mode
    context["session_stats"] = stats
    context["active_sessions"] = active_sessions
    context["session_history"] = session_history
    context["filters"] = {
        "username": username or "",
        "nas_ip": nas_ip or "",
        "framed_ip": framed_ip or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    }
    total_rows = len(active_sessions) if mode != "history" else len(session_history)
    context["pagination"] = build_pagination_context(page, per_page, total_rows)
    context["page"] = page
    context["per_page"] = per_page

    template = templates.get_template("modules/subscriptions/templates/pages/sessions.html")
    return HTMLResponse(template.render(context))


@router.post("/sessions/disconnect", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def sessions_disconnect(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Disconnect a session by session ID or username."""
    form = await request.form()
    session_id = _form_str(form, "session_id")
    username = _form_str(form, "username")
    reason = _form_str(form, "reason") or "admin_disconnect"

    if not session_id and not username:
        raise HTTPException(status_code=400, detail="Session ID or username is required")

    service = SessionService(db, principal=user)
    if session_id:
        result = service.disconnect_session(
            DisconnectRequest(
                session_id=session_id,
                username=username or None,
                reason=reason,
            )
        )
        results = [result]
    else:
        results = service.disconnect_user(username, reason=reason)

    if any(r.success for r in results):
        message = "Disconnect request sent"
        if is_htmx_request(request):
            htmx_toast(response, message, "success")
            response.headers["HX-Redirect"] = "/subscriptions/sessions?mode=active"
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, message, "success")
    else:
        message = results[0].message if results else "Disconnect failed"
        if is_htmx_request(request):
            htmx_toast(response, message, "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, message, "error")

    return RedirectResponse(url="/subscriptions/sessions?mode=active", status_code=303)


@router.get("/provisioning", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_provisioning_logs(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    subscription_id: Optional[int] = Query(None),
    router_id: Optional[int] = Query(None),
    failed_only: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Provisioning logs and outcomes."""
    filters = ProvisioningLogFilters(
        status=status,
        action=action,
        subscription_id=subscription_id,
        router_id=router_id,
        failed_only=failed_only,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    service = ProvisioningService(db, principal=user)
    result = service.list_logs(filters, pagination)

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "provisioning",
        "Provisioning Logs",
        "Provisioning",
    )
    context["logs"] = result.items
    context["filters"] = {
        "status": status or "",
        "action": action or "",
        "subscription_id": subscription_id,
        "router_id": router_id,
        "failed_only": failed_only,
    }
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/subscriptions/templates/pages/provisioning_logs.html")
    return HTMLResponse(template.render(context))


@router.post("/provisioning/retry/{log_id}", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def provisioning_retry(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    log_id: int,
):
    """Retry failed provisioning log."""
    service = ProvisioningService(db, principal=user)
    try:
        result = service.retry_failed(log_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result.success:
        message = "Retry queued"
        if is_htmx_request(request):
            htmx_toast(response, message, "success")
            response.headers["HX-Redirect"] = "/subscriptions/provisioning"
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, message, "success")
    else:
        message = result.message
        if is_htmx_request(request):
            htmx_toast(response, message, "error")
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, message, "error")

    return RedirectResponse(url="/subscriptions/provisioning", status_code=303)


@router.post("/provisioning/test-router", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def provisioning_test_router(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Test router connection via provisioning service."""
    form = await request.form()
    router_id_str = _form_str(form, "router_id")
    if not router_id_str.isdigit():
        raise HTTPException(status_code=400, detail="Valid router ID is required")

    service = ProvisioningService(db, principal=user)
    try:
        result = service.test_router_connection(int(router_id_str))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    message = result.message
    level = "success" if result.success else "error"

    if is_htmx_request(request):
        htmx_toast(response, message, level)
        response.headers["HX-Redirect"] = "/subscriptions/provisioning"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, level)
    return RedirectResponse(url="/subscriptions/provisioning", status_code=303)


@router.get("/transactions", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_transactions(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    subscription_id: Optional[int] = Query(None),
    party_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Service transaction audit trail."""
    filters = ServiceTransactionFilters(
        subscription_id=subscription_id,
        party_id=party_id,
        transaction_type=transaction_type,
        status=status,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    service = ServiceTransactionService(db, principal=user)
    result = service.list_transactions(filters, pagination)

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "transactions",
        "Service Transactions",
        "Transactions",
    )
    context["transactions"] = result.items
    context["filters"] = {
        "subscription_id": subscription_id,
        "party_id": party_id,
        "transaction_type": transaction_type or "",
        "status": status or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    }
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/subscriptions/templates/pages/transactions.html")
    return HTMLResponse(template.render(context))


@router.get("/billing", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_billing(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Billing configuration and upcoming billables."""
    config_service = BillingConfigService(db, principal=user)
    config = config_service.get_config()

    billing_service = BillingService(db, principal=user)
    cycles = ["daily", "weekly", "monthly", "quarterly", "yearly"]
    billables = {
        cycle: billing_service.get_billable_subscriptions(cycle)
        for cycle in cycles
    }

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "billing",
        "Billing Overview",
        "Billing",
    )
    context["billing_config"] = config
    context["billables"] = billables
    context["cycles"] = cycles

    template = templates.get_template("modules/subscriptions/templates/pages/billing.html")
    return HTMLResponse(template.render(context))


@router.get("/finance", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_finance(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    party_id: Optional[int] = Query(None),
    subscription_id: Optional[int] = Query(None),
):
    """Financial summary and invoice visibility."""
    reports = SubscriptionReportsService(db, principal=user)
    revenue_summary = reports.get_revenue_summary()
    churn_summary = reports.get_churn_summary()

    finance = SubscriptionFinanceService(db, principal=user)
    recent_invoices = (
        db.query(Invoice)
        .filter(Invoice.is_deleted == False)
        .order_by(Invoice.invoice_date.desc())
        .limit(20)
        .all()
    )

    ar_balance = None
    subscription_summary = None
    payment_history = None
    if party_id:
        ar_balance = finance.get_party_ar_balance(party_id)
        payment_history = finance.get_payment_history(party_id, limit=10)
    if subscription_id:
        subscription_summary = finance.get_subscription_financial_summary(subscription_id)

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "finance",
        "Finance Overview",
        "Finance",
    )
    context["revenue_summary"] = revenue_summary
    context["churn_summary"] = churn_summary
    context["recent_invoices"] = recent_invoices
    context["finance_service"] = finance
    context["ar_balance"] = ar_balance
    context["subscription_summary"] = subscription_summary
    context["payment_history"] = payment_history

    template = templates.get_template("modules/subscriptions/templates/pages/finance.html")
    return HTMLResponse(template.render(context))


@router.post("/billing/run-daily", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def run_daily_billing(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Trigger a daily billing run."""
    form = await request.form()
    billing_date = _parse_date(_form_str(form, "billing_date"))
    dry_run = _form_bool(form, "dry_run")

    service = BillingService(db, principal=user)
    summary = service.run_daily_billing(billing_date=billing_date, dry_run=dry_run)

    message = (
        f"Daily billing run complete: {summary.successful} success, "
        f"{summary.failed} failed, total {summary.total_amount}"
    )
    set_flash(response, message, "success")
    return RedirectResponse(url="/subscriptions/billing", status_code=303)


@router.get("/settings", response_class=HTMLResponse, dependencies=[RequireSubscriptionsRead])
async def subscriptions_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Subscription service settings overview."""
    billing_config = BillingConfigService(db, principal=user).get_config()
    service_config = ServiceTypeConfigService(db, principal=user).get_config()

    radius_service = RADIUSSettingsService(db, principal=user)
    radius_settings = radius_service.get_settings()
    mappings = radius_service.list_attribute_mappings(
        AttributeMappingFilters(), PaginationParams(offset=0, limit=20)
    )
    nas_configs = radius_service.list_nas_configs(
        NASConfigFilters(), PaginationParams(offset=0, limit=20)
    )
    dictionary_entries = radius_service.list_dictionary_entries(
        DictionaryFilters(), PaginationParams(offset=0, limit=20)
    )

    context = _build_service_context(
        request,
        response,
        user,
        csrf_token,
        "settings",
        "Subscription Settings",
        "Settings",
    )
    context["billing_config"] = billing_config
    context["service_config"] = service_config
    context["radius_settings"] = radius_settings
    context["radius_mappings"] = mappings.items
    context["nas_configs"] = nas_configs.items
    context["dictionary_entries"] = dictionary_entries.items

    # RADIUS credential generation config
    credential_config = RADIUSCredentialConfigService(db, principal=user).get_config()
    context["credential_config"] = credential_config

    template = templates.get_template("modules/subscriptions/templates/pages/settings.html")
    return HTMLResponse(template.render(context))


@router.post("/settings/billing", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def update_billing_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Update subscription billing configuration."""
    form = await request.form()
    updates = {
        "enabled": _form_bool(form, "enabled"),
        "default_currency": _form_str(form, "default_currency") or "NGN",
        "tax_rate": float(_form_str(form, "tax_rate", "0") or 0),
        "invoice_due_days": _form_int(form, "invoice_due_days", 7),
        "auto_charge_enabled": _form_bool(form, "auto_charge_enabled"),
        "auto_suspend_enabled": _form_bool(form, "auto_suspend_enabled"),
    }

    BillingConfigService(db, principal=user).update_config(updates)
    set_flash(response, "Billing settings updated.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/lifecycle", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def update_lifecycle_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Update lifecycle and plan change settings."""
    form = await request.form()
    config_service = ServiceTypeConfigService(db, principal=user)
    config = config_service.get_config(use_cache=False)

    lifecycle_updates = {
        "auto_activate_on_payment": _form_bool(form, "auto_activate_on_payment"),
        "auto_suspend_on_nonpayment": _form_bool(form, "auto_suspend_on_nonpayment"),
        "auto_cancel_after_days": _form_int(form, "auto_cancel_after_days", config.lifecycle.auto_cancel_after_days),
        "allow_self_reactivation": _form_bool(form, "allow_self_reactivation"),
        "require_payment_for_reactivation": _form_bool(form, "require_payment_for_reactivation"),
    }

    plan_updates = {
        "allow_upgrades": _form_bool(form, "allow_upgrades"),
        "allow_downgrades": _form_bool(form, "allow_downgrades"),
        "upgrade_fee": float(_form_str(form, "upgrade_fee", "0") or 0),
        "downgrade_fee": float(_form_str(form, "downgrade_fee", "0") or 0),
        "min_days_before_downgrade": _form_int(form, "min_days_before_downgrade", config.plan_changes.min_days_before_downgrade),
    }

    new_dict = config.to_dict()
    new_dict["lifecycle"].update(lifecycle_updates)
    new_dict["plan_changes"].update(plan_updates)
    config_service.save_config(ServiceTypeConfig.from_dict(new_dict))

    set_flash(response, "Lifecycle settings updated.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/service-types", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def update_service_types(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Update service type definitions."""
    form = await request.form()
    config_service = ServiceTypeConfigService(db, principal=user)

    for type_code in ("internet", "voice", "bundle", "custom"):
        updates = {
            "enabled": _form_bool(form, f"{type_code}_enabled"),
            "default_billing_cycle": _form_str(form, f"{type_code}_default_billing_cycle") or "monthly",
            "requires_provisioning": _form_bool(form, f"{type_code}_requires_provisioning"),
            "requires_router": _form_bool(form, f"{type_code}_requires_router"),
            "grace_period_days": _form_int(form, f"{type_code}_grace_period_days", 3),
        }
        config_service.update_type(type_code, updates)

    set_flash(response, "Service type settings updated.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/radius", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def update_radius_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Update core RADIUS settings."""
    form = await request.form()
    updates = {
        "server": {
            "host": _form_str(form, "radius_host") or "localhost",
            "auth_port": _form_int(form, "radius_auth_port", 1812),
            "acct_port": _form_int(form, "radius_acct_port", 1813),
            "timeout_seconds": _form_int(form, "radius_timeout_seconds", 5),
            "retries": _form_int(form, "radius_retries", 3),
        },
        "accounting": {
            "method": _form_str(form, "accounting_method") or "RADIUS",
            "interim_update_interval_seconds": _form_int(form, "interim_update_interval_seconds", 300),
            "track_sessions": _form_bool(form, "track_sessions"),
            "track_usage": _form_bool(form, "track_usage"),
        },
    }

    service = RADIUSSettingsService(db, principal=user)
    service.update_settings(RADIUSSettingsUpdate(**updates))

    set_flash(response, "RADIUS settings updated.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/radius/mappings", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def create_radius_mapping(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a RADIUS attribute mapping."""
    form = await request.form()
    service = RADIUSSettingsService(db, principal=user)

    data = AttributeMappingData(
        nas_type=_form_str(form, "nas_type") or "MIKROTIK",
        attribute_name=_form_str(form, "attribute_name"),
        radius_attribute=_form_str(form, "radius_attribute"),
        radius_vendor_id=int(_form_str(form, "radius_vendor_id", "0") or 0) or None,
        radius_vendor_type=int(_form_str(form, "radius_vendor_type", "0") or 0) or None,
        value_format=_form_str(form, "value_format") or None,
    )
    service.create_attribute_mapping(data)

    set_flash(response, "Attribute mapping created.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/radius/nas", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def create_radius_nas_config(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Create NAS configuration for a router."""
    form = await request.form()
    service = RADIUSSettingsService(db, principal=user)

    data = NASConfigData(
        router_id=_form_int(form, "router_id", 0),
        nas_identifier=_form_str(form, "nas_identifier") or None,
        radius_secret=_form_str(form, "radius_secret") or None,
        nas_type=_form_str(form, "nas_type") or "MIKROTIK",
        coa_enabled=_form_bool(form, "coa_enabled"),
        coa_port=_form_int(form, "coa_port", 3799),
        coa_secret=_form_str(form, "coa_secret") or None,
        interim_interval=_form_int(form, "interim_interval", 300),
        custom_attributes={},
    )
    if data.router_id <= 0:
        raise HTTPException(status_code=400, detail="Valid router ID is required")

    service.create_nas_config(data)
    set_flash(response, "NAS configuration created.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


@router.post("/settings/radius/credentials", response_class=HTMLResponse, dependencies=[RequireSubscriptionsWrite])
async def update_radius_credential_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Update RADIUS credential generation settings."""
    form = await request.form()

    updates = {
        "enabled": _form_bool(form, "cred_enabled"),
        "auto_generate_on_create": _form_bool(form, "cred_auto_generate"),
        "notify_on_regenerate": _form_bool(form, "cred_notify"),
        "username": {
            "format_type": _form_str(form, "cred_format_type") or "template",
            "template": _form_str(form, "cred_template") or "{email}",
            "domain": _form_str(form, "cred_domain") or None,
            "lowercase": _form_bool(form, "cred_lowercase"),
            "strip_special": _form_bool(form, "cred_strip_special"),
            "max_length": _form_int(form, "cred_max_length", 64),
        },
        "sequential": {
            "prefix": _form_str(form, "cred_seq_prefix") or "USER",
            "padding_length": _form_int(form, "cred_seq_padding", 4),
            "start_from": _form_int(form, "cred_seq_start", 1),
        },
        "password": {
            "min_length": _form_int(form, "cred_pwd_min", 12),
            "max_length": _form_int(form, "cred_pwd_max", 16),
            "include_lowercase": _form_bool(form, "cred_pwd_lower"),
            "include_uppercase": _form_bool(form, "cred_pwd_upper"),
            "include_digits": _form_bool(form, "cred_pwd_digits"),
            "include_special": _form_bool(form, "cred_pwd_special"),
            "special_chars": _form_str(form, "cred_pwd_special_chars") or "!@#$%^&*",
            "exclude_ambiguous": _form_bool(form, "cred_pwd_exclude_ambig"),
        },
    }

    service = RADIUSCredentialConfigService(db, principal=user)
    service.update_config(updates)

    set_flash(response, "RADIUS credential settings updated.", "success")
    return RedirectResponse(url="/subscriptions/settings", status_code=303)


# =============================================================================
# EXPORT ROUTES
# =============================================================================

@router.get("/reports/export/{report_type}", dependencies=[RequireSubscriptionsRead])
async def export_report(
    report_type: str,
    user: SessionUser,
    db: DB,
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    period: str = Query("this_month", description="Report period"),
    currency: str = Query("NGN", description="Currency code"),
):
    """
    Export subscription report as CSV or JSON.

    Supported report types: mrr, churn, revenue
    """
    import csv
    import io
    import json
    from fastapi.responses import StreamingResponse
    from app.services.subscriptions import ReportPeriod

    reports = SubscriptionReportsService(db, principal=user)

    # Map period string to enum
    period_map = {
        "today": ReportPeriod.TODAY,
        "this_week": ReportPeriod.THIS_WEEK,
        "this_month": ReportPeriod.THIS_MONTH,
        "last_month": ReportPeriod.LAST_MONTH,
        "this_quarter": ReportPeriod.THIS_QUARTER,
        "this_year": ReportPeriod.THIS_YEAR,
        "last_year": ReportPeriod.LAST_YEAR,
    }
    report_period = period_map.get(period, ReportPeriod.THIS_MONTH)

    # Get report data based on type
    if report_type == "mrr":
        report_data = reports.get_mrr_summary(period=report_period, currency=currency)
        filename = f"mrr_report_{period}"
    elif report_type == "churn":
        report_data = reports.get_churn_summary(period=report_period, currency=currency)
        filename = f"churn_report_{period}"
    elif report_type == "revenue":
        report_data = reports.get_revenue_summary(period=report_period, currency=currency)
        filename = f"revenue_report_{period}"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    # Convert to dict for export
    data_dict = reports.export_to_dict(report_data)

    if format == "json":
        # JSON export
        content = json.dumps(data_dict, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.json"
            }
        )
    else:
        # CSV export - flatten the data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers and values
        def flatten_dict(d, parent_key=""):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key))
                elif isinstance(v, list):
                    items.append((new_key, json.dumps(v)))
                else:
                    items.append((new_key, v))
            return items

        flat_data = flatten_dict(data_dict)
        writer.writerow([item[0] for item in flat_data])
        writer.writerow([item[1] for item in flat_data])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.csv"
            }
        )

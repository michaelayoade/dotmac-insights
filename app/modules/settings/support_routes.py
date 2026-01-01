"""
Support Settings Routes - Helpdesk module configuration.

Handles SLA, routing, escalations, queues, and portal settings.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, set_flash

# Permission dependencies
RequireSupportSettingsRead = Depends(require_scope("support:settings:read"))
RequireSupportSettingsWrite = Depends(require_scope("support:settings:write"))

router = APIRouter(prefix="/support", tags=["settings-support"])
templates = get_template_env()


def _form_int(form: Any, key: str, default: int) -> int:
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


def get_settings_nav(user, current_section: str = "support") -> list[dict]:
    """Get settings navigation."""
    from app.modules.settings.routes import SETTINGS_CATEGORIES
    nav_items = []
    for cat in SETTINGS_CATEGORIES:
        if cat["scope"] is None or user.has_scope(cat["scope"]):
            nav_items.append({
                **cat,
                "is_current": current_section == cat["id"],
            })
    return nav_items


SUPPORT_TABS = [
    {"id": "general", "label": "General", "href": "/settings/support"},
    {"id": "escalations", "label": "Escalations", "href": "/settings/support/escalations"},
    {"id": "queues", "label": "Queues", "href": "/settings/support/queues"},
    {"id": "fields", "label": "Custom Fields", "href": "/settings/support/fields"},
    {"id": "templates", "label": "Email Templates", "href": "/settings/support/templates"},
]


@router.get("", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def support_settings_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support settings - general configuration."""
    from app.models.support_settings import SupportSettings

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "general"

    # Get or create settings
    settings = db.query(SupportSettings).filter(SupportSettings.company == None).first()
    if not settings:
        settings = SupportSettings()

    context["page_title"] = "Support Settings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "General"},
    ])

    context["settings"] = settings
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/general.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireSupportSettingsWrite])
async def save_support_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Save support settings."""
    from app.models.support_settings import SupportSettings

    form = await request.form()

    settings = db.query(SupportSettings).filter(SupportSettings.company == None).first()
    if not settings:
        settings = SupportSettings()
        db.add(settings)

    settings_any: Any = settings

    # SLA settings
    settings_any.sla_warning_threshold_percent = _form_int(form, "sla_warning_threshold_percent", 80)
    settings_any.default_first_response_hours = _form_int(form, "default_first_response_hours", 4)
    settings_any.default_resolution_hours = _form_int(form, "default_resolution_hours", 24)
    settings_any.sla_include_holidays = _form_bool(form, "sla_include_holidays")
    settings_any.sla_include_weekends = _form_bool(form, "sla_include_weekends")

    # Routing settings
    settings_any.max_tickets_per_agent = _form_int(form, "max_tickets_per_agent", 20)
    settings_any.rebalance_threshold_percent = _form_int(form, "rebalance_threshold_percent", 20)

    # Auto-close settings
    settings_any.auto_close_enabled = _form_bool(form, "auto_close_enabled")
    settings_any.auto_close_resolved_days = _form_int(form, "auto_close_resolved_days", 7)
    settings_any.allow_customer_reopen = _form_bool(form, "allow_customer_reopen")
    settings_any.reopen_window_days = _form_int(form, "reopen_window_days", 14)
    settings_any.max_reopens_allowed = _form_int(form, "max_reopens_allowed", 3)

    # CSAT settings
    settings_any.csat_enabled = _form_bool(form, "csat_enabled")
    settings_any.csat_delay_hours = _form_int(form, "csat_delay_hours", 24)
    settings_any.csat_survey_expiry_days = _form_int(form, "csat_survey_expiry_days", 7)

    # Portal settings
    settings_any.portal_enabled = _form_bool(form, "portal_enabled")
    settings_any.portal_ticket_creation_enabled = _form_bool(form, "portal_ticket_creation_enabled")
    settings_any.portal_show_ticket_history = _form_bool(form, "portal_show_ticket_history")
    settings_any.portal_require_login = _form_bool(form, "portal_require_login")

    # Knowledge base settings
    settings_any.kb_enabled = _form_bool(form, "kb_enabled")
    settings_any.kb_public_access = _form_bool(form, "kb_public_access")
    settings_any.kb_suggest_articles_on_create = _form_bool(form, "kb_suggest_articles_on_create")

    db.commit()

    set_flash(response, "Support settings saved successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/support", status_code=303)


@router.get("/escalations", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def escalations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Escalation policies."""
    from app.models.support_settings import EscalationPolicy

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "escalations"

    policies = db.query(EscalationPolicy).order_by(EscalationPolicy.name).all()

    context["page_title"] = "Escalation Policies"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "Escalations"},
    ])

    context["policies"] = policies
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/escalations.html")
    return HTMLResponse(template.render(context))


@router.get("/queues", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def queues_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support queues."""
    from app.models.support_settings import SupportQueue

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "queues"

    queues = db.query(SupportQueue).order_by(SupportQueue.display_order, SupportQueue.name).all()

    context["page_title"] = "Support Queues"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "Queues"},
    ])

    context["queues"] = queues
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/queues.html")
    return HTMLResponse(template.render(context))


@router.get("/fields", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def fields_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Custom ticket fields."""
    from app.models.support_settings import TicketFieldConfig

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "fields"

    fields = db.query(TicketFieldConfig).order_by(TicketFieldConfig.display_order, TicketFieldConfig.field_name).all()

    context["page_title"] = "Custom Fields"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "Custom Fields"},
    ])

    context["fields"] = fields
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/fields.html")
    return HTMLResponse(template.render(context))


@router.get("/templates", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def templates_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Email templates."""
    from app.models.support_settings import SupportEmailTemplate

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "templates"

    email_templates = db.query(SupportEmailTemplate).order_by(SupportEmailTemplate.template_type).all()

    context["page_title"] = "Email Templates"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "Email Templates"},
    ])

    context["email_templates"] = email_templates
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/templates.html")
    return HTMLResponse(template.render(context))

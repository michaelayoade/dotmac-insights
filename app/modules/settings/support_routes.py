"""
Support Settings Routes - Helpdesk module configuration.

Handles SLA, routing, escalations, queues, and portal settings.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import set_flash
from app.services.settings_support_service import SettingsSupportService

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
    {"id": "tags", "label": "Tags", "href": "/settings/support/tags"},
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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "general"

    service = SettingsSupportService(db, principal=user)
    settings = service.get_general_settings()

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
    from app.services.support.types import SupportSettingsUpdate

    form = await request.form()

    service = SettingsSupportService(db, principal=user)
    update_data = SupportSettingsUpdate(
        sla_warning_threshold_percent=_form_int(form, "sla_warning_threshold_percent", 80),
        default_first_response_hours=_form_int(form, "default_first_response_hours", 4),
        default_resolution_hours=_form_int(form, "default_resolution_hours", 24),
        sla_include_holidays=_form_bool(form, "sla_include_holidays"),
        sla_include_weekends=_form_bool(form, "sla_include_weekends"),
        max_tickets_per_agent=_form_int(form, "max_tickets_per_agent", 20),
        rebalance_threshold_percent=_form_int(form, "rebalance_threshold_percent", 20),
        auto_close_enabled=_form_bool(form, "auto_close_enabled"),
        auto_close_resolved_days=_form_int(form, "auto_close_resolved_days", 7),
        allow_customer_reopen=_form_bool(form, "allow_customer_reopen"),
        reopen_window_days=_form_int(form, "reopen_window_days", 14),
        max_reopens_allowed=_form_int(form, "max_reopens_allowed", 3),
        csat_enabled=_form_bool(form, "csat_enabled"),
        csat_delay_hours=_form_int(form, "csat_delay_hours", 24),
        csat_survey_expiry_days=_form_int(form, "csat_survey_expiry_days", 7),
        portal_enabled=_form_bool(form, "portal_enabled"),
        portal_ticket_creation_enabled=_form_bool(form, "portal_ticket_creation_enabled"),
        portal_show_ticket_history=_form_bool(form, "portal_show_ticket_history"),
        portal_require_login=_form_bool(form, "portal_require_login"),
        kb_enabled=_form_bool(form, "kb_enabled"),
        kb_public_access=_form_bool(form, "kb_public_access"),
        kb_suggest_articles_on_create=_form_bool(form, "kb_suggest_articles_on_create"),
    )
    service.save_general_settings(update_data)

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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "escalations"

    service = SettingsSupportService(db, principal=user)
    policies = service.list_escalation_policies()

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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "queues"

    service = SettingsSupportService(db, principal=user)
    queues = service.list_queues()

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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "fields"

    service = SettingsSupportService(db, principal=user)
    fields = service.list_custom_fields()

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
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "templates"

    service = SettingsSupportService(db, principal=user)
    email_templates = service.list_email_templates()

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


# =============================================================================
# TAGS MANAGEMENT
# =============================================================================

@router.get("/tags", response_class=HTMLResponse, dependencies=[RequireSupportSettingsRead])
async def tags_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Support tags management."""
    from app.models.support_tags import TicketTag

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "support")
    context["support_tabs"] = SUPPORT_TABS
    context["current_tab"] = "tags"

    # Get all tags
    tags = db.query(TicketTag).order_by(TicketTag.name).all()

    context["page_title"] = "Ticket Tags"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Support", "href": "/settings/support"},
        {"label": "Tags"},
    ])

    context["tags"] = tags
    context["can_edit"] = user.has_scope("support:settings:write")

    template = templates.get_template("modules/settings/templates/pages/support/tags.html")
    return HTMLResponse(template.render(context))


@router.post("/tags", response_class=HTMLResponse, dependencies=[RequireSupportSettingsWrite])
async def create_tag(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Create a new tag."""
    from app.models.support_tags import TicketTag
    from fastapi.responses import RedirectResponse

    form = await request.form()
    name = form.get("name", "").strip()
    color = form.get("color", "#6B7280").strip()
    description = form.get("description", "").strip()

    if not name:
        set_flash(response, "Tag name is required.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    # Check if tag exists
    existing = db.query(TicketTag).filter(TicketTag.name == name).first()
    if existing:
        set_flash(response, f"Tag '{name}' already exists.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    tag = TicketTag(
        name=name,
        color=color,
        description=description or None,
        is_active=True,
        usage_count=0,
    )
    db.add(tag)
    db.commit()

    set_flash(response, f"Tag '{name}' created successfully.", "success")
    return RedirectResponse(url="/settings/support/tags", status_code=303)


@router.post("/tags/{tag_id}/update", response_class=HTMLResponse, dependencies=[RequireSupportSettingsWrite])
async def update_tag(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tag_id: int,
    _csrf: CSRFProtect,
):
    """Update a tag."""
    from app.models.support_tags import TicketTag
    from fastapi.responses import RedirectResponse

    tag = db.query(TicketTag).filter(TicketTag.id == tag_id).first()
    if not tag:
        set_flash(response, "Tag not found.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    form = await request.form()
    name = form.get("name", "").strip()
    color = form.get("color", "#6B7280").strip()
    description = form.get("description", "").strip()
    is_active = form.get("is_active") in ("true", "on", "1", True)

    if not name:
        set_flash(response, "Tag name is required.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    # Check if name conflicts with another tag
    existing = db.query(TicketTag).filter(TicketTag.name == name, TicketTag.id != tag_id).first()
    if existing:
        set_flash(response, f"Tag '{name}' already exists.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    tag.name = name
    tag.color = color
    tag.description = description or None
    tag.is_active = is_active
    db.commit()

    set_flash(response, f"Tag '{name}' updated successfully.", "success")
    return RedirectResponse(url="/settings/support/tags", status_code=303)


@router.post("/tags/{tag_id}/delete", response_class=HTMLResponse, dependencies=[RequireSupportSettingsWrite])
async def delete_tag(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tag_id: int,
    _csrf: CSRFProtect,
):
    """Delete a tag."""
    from app.models.support_tags import TicketTag
    from fastapi.responses import RedirectResponse

    tag = db.query(TicketTag).filter(TicketTag.id == tag_id).first()
    if not tag:
        set_flash(response, "Tag not found.", "error")
        return RedirectResponse(url="/settings/support/tags", status_code=303)

    tag_name = tag.name

    # If tag has usage, deactivate instead of delete
    if tag.usage_count > 0:
        tag.is_active = False
        db.commit()
        set_flash(response, f"Tag '{tag_name}' deactivated (in use by {tag.usage_count} tickets).", "info")
    else:
        db.delete(tag)
        db.commit()
        set_flash(response, f"Tag '{tag_name}' deleted successfully.", "success")

    return RedirectResponse(url="/settings/support/tags", status_code=303)

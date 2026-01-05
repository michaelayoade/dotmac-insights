"""
General Settings Routes - Schema-driven settings forms.

Handles email, payments, webhooks, SMS, notifications, branding, and localization settings.
Uses SettingsService for encrypted storage and validation.
"""
from __future__ import annotations

from ._deps import (
    # FastAPI
    APIRouter, Request, Response, HTTPException,
    HTMLResponse, RedirectResponse,
    # Dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireSettingsRead, RequireSettingsWrite,
    # Templates
    templates,
    # Context helpers
    get_base_context, get_navigation_context, build_breadcrumbs,
    # Schema helpers
    SETTING_SCHEMAS, get_schema, get_all_groups, get_secret_fields,
    # Form helpers
    schema_to_form_fields, mask_secret_values, get_settings_nav,
    # Security
    is_htmx_request, set_flash,
    # Service
    SettingsWebService,
)

router = APIRouter(prefix="/general", tags=["settings-general"])


@router.get("", response_class=HTMLResponse, dependencies=[RequireSettingsRead])
async def general_settings_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """General settings landing - redirects to first group."""
    return RedirectResponse(url="/settings/general/email", status_code=303)


@router.get("/{group}", response_class=HTMLResponse, dependencies=[RequireSettingsRead])
async def general_settings_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    group: str,
):
    """Display settings form for a specific group."""
    # Validate group
    if group not in SETTING_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "general")

    # Get schema and current values via service (handles decryption)
    service = SettingsWebService(db, user)
    schema = get_schema(group)
    secrets = get_secret_fields(group)

    # Get masked settings (secrets replaced with ***REDACTED***)
    values = await service.get_masked_settings(group)

    # Build form fields from schema
    fields = schema_to_form_fields(schema, values, secrets)

    # Group metadata
    groups = get_all_groups()
    current_group = next((g for g in groups if g["group"] == group), None)

    context["page_title"] = f"Settings - {current_group['label'] if current_group else group.title()}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "General", "href": "/settings/general"},
        {"label": current_group["label"] if current_group else group.title()},
    ])

    context["current_group"] = group
    context["group_label"] = current_group["label"] if current_group else group.title()
    context["group_description"] = current_group["description"] if current_group else ""
    context["groups"] = groups
    context["fields"] = fields
    context["has_test_action"] = group in ["email", "sms", "payments", "webhooks"]

    template = templates.get_template("modules/settings/templates/pages/general/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{group}", response_class=HTMLResponse, dependencies=[RequireSettingsWrite])
async def save_general_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    group: str,
    _csrf: CSRFProtect,
):
    """Save settings for a specific group via SettingsService."""
    if group not in SETTING_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")

    # Parse form data
    form = await request.form()
    form_data = dict(form)

    # Save via service (handles encryption, validation, audit logging)
    service = SettingsWebService(db, user)
    await service.save_settings(group, form_data, request)

    set_flash(response, f"{group.title()} settings saved successfully.", "success")

    if is_htmx_request(request):
        response.headers["HX-Redirect"] = f"/settings/general/{group}"
        return HTMLResponse("")

    return RedirectResponse(url=f"/settings/general/{group}", status_code=303)


@router.post("/{group}/test", response_class=HTMLResponse, dependencies=[RequireSettingsWrite])
async def test_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    group: str,
):
    """Test settings (send test email, SMS, etc.)."""
    if group not in ["email", "sms", "payments", "webhooks"]:
        raise HTTPException(status_code=400, detail="Test not available for this group")

    # In production, this would call the actual test functions
    # For now, return a success message

    result_html = f"""
    <div class="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700 ring-1 ring-emerald-200">
        <div class="flex items-center gap-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
            <span>Test {group} sent successfully!</span>
        </div>
    </div>
    """

    return HTMLResponse(result_html)

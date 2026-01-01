"""
Assets Settings Routes - Asset management configuration.

Handles depreciation and alert thresholds.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, set_flash
from app.models.asset_settings import AssetSettings, DepreciationMethod, DepreciationPostingDate

# Permission dependencies
RequireAssetsSettingsRead = Depends(require_scope("assets:settings:read"))
RequireAssetsSettingsWrite = Depends(require_scope("assets:settings:write"))

router = APIRouter(prefix="/assets", tags=["settings-assets"])
templates = get_template_env()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value)


def _form_bool(form: Any, key: str) -> bool:
    value = form.get(key)
    if isinstance(value, UploadFile):
        return False
    return value in ("true", "on", "1", True)


def get_settings_nav(user, current_section: str = "assets") -> list[dict]:
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


@router.get("", response_class=HTMLResponse, dependencies=[RequireAssetsSettingsRead])
async def assets_settings_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Assets settings - general configuration."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "assets")

    # Get or create settings
    settings = db.query(AssetSettings).filter(AssetSettings.company == None).first()
    if not settings:
        settings = AssetSettings()

    context["page_title"] = "Asset Settings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Assets", "href": "/settings/assets"},
        {"label": "General"},
    ])

    context["settings"] = settings
    context["can_edit"] = user.has_scope("assets:settings:write")

    # Enum options
    context["depreciation_methods"] = [
        {"value": e.value, "label": e.value.replace("_", " ").title()}
        for e in DepreciationMethod
    ]
    context["posting_dates"] = [
        {"value": e.value, "label": e.value.replace("_", " ").title()}
        for e in DepreciationPostingDate
    ]

    template = templates.get_template("modules/settings/templates/pages/assets/general.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireAssetsSettingsWrite])
async def save_assets_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Save assets settings."""
    form = await request.form()

    settings = db.query(AssetSettings).filter(AssetSettings.company == None).first()
    if not settings:
        settings = AssetSettings()
        db.add(settings)

    settings_any: Any = settings

    # Depreciation settings
    settings_any.default_depreciation_method = _form_str(
        form, "default_depreciation_method", DepreciationMethod.STRAIGHT_LINE.value
    )
    settings_any.default_finance_book = _form_str(form, "default_finance_book") or None
    settings_any.depreciation_posting_date = _form_str(
        form, "depreciation_posting_date", DepreciationPostingDate.LAST_DAY.value
    )
    settings_any.auto_post_depreciation = _form_bool(form, "auto_post_depreciation")

    # CWIP settings
    settings_any.enable_cwip_by_default = _form_bool(form, "enable_cwip_by_default")

    # Alert thresholds
    settings_any.maintenance_alert_days = _form_int(form, "maintenance_alert_days", 7)
    settings_any.warranty_alert_days = _form_int(form, "warranty_alert_days", 30)
    settings_any.insurance_alert_days = _form_int(form, "insurance_alert_days", 30)

    db.commit()

    set_flash(response, "Asset settings saved successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/assets", status_code=303)

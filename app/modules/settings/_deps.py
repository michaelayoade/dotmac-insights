"""
Shared dependencies for Settings routes.

This module contains common imports, helpers, and the SettingsWebService
used across all settings route modules.
"""
from __future__ import annotations

from typing import Optional, Any, Dict, Set

from fastapi import APIRouter, Request, Response, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.schemas.settings_schemas import (
    SETTING_SCHEMAS,
    get_schema,
    get_all_groups,
    get_secret_fields,
    get_defaults,
)
from app.core.security import is_htmx_request, set_flash
from app.services.settings_service import SettingsService, SettingsServiceError, SettingsValidationError

# Permission dependencies
RequireSettingsRead = Depends(require_scope("settings:read"))
RequireSettingsWrite = Depends(require_scope("settings:write"))

# Template environment
templates = get_template_env()


# =============================================================================
# SETTINGS WEB SERVICE
# =============================================================================

class SettingsWebService:
    """
    Web-layer wrapper for SettingsService.

    Provides synchronous-style methods and handles form data transformation.
    """

    def __init__(self, db: Session, user: Any):
        self.db = db
        self.user = user
        self._service = SettingsService(db)

    async def get_settings(self, group: str) -> Dict[str, Any]:
        """Get settings for a group (decrypted)."""
        if group not in SETTING_SCHEMAS:
            raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")
        return await self._service.get(group)

    async def get_masked_settings(self, group: str) -> Dict[str, Any]:
        """Get settings with secrets replaced by ***REDACTED***."""
        if group not in SETTING_SCHEMAS:
            raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")
        return await self._service.get_masked(group)

    async def save_settings(
        self,
        group: str,
        form_data: Dict[str, Any],
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        """Save settings from form data."""
        if group not in SETTING_SCHEMAS:
            raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")

        schema = get_schema(group)
        secrets = get_secret_fields(group)

        # Transform form data to proper types
        values = self._transform_form_data(schema, secrets, form_data)

        # Get existing secrets that weren't changed
        try:
            existing = await self._service.get(group)
            for secret_field in secrets:
                # If the form value is the masked placeholder, keep the existing value
                if secret_field not in values or values.get(secret_field) == "***REDACTED***":
                    if secret_field in existing and existing[secret_field]:
                        values[secret_field] = existing[secret_field]
                # Remove placeholder values
                if values.get(secret_field) in ("***REDACTED***", "********", None, ""):
                    if secret_field in existing and existing[secret_field]:
                        values[secret_field] = existing[secret_field]
                    elif secret_field in values:
                        del values[secret_field]
        except SettingsServiceError:
            pass

        # Save via service (handles encryption, validation, audit)
        try:
            return await self._service.update(group, values, self.user, request)
        except SettingsValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def _transform_form_data(
        self,
        schema: Dict[str, Any],
        secrets: Set[str],
        form_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Transform form data to proper types based on schema."""
        values: Dict[str, Any] = {}
        properties = schema.get("properties", {})

        for name, prop in properties.items():
            form_value = form_data.get(name)

            if form_value is None:
                continue

            # Skip upload files
            if isinstance(form_value, UploadFile):
                continue

            form_value_str = str(form_value).strip() if form_value else ""

            # Handle type conversion
            if prop.get("type") == "boolean":
                values[name] = form_value_str.lower() in ("true", "on", "1", "yes")
            elif prop.get("type") == "integer":
                if form_value_str:
                    try:
                        values[name] = int(form_value_str)
                    except ValueError:
                        values[name] = None
            elif prop.get("type") == "number":
                if form_value_str:
                    try:
                        values[name] = float(form_value_str)
                    except ValueError:
                        values[name] = None
            elif name in secrets and form_value_str in ("********", "***REDACTED***"):
                # Don't overwrite secret with masked value
                pass
            else:
                values[name] = form_value_str if form_value_str else None

        return values

    async def get_audit_log(
        self,
        group: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ):
        """Get audit log entries."""
        return await self._service.get_audit_log(group, skip, limit)


# =============================================================================
# NAVIGATION HELPERS
# =============================================================================

def get_settings_nav(user: Any, current_section: str = "general") -> list[dict]:
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


# =============================================================================
# FORM FIELD HELPERS
# =============================================================================

def schema_to_form_fields(schema: dict, values: dict, secrets: set) -> list[dict]:
    """Convert JSON schema to form field definitions."""
    fields = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in properties.items():
        field = {
            "name": name,
            "label": prop.get("description", name.replace("_", " ").title()),
            "type": prop.get("type", "string"),
            "required": name in required,
            "is_secret": name in secrets,
            "value": values.get(name, prop.get("default", "")),
            "default": prop.get("default"),
            "description": prop.get("description", ""),
        }

        # Handle enums
        if "enum" in prop:
            field["type"] = "select"
            field["options"] = [
                {"value": v, "label": v.replace("_", " ").title()}
                for v in prop["enum"]
            ]

        # Handle specific formats
        if prop.get("format") == "email":
            field["input_type"] = "email"
        elif prop.get("format") == "uri":
            field["input_type"] = "url"
        elif prop.get("type") == "integer":
            field["input_type"] = "number"
            field["min"] = prop.get("minimum")
            field["max"] = prop.get("maximum")
        elif prop.get("type") == "boolean":
            field["type"] = "toggle"
        elif field["is_secret"]:
            field["input_type"] = "password"
        else:
            field["input_type"] = "text"

        # Handle pattern (for validation hint)
        if "pattern" in prop:
            field["pattern"] = prop["pattern"]

        fields.append(field)

    return fields


def mask_secret_values(values: dict, secrets: set) -> dict:
    """Replace secret field values with placeholder."""
    masked = dict(values)
    for field in secrets:
        if field in masked and masked[field]:
            masked[field] = "***REDACTED***"
    return masked

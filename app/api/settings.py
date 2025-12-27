"""
General Settings API Endpoints

Admin-only endpoints for managing application settings:
- Email, payments, webhooks, SMS, notifications, branding, localization
- Encrypted secret storage via OpenBao
- Audit logging for all changes
- Test actions for validating configurations
"""

import uuid
import json
import asyncio
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.models.auth import User
from app.services.settings_service import (
    SettingsService,
    SettingsCache,
    SettingsServiceError,
    SettingsValidationError,
)
from app.schemas.settings_schemas import (
    get_all_groups,
    get_schema,
    get_secret_fields,
    SETTING_SCHEMAS,
)

router = APIRouter(prefix="/admin/settings", tags=["settings"])

# In-memory store for test job results (would use Redis in production)
_test_jobs: dict[str, dict] = {}


# =============================================================================
# SCHEMAS
# =============================================================================

class SettingsGroupMeta(BaseModel):
    group: str
    label: str
    description: str


class SettingsResponse(BaseModel):
    group: str
    schema_version: int
    data: dict
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    data: dict


class TestActionResponse(BaseModel):
    job_id: str
    status: str  # pending, running, success, failed
    result: Optional[dict] = None
    error: Optional[str] = None


class AuditLogEntry(BaseModel):
    id: int
    group_name: str
    action: str
    old_value_redacted: Optional[str]
    new_value_redacted: Optional[str]
    user_email: str
    ip_address: Optional[str]
    created_at: datetime


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """Get settings service with cache."""
    # TODO: Inject Redis client from app state for proper caching
    cache = SettingsCache(redis_client=None)
    return SettingsService(db=db, cache=cache)


async def get_current_user(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    if principal.type != "user":
        raise HTTPException(403, "User authentication required")

    user = db.query(User).filter(User.id == principal.id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=list[SettingsGroupMeta])
async def list_settings_groups(
    _: None = Depends(Require("settings:read")),
):
    """
    List all available settings groups.

    Returns metadata about each group (name, label, description).
    """
    return get_all_groups()


@router.get("/{group}", response_model=SettingsResponse)
async def get_settings(
    group: str,
    service: SettingsService = Depends(get_settings_service),
    _: None = Depends(Require("settings:read")),
):
    """
    Get settings for a group.

    Secret fields are masked as ***REDACTED***.
    """
    if group not in SETTING_SCHEMAS:
        raise HTTPException(404, f"Unknown settings group: {group}")

    try:
        data = await service.get_masked(group)
        return SettingsResponse(
            group=group,
            schema_version=max(SETTING_SCHEMAS[group].keys()),
            data=data,
        )
    except SettingsServiceError as e:
        raise HTTPException(500, str(e))


@router.get("/{group}/schema")
async def get_settings_schema(
    group: str,
    _: None = Depends(Require("settings:read")),
):
    """
    Get the JSON schema for a settings group.

    Useful for building dynamic forms.
    """
    if group not in SETTING_SCHEMAS:
        raise HTTPException(404, f"Unknown settings group: {group}")

    schema = get_schema(group)
    secret_fields = list(get_secret_fields(group))

    return {
        "group": group,
        "schema": schema,
        "secret_fields": secret_fields,
    }


@router.put("/{group}", response_model=SettingsResponse)
async def update_settings(
    group: str,
    payload: SettingsUpdateRequest,
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    user: User = Depends(get_current_user),
    _: None = Depends(Require("settings:write")),
):
    """
    Update settings for a group.

    Validates against schema, encrypts secrets, and creates audit log.
    """
    if group not in SETTING_SCHEMAS:
        raise HTTPException(404, f"Unknown settings group: {group}")

    # Check write_secrets permission if payload contains secrets
    if service.has_secrets(group, payload.data):
        principal = await get_current_principal(request)
        if not principal.has_scope("settings:write_secrets"):
            raise HTTPException(403, "settings:write_secrets permission required to update secret fields")

    try:
        # Merge with existing data (preserve secrets if ***REDACTED***)
        existing = await service.get(group)
        merged = dict(existing)

        for key, value in payload.data.items():
            # Don't overwrite secrets with the redacted placeholder
            if value == "***REDACTED***":
                continue
            merged[key] = value

        data = await service.update(group, merged, user, request)
        return SettingsResponse(
            group=group,
            schema_version=max(SETTING_SCHEMAS[group].keys()),
            data=service._mask_secrets(group, data),
        )
    except SettingsValidationError as e:
        raise HTTPException(400, str(e))
    except SettingsServiceError as e:
        raise HTTPException(500, str(e))


@router.post("/{group}/test", response_model=TestActionResponse)
async def test_settings(
    group: str,
    payload: SettingsUpdateRequest,
    background_tasks: BackgroundTasks,
    service: SettingsService = Depends(get_settings_service),
    _: None = Depends(Require("settings:test")),
):
    """
    Run a test action for a settings group.

    Tests the configuration without saving it (e.g., send test email, verify API keys).
    Returns a job ID for polling the result.
    """
    if group not in SETTING_SCHEMAS:
        raise HTTPException(404, f"Unknown settings group: {group}")

    if group not in TEST_HANDLERS:
        raise HTTPException(400, f"No test action available for group: {group}")

    job_id = str(uuid.uuid4())
    _test_jobs[job_id] = {"status": "pending", "started_at": datetime.utcnow().isoformat()}

    background_tasks.add_task(run_test_action, job_id, group, payload.data)

    return TestActionResponse(job_id=job_id, status="pending")


@router.get("/test/{job_id}", response_model=TestActionResponse)
async def get_test_status(
    job_id: str,
    _: None = Depends(Require("settings:test")),
):
    """
    Get the status of a test action.

    Poll this endpoint until status is 'success' or 'failed'.
    """
    if job_id not in _test_jobs:
        raise HTTPException(404, "Test job not found or expired")

    job = _test_jobs[job_id]
    return TestActionResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )


@router.get("/audit", response_model=list[AuditLogEntry])
async def get_audit_log(
    group: Optional[str] = Query(None, description="Filter by group"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: SettingsService = Depends(get_settings_service),
    _: None = Depends(Require("settings:audit_view")),
):
    """
    Get settings audit log.

    Returns a paginated list of all settings changes.
    """
    entries = await service.get_audit_log(group=group, skip=skip, limit=limit)

    return [
        AuditLogEntry(
            id=entry.id,
            group_name=entry.group_name,
            action=entry.action,
            old_value_redacted=entry.old_value_redacted,
            new_value_redacted=entry.new_value_redacted,
            user_email=entry.user_email,
            ip_address=entry.ip_address,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


# =============================================================================
# TEST ACTION HANDLERS
# =============================================================================

TEST_TIMEOUT = 30  # seconds


async def run_test_action(job_id: str, group: str, settings: dict):
    """Execute a test action in the background."""
    _test_jobs[job_id]["status"] = "running"

    try:
        async with asyncio.timeout(TEST_TIMEOUT):
            result = await TEST_HANDLERS[group](settings)
        _test_jobs[job_id]["status"] = "success"
        _test_jobs[job_id]["result"] = result
    except asyncio.TimeoutError:
        _test_jobs[job_id]["status"] = "failed"
        _test_jobs[job_id]["error"] = f"Test timed out after {TEST_TIMEOUT} seconds"
    except Exception as e:
        _test_jobs[job_id]["status"] = "failed"
        _test_jobs[job_id]["error"] = str(e)


async def test_email_settings(settings: dict) -> dict:
    """Test email configuration by sending a test email or verifying SMTP connection."""
    import aiosmtplib

    provider = settings.get("provider", "smtp")

    if provider == "smtp":
        host = settings.get("smtp_host")
        port = settings.get("smtp_port", 587)
        user = settings.get("smtp_user")
        password = settings.get("smtp_password")

        if not all([host, user, password]):
            raise ValueError("SMTP host, user, and password are required")

        try:
            smtp = aiosmtplib.SMTP(hostname=host, port=port, timeout=10)
            await smtp.connect()
            if settings.get("smtp_use_tls", True):
                await smtp.starttls()
            await smtp.login(user, password)
            await smtp.quit()
            return {"message": "SMTP connection successful", "provider": "smtp", "host": host}
        except Exception as e:
            raise ValueError(f"SMTP connection failed: {e}")

    elif provider == "sendgrid":
        import httpx
        api_key = settings.get("sendgrid_api_key")
        if not api_key:
            raise ValueError("SendGrid API key is required")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                return {"message": "SendGrid API key valid", "provider": "sendgrid"}
            else:
                raise ValueError(f"SendGrid API error: {response.status_code}")

    else:
        raise ValueError(f"Test not implemented for provider: {provider}")


async def test_payment_settings(settings: dict) -> dict:
    """Test payment gateway configuration by verifying API keys."""
    import httpx

    provider = settings.get("provider", "paystack")

    if provider == "paystack":
        secret_key = settings.get("paystack_secret_key")
        if not secret_key:
            raise ValueError("Paystack secret key is required")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.paystack.co/balance",
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                return {"message": "Paystack credentials valid", "provider": "paystack"}
            else:
                raise ValueError(f"Paystack API error: {response.status_code} - {response.text}")

    elif provider == "flutterwave":
        secret_key = settings.get("flutterwave_secret_key")
        if not secret_key:
            raise ValueError("Flutterwave secret key is required")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.flutterwave.com/v3/balances",
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                return {"message": "Flutterwave credentials valid", "provider": "flutterwave"}
            else:
                raise ValueError(f"Flutterwave API error: {response.status_code}")

    else:
        raise ValueError(f"Test not implemented for provider: {provider}")


async def test_sms_settings(settings: dict) -> dict:
    """Test SMS provider configuration."""
    import httpx

    provider = settings.get("provider", "termii")

    if provider == "termii":
        api_key = settings.get("termii_api_key")
        if not api_key:
            raise ValueError("Termii API key is required")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.ng.termii.com/api/get-balance",
                params={"api_key": api_key},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "message": "Termii API key valid",
                    "provider": "termii",
                    "balance": data.get("balance"),
                }
            else:
                raise ValueError(f"Termii API error: {response.status_code}")

    else:
        raise ValueError(f"Test not implemented for provider: {provider}")


async def test_webhook_settings(settings: dict) -> dict:
    """Test webhook configuration (just validates the settings)."""
    # Webhook settings don't have external dependencies to test
    # Just validate the configuration
    if settings.get("enabled", True):
        retry_attempts = settings.get("retry_attempts", 3)
        retry_delay = settings.get("retry_delay_seconds", 60)

        if retry_attempts < 0 or retry_attempts > 10:
            raise ValueError("retry_attempts must be between 0 and 10")
        if retry_delay < 1 or retry_delay > 3600:
            raise ValueError("retry_delay_seconds must be between 1 and 3600")

    return {"message": "Webhook configuration valid", "enabled": settings.get("enabled", True)}


# Register test handlers
TEST_HANDLERS = {
    "email": test_email_settings,
    "payments": test_payment_settings,
    "sms": test_sms_settings,
    "webhooks": test_webhook_settings,
}

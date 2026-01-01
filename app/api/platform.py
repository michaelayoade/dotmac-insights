"""Platform Integration Status API

Endpoints for UI to display:
- License status (valid, grace period, expired)
- Feature flags (current values and source)
- Platform connectivity health
- System configuration overview
"""
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import Require
from app.config import settings
from app.feature_flags import feature_flags, FeatureFlags
from app.services.platform_integration import (
    get_license_status,
    get_feature_flags_status,
    LicenseStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/platform", tags=["platform"])


# ============================================================================
# Response Schemas
# ============================================================================


class LicenseStatusResponse(BaseModel):
    """License validation status for UI display."""
    configured: bool
    status: str  # valid, grace_period, expired, invalid
    last_checked: Optional[str]
    last_successful: Optional[str]
    grace_started_at: Optional[str]
    in_grace_period: bool
    grace_period_hours: int
    message: str
    entitlements: Optional[dict] = None


class FeatureFlagItem(BaseModel):
    """Individual feature flag status."""
    name: str
    enabled: bool
    description: str
    category: str


class FeatureFlagsResponse(BaseModel):
    """Feature flags status for UI display."""
    flags: List[FeatureFlagItem]
    source: str  # platform, cached, env, defaults
    last_refresh: Optional[str]
    platform_precedence: bool


class PlatformHealthResponse(BaseModel):
    """Platform integration health summary."""
    platform_configured: bool
    platform_url: Optional[str]
    instance_id: Optional[str]
    tenant_id: Optional[str]
    license: LicenseStatusResponse
    feature_flags: FeatureFlagsResponse
    otel_enabled: bool
    environment: str


class SystemConfigResponse(BaseModel):
    """Non-sensitive system configuration for admin UI."""
    environment: str
    version: str
    platform_configured: bool
    otel_enabled: bool
    otel_sample_rate: float
    license_grace_period_hours: int
    feature_flags_refresh_seconds: int
    heartbeat_interval_seconds: int
    cors_origins: List[str]


# ============================================================================
# Feature Flag Descriptions (for UI)
# ============================================================================

FLAG_DESCRIPTIONS = {
    # Contacts flags
    "CONTACTS_DUAL_WRITE_ENABLED": {
        "description": "Sync unified contacts to legacy customers table",
        "category": "contacts",
    },
    "CONTACTS_OUTBOUND_SYNC_ENABLED": {
        "description": "Push contact changes to external systems (Splynx, ERPNext)",
        "category": "contacts",
    },
    "CONTACTS_OUTBOUND_DRY_RUN": {
        "description": "Log outbound sync operations without making actual API calls",
        "category": "contacts",
    },
    "CONTACTS_RECONCILIATION_ENABLED": {
        "description": "Run periodic reconciliation to detect drift between systems",
        "category": "contacts",
    },
    # Tickets flags
    "TICKETS_DUAL_WRITE_ENABLED": {
        "description": "Sync unified tickets to legacy tickets/conversations tables",
        "category": "tickets",
    },
    "TICKETS_OUTBOUND_SYNC_ENABLED": {
        "description": "Push ticket changes to external systems (Splynx, ERPNext, Chatwoot)",
        "category": "tickets",
    },
    "TICKETS_OUTBOUND_DRY_RUN": {
        "description": "Log ticket outbound sync without making actual API calls",
        "category": "tickets",
    },
    "TICKETS_RECONCILIATION_ENABLED": {
        "description": "Run periodic reconciliation to detect ticket drift between systems",
        "category": "tickets",
    },
    # Data management flags
    "SOFT_DELETE_ENABLED": {
        "description": "Use soft delete instead of hard delete for entities with dependencies",
        "category": "data",
    },
}


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/status",
    response_model=PlatformHealthResponse,
    dependencies=[Depends(Require("admin:read"))],
)
async def get_platform_status():
    """
    Get comprehensive platform integration status.

    Returns license status, feature flags, and connectivity health
    for display in admin dashboard.
    """
    platform_configured = bool(settings.platform_api_url and settings.platform_instance_id)

    # License status
    license_info = get_license_status() if platform_configured else {
        "status": LicenseStatus.VALID,
        "last_checked": None,
        "last_successful": None,
        "grace_started_at": None,
        "in_grace_period": False,
    }

    license_message = _get_license_message(license_info["status"], license_info.get("in_grace_period", False))

    license_response = LicenseStatusResponse(
        configured=platform_configured,
        status=license_info["status"],
        last_checked=license_info.get("last_checked"),
        last_successful=license_info.get("last_successful"),
        grace_started_at=license_info.get("grace_started_at"),
        in_grace_period=license_info.get("in_grace_period", False),
        grace_period_hours=settings.license_grace_period_hours,
        message=license_message,
    )

    # Feature flags status
    ff_status = get_feature_flags_status() if platform_configured else {
        "last_refresh": None,
        "cached_count": 0,
        "last_error": None,
        "platform_precedence": settings.feature_flags_platform_precedence,
    }

    flags_list = _get_feature_flags_list()
    source = "platform" if ff_status.get("cached_count", 0) > 0 else "env"
    if ff_status.get("last_error"):
        source = "cached" if ff_status.get("cached_count", 0) > 0 else "defaults"

    ff_response = FeatureFlagsResponse(
        flags=flags_list,
        source=source,
        last_refresh=ff_status.get("last_refresh"),
        platform_precedence=ff_status.get("platform_precedence", True),
    )

    return PlatformHealthResponse(
        platform_configured=platform_configured,
        platform_url=settings.platform_api_url if platform_configured else None,
        instance_id=settings.platform_instance_id,
        tenant_id=settings.platform_tenant_id,
        license=license_response,
        feature_flags=ff_response,
        otel_enabled=settings.otel_enabled,
        environment=settings.environment,
    )


@router.get(
    "/license",
    response_model=LicenseStatusResponse,
    dependencies=[Depends(Require("admin:read"))],
)
async def get_license():
    """Get current license validation status."""
    platform_configured = bool(settings.platform_api_url and settings.platform_instance_id)

    if not platform_configured:
        return LicenseStatusResponse(
            configured=False,
            status=LicenseStatus.VALID,
            last_checked=None,
            last_successful=None,
            grace_started_at=None,
            in_grace_period=False,
            grace_period_hours=settings.license_grace_period_hours,
            message="Platform not configured - running in standalone mode",
        )

    license_info = get_license_status()
    message = _get_license_message(license_info["status"], license_info.get("in_grace_period", False))

    return LicenseStatusResponse(
        configured=True,
        status=license_info["status"],
        last_checked=license_info.get("last_checked"),
        last_successful=license_info.get("last_successful"),
        grace_started_at=license_info.get("grace_started_at"),
        in_grace_period=license_info.get("in_grace_period", False),
        grace_period_hours=settings.license_grace_period_hours,
        message=message,
        entitlements=license_info.get("entitlements"),
    )


@router.get(
    "/feature-flags",
    response_model=FeatureFlagsResponse,
    dependencies=[Depends(Require("admin:read"))],
)
async def get_feature_flags():
    """Get current feature flags and their sources."""
    platform_configured = bool(settings.platform_api_url)

    ff_status = get_feature_flags_status() if platform_configured else {
        "last_refresh": None,
        "cached_count": 0,
        "last_error": None,
        "platform_precedence": settings.feature_flags_platform_precedence,
    }

    flags_list = _get_feature_flags_list()

    # Determine source
    source = "defaults"
    if platform_configured:
        if ff_status.get("cached_count", 0) > 0:
            source = "cached" if ff_status.get("last_error") else "platform"
    else:
        source = "env"

    return FeatureFlagsResponse(
        flags=flags_list,
        source=source,
        last_refresh=ff_status.get("last_refresh"),
        platform_precedence=ff_status.get("platform_precedence", True),
    )


@router.get(
    "/config",
    response_model=SystemConfigResponse,
    dependencies=[Depends(Require("admin:read"))],
)
async def get_system_config():
    """Get non-sensitive system configuration for admin display."""
    return SystemConfigResponse(
        environment=settings.environment,
        version="1.0.0",
        platform_configured=bool(settings.platform_api_url and settings.platform_instance_id),
        otel_enabled=settings.otel_enabled,
        otel_sample_rate=settings.otel_trace_sample_rate,
        license_grace_period_hours=settings.license_grace_period_hours,
        feature_flags_refresh_seconds=settings.feature_flags_refresh_interval_seconds,
        heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        cors_origins=settings.cors_origins_list,
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _get_license_message(status: str, in_grace: bool) -> str:
    """Generate human-readable license status message."""
    if status == LicenseStatus.VALID:
        return "License is valid"
    elif status == LicenseStatus.GRACE_PERIOD:
        return f"License validation pending - operating in grace period ({settings.license_grace_period_hours}h)"
    elif status == LicenseStatus.EXPIRED:
        return "License grace period has expired - some features may be restricted"
    elif status == LicenseStatus.INVALID:
        return "License is invalid - please contact support"
    return "Unknown license status"


def _get_feature_flags_list() -> List[FeatureFlagItem]:
    """Get list of all feature flags with current values."""
    flags = []

    # Get all flag attributes from the FeatureFlags class
    for attr_name in dir(feature_flags):
        if attr_name.isupper() and not attr_name.startswith("_"):
            value = getattr(feature_flags, attr_name, None)
            if isinstance(value, bool):
                info = FLAG_DESCRIPTIONS.get(attr_name, {
                    "description": f"Feature flag: {attr_name}",
                    "category": "other",
                })
                flags.append(FeatureFlagItem(
                    name=attr_name,
                    enabled=value,
                    description=info["description"],
                    category=info["category"],
                ))

    return sorted(flags, key=lambda f: (f.category, f.name))

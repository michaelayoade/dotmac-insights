"""
Platform Integration Service

Provides async functions for platform communication:
- License validation with caching and grace period
- Feature flag refresh from platform
- Usage reporting with batching
- Heartbeat/health reporting

Uses async PlatformClient with correct platform API endpoints:
- POST /api/licensing/validate for license validation
- GET /api/v1/tenants/current for tenant features
- POST /api/v1/tenants/{tenant_id}/usage for usage reporting
- POST /api/v1/deployment/instances/{id}/health-check for heartbeat
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, List
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.feature_flags import feature_flags
from app.models.unified_contact import UnifiedContact
from app.models.invoice import Invoice
from app.middleware.metrics import CONTACTS_DUAL_WRITE_FAILURES

logger = logging.getLogger(__name__)


# =============================================================================
# LICENSE CACHE (Sync-compatible wrapper)
# =============================================================================


class LicenseCache:
    """In-memory cache for license validation with grace period tracking."""

    def __init__(self) -> None:
        self.valid_until: float = 0
        self.last_checked: float = 0
        self.last_result: bool = True
        self.last_successful_validation: float = 0  # Track last known-good
        self.grace_started_at: Optional[float] = None  # When grace period began
        self.entitlements: Optional[dict] = None  # Raw entitlements from platform
        self.license_info: Optional[dict] = None  # Full license data

    def is_valid(self) -> bool:
        now = time.time()
        return self.last_result and now < self.valid_until

    def is_in_grace_period(self, grace_seconds: int) -> bool:
        """Check if currently in grace period (platform unreachable)."""
        if not self.grace_started_at:
            return False
        return (time.time() - self.grace_started_at) < grace_seconds

    def grace_period_expired(self, grace_seconds: int) -> bool:
        """Check if grace period has fully expired."""
        if not self.grace_started_at:
            return False
        return (time.time() - self.grace_started_at) >= grace_seconds

    def update(self, valid: bool, ttl_seconds: int, license_info: Optional[dict] = None) -> None:
        self.last_result = valid
        self.last_checked = time.time()
        self.valid_until = self.last_checked + ttl_seconds
        self.license_info = license_info
        if valid:
            self.last_successful_validation = self.last_checked
            self.grace_started_at = None  # Clear grace period on success

    def start_grace_period(self) -> None:
        """Mark the start of grace period when platform becomes unreachable."""
        if self.grace_started_at is None:
            self.grace_started_at = time.time()
            logger.warning("license_grace_period_started started_at=%s", self.grace_started_at)


license_cache = LicenseCache()


class LicenseStatus:
    """License validation result with detailed status."""
    VALID = "valid"
    GRACE_PERIOD = "grace_period"  # Platform unreachable but within grace
    EXPIRED = "expired"  # Grace period exhausted
    INVALID = "invalid"  # Platform explicitly rejected


# =============================================================================
# ASYNC PLATFORM CLIENT
# =============================================================================

from app.services.platform_client import (
    get_platform_client,
    PlatformClientError,
    PlatformConnectionError,
)


# =============================================================================
# LICENSE VALIDATION
# =============================================================================


async def validate_license_async() -> bool:
    """Validate license via platform; respects fail-open and grace period.

    Behavior:
    - No platform configured: Always valid (standalone mode)
    - Platform reachable + valid: Valid, cache refreshed
    - Platform reachable + invalid: Invalid immediately (no grace)
    - Platform unreachable + within grace: Valid (degraded mode)
    - Platform unreachable + grace expired: Invalid (block operations)
    """
    # No platform configured -> assume valid (standalone mode)
    if not settings.platform_api_url or not settings.platform_instance_id:
        return True

    # Use cache if still valid
    if license_cache.is_valid():
        return True

    ttl = settings.license_cache_ttl_seconds
    grace_seconds = settings.license_grace_period_hours * 3600

    try:
        client = get_platform_client()
        license_info = await client.validate_license()

        # Update cache with validation result
        license_data = {
            "id": license_info.license_id,
            "license_key": license_info.license_key,
            "status": license_info.status.value,
            "type": license_info.license_type.value,
            "features": license_info.features,
            "limits": license_info.limits,
            "max_users": license_info.max_users,
            "expires_at": license_info.expires_at.isoformat() if license_info.expires_at else None,
        }
        if license_info.is_valid:
            entitlements = license_info.features
            license_cache.entitlements = entitlements
            license_cache.update(True, ttl, license_data)
            _apply_entitlements(entitlements, disable_missing=False)

            logger.info(
                "license_validated_async status=%s license_id=%s",
                license_info.status.value,
                license_info.license_id,
            )
            return True

        license_cache.entitlements = {}
        license_cache.update(False, ttl, license_data)
        _apply_entitlements({}, disable_missing=True)
        logger.error(
            "license_invalid_async status=%s license_id=%s",
            license_info.status.value,
            license_info.license_id,
        )
        return False

    except PlatformConnectionError:
        # Platform unreachable - apply fail-open with grace period
        if settings.license_fail_open_on_startup:
            license_cache.start_grace_period()

            if license_cache.is_in_grace_period(grace_seconds):
                remaining = grace_seconds - (time.time() - (license_cache.grace_started_at or 0))
                logger.warning(
                    "license_validation_fail_open_async reason=%s status=%s grace_remaining_hours=%s",
                    "platform_unreachable",
                    LicenseStatus.GRACE_PERIOD,
                    round(remaining / 3600, 1),
                )
                license_cache.update(True, ttl)
                return True
            else:
                logger.error(
                    "license_grace_period_expired_async status=%s grace_started_at=%s",
                    LicenseStatus.EXPIRED,
                    license_cache.grace_started_at,
                )
                license_cache.update(False, ttl)
                license_cache.entitlements = {}
                _apply_entitlements({}, disable_missing=True)
                return False

        logger.error("license_validation_failed_async reason=connection_error status=%s", LicenseStatus.INVALID)
        license_cache.update(False, ttl)
        license_cache.entitlements = {}
        _apply_entitlements({}, disable_missing=True)
        return False

    except PlatformClientError as e:
        # Platform reachable but validation failed
        logger.error("license_explicitly_invalid_async error=%s status=%s", str(e), LicenseStatus.INVALID)
        license_cache.update(False, ttl)
        license_cache.entitlements = {}
        _apply_entitlements({}, disable_missing=True)
        return False


def get_license_status() -> dict:
    """Get detailed license status for health checks / admin endpoints."""
    grace_seconds = settings.license_grace_period_hours * 3600

    status = LicenseStatus.VALID
    if license_cache.grace_started_at:
        if license_cache.is_in_grace_period(grace_seconds):
            status = LicenseStatus.GRACE_PERIOD
        else:
            status = LicenseStatus.EXPIRED
    elif not license_cache.last_result:
        status = LicenseStatus.INVALID

    license_info = license_cache.license_info or {}

    return {
        "status": status,
        "last_checked": datetime.fromtimestamp(license_cache.last_checked).isoformat() if license_cache.last_checked else None,
        "last_successful": datetime.fromtimestamp(license_cache.last_successful_validation).isoformat() if license_cache.last_successful_validation else None,
        "grace_started_at": datetime.fromtimestamp(license_cache.grace_started_at).isoformat() if license_cache.grace_started_at else None,
        "in_grace_period": license_cache.is_in_grace_period(grace_seconds),
        "entitlements": getattr(license_cache, "entitlements", None),
        "license_id": license_info.get("id"),
        "license_type": license_info.get("type"),
        "expires_at": license_info.get("expires_at"),
        "max_users": license_info.get("max_users"),
    }


# =============================================================================
# FEATURE FLAGS
# =============================================================================


class FeatureFlagsCache:
    """Cache for feature flags with last-known-good fallback."""

    def __init__(self) -> None:
        self.last_known_good: dict = {}
        self.last_refresh: float = 0
        self.last_error: Optional[str] = None
        self.tenant_features: dict = {}
        self.tenant_limits: dict = {}

    def update_from_platform(self, data: dict) -> None:
        """Update cache with platform data (last-known-good)."""
        self.last_known_good = data.copy()
        self.last_refresh = time.time()
        self.last_error = None

    def update_from_tenant(self, features: dict, limits: dict) -> None:
        """Update cache with tenant data."""
        self.tenant_features = features.copy()
        self.tenant_limits = limits.copy()
        self.last_known_good = features.copy()  # Store as fallback
        self.last_refresh = time.time()
        self.last_error = None

    def get_fallback(self) -> dict:
        """Return last-known-good values for fallback."""
        return self.last_known_good


_feature_flags_cache = FeatureFlagsCache()


async def refresh_feature_flags_from_platform_async() -> None:
    """Fetch feature entitlements from platform and apply overrides.

    Uses GET /api/v1/tenants/current for tenant-specific features.
    Falls back to cached values if platform is unreachable.
    """
    if not settings.platform_api_url:
        return

    try:
        client = get_platform_client()
        tenant_info = await client.get_current_tenant()

        features = tenant_info.features
        limits = tenant_info.limits

        # Update cache
        _feature_flags_cache.update_from_tenant(features, limits)
        _feature_flags_cache.update_from_platform(features)

        if settings.feature_flags_platform_precedence:
            _apply_feature_flags(features, source="tenant_async")
            logger.info(
                "feature_flags_from_tenant_async tenant_id=%s features=%s",
                tenant_info.tenant_id,
                list(features.keys()),
            )

    except PlatformClientError as e:
        # Platform unreachable - use last-known-good if available
        _feature_flags_cache.last_error = f"platform_error: {str(e)}"
        cached = _feature_flags_cache.get_fallback()
        if cached and settings.feature_flags_platform_precedence:
            logger.warning(
                "feature_flags_using_cached_async cached_count=%s last_refresh=%s error=%s",
                len(cached),
                _feature_flags_cache.last_refresh,
                str(e),
            )
            _apply_feature_flags(cached, source="cached")


def _apply_feature_flags(data: dict, source: str) -> None:
    """Apply feature flag values to the singleton."""
    applied = []
    for key, value in data.items():
        if hasattr(feature_flags, key):
            try:
                setattr(feature_flags, key, bool(value))
                applied.append(key)
            except Exception:
                pass
    if applied:
        logger.info("feature_flags_applied source=%s flags=%s", source, applied)


def _apply_entitlements(entitlements: dict, disable_missing: bool) -> None:
    """
    Apply license entitlements to feature flags.

    If disable_missing is True, any known feature flag not present in entitlements
    will be set to False (hard gate). If False, only provided entitlements override.
    """
    if entitlements is None:
        entitlements = {}

    # Entitlements may be nested under "feature_flags" or at the top level
    flags_data = entitlements.get("feature_flags") if isinstance(entitlements, dict) else None
    if not flags_data and isinstance(entitlements, dict):
        flags_data = entitlements

    if not isinstance(flags_data, dict):
        flags_data = {}

    known_flags = [
        attr for attr in dir(feature_flags)
        if attr.isupper() and not attr.startswith("_") and isinstance(getattr(feature_flags, attr), bool)
    ]

    # Apply provided entitlements
    _apply_feature_flags(flags_data, source="entitlements")

    if disable_missing:
        # Hard gate: disable any known flags not explicitly allowed
        for flag in known_flags:
            if flag not in flags_data:
                try:
                    setattr(feature_flags, flag, False)
                except Exception:
                    pass


def get_feature_flags_status() -> dict:
    """Get feature flags status for health/admin endpoints."""
    return {
        "last_refresh": datetime.fromtimestamp(_feature_flags_cache.last_refresh).isoformat() if _feature_flags_cache.last_refresh else None,
        "cached_count": len(_feature_flags_cache.last_known_good),
        "tenant_features_count": len(_feature_flags_cache.tenant_features),
        "tenant_limits": _feature_flags_cache.tenant_limits,
        "last_error": _feature_flags_cache.last_error,
        "platform_precedence": settings.feature_flags_platform_precedence,
    }


def has_feature(feature: str) -> bool:
    """Check if a feature is enabled (sync check from cache)."""
    # Check tenant features first
    if feature in _feature_flags_cache.tenant_features:
        return bool(_feature_flags_cache.tenant_features[feature])
    # Check license entitlements
    if license_cache.entitlements and feature in license_cache.entitlements:
        return bool(license_cache.entitlements[feature])
    # Check local feature flags
    if hasattr(feature_flags, feature):
        return bool(getattr(feature_flags, feature))
    return False


def get_limit(limit_name: str, default: int = 0) -> int:
    """Get a limit value from cached tenant data."""
    value = _feature_flags_cache.tenant_limits.get(limit_name, default)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


# =============================================================================
# USAGE REPORTING
# =============================================================================


async def report_usage_async(db: Session) -> None:
    """Send usage metrics to platform.

    Uses POST /api/v1/tenants/{tenant_id}/usage.
    """
    if not settings.platform_api_url or not settings.platform_instance_id:
        return

    if not settings.platform_tenant_id:
        logger.warning("usage_report_skipped_async reason=no_tenant_id")
        return

    active_contacts = db.execute(select(func.count(UnifiedContact.id))).scalar() or 0
    invoices_count = db.execute(select(func.count(Invoice.id))).scalar() or 0
    dual_write_failures = 0
    try:
        dual_write_failures = int(CONTACTS_DUAL_WRITE_FAILURES.get())
    except Exception:
        dual_write_failures = 0

    try:
        client = get_platform_client()

        # Report each metric
        await client.report_usage(
            metric="active_contacts",
            value=active_contacts,
            metadata={"instance_id": settings.platform_instance_id},
        )
        await client.report_usage(
            metric="invoices",
            value=invoices_count,
            metadata={"instance_id": settings.platform_instance_id},
        )
        await client.report_usage(
            metric="dual_write_failures",
            value=dual_write_failures,
            metadata={"instance_id": settings.platform_instance_id},
        )

        # Flush the usage buffer
        await client.flush_usage_if_needed()

        logger.debug("usage_reported_async metrics_count=3")

    except PlatformClientError as e:
        logger.warning("usage_report_failed_async error=%s", str(e))


# =============================================================================
# HEARTBEAT
# =============================================================================


async def send_heartbeat_async(db: Session) -> None:
    """Send heartbeat/health snapshot to platform.

    Uses POST /api/v1/deployment/instances/{instance_id}/health-check.
    """
    if not settings.platform_api_url or not settings.platform_instance_id:
        return

    # Simple DB check
    db_ok = True
    try:
        db.execute(select(func.count(UnifiedContact.id)).limit(1))
    except Exception:
        db_ok = False

    try:
        client = get_platform_client()
        result = await client.send_heartbeat(
            status="healthy" if db_ok else "degraded",
            components={"database": "ok" if db_ok else "error"},
        )

        if result.get("status") != "error":
            logger.debug("heartbeat_sent_async status=%s", "healthy" if db_ok else "degraded")
        else:
            logger.warning("heartbeat_failed_async error=%s", result.get("error"))

    except PlatformClientError as e:
        logger.warning("heartbeat_failed_async error=%s", str(e))

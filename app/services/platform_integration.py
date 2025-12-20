"""
Platform Integration Service

Provides:
- License validation with caching and grace period
- Feature flag refresh from platform
- Usage reporting
- Heartbeat/health reporting
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.client import platform_client
from app.feature_flags import feature_flags
from app.models.unified_contact import UnifiedContact
from app.models.invoice import Invoice
from app.middleware.metrics import CONTACTS_DUAL_WRITE_FAILURES

logger = logging.getLogger(__name__)


class LicenseCache:
    """In-memory cache for license validation with grace period tracking."""

    def __init__(self):
        self.valid_until: float = 0
        self.last_checked: float = 0
        self.last_result: bool = True
        self.last_successful_validation: float = 0  # Track last known-good
        self.grace_started_at: Optional[float] = None  # When grace period began
        self.entitlements: Optional[dict] = None  # Raw entitlements from platform

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

    def update(self, valid: bool, ttl_seconds: int) -> None:
        self.last_result = valid
        self.last_checked = time.time()
        self.valid_until = self.last_checked + ttl_seconds
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


def validate_license() -> bool:
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

    data = platform_client.get_json("/api/licenses/validate")

    # Platform reachable and returned valid response
    if data and isinstance(data, dict) and data.get("valid") is True:
        entitlements = data.get("entitlements") or {}
        license_cache.entitlements = entitlements
        license_cache.update(True, ttl)
        _apply_entitlements(entitlements, disable_missing=False)
        return True

    # Platform reachable but explicitly invalid
    if data and isinstance(data, dict) and data.get("valid") is False:
        logger.error("license_explicitly_invalid data=%s status=%s", data, LicenseStatus.INVALID)
        license_cache.update(False, ttl)
        license_cache.entitlements = {}
        _apply_entitlements({}, disable_missing=True)
        return False

    # Platform unreachable (data is None or malformed)
    # Apply fail-open with grace period
    if settings.license_fail_open_on_startup:
        license_cache.start_grace_period()

        if license_cache.is_in_grace_period(grace_seconds):
            remaining = grace_seconds - (time.time() - (license_cache.grace_started_at or 0))
            logger.warning(
                "license_validation_fail_open reason=%s status=%s grace_remaining_hours=%s",
                "platform_unreachable",
                LicenseStatus.GRACE_PERIOD,
                round(remaining / 3600, 1),
            )
            license_cache.update(True, ttl)  # Allow operation during grace
            return True
        else:
            # Grace period exhausted
            logger.error(
                "license_grace_period_expired status=%s grace_started_at=%s",
                LicenseStatus.EXPIRED,
                license_cache.grace_started_at,
            )
            license_cache.update(False, ttl)
            license_cache.entitlements = {}
            _apply_entitlements({}, disable_missing=True)
            return False

    # No fail-open configured
    logger.error("license_validation_failed data=%s status=%s", data, LicenseStatus.INVALID)
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

    return {
        "status": status,
        "last_checked": datetime.fromtimestamp(license_cache.last_checked).isoformat() if license_cache.last_checked else None,
        "last_successful": datetime.fromtimestamp(license_cache.last_successful_validation).isoformat() if license_cache.last_successful_validation else None,
        "grace_started_at": datetime.fromtimestamp(license_cache.grace_started_at).isoformat() if license_cache.grace_started_at else None,
        "in_grace_period": license_cache.is_in_grace_period(grace_seconds),
        "entitlements": getattr(license_cache, "entitlements", None),
    }


class FeatureFlagsCache:
    """Cache for feature flags with last-known-good fallback."""

    def __init__(self):
        self.last_known_good: dict = {}
        self.last_refresh: float = 0
        self.last_error: Optional[str] = None

    def update_from_platform(self, data: dict) -> None:
        """Update cache with platform data (last-known-good)."""
        self.last_known_good = data.copy()
        self.last_refresh = time.time()
        self.last_error = None

    def get_fallback(self) -> dict:
        """Return last-known-good values for fallback."""
        return self.last_known_good


_feature_flags_cache = FeatureFlagsCache()


def refresh_feature_flags_from_platform() -> None:
    """Fetch feature entitlements from platform and apply overrides.

    Fallback chain (in order of precedence):
    1. Platform entitlements (if reachable and platform_precedence=True)
    2. Last-known-good cached values (if platform unreachable)
    3. Environment variable defaults (FF_* prefix)
    4. Code defaults in FeatureFlags class
    """
    if not settings.platform_api_url:
        return

    data = platform_client.get_json("/api/features/entitlements")

    if data and isinstance(data, dict):
        # Platform reachable - update cache and apply
        _feature_flags_cache.update_from_platform(data)

        if settings.feature_flags_platform_precedence:
            _apply_feature_flags(data, source="platform")
    else:
        # Platform unreachable - use last-known-good if available
        _feature_flags_cache.last_error = "platform_unreachable"
        cached = _feature_flags_cache.get_fallback()
        if cached and settings.feature_flags_platform_precedence:
            logger.warning(
                "feature_flags_using_cached cached_count=%s last_refresh=%s",
                len(cached),
                _feature_flags_cache.last_refresh,
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
        "last_error": _feature_flags_cache.last_error,
        "platform_precedence": settings.feature_flags_platform_precedence,
    }


def report_usage(db: Session) -> None:
    """Send usage metrics to platform (best effort)."""
    if not settings.platform_api_url or not settings.platform_instance_id:
        return

    active_contacts = db.execute(select(func.count(UnifiedContact.id))).scalar() or 0
    invoices_count = db.execute(select(func.count(Invoice.id))).scalar() or 0
    dual_write_failures = 0
    # Use metric getter if available (stub returns 0 when prometheus is absent)
    try:
        dual_write_failures = int(CONTACTS_DUAL_WRITE_FAILURES.get())
    except Exception:
        dual_write_failures = 0

    payload = {
        "instance_id": settings.platform_instance_id,
        "tenant_id": settings.platform_tenant_id,
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {
            "active_contacts": active_contacts,
            "invoices": invoices_count,
            "dual_write_failures": dual_write_failures,
        },
    }

    platform_client.post_json("/api/usage/report", payload)


def send_heartbeat(db: Session) -> None:
    """Send heartbeat/health snapshot to platform."""
    if not settings.platform_api_url or not settings.platform_instance_id:
        return

    # Simple DB check
    db_ok = True
    try:
        db.execute(select(func.count(UnifiedContact.id)).limit(1))
    except Exception:
        db_ok = False

    payload = {
        "instance_id": settings.platform_instance_id,
        "tenant_id": settings.platform_tenant_id,
        "version": "1.0.0",
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "ok" if db_ok else "error",
        },
    }

    platform_client.post_json("/api/instances/heartbeat", payload)

"""Subscription Settings Service.

Provides typed access to subscription-related settings stored in the
central settings service. All hardcoded values should be replaced
with settings from this service.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.schemas.settings_schemas import get_defaults
from app.services.settings_service import SettingsService, SyncSettingsService

logger = logging.getLogger(__name__)

# Settings group name
SETTINGS_GROUP = "subscriptions"


@dataclass(frozen=True)
class SubscriptionSettings:
    """Typed subscription settings."""

    # Billing Settings
    default_currency: str
    invoice_due_days: int
    daily_billing_invoice_due_days: int
    billing_lookback_days: int
    max_billing_day_of_month: int

    # Bundle Settings
    bundle_expiry_warning_days: List[int]
    bundle_cleanup_retention_days: int
    bundle_default_throttle_speed_kbps: int
    bundle_expiring_soon_threshold_days: int

    # Usage Alert Thresholds
    bundle_alert_threshold_1: int
    bundle_alert_threshold_2: int
    bundle_alert_threshold_3: int

    # RADIUS Settings
    radius_username_max_collision_attempts: int
    radius_subscription_prefix: str

    # Provisioning Settings
    provisioning_retry_attempts: int
    provisioning_retry_delay_seconds: int

    # Lifecycle Settings
    auto_suspend_after_grace_days: int
    auto_cancel_after_suspend_days: int

    # Session Settings
    max_concurrent_sessions: int
    session_timeout_seconds: int
    idle_timeout_seconds: int

    # Notification Settings
    notify_on_bundle_purchase: bool
    notify_on_bundle_exhaustion: bool
    notify_on_bundle_expiry: bool
    notify_on_subscription_status_change: bool

    @classmethod
    def from_dict(cls, data: dict) -> "SubscriptionSettings":
        """Create from dictionary, applying defaults for missing keys."""
        defaults = get_defaults(SETTINGS_GROUP)
        merged = {**defaults, **data}
        return cls(
            default_currency=merged.get("default_currency", "NGN"),
            invoice_due_days=merged.get("invoice_due_days", 7),
            daily_billing_invoice_due_days=merged.get("daily_billing_invoice_due_days", 1),
            billing_lookback_days=merged.get("billing_lookback_days", 1),
            max_billing_day_of_month=merged.get("max_billing_day_of_month", 28),
            bundle_expiry_warning_days=merged.get("bundle_expiry_warning_days", [7, 3, 1]),
            bundle_cleanup_retention_days=merged.get("bundle_cleanup_retention_days", 90),
            bundle_default_throttle_speed_kbps=merged.get("bundle_default_throttle_speed_kbps", 128),
            bundle_expiring_soon_threshold_days=merged.get("bundle_expiring_soon_threshold_days", 7),
            bundle_alert_threshold_1=merged.get("bundle_alert_threshold_1", 50),
            bundle_alert_threshold_2=merged.get("bundle_alert_threshold_2", 80),
            bundle_alert_threshold_3=merged.get("bundle_alert_threshold_3", 95),
            radius_username_max_collision_attempts=merged.get("radius_username_max_collision_attempts", 100),
            radius_subscription_prefix=merged.get("radius_subscription_prefix", "SUB"),
            provisioning_retry_attempts=merged.get("provisioning_retry_attempts", 3),
            provisioning_retry_delay_seconds=merged.get("provisioning_retry_delay_seconds", 30),
            auto_suspend_after_grace_days=merged.get("auto_suspend_after_grace_days", 0),
            auto_cancel_after_suspend_days=merged.get("auto_cancel_after_suspend_days", 30),
            max_concurrent_sessions=merged.get("max_concurrent_sessions", 1),
            session_timeout_seconds=merged.get("session_timeout_seconds", 3600),
            idle_timeout_seconds=merged.get("idle_timeout_seconds", 300),
            notify_on_bundle_purchase=merged.get("notify_on_bundle_purchase", True),
            notify_on_bundle_exhaustion=merged.get("notify_on_bundle_exhaustion", True),
            notify_on_bundle_expiry=merged.get("notify_on_bundle_expiry", True),
            notify_on_subscription_status_change=merged.get("notify_on_subscription_status_change", True),
        )


class SubscriptionSettingsService:
    """Async service for accessing subscription settings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings_service: Optional[SettingsService] = None
        self._cached_settings: Optional[SubscriptionSettings] = None

    async def get_settings(self) -> SubscriptionSettings:
        """Get subscription settings with caching."""
        if self._cached_settings is not None:
            return self._cached_settings

        try:
            # Use sync session wrapper for now
            # In production, would use async SettingsService
            from app.schemas.settings_schemas import get_defaults
            data = get_defaults(SETTINGS_GROUP)
            self._cached_settings = SubscriptionSettings.from_dict(data)
            return self._cached_settings
        except Exception as e:
            logger.warning(
                "Failed to load subscription settings, using defaults: %s",
                str(e)
            )
            return SubscriptionSettings.from_dict({})

    def invalidate_cache(self) -> None:
        """Invalidate cached settings."""
        self._cached_settings = None


class SyncSubscriptionSettingsService:
    """Synchronous service for accessing subscription settings."""

    def __init__(self, db: Session):
        self.db = db
        self._settings_service = SyncSettingsService(db)
        self._cached_settings: Optional[SubscriptionSettings] = None

    def get_settings(self) -> SubscriptionSettings:
        """Get subscription settings with caching."""
        if self._cached_settings is not None:
            return self._cached_settings

        try:
            data = self._settings_service.get(SETTINGS_GROUP)
            self._cached_settings = SubscriptionSettings.from_dict(data)
            return self._cached_settings
        except Exception as e:
            logger.warning(
                "Failed to load subscription settings, using defaults: %s",
                str(e)
            )
            return SubscriptionSettings.from_dict({})

    def get_value(self, key: str, default=None):
        """Get a single setting value."""
        settings = self.get_settings()
        return getattr(settings, key, default)

    def invalidate_cache(self) -> None:
        """Invalidate cached settings."""
        self._cached_settings = None


# Convenience function for quick access
def get_subscription_defaults() -> SubscriptionSettings:
    """Get default subscription settings without DB access."""
    return SubscriptionSettings.from_dict({})

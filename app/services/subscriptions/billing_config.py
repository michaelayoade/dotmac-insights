"""Billing configuration - module-specific settings for subscription billing.

This module defines its own settings schema and provides typed access
to billing configuration. Settings are stored in the database via
the SettingGroup model but the schema is owned by this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    "BillingConfig",
    "BillingConfigService",
    "BILLING_SETTINGS_SCHEMA",
    "get_billing_config",
]


# =============================================================================
# Billing Settings Schema (module-owned)
# =============================================================================

BILLING_SETTINGS_SCHEMA = {
    "version": 1,
    "label": "Billing Configuration",
    "description": "Subscription billing and payment settings",
    "properties": {
        # General billing settings
        "enabled": {
            "type": "boolean",
            "default": True,
            "label": "Enable Billing",
            "description": "Enable automated billing",
        },
        "default_currency": {
            "type": "string",
            "default": "NGN",
            "label": "Default Currency",
            "description": "Default billing currency code",
        },
        "supported_currencies": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["NGN", "USD"],
            "label": "Supported Currencies",
            "description": "List of supported currency codes",
        },
        "tax_rate": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "default": 0,
            "label": "Tax Rate (%)",
            "description": "Default tax rate percentage",
        },
        "invoice_prefix": {
            "type": "string",
            "default": "INV",
            "label": "Invoice Prefix",
            "description": "Prefix for invoice numbers",
        },
        "invoice_due_days": {
            "type": "integer",
            "minimum": 0,
            "maximum": 90,
            "default": 7,
            "label": "Invoice Due Days",
            "description": "Days until invoice is due after creation",
        },

        # Daily billing settings
        "daily_billing_enabled": {
            "type": "boolean",
            "default": True,
            "label": "Daily Billing Enabled",
            "description": "Enable daily billing automation",
        },
        "daily_billing_hour": {
            "type": "integer",
            "minimum": 0,
            "maximum": 23,
            "default": 1,
            "label": "Daily Billing Hour",
            "description": "Hour to run daily billing (0-23)",
        },
        "daily_billing_minute": {
            "type": "integer",
            "minimum": 0,
            "maximum": 59,
            "default": 0,
            "label": "Daily Billing Minute",
            "description": "Minute to run daily billing (0-59)",
        },
        "daily_billing_type": {
            "type": "string",
            "enum": ["fixed", "usage_based", "hybrid"],
            "default": "fixed",
            "label": "Daily Billing Type",
            "description": "Default billing type for daily subscriptions",
        },
        "daily_usage_rate_per_gb": {
            "type": "number",
            "minimum": 0,
            "default": 0,
            "label": "Usage Rate per GB",
            "description": "Rate per GB for usage-based daily billing",
        },
        "daily_included_gb": {
            "type": "number",
            "minimum": 0,
            "default": 0,
            "label": "Included GB per Day",
            "description": "Free GB included per day before usage charges",
        },

        # Monthly billing settings
        "monthly_billing_enabled": {
            "type": "boolean",
            "default": True,
            "label": "Monthly Billing Enabled",
            "description": "Enable monthly billing automation",
        },
        "monthly_billing_day": {
            "type": "integer",
            "minimum": 1,
            "maximum": 28,
            "default": 1,
            "label": "Monthly Billing Day",
            "description": "Day of month for monthly billing (1-28)",
        },
        "monthly_billing_hour": {
            "type": "integer",
            "minimum": 0,
            "maximum": 23,
            "default": 2,
            "label": "Monthly Billing Hour",
            "description": "Hour to run monthly billing",
        },

        # Invoice overdue settings
        "overdue_check_enabled": {
            "type": "boolean",
            "default": True,
            "label": "Overdue Check Enabled",
            "description": "Enable automatic overdue invoice marking",
        },
        "overdue_check_hour": {
            "type": "integer",
            "minimum": 0,
            "maximum": 23,
            "default": 6,
            "label": "Overdue Check Hour",
            "description": "Hour to check for overdue invoices",
        },

        # Retry settings
        "charge_retry_enabled": {
            "type": "boolean",
            "default": True,
            "label": "Charge Retry Enabled",
            "description": "Enable automatic retry of failed charges",
        },
        "charge_retry_interval_hours": {
            "type": "integer",
            "minimum": 1,
            "maximum": 24,
            "default": 4,
            "label": "Retry Interval (hours)",
            "description": "Hours between retry attempts",
        },
        "charge_max_retries": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
            "label": "Max Retries",
            "description": "Maximum number of retry attempts",
        },
        "charge_retry_backoff": {
            "type": "boolean",
            "default": True,
            "label": "Exponential Backoff",
            "description": "Use exponential backoff for retries",
        },

        # Auto-charge settings
        "auto_charge_enabled": {
            "type": "boolean",
            "default": True,
            "label": "Auto-Charge Enabled",
            "description": "Enable automatic charging via saved payment methods",
        },
        "auto_charge_generate_invoice": {
            "type": "boolean",
            "default": True,
            "label": "Generate Invoice",
            "description": "Generate invoice before auto-charging",
        },

        # Suspension settings
        "auto_suspend_enabled": {
            "type": "boolean",
            "default": False,
            "label": "Auto-Suspend Enabled",
            "description": "Automatically suspend subscription on payment failure",
        },
        "auto_suspend_grace_days": {
            "type": "integer",
            "minimum": 0,
            "maximum": 30,
            "default": 3,
            "label": "Grace Period (days)",
            "description": "Days to wait before auto-suspension",
        },

        # Notification settings
        "send_invoice_email": {
            "type": "boolean",
            "default": True,
            "label": "Send Invoice Email",
            "description": "Email invoice to customer on creation",
        },
        "send_payment_receipt": {
            "type": "boolean",
            "default": True,
            "label": "Send Payment Receipt",
            "description": "Email receipt after successful payment",
        },
        "send_payment_failed_alert": {
            "type": "boolean",
            "default": True,
            "label": "Send Payment Failed Alert",
            "description": "Alert customer on payment failure",
        },
        "send_overdue_reminder": {
            "type": "boolean",
            "default": True,
            "label": "Send Overdue Reminders",
            "description": "Send reminders for overdue invoices",
        },
        "overdue_reminder_days": {
            "type": "array",
            "items": {"type": "integer"},
            "default": [1, 3, 7],
            "label": "Reminder Days",
            "description": "Days after due date to send reminders",
        },
    },
}


def _get_schema_defaults() -> Dict[str, Any]:
    """Extract default values from schema."""
    defaults = {}
    for key, prop in BILLING_SETTINGS_SCHEMA["properties"].items():
        if "default" in prop:
            defaults[key] = prop["default"]
    return defaults


# =============================================================================
# Billing Config Dataclass
# =============================================================================

@dataclass
class BillingConfig:
    """Typed billing configuration."""

    # General
    enabled: bool = True
    default_currency: str = "NGN"
    supported_currencies: List[str] = field(default_factory=lambda: ["NGN", "USD"])
    tax_rate: Decimal = Decimal("0")
    invoice_prefix: str = "INV"
    invoice_due_days: int = 7

    # Daily billing
    daily_billing_enabled: bool = True
    daily_billing_hour: int = 1
    daily_billing_minute: int = 0
    daily_billing_type: str = "fixed"
    daily_usage_rate_per_gb: Decimal = Decimal("0")
    daily_included_gb: Decimal = Decimal("0")

    # Monthly billing
    monthly_billing_enabled: bool = True
    monthly_billing_day: int = 1
    monthly_billing_hour: int = 2

    # Overdue
    overdue_check_enabled: bool = True
    overdue_check_hour: int = 6

    # Retries
    charge_retry_enabled: bool = True
    charge_retry_interval_hours: int = 4
    charge_max_retries: int = 3
    charge_retry_backoff: bool = True

    # Auto-charge
    auto_charge_enabled: bool = True
    auto_charge_generate_invoice: bool = True

    # Suspension
    auto_suspend_enabled: bool = False
    auto_suspend_grace_days: int = 3

    # Notifications
    send_invoice_email: bool = True
    send_payment_receipt: bool = True
    send_payment_failed_alert: bool = True
    send_overdue_reminder: bool = True
    overdue_reminder_days: List[int] = field(default_factory=lambda: [1, 3, 7])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BillingConfig":
        """Create config from dictionary, using defaults for missing keys."""
        defaults = _get_schema_defaults()
        merged = {**defaults, **data}

        return cls(
            enabled=merged.get("enabled", True),
            default_currency=merged.get("default_currency", "NGN"),
            supported_currencies=merged.get("supported_currencies", ["NGN", "USD"]),
            tax_rate=Decimal(str(merged.get("tax_rate", 0))),
            invoice_prefix=merged.get("invoice_prefix", "INV"),
            invoice_due_days=merged.get("invoice_due_days", 7),
            daily_billing_enabled=merged.get("daily_billing_enabled", True),
            daily_billing_hour=merged.get("daily_billing_hour", 1),
            daily_billing_minute=merged.get("daily_billing_minute", 0),
            daily_billing_type=merged.get("daily_billing_type", "fixed"),
            daily_usage_rate_per_gb=Decimal(str(merged.get("daily_usage_rate_per_gb", 0))),
            daily_included_gb=Decimal(str(merged.get("daily_included_gb", 0))),
            monthly_billing_enabled=merged.get("monthly_billing_enabled", True),
            monthly_billing_day=merged.get("monthly_billing_day", 1),
            monthly_billing_hour=merged.get("monthly_billing_hour", 2),
            overdue_check_enabled=merged.get("overdue_check_enabled", True),
            overdue_check_hour=merged.get("overdue_check_hour", 6),
            charge_retry_enabled=merged.get("charge_retry_enabled", True),
            charge_retry_interval_hours=merged.get("charge_retry_interval_hours", 4),
            charge_max_retries=merged.get("charge_max_retries", 3),
            charge_retry_backoff=merged.get("charge_retry_backoff", True),
            auto_charge_enabled=merged.get("auto_charge_enabled", True),
            auto_charge_generate_invoice=merged.get("auto_charge_generate_invoice", True),
            auto_suspend_enabled=merged.get("auto_suspend_enabled", False),
            auto_suspend_grace_days=merged.get("auto_suspend_grace_days", 3),
            send_invoice_email=merged.get("send_invoice_email", True),
            send_payment_receipt=merged.get("send_payment_receipt", True),
            send_payment_failed_alert=merged.get("send_payment_failed_alert", True),
            send_overdue_reminder=merged.get("send_overdue_reminder", True),
            overdue_reminder_days=merged.get("overdue_reminder_days", [1, 3, 7]),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "enabled": self.enabled,
            "default_currency": self.default_currency,
            "supported_currencies": self.supported_currencies,
            "tax_rate": float(self.tax_rate),
            "invoice_prefix": self.invoice_prefix,
            "invoice_due_days": self.invoice_due_days,
            "daily_billing_enabled": self.daily_billing_enabled,
            "daily_billing_hour": self.daily_billing_hour,
            "daily_billing_minute": self.daily_billing_minute,
            "daily_billing_type": self.daily_billing_type,
            "daily_usage_rate_per_gb": float(self.daily_usage_rate_per_gb),
            "daily_included_gb": float(self.daily_included_gb),
            "monthly_billing_enabled": self.monthly_billing_enabled,
            "monthly_billing_day": self.monthly_billing_day,
            "monthly_billing_hour": self.monthly_billing_hour,
            "overdue_check_enabled": self.overdue_check_enabled,
            "overdue_check_hour": self.overdue_check_hour,
            "charge_retry_enabled": self.charge_retry_enabled,
            "charge_retry_interval_hours": self.charge_retry_interval_hours,
            "charge_max_retries": self.charge_max_retries,
            "charge_retry_backoff": self.charge_retry_backoff,
            "auto_charge_enabled": self.auto_charge_enabled,
            "auto_charge_generate_invoice": self.auto_charge_generate_invoice,
            "auto_suspend_enabled": self.auto_suspend_enabled,
            "auto_suspend_grace_days": self.auto_suspend_grace_days,
            "send_invoice_email": self.send_invoice_email,
            "send_payment_receipt": self.send_payment_receipt,
            "send_payment_failed_alert": self.send_payment_failed_alert,
            "send_overdue_reminder": self.send_overdue_reminder,
            "overdue_reminder_days": self.overdue_reminder_days,
        }


# =============================================================================
# Configuration Service
# =============================================================================

SETTINGS_GROUP = "subscriptions.billing"


class BillingConfigService:
    """Service for managing billing configuration.

    This service owns the billing settings and provides:
    - Typed access to configuration
    - Settings CRUD operations
    - Schedule helpers for Celery tasks
    - Validation helpers
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._config: Optional[BillingConfig] = None

    def get_config(self, use_cache: bool = True) -> BillingConfig:
        """Get billing configuration.

        Args:
            use_cache: Use cached config if available.

        Returns:
            BillingConfig instance.
        """
        if use_cache and self._config is not None:
            return self._config

        self._config = self._load_config()
        return self._config

    def save_config(self, config: BillingConfig) -> BillingConfig:
        """Save billing configuration.

        Args:
            config: Configuration to save.

        Returns:
            Saved configuration.
        """
        self._save_to_db(config.to_dict())
        self._config = config
        return config

    def update_config(self, updates: Dict[str, Any]) -> BillingConfig:
        """Update specific configuration values.

        Args:
            updates: Dictionary of values to update.

        Returns:
            Updated configuration.
        """
        current = self.get_config(use_cache=False)
        current_dict = current.to_dict()
        current_dict.update(updates)

        new_config = BillingConfig.from_dict(current_dict)
        return self.save_config(new_config)

    def reset_to_defaults(self) -> BillingConfig:
        """Reset configuration to defaults.

        Returns:
            Default configuration.
        """
        defaults = _get_schema_defaults()
        config = BillingConfig.from_dict(defaults)
        return self.save_config(config)

    def get_schema(self) -> Dict[str, Any]:
        """Get the settings schema for UI rendering."""
        return BILLING_SETTINGS_SCHEMA

    # -------------------------------------------------------------------------
    # Schedule Helpers
    # -------------------------------------------------------------------------

    def get_daily_billing_cron(self) -> Dict[str, int]:
        """Get cron schedule for daily billing."""
        config = self.get_config()
        return {
            "hour": config.daily_billing_hour,
            "minute": config.daily_billing_minute,
        }

    def get_monthly_billing_cron(self) -> Dict[str, int]:
        """Get cron schedule for monthly billing."""
        config = self.get_config()
        return {
            "day_of_month": config.monthly_billing_day,
            "hour": config.monthly_billing_hour,
            "minute": 0,
        }

    def get_overdue_check_cron(self) -> Dict[str, int]:
        """Get cron schedule for overdue checking."""
        config = self.get_config()
        return {
            "hour": config.overdue_check_hour,
            "minute": 0,
        }

    def get_retry_interval_seconds(self, retry_count: int = 0) -> int:
        """Get retry delay in seconds.

        Args:
            retry_count: Current retry count for backoff calculation.

        Returns:
            Delay in seconds.
        """
        config = self.get_config()
        base_delay = config.charge_retry_interval_hours * 3600

        if config.charge_retry_backoff and retry_count > 0:
            return base_delay * (2 ** retry_count)

        return base_delay

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Check if billing is enabled."""
        return self.get_config().enabled

    def is_daily_billing_enabled(self) -> bool:
        """Check if daily billing is enabled."""
        config = self.get_config()
        return config.enabled and config.daily_billing_enabled

    def is_monthly_billing_enabled(self) -> bool:
        """Check if monthly billing is enabled."""
        config = self.get_config()
        return config.enabled and config.monthly_billing_enabled

    def is_currency_supported(self, currency: str) -> bool:
        """Check if currency is supported."""
        return currency in self.get_config().supported_currencies

    def should_retry_charge(self, retry_count: int) -> bool:
        """Check if charge should be retried."""
        config = self.get_config()
        return (
            config.charge_retry_enabled
            and retry_count < config.charge_max_retries
        )

    def should_auto_suspend(self) -> bool:
        """Check if auto-suspension is enabled."""
        return self.get_config().auto_suspend_enabled

    # -------------------------------------------------------------------------
    # Calculation Helpers
    # -------------------------------------------------------------------------

    def calculate_tax(self, amount: Decimal) -> Decimal:
        """Calculate tax amount.

        Args:
            amount: Base amount.

        Returns:
            Tax amount.
        """
        config = self.get_config()
        if config.tax_rate <= 0:
            return Decimal("0")
        return amount * (config.tax_rate / 100)

    def get_invoice_due_date(self, invoice_date) -> "date":
        """Calculate invoice due date.

        Args:
            invoice_date: Invoice creation date.

        Returns:
            Due date.
        """
        from datetime import timedelta
        config = self.get_config()
        return invoice_date + timedelta(days=config.invoice_due_days)

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _load_config(self) -> BillingConfig:
        """Load configuration from database."""
        from app.models.settings import SettingGroup

        try:
            setting = (
                self.db.query(SettingGroup)
                .filter(SettingGroup.group == SETTINGS_GROUP)
                .first()
            )

            if setting and setting.data:
                data = json.loads(setting.data) if isinstance(setting.data, str) else setting.data
                return BillingConfig.from_dict(data)

        except Exception:
            pass

        # Return defaults
        return BillingConfig.from_dict(_get_schema_defaults())

    def _save_to_db(self, data: Dict[str, Any]) -> None:
        """Save configuration to database."""
        from app.models.settings import SettingGroup

        data_json = json.dumps(data)

        stmt = insert(SettingGroup).values(
            group=SETTINGS_GROUP,
            data=data_json,
            schema_version=BILLING_SETTINGS_SCHEMA["version"],
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["group"],
            set_={
                "data": data_json,
                "schema_version": BILLING_SETTINGS_SCHEMA["version"],
                "updated_at": stmt.excluded.updated_at,
            },
        )

        self.db.execute(stmt)
        self.db.flush()


def get_billing_config(db: Session) -> BillingConfig:
    """Convenience function to get billing config.

    Args:
        db: Database session.

    Returns:
        BillingConfig instance.
    """
    service = BillingConfigService(db)
    return service.get_config()

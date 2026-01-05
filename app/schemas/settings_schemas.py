"""
Settings JSON Schemas

Defines validation schemas for each settings group.
Schemas support versioning for forward migration.
"""

from typing import Any

# Schema definitions per group, versioned
SETTING_SCHEMAS: dict[str, dict[int, dict[str, Any]]] = {
    "email": {
        1: {
            "label": "Email Configuration",
            "description": "SMTP and email provider settings",
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["smtp", "sendgrid", "ses"],
                    "default": "smtp",
                    "description": "Email provider",
                },
                "smtp_host": {
                    "type": "string",
                    "description": "SMTP server hostname",
                },
                "smtp_port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                    "default": 587,
                    "description": "SMTP server port",
                },
                "smtp_user": {
                    "type": "string",
                    "description": "SMTP username",
                },
                "smtp_password": {
                    "type": "string",
                    "x-secret": True,
                    "description": "SMTP password",
                },
                "smtp_use_tls": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use TLS encryption",
                },
                "from_address": {
                    "type": "string",
                    "format": "email",
                    "description": "Default from email address",
                },
                "from_name": {
                    "type": "string",
                    "description": "Default from name",
                },
                "reply_to": {
                    "type": "string",
                    "format": "email",
                    "description": "Reply-to email address",
                },
                "sendgrid_api_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "SendGrid API key",
                },
                "ses_access_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "AWS SES access key",
                },
                "ses_secret_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "AWS SES secret key",
                },
                "ses_region": {
                    "type": "string",
                    "default": "us-east-1",
                    "description": "AWS SES region",
                },
            },
            "required": ["provider", "from_address"],
        },
    },

    "payments": {
        1: {
            "label": "Payment Gateway",
            "description": "Payment provider configuration",
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["paystack", "flutterwave", "stripe"],
                    "default": "paystack",
                    "description": "Primary payment provider",
                },
                "test_mode": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use test/sandbox mode",
                },
                "paystack_public_key": {
                    "type": "string",
                    "description": "Paystack public key",
                },
                "paystack_secret_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Paystack secret key",
                },
                "flutterwave_public_key": {
                    "type": "string",
                    "description": "Flutterwave public key",
                },
                "flutterwave_secret_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Flutterwave secret key",
                },
                "stripe_publishable_key": {
                    "type": "string",
                    "description": "Stripe publishable key",
                },
                "stripe_secret_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Stripe secret key",
                },
                "webhook_secret": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Webhook signing secret",
                },
            },
            "required": ["provider"],
        },
    },

    "webhooks": {
        1: {
            "label": "Outgoing Webhooks",
            "description": "Webhook delivery configuration",
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable webhook delivery",
                },
                "signing_secret": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Secret for signing webhook payloads",
                },
                "retry_attempts": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10,
                    "default": 3,
                    "description": "Number of retry attempts",
                },
                "retry_delay_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3600,
                    "default": 60,
                    "description": "Delay between retries (seconds)",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 60,
                    "default": 30,
                    "description": "Request timeout (seconds)",
                },
            },
            "required": [],
        },
    },

    "sms": {
        1: {
            "label": "SMS Configuration",
            "description": "SMS provider settings",
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["termii", "africas_talking", "twilio"],
                    "default": "termii",
                    "description": "SMS provider",
                },
                "enabled": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable SMS notifications",
                },
                "sender_id": {
                    "type": "string",
                    "maxLength": 11,
                    "description": "SMS sender ID",
                },
                "termii_api_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Termii API key",
                },
                "africas_talking_username": {
                    "type": "string",
                    "description": "Africa's Talking username",
                },
                "africas_talking_api_key": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Africa's Talking API key",
                },
                "twilio_account_sid": {
                    "type": "string",
                    "description": "Twilio account SID",
                },
                "twilio_auth_token": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Twilio auth token",
                },
                "twilio_phone_number": {
                    "type": "string",
                    "description": "Twilio phone number",
                },
            },
            "required": ["provider"],
        },
    },

    "notifications": {
        1: {
            "label": "Notification Preferences",
            "description": "System-wide notification settings",
            "type": "object",
            "properties": {
                "email_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable email notifications",
                },
                "sms_enabled": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable SMS notifications",
                },
                "in_app_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable in-app notifications",
                },
                "digest_frequency": {
                    "type": "string",
                    "enum": ["realtime", "hourly", "daily", "weekly"],
                    "default": "realtime",
                    "description": "Notification digest frequency",
                },
                "quiet_hours_start": {
                    "type": "string",
                    "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                    "description": "Quiet hours start time (HH:MM)",
                },
                "quiet_hours_end": {
                    "type": "string",
                    "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                    "description": "Quiet hours end time (HH:MM)",
                },
            },
            "required": [],
        },
    },

    "branding": {
        1: {
            "label": "Company Branding",
            "description": "Company information and branding",
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Company name",
                },
                "logo_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Company logo URL",
                },
                "favicon_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Favicon URL",
                },
                "support_email": {
                    "type": "string",
                    "format": "email",
                    "description": "Support email address",
                },
                "support_phone": {
                    "type": "string",
                    "description": "Support phone number",
                },
                "website_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Company website URL",
                },
                "primary_color": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "default": "#3B82F6",
                    "description": "Primary brand color (hex)",
                },
                "accent_color": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "default": "#10B981",
                    "description": "Accent color (hex)",
                },
            },
            "required": [],
        },
    },

    "localization": {
        1: {
            "label": "Localization",
            "description": "Regional and language settings",
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "default": "Africa/Lagos",
                    "description": "Default timezone",
                },
                "date_format": {
                    "type": "string",
                    "enum": ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"],
                    "default": "DD/MM/YYYY",
                    "description": "Date display format",
                },
                "time_format": {
                    "type": "string",
                    "enum": ["12h", "24h"],
                    "default": "12h",
                    "description": "Time display format",
                },
                "currency": {
                    "type": "string",
                    "default": "NGN",
                    "description": "Default currency code",
                },
                "language": {
                    "type": "string",
                    "default": "en",
                    "description": "Default language",
                },
                "first_day_of_week": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 6,
                    "default": 1,
                    "description": "First day of week (0=Sunday, 1=Monday)",
                },
            },
            "required": [],
        },
    },

    "billing": {
        1: {
            "label": "Billing Configuration",
            "description": "Subscription billing and payment settings",
            "type": "object",
            "properties": {
                # General billing settings
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable automated billing",
                },
                "default_currency": {
                    "type": "string",
                    "default": "NGN",
                    "description": "Default billing currency",
                },
                "supported_currencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["NGN", "USD"],
                    "description": "Supported currencies for billing",
                },
                "tax_rate": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 0,
                    "description": "Default tax rate percentage",
                },
                "invoice_prefix": {
                    "type": "string",
                    "default": "INV",
                    "description": "Invoice number prefix",
                },
                "invoice_due_days": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 90,
                    "default": 7,
                    "description": "Days until invoice is due",
                },

                # Daily billing settings
                "daily_billing_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable daily billing automation",
                },
                "daily_billing_hour": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 1,
                    "description": "Hour to run daily billing (0-23)",
                },
                "daily_billing_minute": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 59,
                    "default": 0,
                    "description": "Minute to run daily billing (0-59)",
                },
                "daily_billing_type": {
                    "type": "string",
                    "enum": ["fixed", "usage_based", "hybrid"],
                    "default": "fixed",
                    "description": "Default daily billing type",
                },
                "daily_usage_rate_per_gb": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Rate per GB for usage-based billing",
                },
                "daily_included_gb": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Free GB included per day",
                },

                # Monthly billing settings
                "monthly_billing_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable monthly billing automation",
                },
                "monthly_billing_day": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 28,
                    "default": 1,
                    "description": "Day of month for billing (1-28)",
                },
                "monthly_billing_hour": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 2,
                    "description": "Hour to run monthly billing",
                },

                # Invoice overdue settings
                "overdue_check_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable overdue invoice marking",
                },
                "overdue_check_hour": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 6,
                    "description": "Hour to check for overdue invoices",
                },

                # Retry settings
                "charge_retry_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable failed charge retries",
                },
                "charge_retry_interval_hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 24,
                    "default": 4,
                    "description": "Hours between retry attempts",
                },
                "charge_max_retries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                    "description": "Maximum retry attempts",
                },
                "charge_retry_backoff": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use exponential backoff for retries",
                },

                # Auto-charge settings
                "auto_charge_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable automatic charging via payment subscriptions",
                },
                "auto_charge_generate_invoice": {
                    "type": "boolean",
                    "default": True,
                    "description": "Generate invoice before auto-charging",
                },

                # Suspension settings
                "auto_suspend_enabled": {
                    "type": "boolean",
                    "default": False,
                    "description": "Auto-suspend on failed payment",
                },
                "auto_suspend_grace_days": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 30,
                    "default": 3,
                    "description": "Grace period before suspension",
                },

                # Notification settings
                "send_invoice_email": {
                    "type": "boolean",
                    "default": True,
                    "description": "Email invoice to customer",
                },
                "send_payment_receipt": {
                    "type": "boolean",
                    "default": True,
                    "description": "Email payment receipt",
                },
                "send_payment_failed_alert": {
                    "type": "boolean",
                    "default": True,
                    "description": "Alert on payment failure",
                },
                "send_overdue_reminder": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send overdue invoice reminders",
                },
                "overdue_reminder_days": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "default": [1, 3, 7],
                    "description": "Days after due date to send reminders",
                },
            },
            "required": [],
        },
    },

    "subscriptions": {
        1: {
            "label": "Subscription Settings",
            "description": "Subscription lifecycle, billing, and bundle configuration",
            "type": "object",
            "properties": {
                # Billing Settings
                "default_currency": {
                    "type": "string",
                    "default": "NGN",
                    "description": "Default currency for subscriptions",
                },
                "invoice_due_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 90,
                    "default": 7,
                    "description": "Days until invoice is due",
                },
                "daily_billing_invoice_due_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 1,
                    "description": "Days until daily billing invoice is due",
                },
                "billing_lookback_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7,
                    "default": 1,
                    "description": "Days to look back for billing",
                },
                "max_billing_day_of_month": {
                    "type": "integer",
                    "minimum": 28,
                    "maximum": 31,
                    "default": 28,
                    "description": "Max day of month for billing anchor (handles Feb)",
                },

                # Bundle Settings
                "bundle_expiry_warning_days": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "default": [7, 3, 1],
                    "description": "Days before expiry to send warnings",
                },
                "bundle_cleanup_retention_days": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 365,
                    "default": 90,
                    "description": "Days to retain expired/cancelled bundles",
                },
                "bundle_default_throttle_speed_kbps": {
                    "type": "integer",
                    "minimum": 32,
                    "maximum": 1024,
                    "default": 128,
                    "description": "Default throttle speed when bundle exhausted",
                },
                "bundle_expiring_soon_threshold_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 7,
                    "description": "Days to consider bundle 'expiring soon'",
                },

                # Usage Alert Thresholds
                "bundle_alert_threshold_1": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 90,
                    "default": 50,
                    "description": "First usage alert threshold (%)",
                },
                "bundle_alert_threshold_2": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 95,
                    "default": 80,
                    "description": "Second usage alert threshold (%)",
                },
                "bundle_alert_threshold_3": {
                    "type": "integer",
                    "minimum": 80,
                    "maximum": 99,
                    "default": 95,
                    "description": "Final usage alert threshold (%)",
                },

                # RADIUS Settings
                "radius_username_max_collision_attempts": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 500,
                    "default": 100,
                    "description": "Max attempts to resolve username collisions",
                },
                "radius_subscription_prefix": {
                    "type": "string",
                    "default": "SUB",
                    "description": "Prefix for subscription-based usernames",
                },

                # Provisioning Settings
                "provisioning_retry_attempts": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                    "description": "Number of provisioning retry attempts",
                },
                "provisioning_retry_delay_seconds": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 300,
                    "default": 30,
                    "description": "Delay between provisioning retries",
                },

                # Lifecycle Settings
                "auto_suspend_after_grace_days": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 90,
                    "default": 0,
                    "description": "Days after grace period to auto-suspend (0=disabled)",
                },
                "auto_cancel_after_suspend_days": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 365,
                    "default": 30,
                    "description": "Days after suspension to auto-cancel (0=disabled)",
                },

                # Session Settings
                "max_concurrent_sessions": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 1,
                    "description": "Max concurrent RADIUS sessions per subscription",
                },
                "session_timeout_seconds": {
                    "type": "integer",
                    "minimum": 300,
                    "maximum": 86400,
                    "default": 3600,
                    "description": "Default RADIUS session timeout",
                },
                "idle_timeout_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 300,
                    "description": "Default RADIUS idle timeout",
                },

                # Notification Settings
                "notify_on_bundle_purchase": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send notification on bundle purchase",
                },
                "notify_on_bundle_exhaustion": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send notification when bundle exhausted",
                },
                "notify_on_bundle_expiry": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send notification on bundle expiry",
                },
                "notify_on_subscription_status_change": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send notification on status changes",
                },
            },
            "required": [],
        },
    },

    "monitoring": {
        1: {
            "label": "Network Monitoring Settings",
            "description": "SNMP polling, alerting, and incident management configuration",
            "type": "object",
            "properties": {
                # SNMP Polling Settings
                "polling_interval_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 300,
                    "description": "Default SNMP polling interval in seconds",
                },
                "polling_timeout_seconds": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 60,
                    "default": 10,
                    "description": "SNMP request timeout in seconds",
                },
                "polling_retries": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 5,
                    "default": 2,
                    "description": "Number of SNMP request retries",
                },
                "polling_batch_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Number of devices to poll concurrently",
                },

                # Device Down Detection
                "device_down_after_failures": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                    "description": "Consecutive poll failures before device marked down",
                },
                "device_recovery_polls": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2,
                    "description": "Consecutive successful polls before device marked up",
                },

                # CPU Alert Thresholds
                "cpu_warning_percent": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 95,
                    "default": 80,
                    "description": "CPU percentage for warning alert",
                },
                "cpu_critical_percent": {
                    "type": "integer",
                    "minimum": 70,
                    "maximum": 100,
                    "default": 95,
                    "description": "CPU percentage for critical alert",
                },

                # Memory Alert Thresholds
                "memory_warning_percent": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 95,
                    "default": 80,
                    "description": "Memory percentage for warning alert",
                },
                "memory_critical_percent": {
                    "type": "integer",
                    "minimum": 70,
                    "maximum": 100,
                    "default": 95,
                    "description": "Memory percentage for critical alert",
                },

                # Temperature Alert Thresholds
                "temperature_warning_celsius": {
                    "type": "integer",
                    "minimum": 40,
                    "maximum": 80,
                    "default": 60,
                    "description": "Temperature (Celsius) for warning alert",
                },
                "temperature_critical_celsius": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 100,
                    "default": 75,
                    "description": "Temperature (Celsius) for critical alert",
                },

                # Interface Utilization Thresholds
                "interface_utilization_warning_percent": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 95,
                    "default": 80,
                    "description": "Interface utilization percentage for warning alert",
                },
                "interface_utilization_critical_percent": {
                    "type": "integer",
                    "minimum": 70,
                    "maximum": 100,
                    "default": 95,
                    "description": "Interface utilization percentage for critical alert",
                },

                # Alert Behavior
                "notification_cooldown_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 300,
                    "description": "Minimum time between repeat notifications",
                },
                "auto_resolve_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Automatically resolve alerts when condition clears",
                },
                "auto_resolve_delay_seconds": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 600,
                    "default": 60,
                    "description": "Delay before auto-resolving (to avoid flapping)",
                },

                # Escalation Settings
                "escalation_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable alert escalation",
                },
                "escalation_level_1_minutes": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 60,
                    "default": 15,
                    "description": "Minutes before first escalation",
                },
                "escalation_level_2_minutes": {
                    "type": "integer",
                    "minimum": 15,
                    "maximum": 120,
                    "default": 30,
                    "description": "Minutes before second escalation",
                },
                "escalation_level_3_minutes": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 240,
                    "default": 60,
                    "description": "Minutes before third escalation",
                },

                # Incident Settings
                "auto_create_incident": {
                    "type": "boolean",
                    "default": True,
                    "description": "Auto-create incident for critical alerts",
                },
                "incident_auto_resolve_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Auto-resolve incidents when all alerts cleared",
                },
                "alert_correlation_window_minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 5,
                    "description": "Window for correlating related alerts into incident",
                },

                # Metrics Retention
                "raw_metrics_retention_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 7,
                    "description": "Days to retain raw (5-min) metrics",
                },
                "hourly_rollup_retention_days": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 365,
                    "default": 90,
                    "description": "Days to retain hourly metric rollups",
                },
                "daily_rollup_retention_days": {
                    "type": "integer",
                    "minimum": 180,
                    "maximum": 1095,
                    "default": 730,
                    "description": "Days to retain daily metric rollups (2 years default)",
                },

                # Notification Channels
                "alert_email_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send alert notifications via email",
                },
                "alert_sms_enabled": {
                    "type": "boolean",
                    "default": False,
                    "description": "Send critical alerts via SMS",
                },
                "alert_slack_enabled": {
                    "type": "boolean",
                    "default": False,
                    "description": "Send alerts to Slack",
                },
                "alert_slack_webhook_url": {
                    "type": "string",
                    "x-secret": True,
                    "description": "Slack webhook URL for alerts",
                },

                # NOC Dashboard
                "noc_dashboard_refresh_seconds": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 300,
                    "default": 30,
                    "description": "NOC dashboard auto-refresh interval",
                },
                "noc_dashboard_alert_sound": {
                    "type": "boolean",
                    "default": True,
                    "description": "Play sound for new critical alerts",
                },
            },
            "required": [],
        },
    },
}


def get_schema(group: str, version: int | None = None) -> dict[str, Any]:
    """Get schema for a group, optionally at a specific version."""
    if group not in SETTING_SCHEMAS:
        raise ValueError(f"Unknown settings group: {group}")

    versions = SETTING_SCHEMAS[group]
    if version is None:
        version = max(versions.keys())

    if version not in versions:
        raise ValueError(f"Unknown schema version {version} for group {group}")

    return versions[version]


def get_latest_version(group: str) -> int:
    """Get the latest schema version for a group."""
    if group not in SETTING_SCHEMAS:
        raise ValueError(f"Unknown settings group: {group}")
    return max(SETTING_SCHEMAS[group].keys())


def get_all_groups() -> list[dict[str, Any]]:
    """Get metadata for all settings groups."""
    groups = []
    for group_name, versions in SETTING_SCHEMAS.items():
        latest = versions[max(versions.keys())]
        groups.append({
            "group": group_name,
            "label": latest.get("label", group_name),
            "description": latest.get("description", ""),
        })
    return groups


def get_secret_fields(group: str) -> set[str]:
    """Get field names marked as secrets for a group."""
    schema = get_schema(group)
    secrets = set()
    for field_name, field_schema in schema.get("properties", {}).items():
        if field_schema.get("x-secret"):
            secrets.add(field_name)
    return secrets


def get_defaults(group: str) -> dict[str, Any]:
    """Get default values for a group."""
    schema = get_schema(group)
    defaults = {}
    for field_name, field_schema in schema.get("properties", {}).items():
        if "default" in field_schema:
            defaults[field_name] = field_schema["default"]
    return defaults

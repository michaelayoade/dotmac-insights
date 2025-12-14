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

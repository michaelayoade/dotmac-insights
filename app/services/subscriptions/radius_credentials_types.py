"""RADIUS credential generation types.

Type definitions for the RADIUS credential generation system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from app.services.errors import ValidationError


__all__ = [
    "UsernameFormatType",
    "PasswordComplexityConfig",
    "UsernameTemplateConfig",
    "SequentialConfig",
    "RADIUSCredentialConfig",
    "GeneratedCredentials",
    "CredentialGenerationContext",
    "RADIUS_CREDENTIAL_CONFIG_SCHEMA",
]


class UsernameFormatType(Enum):
    """Username format types."""

    TEMPLATE = "template"
    SEQUENTIAL = "sequential"
    EMAIL = "email"
    PHONE = "phone"
    SUBSCRIPTION_ID = "subscription_id"


@dataclass
class PasswordComplexityConfig:
    """Password generation complexity settings."""

    min_length: int = 12
    max_length: int = 16
    include_lowercase: bool = True
    include_uppercase: bool = True
    include_digits: bool = True
    include_special: bool = True
    special_chars: str = "!@#$%^&*"
    exclude_ambiguous: bool = True  # Exclude 0/O, 1/l/I, etc.

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PasswordComplexityConfig":
        min_length = data.get("min_length", 12)
        max_length = data.get("max_length", 16)

        if min_length > max_length:
            raise ValidationError(
                f"Password min_length ({min_length}) cannot exceed max_length ({max_length})"
            )

        include_lowercase = data.get("include_lowercase", True)
        include_uppercase = data.get("include_uppercase", True)
        include_digits = data.get("include_digits", True)
        include_special = data.get("include_special", True)

        if not any([include_lowercase, include_uppercase, include_digits, include_special]):
            raise ValidationError(
                "Password configuration requires at least one character type "
                "(lowercase, uppercase, digits, or special characters)"
            )

        return cls(
            min_length=min_length,
            max_length=max_length,
            include_lowercase=include_lowercase,
            include_uppercase=include_uppercase,
            include_digits=include_digits,
            include_special=include_special,
            special_chars=data.get("special_chars", "!@#$%^&*"),
            exclude_ambiguous=data.get("exclude_ambiguous", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_length": self.min_length,
            "max_length": self.max_length,
            "include_lowercase": self.include_lowercase,
            "include_uppercase": self.include_uppercase,
            "include_digits": self.include_digits,
            "include_special": self.include_special,
            "special_chars": self.special_chars,
            "exclude_ambiguous": self.exclude_ambiguous,
        }


@dataclass
class UsernameTemplateConfig:
    """Username template configuration."""

    format_type: str = "template"  # template, sequential, email, phone, subscription_id
    template: str = "{email}"  # Template string with placeholders
    domain: Optional[str] = None  # Domain for email-style usernames
    lowercase: bool = True  # Convert to lowercase
    strip_special: bool = True  # Remove special characters
    max_length: int = 64  # Max username length

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsernameTemplateConfig":
        return cls(
            format_type=data.get("format_type", "template"),
            template=data.get("template", "{email}"),
            domain=data.get("domain"),
            lowercase=data.get("lowercase", True),
            strip_special=data.get("strip_special", True),
            max_length=data.get("max_length", 64),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_type": self.format_type,
            "template": self.template,
            "domain": self.domain,
            "lowercase": self.lowercase,
            "strip_special": self.strip_special,
            "max_length": self.max_length,
        }


@dataclass
class SequentialConfig:
    """Sequential username configuration."""

    prefix: str = "USER"
    padding_length: int = 4  # USER0001
    start_from: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SequentialConfig":
        return cls(
            prefix=data.get("prefix", "USER"),
            padding_length=data.get("padding_length", 4),
            start_from=data.get("start_from", 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefix": self.prefix,
            "padding_length": self.padding_length,
            "start_from": self.start_from,
        }


@dataclass
class RADIUSCredentialConfig:
    """Complete RADIUS credential generation configuration."""

    enabled: bool = True
    auto_generate_on_create: bool = True
    notify_on_regenerate: bool = True

    # Username settings
    username: UsernameTemplateConfig = field(default_factory=UsernameTemplateConfig)
    sequential: SequentialConfig = field(default_factory=SequentialConfig)

    # Password settings
    password: PasswordComplexityConfig = field(default_factory=PasswordComplexityConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RADIUSCredentialConfig":
        username_data = data.get("username", {})
        sequential_data = data.get("sequential", {})
        password_data = data.get("password", {})

        return cls(
            enabled=data.get("enabled", True),
            auto_generate_on_create=data.get("auto_generate_on_create", True),
            notify_on_regenerate=data.get("notify_on_regenerate", True),
            username=UsernameTemplateConfig.from_dict(username_data),
            sequential=SequentialConfig.from_dict(sequential_data),
            password=PasswordComplexityConfig.from_dict(password_data),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "auto_generate_on_create": self.auto_generate_on_create,
            "notify_on_regenerate": self.notify_on_regenerate,
            "username": self.username.to_dict(),
            "sequential": self.sequential.to_dict(),
            "password": self.password.to_dict(),
        }


@dataclass
class GeneratedCredentials:
    """Result of credential generation."""

    username: str
    password: str
    generated_at: datetime
    format_used: str


@dataclass
class CredentialGenerationContext:
    """Context data for credential generation."""

    subscription_id: int
    party_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    plan_code: Optional[str] = None
    tariff_name: Optional[str] = None


# =============================================================================
# Configuration Schema
# =============================================================================

RADIUS_CREDENTIAL_CONFIG_SCHEMA = {
    "version": 1,
    "namespace": "subscriptions.radius_credentials",
    "title": "RADIUS Credential Configuration",
    "description": "Settings for automatic RADIUS credential generation",
    "sections": [
        {
            "key": "general",
            "title": "General Settings",
            "fields": ["enabled", "auto_generate_on_create", "notify_on_regenerate"],
        },
        {
            "key": "username",
            "title": "Username Settings",
            "fields": ["username.format_type", "username.template", "username.domain",
                       "username.lowercase", "username.strip_special", "username.max_length"],
        },
        {
            "key": "sequential",
            "title": "Sequential Settings",
            "description": "Settings for sequential username generation (USER0001, USER0002, ...)",
            "condition": {"field": "username.format_type", "equals": "sequential"},
            "fields": ["sequential.prefix", "sequential.padding_length", "sequential.start_from"],
        },
        {
            "key": "password",
            "title": "Password Complexity",
            "fields": ["password.min_length", "password.max_length", "password.include_lowercase",
                       "password.include_uppercase", "password.include_digits", "password.include_special",
                       "password.special_chars", "password.exclude_ambiguous"],
        },
    ],
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": True,
            "label": "Enable Credential Generation",
            "description": "Enable automatic RADIUS credential generation",
        },
        "auto_generate_on_create": {
            "type": "boolean",
            "default": True,
            "label": "Auto-Generate on Create",
            "description": "Automatically generate credentials when subscription is created",
        },
        "notify_on_regenerate": {
            "type": "boolean",
            "default": True,
            "label": "Notify on Regenerate",
            "description": "Send notification when credentials are regenerated",
        },
        "username": {
            "type": "object",
            "properties": {
                "format_type": {
                    "type": "string",
                    "enum": ["template", "sequential", "email", "phone", "subscription_id"],
                    "default": "template",
                    "label": "Username Format",
                    "description": "How usernames should be generated",
                },
                "template": {
                    "type": "string",
                    "default": "{email}",
                    "label": "Template Pattern",
                    "description": "Template with placeholders: {email}, {phone}, {party_id}, {subscription_id}, {first_name}, {last_name}, {plan_code}, {tariff_name}, {domain}",
                },
                "domain": {
                    "type": "string",
                    "default": None,
                    "label": "Domain",
                    "description": "Domain for {domain} placeholder or email-style usernames",
                },
                "lowercase": {
                    "type": "boolean",
                    "default": True,
                    "label": "Lowercase",
                    "description": "Convert username to lowercase",
                },
                "strip_special": {
                    "type": "boolean",
                    "default": True,
                    "label": "Strip Special Characters",
                    "description": "Remove special characters from username",
                },
                "max_length": {
                    "type": "integer",
                    "minimum": 8,
                    "maximum": 128,
                    "default": 64,
                    "label": "Max Length",
                    "description": "Maximum username length",
                },
            },
        },
        "sequential": {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "default": "USER",
                    "maxLength": 20,
                    "label": "Prefix",
                    "description": "Prefix for sequential usernames (e.g., USER0001)",
                },
                "padding_length": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 4,
                    "label": "Padding Length",
                    "description": "Number of digits (e.g., 4 = USER0001)",
                },
                "start_from": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "label": "Start From",
                    "description": "Starting number for sequence",
                },
            },
        },
        "password": {
            "type": "object",
            "properties": {
                "min_length": {
                    "type": "integer",
                    "minimum": 8,
                    "maximum": 32,
                    "default": 12,
                    "label": "Minimum Length",
                },
                "max_length": {
                    "type": "integer",
                    "minimum": 8,
                    "maximum": 64,
                    "default": 16,
                    "label": "Maximum Length",
                },
                "include_lowercase": {
                    "type": "boolean",
                    "default": True,
                    "label": "Include Lowercase Letters",
                },
                "include_uppercase": {
                    "type": "boolean",
                    "default": True,
                    "label": "Include Uppercase Letters",
                },
                "include_digits": {
                    "type": "boolean",
                    "default": True,
                    "label": "Include Digits",
                },
                "include_special": {
                    "type": "boolean",
                    "default": True,
                    "label": "Include Special Characters",
                },
                "special_chars": {
                    "type": "string",
                    "default": "!@#$%^&*",
                    "maxLength": 20,
                    "label": "Special Characters",
                    "description": "Allowed special characters",
                },
                "exclude_ambiguous": {
                    "type": "boolean",
                    "default": True,
                    "label": "Exclude Ambiguous Characters",
                    "description": "Exclude characters that look similar (0/O, 1/l/I)",
                },
            },
        },
    },
}

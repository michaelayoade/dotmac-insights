"""RADIUS credential configuration service.

Module-specific settings for RADIUS credential generation.
Settings are stored in the database via SettingGroup model.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from .radius_credentials_types import (
    RADIUSCredentialConfig,
    RADIUS_CREDENTIAL_CONFIG_SCHEMA,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    "RADIUSCredentialConfigService",
    "get_radius_credential_config",
]


# =============================================================================
# Configuration Service
# =============================================================================

SETTINGS_GROUP = "subscriptions.radius_credentials"


def _get_schema_defaults() -> Dict[str, Any]:
    """Extract default values from schema."""
    defaults = {}
    props = RADIUS_CREDENTIAL_CONFIG_SCHEMA.get("properties", {})

    for key, prop in props.items():
        if "default" in prop:
            defaults[key] = prop["default"]
        elif prop.get("type") == "object" and "properties" in prop:
            # Handle nested objects
            nested_defaults = {}
            for nested_key, nested_prop in prop["properties"].items():
                if "default" in nested_prop:
                    nested_defaults[nested_key] = nested_prop["default"]
            if nested_defaults:
                defaults[key] = nested_defaults

    return defaults


class RADIUSCredentialConfigService:
    """Service for managing RADIUS credential generation configuration.

    This service owns the credential generation settings and provides:
    - Typed access to configuration
    - Settings CRUD operations
    - Username format helpers
    - Validation helpers
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._config: Optional[RADIUSCredentialConfig] = None

    def get_config(self, use_cache: bool = True) -> RADIUSCredentialConfig:
        """Get credential generation configuration.

        Args:
            use_cache: Use cached config if available.

        Returns:
            RADIUSCredentialConfig instance.
        """
        if use_cache and self._config is not None:
            return self._config

        self._config = self._load_config()
        return self._config

    def save_config(self, config: RADIUSCredentialConfig) -> RADIUSCredentialConfig:
        """Save credential generation configuration.

        Args:
            config: Configuration to save.

        Returns:
            Saved configuration.
        """
        self._save_to_db(config.to_dict())
        self._config = config
        return config

    def update_config(self, updates: Dict[str, Any]) -> RADIUSCredentialConfig:
        """Update specific configuration values.

        Args:
            updates: Dictionary of values to update.

        Returns:
            Updated configuration.
        """
        current = self.get_config(use_cache=False)
        current_dict = current.to_dict()

        # Deep merge for nested objects
        for key, value in updates.items():
            if isinstance(value, dict) and key in current_dict and isinstance(current_dict[key], dict):
                current_dict[key].update(value)
            else:
                current_dict[key] = value

        new_config = RADIUSCredentialConfig.from_dict(current_dict)
        return self.save_config(new_config)

    def reset_to_defaults(self) -> RADIUSCredentialConfig:
        """Reset configuration to defaults.

        Returns:
            Default configuration.
        """
        defaults = _get_schema_defaults()
        config = RADIUSCredentialConfig.from_dict(defaults)
        return self.save_config(config)

    def get_schema(self) -> Dict[str, Any]:
        """Get the settings schema for UI rendering."""
        return RADIUS_CREDENTIAL_CONFIG_SCHEMA

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Check if credential generation is enabled."""
        return self.get_config().enabled

    def should_auto_generate(self) -> bool:
        """Check if credentials should be auto-generated on create."""
        config = self.get_config()
        return config.enabled and config.auto_generate_on_create

    def should_notify_on_regenerate(self) -> bool:
        """Check if notification should be sent on regenerate."""
        return self.get_config().notify_on_regenerate

    def get_username_format(self) -> str:
        """Get current username format type."""
        return self.get_config().username.format_type

    def is_sequential_format(self) -> bool:
        """Check if sequential username format is configured."""
        return self.get_config().username.format_type == "sequential"

    def get_template(self) -> str:
        """Get username template string."""
        return self.get_config().username.template

    def get_domain(self) -> Optional[str]:
        """Get configured domain for username generation."""
        return self.get_config().username.domain

    # -------------------------------------------------------------------------
    # Password Complexity Helpers
    # -------------------------------------------------------------------------

    def get_password_length_range(self) -> tuple:
        """Get min/max password length.

        Returns:
            Tuple of (min_length, max_length).
        """
        config = self.get_config()
        return (config.password.min_length, config.password.max_length)

    def get_password_char_pool(self) -> str:
        """Build character pool for password generation.

        Returns:
            String of allowed characters.
        """
        config = self.get_config().password
        pool = ""

        lowercase = "abcdefghijklmnopqrstuvwxyz"
        uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"

        # Exclude ambiguous characters if configured
        if config.exclude_ambiguous:
            lowercase = lowercase.replace("l", "")
            uppercase = uppercase.replace("I", "").replace("O", "")
            digits = digits.replace("0", "").replace("1", "")

        if config.include_lowercase:
            pool += lowercase
        if config.include_uppercase:
            pool += uppercase
        if config.include_digits:
            pool += digits
        if config.include_special:
            pool += config.special_chars

        return pool

    # -------------------------------------------------------------------------
    # Sequential Config Helpers
    # -------------------------------------------------------------------------

    def get_sequential_config(self) -> Dict[str, Any]:
        """Get sequential username configuration.

        Returns:
            Dictionary with prefix, padding_length, start_from.
        """
        config = self.get_config()
        return {
            "prefix": config.sequential.prefix,
            "padding_length": config.sequential.padding_length,
            "start_from": config.sequential.start_from,
        }

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _load_config(self) -> RADIUSCredentialConfig:
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
                return RADIUSCredentialConfig.from_dict(data)

        except Exception as e:
            logger.warning(
                "Failed to load RADIUS credential config, using defaults: %s",
                str(e),
            )

        # Return defaults
        return RADIUSCredentialConfig.from_dict(_get_schema_defaults())

    def _save_to_db(self, data: Dict[str, Any]) -> None:
        """Save configuration to database."""
        from app.models.settings import SettingGroup

        data_json = json.dumps(data)

        stmt = insert(SettingGroup).values(
            group=SETTINGS_GROUP,
            data=data_json,
            schema_version=RADIUS_CREDENTIAL_CONFIG_SCHEMA["version"],
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["group"],
            set_={
                "data": data_json,
                "schema_version": RADIUS_CREDENTIAL_CONFIG_SCHEMA["version"],
                "updated_at": stmt.excluded.updated_at,
            },
        )

        self.db.execute(stmt)
        self.db.flush()


def get_radius_credential_config(db: Session) -> RADIUSCredentialConfig:
    """Convenience function to get RADIUS credential config.

    Args:
        db: Database session.

    Returns:
        RADIUSCredentialConfig instance.
    """
    service = RADIUSCredentialConfigService(db)
    return service.get_config()

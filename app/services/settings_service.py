"""
Settings Service

Core service for reading/writing application settings with:
- Encrypted storage via OpenBao Transit
- Redis + local caching
- Schema validation
- Audit logging
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.settings import SettingGroup, SettingsAuditLog
from app.models.auth import User
from app.schemas.settings_schemas import (
    SETTING_SCHEMAS,
    get_schema,
    get_latest_version,
    get_secret_fields,
    get_defaults,
)
from app.services.secrets_service import get_secrets, SecretsServiceError

logger = structlog.get_logger()


class SettingsServiceError(Exception):
    """Base exception for settings service errors."""
    pass


class SettingsValidationError(SettingsServiceError):
    """Raised when settings validation fails."""
    pass


class SettingsCache:
    """
    Two-tier cache: local memory + Redis.

    TTL: 60 seconds for both tiers.
    Invalidation: Explicit on write + pub/sub for multi-instance.
    """

    TTL = 60  # seconds

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local: dict[str, tuple[dict, float]] = {}  # group -> (data, expires_at)

    async def get(self, group: str) -> Optional[dict]:
        """Get cached settings for a group."""
        # Check local cache first
        if group in self._local:
            data, expires_at = self._local[group]
            if time.time() < expires_at:
                return data
            del self._local[group]

        # Check Redis if available
        if self.redis:
            try:
                cached = await self.redis.get(f"settings:{group}")
                if cached:
                    data = json.loads(cached)
                    self._local[group] = (data, time.time() + self.TTL)
                    return data
            except Exception as e:
                logger.warning("redis_cache_get_error", group=group, error=str(e))

        return None

    async def set(self, group: str, data: dict):
        """Cache settings for a group."""
        self._local[group] = (data, time.time() + self.TTL)

        if self.redis:
            try:
                await self.redis.setex(
                    f"settings:{group}",
                    self.TTL,
                    json.dumps(data)
                )
                # Publish invalidation for other instances
                await self.redis.publish("settings:invalidate", group)
            except Exception as e:
                logger.warning("redis_cache_set_error", group=group, error=str(e))

    async def invalidate(self, group: str):
        """Invalidate cache for a group."""
        self._local.pop(group, None)

        if self.redis:
            try:
                await self.redis.delete(f"settings:{group}")
                await self.redis.publish("settings:invalidate", group)
            except Exception as e:
                logger.warning("redis_cache_invalidate_error", group=group, error=str(e))

    def invalidate_local(self, group: str):
        """Invalidate local cache only (called from pub/sub listener)."""
        self._local.pop(group, None)


class SettingsService:
    """
    Main settings service for CRUD operations.
    """

    def __init__(self, db: Session, cache: Optional[SettingsCache] = None):
        self.db = db
        self.cache = cache or SettingsCache()
        self.secrets = get_secrets()

    async def get(self, group: str) -> dict:
        """
        Get settings for a group.

        Returns decrypted settings merged with defaults.
        """
        if group not in SETTING_SCHEMAS:
            raise SettingsServiceError(f"Unknown settings group: {group}")

        # Try cache first
        cached = await self.cache.get(group)
        if cached is not None:
            return cached

        # Load from DB
        result = self.db.execute(
            select(SettingGroup).where(SettingGroup.group_name == group)
        )
        setting = result.scalar_one_or_none()

        if not setting:
            # Return defaults
            data = get_defaults(group)
            await self.cache.set(group, data)
            return data

        # Decrypt
        try:
            decrypted = self.secrets.decrypt(setting.data_encrypted)
            data = json.loads(decrypted)
        except (SecretsServiceError, json.JSONDecodeError) as e:
            logger.error("settings_decrypt_error", group=group, error=str(e))
            raise SettingsServiceError(f"Failed to decrypt settings: {e}") from e

        # Migrate schema if needed
        if setting.schema_version < get_latest_version(group):
            data = self._migrate_schema(group, data, setting.schema_version)

        # Merge with defaults for any missing fields
        defaults = get_defaults(group)
        merged = {**defaults, **data}

        await self.cache.set(group, merged)
        return merged

    async def get_masked(self, group: str) -> dict:
        """Get settings with secrets replaced by ***REDACTED***."""
        data = await self.get(group)
        return self._mask_secrets(group, data)

    async def update(
        self,
        group: str,
        data: dict,
        user: User,
        request: Optional[Request] = None,
    ) -> dict:
        """
        Update settings for a group.

        Validates against schema, encrypts, and stores.
        Creates audit log entry.
        """
        if group not in SETTING_SCHEMAS:
            raise SettingsServiceError(f"Unknown settings group: {group}")

        # Validate against schema
        self._validate(group, data)

        # Get old value for audit
        try:
            old_data = await self.get(group)
        except SettingsServiceError:
            old_data = {}

        # Encrypt
        try:
            encrypted = self.secrets.encrypt(json.dumps(data))
        except SecretsServiceError as e:
            logger.error("settings_encrypt_error", group=group, error=str(e))
            raise SettingsServiceError(f"Failed to encrypt settings: {e}") from e

        # Upsert
        stmt = insert(SettingGroup).values(
            group_name=group,
            schema_version=get_latest_version(group),
            data_encrypted=encrypted,
            updated_by_id=user.id,
            updated_at=func.now(),
        ).on_conflict_do_update(
            index_elements=["group_name"],
            set_={
                "data_encrypted": encrypted,
                "schema_version": get_latest_version(group),
                "updated_at": func.now(),
                "updated_by_id": user.id,
            }
        )
        self.db.execute(stmt)

        # Create audit log
        self._create_audit_log(
            group=group,
            action="update",
            old_data=old_data,
            new_data=data,
            user=user,
            request=request,
        )

        self.db.commit()

        # Invalidate cache
        await self.cache.invalidate(group)

        logger.info("settings_updated", group=group, user_id=user.id)
        return data

    def _validate(self, group: str, data: dict):
        """Validate data against the group's JSON schema."""
        schema = get_schema(group)
        errors = []

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate each field
        for field_name, value in data.items():
            if field_name not in properties:
                continue  # Allow extra fields

            field_schema = properties[field_name]
            field_type = field_schema.get("type")

            if value is None:
                continue

            # Type validation
            if field_type == "string" and not isinstance(value, str):
                errors.append(f"{field_name}: expected string")
            elif field_type == "integer" and not isinstance(value, int):
                errors.append(f"{field_name}: expected integer")
            elif field_type == "boolean" and not isinstance(value, bool):
                errors.append(f"{field_name}: expected boolean")

            # Enum validation
            if "enum" in field_schema and value not in field_schema["enum"]:
                errors.append(f"{field_name}: must be one of {field_schema['enum']}")

            # Range validation for integers
            if field_type == "integer" and isinstance(value, int):
                if "minimum" in field_schema and value < field_schema["minimum"]:
                    errors.append(f"{field_name}: must be >= {field_schema['minimum']}")
                if "maximum" in field_schema and value > field_schema["maximum"]:
                    errors.append(f"{field_name}: must be <= {field_schema['maximum']}")

            # Pattern validation for strings
            if field_type == "string" and isinstance(value, str) and "pattern" in field_schema:
                if not re.match(field_schema["pattern"], value):
                    errors.append(f"{field_name}: invalid format")

            # Email format validation
            if field_schema.get("format") == "email" and isinstance(value, str):
                if not re.match(r"^[^@]+@[^@]+\.[^@]+$", value):
                    errors.append(f"{field_name}: invalid email format")

        if errors:
            raise SettingsValidationError(f"Validation failed: {'; '.join(errors)}")

    def _mask_secrets(self, group: str, data: dict) -> dict:
        """Replace secret field values with ***REDACTED***."""
        secret_fields = get_secret_fields(group)
        masked = dict(data)
        for field in secret_fields:
            if field in masked and masked[field]:
                masked[field] = "***REDACTED***"
        return masked

    def _migrate_schema(self, group: str, data: dict, from_version: int) -> dict:
        """Migrate data through schema versions."""
        current_version = from_version
        latest_version = get_latest_version(group)

        while current_version < latest_version:
            next_version = current_version + 1
            schema = get_schema(group, next_version)
            migrations = schema.get("x-migrations", {})

            migration_fn = migrations.get(f"from_{current_version}")
            if migration_fn and callable(migration_fn):
                data = migration_fn(data)

            current_version = next_version

        return data

    def _create_audit_log(
        self,
        group: str,
        action: str,
        old_data: dict,
        new_data: dict,
        user: User,
        request: Optional[Request] = None,
    ):
        """Create an audit log entry with secrets redacted."""
        old_redacted = json.dumps(self._mask_secrets(group, old_data)) if old_data else None
        new_redacted = json.dumps(self._mask_secrets(group, new_data)) if new_data else None

        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]

        audit = SettingsAuditLog(
            group_name=group,
            action=action,
            old_value_redacted=old_redacted,
            new_value_redacted=new_redacted,
            user_id=user.id,
            user_email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(audit)

    def has_secrets(self, group: str, data: dict) -> bool:
        """Check if data contains any non-redacted secret fields."""
        secret_fields = get_secret_fields(group)
        for field in secret_fields:
            if field in data and data[field] and data[field] != "***REDACTED***":
                return True
        return False

    async def get_audit_log(
        self,
        group: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[SettingsAuditLog]:
        """Get audit log entries."""
        query = select(SettingsAuditLog).order_by(SettingsAuditLog.created_at.desc())

        if group:
            query = query.where(SettingsAuditLog.group_name == group)

        query = query.offset(skip).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars().all())


# Synchronous versions for non-async contexts
class SyncSettingsService:
    """Synchronous version of SettingsService for non-async contexts."""

    def __init__(self, db: Session):
        self.db = db
        self.secrets = get_secrets()
        self._local_cache: dict[str, tuple[dict, float]] = {}

    def get(self, group: str) -> dict:
        """Get settings for a group (sync version)."""
        if group not in SETTING_SCHEMAS:
            raise SettingsServiceError(f"Unknown settings group: {group}")

        # Check local cache
        if group in self._local_cache:
            data, expires_at = self._local_cache[group]
            if time.time() < expires_at:
                return data

        # Load from DB
        result = self.db.execute(
            select(SettingGroup).where(SettingGroup.group_name == group)
        )
        setting = result.scalar_one_or_none()

        if not setting:
            data = get_defaults(group)
            self._local_cache[group] = (data, time.time() + 60)
            return data

        # Decrypt
        try:
            decrypted = self.secrets.decrypt(setting.data_encrypted)
            data = json.loads(decrypted)
        except (SecretsServiceError, json.JSONDecodeError) as e:
            logger.error("settings_decrypt_error", group=group, error=str(e))
            raise SettingsServiceError(f"Failed to decrypt settings: {e}") from e

        # Merge with defaults
        defaults = get_defaults(group)
        merged = {**defaults, **data}

        self._local_cache[group] = (merged, time.time() + 60)
        return merged

    def get_value(self, group: str, key: str, default: Any = None) -> Any:
        """Get a single setting value."""
        try:
            data = self.get(group)
            return data.get(key, default)
        except SettingsServiceError:
            return default

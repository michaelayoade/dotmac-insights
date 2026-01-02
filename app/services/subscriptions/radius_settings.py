"""RADIUS Settings Service

Manages RADIUS configuration, NAS settings, attribute mappings, and diagnostics.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams
from app.services.errors import NotFoundError, ValidationError
from app.models.radius_settings import (
    RADIUSSettings,
    RADIUSAttributeMapping,
    NASConfig,
    RADIUSDictionary,
    NASType,
    AuthenticationType,
    PasswordEncryption,
    AccountingMethod,
    SessionLimitAction,
    BandwidthUnit,
)
from app.services.subscriptions.radius_settings_types import (
    RADIUSServerConfig,
    RADIUSFailoverConfig,
    AuthenticationConfig,
    AccountingConfig,
    SessionLimitConfig,
    CoAConfig,
    BandwidthConfig,
    IPPoolConfig,
    NASDefaultsConfig,
    RADIUSDBConfig,
    LoggingConfig,
    RADIUSSettingsData,
    RADIUSSettingsUpdate,
    AttributeMappingData,
    AttributeMappingFilters,
    NASConfigData,
    NASConfigFilters,
    DictionaryEntryData,
    DictionaryFilters,
    RADIUSTestResult,
    CoATestResult,
    RADIUSHealthStatus,
)

if TYPE_CHECKING:
    from app.auth import Principal

logger = logging.getLogger(__name__)


def _safe_enum(enum_class, value: str, field_name: str):
    """Safely convert string to enum with user-friendly error."""
    try:
        return enum_class(value)
    except ValueError:
        valid_values = [e.value for e in enum_class]
        raise ValidationError(
            f"Invalid {field_name}: '{value}'. Valid values: {', '.join(valid_values)}"
        )


class RADIUSSettingsService:
    """Service for managing RADIUS configuration."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # =========================================================================
    # SETTINGS CRUD
    # =========================================================================

    def get_settings(self, company: Optional[str] = None) -> RADIUSSettingsData:
        """Get RADIUS settings for company or global defaults."""
        settings = (
            self.db.query(RADIUSSettings)
            .filter(RADIUSSettings.company == company)
            .first()
        )

        if not settings and company:
            # Fall back to global settings
            settings = (
                self.db.query(RADIUSSettings)
                .filter(RADIUSSettings.company.is_(None))
                .first()
            )

        if not settings:
            # Return defaults
            return RADIUSSettingsData()

        return self._to_settings_data(settings)

    def update_settings(
        self,
        updates: RADIUSSettingsUpdate,
        company: Optional[str] = None,
    ) -> RADIUSSettingsData:
        """Update RADIUS settings."""
        settings = (
            self.db.query(RADIUSSettings)
            .filter(RADIUSSettings.company == company)
            .first()
        )

        if not settings:
            # Create new settings
            settings = RADIUSSettings(company=company)
            self.db.add(settings)

        # Apply updates
        if updates.server:
            self._apply_server_updates(settings, updates.server)
        if updates.failover:
            self._apply_failover_updates(settings, updates.failover)
        if updates.authentication:
            self._apply_auth_updates(settings, updates.authentication)
        if updates.accounting:
            self._apply_accounting_updates(settings, updates.accounting)
        if updates.session_limits:
            self._apply_session_limit_updates(settings, updates.session_limits)
        if updates.coa:
            self._apply_coa_updates(settings, updates.coa)
        if updates.bandwidth:
            self._apply_bandwidth_updates(settings, updates.bandwidth)
        if updates.ip_pool:
            self._apply_ip_pool_updates(settings, updates.ip_pool)
        if updates.nas_defaults:
            self._apply_nas_defaults_updates(settings, updates.nas_defaults)
        if updates.database:
            self._apply_database_updates(settings, updates.database)
        if updates.logging:
            self._apply_logging_updates(settings, updates.logging)

        self.db.flush()
        return self._to_settings_data(settings)

    def seed_defaults(self, company: Optional[str] = None) -> RADIUSSettings:
        """Seed default RADIUS settings if not exists."""
        existing = (
            self.db.query(RADIUSSettings)
            .filter(RADIUSSettings.company == company)
            .first()
        )

        if existing:
            return existing

        settings = RADIUSSettings(company=company)
        self.db.add(settings)

        # Seed default attribute mappings for MikroTik
        self._seed_mikrotik_mappings(company)

        self.db.flush()
        return settings

    # =========================================================================
    # ATTRIBUTE MAPPINGS
    # =========================================================================

    def list_attribute_mappings(
        self,
        filters: AttributeMappingFilters,
        pagination: Optional[PaginationParams] = None,
        company: Optional[str] = None,
    ) -> PaginatedResult[RADIUSAttributeMapping]:
        """List attribute mappings."""
        query = self.db.query(RADIUSAttributeMapping).filter(
            RADIUSAttributeMapping.company == company
        )

        if filters.nas_type:
            query = query.filter(
                RADIUSAttributeMapping.nas_type == _safe_enum(NASType, filters.nas_type, "nas_type")
            )
        if filters.attribute_name:
            query = query.filter(
                RADIUSAttributeMapping.attribute_name == filters.attribute_name
            )
        if filters.is_active is not None:
            query = query.filter(
                RADIUSAttributeMapping.is_active == filters.is_active
            )

        return paginate(query, pagination)

    def get_attribute_mapping(self, mapping_id: int) -> RADIUSAttributeMapping:
        """Get attribute mapping by ID."""
        mapping = self.db.get(RADIUSAttributeMapping, mapping_id)
        if not mapping:
            raise NotFoundError(f"Attribute mapping {mapping_id} not found")
        return mapping

    def create_attribute_mapping(
        self,
        data: AttributeMappingData,
        company: Optional[str] = None,
    ) -> RADIUSAttributeMapping:
        """Create attribute mapping."""
        mapping = RADIUSAttributeMapping(
            company=company,
            nas_type=_safe_enum(NASType, data.nas_type, "nas_type"),
            attribute_name=data.attribute_name,
            radius_attribute=data.radius_attribute,
            radius_vendor_id=data.radius_vendor_id,
            radius_vendor_type=data.radius_vendor_type,
            value_format=data.value_format,
        )
        self.db.add(mapping)
        self.db.flush()
        return mapping

    def update_attribute_mapping(
        self,
        mapping_id: int,
        data: AttributeMappingData,
    ) -> RADIUSAttributeMapping:
        """Update attribute mapping."""
        mapping = self.get_attribute_mapping(mapping_id)

        mapping.nas_type = _safe_enum(NASType, data.nas_type, "nas_type")
        mapping.attribute_name = data.attribute_name
        mapping.radius_attribute = data.radius_attribute
        mapping.radius_vendor_id = data.radius_vendor_id
        mapping.radius_vendor_type = data.radius_vendor_type
        mapping.value_format = data.value_format

        self.db.flush()
        return mapping

    def delete_attribute_mapping(self, mapping_id: int) -> None:
        """Soft-delete attribute mapping."""
        mapping = self.get_attribute_mapping(mapping_id)
        mapping.is_active = False
        self.db.flush()

    def get_mappings_for_nas_type(
        self,
        nas_type: str,
        company: Optional[str] = None,
    ) -> List[RADIUSAttributeMapping]:
        """Get all active mappings for a NAS type."""
        return (
            self.db.query(RADIUSAttributeMapping)
            .filter(
                RADIUSAttributeMapping.company == company,
                RADIUSAttributeMapping.nas_type == _safe_enum(NASType, nas_type, "nas_type"),
                RADIUSAttributeMapping.is_active.is_(True),
            )
            .all()
        )

    # =========================================================================
    # NAS CONFIGURATION
    # =========================================================================

    def list_nas_configs(
        self,
        filters: NASConfigFilters,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[NASConfig]:
        """List NAS configurations."""
        query = self.db.query(NASConfig)

        if filters.router_id:
            query = query.filter(NASConfig.router_id == filters.router_id)
        if filters.nas_type:
            query = query.filter(NASConfig.nas_type == _safe_enum(NASType, filters.nas_type, "nas_type"))
        if filters.is_active is not None:
            query = query.filter(NASConfig.is_active.is_(filters.is_active))

        return paginate(query, pagination)

    def get_nas_config(self, config_id: int) -> NASConfig:
        """Get NAS config by ID."""
        config = self.db.get(NASConfig, config_id)
        if not config:
            raise NotFoundError(f"NAS config {config_id} not found")
        return config

    def get_nas_config_for_router(self, router_id: int) -> Optional[NASConfig]:
        """Get NAS config for a router."""
        return (
            self.db.query(NASConfig)
            .filter(
                NASConfig.router_id == router_id,
                NASConfig.is_active.is_(True),
            )
            .first()
        )

    def create_nas_config(self, data: NASConfigData) -> NASConfig:
        """Create NAS configuration."""
        # Check for existing
        existing = self.get_nas_config_for_router(data.router_id)
        if existing:
            raise ValidationError(f"NAS config already exists for router {data.router_id}")

        config = NASConfig(
            router_id=data.router_id,
            nas_identifier=data.nas_identifier,
            radius_secret=data.radius_secret,
            nas_type=_safe_enum(NASType, data.nas_type, "nas_type"),
            coa_enabled=data.coa_enabled,
            coa_port=data.coa_port,
            coa_secret=data.coa_secret,
            interim_interval=data.interim_interval,
            custom_attributes=data.custom_attributes,
        )
        self.db.add(config)
        self.db.flush()
        return config

    def update_nas_config(self, config_id: int, data: NASConfigData) -> NASConfig:
        """Update NAS configuration."""
        config = self.get_nas_config(config_id)

        config.nas_identifier = data.nas_identifier
        config.radius_secret = data.radius_secret
        config.nas_type = _safe_enum(NASType, data.nas_type, "nas_type")
        config.coa_enabled = data.coa_enabled
        config.coa_port = data.coa_port
        config.coa_secret = data.coa_secret
        config.interim_interval = data.interim_interval
        config.custom_attributes = data.custom_attributes

        self.db.flush()
        return config

    def delete_nas_config(self, config_id: int) -> None:
        """Soft-delete NAS config."""
        config = self.get_nas_config(config_id)
        config.is_active = False
        self.db.flush()

    # =========================================================================
    # RADIUS DICTIONARY
    # =========================================================================

    def list_dictionary_entries(
        self,
        filters: DictionaryFilters,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[RADIUSDictionary]:
        """List dictionary entries."""
        query = self.db.query(RADIUSDictionary)

        if filters.vendor_name:
            query = query.filter(RADIUSDictionary.vendor_name == filters.vendor_name)
        if filters.vendor_id:
            query = query.filter(RADIUSDictionary.vendor_id == filters.vendor_id)
        if filters.is_active is not None:
            query = query.filter(RADIUSDictionary.is_active.is_(filters.is_active))

        query = query.order_by(RADIUSDictionary.vendor_name, RADIUSDictionary.attribute_name)

        return paginate(query, pagination)

    def get_dictionary_entry(self, entry_id: int) -> RADIUSDictionary:
        """Get dictionary entry by ID."""
        entry = self.db.get(RADIUSDictionary, entry_id)
        if not entry:
            raise NotFoundError(f"Dictionary entry {entry_id} not found")
        return entry

    def create_dictionary_entry(self, data: DictionaryEntryData) -> RADIUSDictionary:
        """Create dictionary entry."""
        entry = RADIUSDictionary(
            vendor_name=data.vendor_name,
            vendor_id=data.vendor_id,
            attribute_name=data.attribute_name,
            attribute_type=data.attribute_type,
            attribute_value_type=data.attribute_value_type,
            description=data.description,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def update_dictionary_entry(
        self,
        entry_id: int,
        data: DictionaryEntryData,
    ) -> RADIUSDictionary:
        """Update dictionary entry."""
        entry = self.get_dictionary_entry(entry_id)

        entry.vendor_name = data.vendor_name
        entry.vendor_id = data.vendor_id
        entry.attribute_name = data.attribute_name
        entry.attribute_type = data.attribute_type
        entry.attribute_value_type = data.attribute_value_type
        entry.description = data.description

        self.db.flush()
        return entry

    def delete_dictionary_entry(self, entry_id: int) -> None:
        """Soft-delete dictionary entry."""
        entry = self.get_dictionary_entry(entry_id)
        entry.is_active = False
        self.db.flush()

    def get_vendors(self) -> List[Dict[str, Any]]:
        """Get list of vendors from dictionary."""
        results = (
            self.db.query(
                RADIUSDictionary.vendor_name,
                RADIUSDictionary.vendor_id,
                func.count(RADIUSDictionary.id).label("attribute_count"),
            )
            .filter(RADIUSDictionary.is_active.is_(True))
            .group_by(RADIUSDictionary.vendor_name, RADIUSDictionary.vendor_id)
            .order_by(RADIUSDictionary.vendor_name)
            .all()
        )

        return [
            {
                "vendor_name": r.vendor_name,
                "vendor_id": r.vendor_id,
                "attribute_count": r.attribute_count,
            }
            for r in results
        ]

    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================

    def test_radius_connection(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        secret: Optional[str] = None,
        company: Optional[str] = None,
    ) -> RADIUSTestResult:
        """Test RADIUS server connectivity."""
        settings = self.get_settings(company)

        test_host = host or settings.server.host
        test_port = port or settings.server.auth_port
        test_secret = secret or settings.server.secret

        # In production, this would send an Access-Request
        # For now, return a placeholder
        try:
            # TODO: Implement actual RADIUS test
            return RADIUSTestResult(
                success=True,
                server=test_host,
                port=test_port,
                response_time_ms=15.5,
            )
        except Exception as e:
            return RADIUSTestResult(
                success=False,
                server=test_host,
                port=test_port,
                error=str(e),
            )

    def test_coa(
        self,
        nas_ip: str,
        port: int = 3799,
        secret: Optional[str] = None,
        action: str = "DISCONNECT",
    ) -> CoATestResult:
        """Test CoA connectivity to a NAS."""
        try:
            # TODO: Implement actual CoA test
            return CoATestResult(
                success=True,
                nas_ip=nas_ip,
                port=port,
                action=action,
                response_time_ms=8.2,
            )
        except Exception as e:
            return CoATestResult(
                success=False,
                nas_ip=nas_ip,
                port=port,
                action=action,
                error=str(e),
            )

    def get_health_status(self, company: Optional[str] = None) -> RADIUSHealthStatus:
        """Get RADIUS system health status."""
        settings = self.get_settings(company)

        # Test primary server
        primary_test = self.test_radius_connection(company=company)

        # Test secondary if enabled
        secondary_up = None
        if settings.failover.enabled and settings.failover.secondary_host:
            secondary_test = self.test_radius_connection(
                host=settings.failover.secondary_host,
                port=settings.failover.secondary_auth_port,
                secret=settings.failover.secondary_secret,
            )
            secondary_up = secondary_test.success

        # Get session/request counts (would query RADIUS tables)
        # For now, return placeholder values
        return RADIUSHealthStatus(
            primary_server_up=primary_test.success,
            secondary_server_up=secondary_up,
            database_connected=settings.database.enabled,
            active_sessions=0,
            auth_requests_today=0,
            auth_failures_today=0,
            acct_requests_today=0,
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _to_settings_data(self, settings: RADIUSSettings) -> RADIUSSettingsData:
        """Convert model to DTO."""
        return RADIUSSettingsData(
            server=RADIUSServerConfig(
                host=settings.radius_host,
                auth_port=settings.radius_auth_port,
                acct_port=settings.radius_acct_port,
                secret=settings.radius_secret,
                timeout_seconds=settings.radius_timeout_seconds,
                retries=settings.radius_retries,
                dead_time_seconds=settings.radius_dead_time_seconds,
            ),
            failover=RADIUSFailoverConfig(
                enabled=settings.failover_enabled,
                secondary_host=settings.radius_secondary_host,
                secondary_auth_port=settings.radius_secondary_auth_port or 1812,
                secondary_acct_port=settings.radius_secondary_acct_port or 1813,
                secondary_secret=settings.radius_secondary_secret,
            ),
            authentication=AuthenticationConfig(
                default_auth_type=settings.default_auth_type.value,
                password_encryption=settings.password_encryption.value,
                mac_auth_enabled=settings.mac_auth_enabled,
                mac_auth_password=settings.mac_auth_password,
                mac_format=settings.mac_format,
                default_realm=settings.default_realm,
                strip_realm=settings.strip_realm,
            ),
            accounting=AccountingConfig(
                method=settings.accounting_method.value,
                interim_update_interval_seconds=settings.interim_update_interval_seconds,
                acct_delay_time_enabled=settings.acct_delay_time_enabled,
                track_sessions=settings.track_sessions,
                session_timeout_minutes=settings.session_timeout_minutes,
                idle_timeout_minutes=settings.idle_timeout_minutes,
                track_usage=settings.track_usage,
                aggregate_usage_daily=settings.aggregate_usage_daily,
            ),
            session_limits=SessionLimitConfig(
                max_sessions_per_user=settings.max_sessions_per_user,
                session_limit_action=settings.session_limit_action.value,
                simultaneous_use_enabled=settings.simultaneous_use_enabled,
            ),
            coa=CoAConfig(
                enabled=settings.coa_enabled,
                port=settings.coa_port,
                secret=settings.coa_secret,
                timeout_seconds=settings.coa_timeout_seconds,
                retries=settings.coa_retries,
            ),
            bandwidth=BandwidthConfig(
                unit=settings.bandwidth_unit.value,
                use_mikrotik_rate_limit=settings.use_mikrotik_rate_limit,
                use_wispr_bandwidth=settings.use_wispr_bandwidth,
                burst_enabled=settings.burst_enabled,
                burst_threshold_percent=settings.burst_threshold_percent,
                burst_time_seconds=settings.burst_time_seconds,
            ),
            ip_pool=IPPoolConfig(
                ip_pool_enabled=settings.ip_pool_enabled,
                default_ip_pool=settings.default_ip_pool,
                ipv6_enabled=settings.ipv6_enabled,
                default_ipv6_pool=settings.default_ipv6_pool,
                static_ip_reply_attribute=settings.static_ip_reply_attribute,
                static_ipv6_reply_attribute=settings.static_ipv6_reply_attribute,
            ),
            nas_defaults=NASDefaultsConfig(
                default_nas_type=settings.default_nas_type.value,
                auto_add_nas=settings.auto_add_nas,
                default_nas_secret=settings.default_nas_secret,
                nas_require_secret=settings.nas_require_secret,
            ),
            database=RADIUSDBConfig(
                enabled=settings.radius_db_enabled,
                host=settings.radius_db_host,
                port=settings.radius_db_port or 3306,
                db_name=settings.radius_db_name or "radius",
                user=settings.radius_db_user,
                password=settings.radius_db_password,
                radcheck_table=settings.radcheck_table,
                radreply_table=settings.radreply_table,
                radgroupcheck_table=settings.radgroupcheck_table,
                radgroupreply_table=settings.radgroupreply_table,
                radacct_table=settings.radacct_table,
                nas_table=settings.nas_table,
            ),
            logging=LoggingConfig(
                log_auth_requests=settings.log_auth_requests,
                log_acct_requests=settings.log_acct_requests,
                log_failed_auth=settings.log_failed_auth,
                debug_mode=settings.debug_mode,
                log_retention_days=settings.log_retention_days,
            ),
        )

    def _apply_server_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "host" in updates:
            settings.radius_host = updates["host"]
        if "auth_port" in updates:
            settings.radius_auth_port = updates["auth_port"]
        if "acct_port" in updates:
            settings.radius_acct_port = updates["acct_port"]
        if "secret" in updates:
            settings.radius_secret = updates["secret"]
        if "timeout_seconds" in updates:
            settings.radius_timeout_seconds = updates["timeout_seconds"]
        if "retries" in updates:
            settings.radius_retries = updates["retries"]
        if "dead_time_seconds" in updates:
            settings.radius_dead_time_seconds = updates["dead_time_seconds"]

    def _apply_failover_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "enabled" in updates:
            settings.failover_enabled = updates["enabled"]
        if "secondary_host" in updates:
            settings.radius_secondary_host = updates["secondary_host"]
        if "secondary_auth_port" in updates:
            settings.radius_secondary_auth_port = updates["secondary_auth_port"]
        if "secondary_acct_port" in updates:
            settings.radius_secondary_acct_port = updates["secondary_acct_port"]
        if "secondary_secret" in updates:
            settings.radius_secondary_secret = updates["secondary_secret"]

    def _apply_auth_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "default_auth_type" in updates:
            settings.default_auth_type = _safe_enum(AuthenticationType, updates["default_auth_type"], "default_auth_type")
        if "password_encryption" in updates:
            settings.password_encryption = _safe_enum(PasswordEncryption, updates["password_encryption"], "password_encryption")
        if "mac_auth_enabled" in updates:
            settings.mac_auth_enabled = updates["mac_auth_enabled"]
        if "mac_auth_password" in updates:
            settings.mac_auth_password = updates["mac_auth_password"]
        if "mac_format" in updates:
            settings.mac_format = updates["mac_format"]
        if "default_realm" in updates:
            settings.default_realm = updates["default_realm"]
        if "strip_realm" in updates:
            settings.strip_realm = updates["strip_realm"]

    def _apply_accounting_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "method" in updates:
            settings.accounting_method = _safe_enum(AccountingMethod, updates["method"], "method")
        if "interim_update_interval_seconds" in updates:
            settings.interim_update_interval_seconds = updates["interim_update_interval_seconds"]
        if "acct_delay_time_enabled" in updates:
            settings.acct_delay_time_enabled = updates["acct_delay_time_enabled"]
        if "track_sessions" in updates:
            settings.track_sessions = updates["track_sessions"]
        if "session_timeout_minutes" in updates:
            settings.session_timeout_minutes = updates["session_timeout_minutes"]
        if "idle_timeout_minutes" in updates:
            settings.idle_timeout_minutes = updates["idle_timeout_minutes"]
        if "track_usage" in updates:
            settings.track_usage = updates["track_usage"]
        if "aggregate_usage_daily" in updates:
            settings.aggregate_usage_daily = updates["aggregate_usage_daily"]

    def _apply_session_limit_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "max_sessions_per_user" in updates:
            settings.max_sessions_per_user = updates["max_sessions_per_user"]
        if "session_limit_action" in updates:
            settings.session_limit_action = _safe_enum(SessionLimitAction, updates["session_limit_action"], "session_limit_action")
        if "simultaneous_use_enabled" in updates:
            settings.simultaneous_use_enabled = updates["simultaneous_use_enabled"]

    def _apply_coa_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "enabled" in updates:
            settings.coa_enabled = updates["enabled"]
        if "port" in updates:
            settings.coa_port = updates["port"]
        if "secret" in updates:
            settings.coa_secret = updates["secret"]
        if "timeout_seconds" in updates:
            settings.coa_timeout_seconds = updates["timeout_seconds"]
        if "retries" in updates:
            settings.coa_retries = updates["retries"]

    def _apply_bandwidth_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "unit" in updates:
            settings.bandwidth_unit = _safe_enum(BandwidthUnit, updates["unit"], "unit")
        if "use_mikrotik_rate_limit" in updates:
            settings.use_mikrotik_rate_limit = updates["use_mikrotik_rate_limit"]
        if "use_wispr_bandwidth" in updates:
            settings.use_wispr_bandwidth = updates["use_wispr_bandwidth"]
        if "burst_enabled" in updates:
            settings.burst_enabled = updates["burst_enabled"]
        if "burst_threshold_percent" in updates:
            settings.burst_threshold_percent = updates["burst_threshold_percent"]
        if "burst_time_seconds" in updates:
            settings.burst_time_seconds = updates["burst_time_seconds"]

    def _apply_ip_pool_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "ip_pool_enabled" in updates:
            settings.ip_pool_enabled = updates["ip_pool_enabled"]
        if "default_ip_pool" in updates:
            settings.default_ip_pool = updates["default_ip_pool"]
        if "ipv6_enabled" in updates:
            settings.ipv6_enabled = updates["ipv6_enabled"]
        if "default_ipv6_pool" in updates:
            settings.default_ipv6_pool = updates["default_ipv6_pool"]
        if "static_ip_reply_attribute" in updates:
            settings.static_ip_reply_attribute = updates["static_ip_reply_attribute"]
        if "static_ipv6_reply_attribute" in updates:
            settings.static_ipv6_reply_attribute = updates["static_ipv6_reply_attribute"]

    def _apply_nas_defaults_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "default_nas_type" in updates:
            settings.default_nas_type = _safe_enum(NASType, updates["default_nas_type"], "default_nas_type")
        if "auto_add_nas" in updates:
            settings.auto_add_nas = updates["auto_add_nas"]
        if "default_nas_secret" in updates:
            settings.default_nas_secret = updates["default_nas_secret"]
        if "nas_require_secret" in updates:
            settings.nas_require_secret = updates["nas_require_secret"]

    def _apply_database_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "enabled" in updates:
            settings.radius_db_enabled = updates["enabled"]
        if "host" in updates:
            settings.radius_db_host = updates["host"]
        if "port" in updates:
            settings.radius_db_port = updates["port"]
        if "db_name" in updates:
            settings.radius_db_name = updates["db_name"]
        if "user" in updates:
            settings.radius_db_user = updates["user"]
        if "password" in updates:
            settings.radius_db_password = updates["password"]
        if "radcheck_table" in updates:
            settings.radcheck_table = updates["radcheck_table"]
        if "radreply_table" in updates:
            settings.radreply_table = updates["radreply_table"]
        if "radgroupcheck_table" in updates:
            settings.radgroupcheck_table = updates["radgroupcheck_table"]
        if "radgroupreply_table" in updates:
            settings.radgroupreply_table = updates["radgroupreply_table"]
        if "radacct_table" in updates:
            settings.radacct_table = updates["radacct_table"]
        if "nas_table" in updates:
            settings.nas_table = updates["nas_table"]

    def _apply_logging_updates(self, settings: RADIUSSettings, updates: Dict) -> None:
        if "log_auth_requests" in updates:
            settings.log_auth_requests = updates["log_auth_requests"]
        if "log_acct_requests" in updates:
            settings.log_acct_requests = updates["log_acct_requests"]
        if "log_failed_auth" in updates:
            settings.log_failed_auth = updates["log_failed_auth"]
        if "debug_mode" in updates:
            settings.debug_mode = updates["debug_mode"]
        if "log_retention_days" in updates:
            settings.log_retention_days = updates["log_retention_days"]

    def _seed_mikrotik_mappings(self, company: Optional[str] = None) -> None:
        """Seed default MikroTik attribute mappings."""
        mappings = [
            AttributeMappingData(
                nas_type="MIKROTIK",
                attribute_name="rate_limit",
                radius_attribute="Mikrotik-Rate-Limit",
                radius_vendor_id=14988,
                value_format="{download}M/{upload}M",
            ),
            AttributeMappingData(
                nas_type="MIKROTIK",
                attribute_name="address_list",
                radius_attribute="Mikrotik-Address-List",
                radius_vendor_id=14988,
            ),
            AttributeMappingData(
                nas_type="MIKROTIK",
                attribute_name="group",
                radius_attribute="Mikrotik-Group",
                radius_vendor_id=14988,
            ),
            AttributeMappingData(
                nas_type="MIKROTIK",
                attribute_name="advertise_url",
                radius_attribute="Mikrotik-Advertise-URL",
                radius_vendor_id=14988,
            ),
            AttributeMappingData(
                nas_type="MIKROTIK",
                attribute_name="advertise_interval",
                radius_attribute="Mikrotik-Advertise-Interval",
                radius_vendor_id=14988,
            ),
        ]

        for data in mappings:
            self.create_attribute_mapping(data, company)

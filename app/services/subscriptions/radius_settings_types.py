"""RADIUS Settings Service Types

DTOs for RADIUS configuration management.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class RADIUSServerConfig:
    """RADIUS server connection configuration."""
    host: str = "localhost"
    auth_port: int = 1812
    acct_port: int = 1813
    secret: Optional[str] = None
    timeout_seconds: int = 5
    retries: int = 3
    dead_time_seconds: int = 120


@dataclass
class RADIUSFailoverConfig:
    """RADIUS failover server configuration."""
    enabled: bool = False
    secondary_host: Optional[str] = None
    secondary_auth_port: int = 1812
    secondary_acct_port: int = 1813
    secondary_secret: Optional[str] = None


@dataclass
class AuthenticationConfig:
    """Authentication settings."""
    default_auth_type: str = "PAP"
    password_encryption: str = "CLEARTEXT"
    mac_auth_enabled: bool = False
    mac_auth_password: Optional[str] = None
    mac_format: str = "XX:XX:XX:XX:XX:XX"
    default_realm: Optional[str] = None
    strip_realm: bool = True


@dataclass
class AccountingConfig:
    """Accounting settings."""
    method: str = "RADIUS"
    interim_update_interval_seconds: int = 300
    acct_delay_time_enabled: bool = True
    track_sessions: bool = True
    session_timeout_minutes: int = 0
    idle_timeout_minutes: int = 0
    track_usage: bool = True
    aggregate_usage_daily: bool = True


@dataclass
class SessionLimitConfig:
    """Session limit settings."""
    max_sessions_per_user: int = 1
    session_limit_action: str = "REJECT"
    simultaneous_use_enabled: bool = True


@dataclass
class CoAConfig:
    """Change of Authorization settings."""
    enabled: bool = True
    port: int = 3799
    secret: Optional[str] = None
    timeout_seconds: int = 5
    retries: int = 3


@dataclass
class BandwidthConfig:
    """Bandwidth control settings."""
    unit: str = "MBPS"
    use_mikrotik_rate_limit: bool = True
    use_wispr_bandwidth: bool = False
    burst_enabled: bool = False
    burst_threshold_percent: int = 100
    burst_time_seconds: int = 10


@dataclass
class IPPoolConfig:
    """IP address pool settings."""
    ip_pool_enabled: bool = True
    default_ip_pool: Optional[str] = None
    ipv6_enabled: bool = False
    default_ipv6_pool: Optional[str] = None
    static_ip_reply_attribute: str = "Framed-IP-Address"
    static_ipv6_reply_attribute: str = "Framed-IPv6-Address"


@dataclass
class NASDefaultsConfig:
    """NAS default settings."""
    default_nas_type: str = "MIKROTIK"
    auto_add_nas: bool = False
    default_nas_secret: Optional[str] = None
    nas_require_secret: bool = True


@dataclass
class RADIUSDBConfig:
    """RADIUS database settings."""
    enabled: bool = True
    host: Optional[str] = None
    port: int = 3306
    db_name: str = "radius"
    user: Optional[str] = None
    password: Optional[str] = None
    radcheck_table: str = "radcheck"
    radreply_table: str = "radreply"
    radgroupcheck_table: str = "radgroupcheck"
    radgroupreply_table: str = "radgroupreply"
    radacct_table: str = "radacct"
    nas_table: str = "nas"


@dataclass
class LoggingConfig:
    """RADIUS logging settings."""
    log_auth_requests: bool = True
    log_acct_requests: bool = True
    log_failed_auth: bool = True
    debug_mode: bool = False
    log_retention_days: int = 90


@dataclass
class RADIUSSettingsData:
    """Complete RADIUS settings."""
    server: RADIUSServerConfig = field(default_factory=RADIUSServerConfig)
    failover: RADIUSFailoverConfig = field(default_factory=RADIUSFailoverConfig)
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    accounting: AccountingConfig = field(default_factory=AccountingConfig)
    session_limits: SessionLimitConfig = field(default_factory=SessionLimitConfig)
    coa: CoAConfig = field(default_factory=CoAConfig)
    bandwidth: BandwidthConfig = field(default_factory=BandwidthConfig)
    ip_pool: IPPoolConfig = field(default_factory=IPPoolConfig)
    nas_defaults: NASDefaultsConfig = field(default_factory=NASDefaultsConfig)
    database: RADIUSDBConfig = field(default_factory=RADIUSDBConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


@dataclass
class RADIUSSettingsUpdate:
    """Partial update for RADIUS settings."""
    server: Optional[Dict[str, Any]] = None
    failover: Optional[Dict[str, Any]] = None
    authentication: Optional[Dict[str, Any]] = None
    accounting: Optional[Dict[str, Any]] = None
    session_limits: Optional[Dict[str, Any]] = None
    coa: Optional[Dict[str, Any]] = None
    bandwidth: Optional[Dict[str, Any]] = None
    ip_pool: Optional[Dict[str, Any]] = None
    nas_defaults: Optional[Dict[str, Any]] = None
    database: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None


# =============================================================================
# ATTRIBUTE MAPPING TYPES
# =============================================================================

@dataclass
class AttributeMappingData:
    """RADIUS attribute mapping."""
    nas_type: str
    attribute_name: str
    radius_attribute: str
    radius_vendor_id: Optional[int] = None
    radius_vendor_type: Optional[int] = None
    value_format: Optional[str] = None


@dataclass
class AttributeMappingFilters:
    """Filters for attribute mappings."""
    nas_type: Optional[str] = None
    attribute_name: Optional[str] = None
    is_active: bool = True


# =============================================================================
# NAS CONFIG TYPES
# =============================================================================

@dataclass
class NASConfigData:
    """NAS-specific RADIUS configuration."""
    router_id: int
    nas_identifier: Optional[str] = None
    radius_secret: Optional[str] = None
    nas_type: str = "MIKROTIK"
    coa_enabled: bool = True
    coa_port: int = 3799
    coa_secret: Optional[str] = None
    interim_interval: Optional[int] = None
    custom_attributes: Optional[Dict[str, Any]] = None


@dataclass
class NASConfigFilters:
    """Filters for NAS configs."""
    router_id: Optional[int] = None
    nas_type: Optional[str] = None
    is_active: bool = True


# =============================================================================
# RADIUS DICTIONARY TYPES
# =============================================================================

@dataclass
class DictionaryEntryData:
    """RADIUS dictionary entry."""
    vendor_name: str
    vendor_id: int
    attribute_name: str
    attribute_type: int
    attribute_value_type: str = "string"
    description: Optional[str] = None


@dataclass
class DictionaryFilters:
    """Filters for dictionary entries."""
    vendor_name: Optional[str] = None
    vendor_id: Optional[int] = None
    is_active: bool = True


# =============================================================================
# TEST/DIAGNOSTIC TYPES
# =============================================================================

@dataclass
class RADIUSTestResult:
    """Result of RADIUS connectivity test."""
    success: bool
    server: str
    port: int
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class CoATestResult:
    """Result of CoA test."""
    success: bool
    nas_ip: str
    port: int
    action: str
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class RADIUSHealthStatus:
    """RADIUS system health status."""
    primary_server_up: bool
    secondary_server_up: Optional[bool] = None
    database_connected: bool = True
    active_sessions: int = 0
    auth_requests_today: int = 0
    auth_failures_today: int = 0
    acct_requests_today: int = 0
    last_auth_time: Optional[datetime] = None
    last_acct_time: Optional[datetime] = None

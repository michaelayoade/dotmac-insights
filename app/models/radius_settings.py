"""RADIUS/NAS Settings Models

Configuration for FreeRADIUS integration, NAS management, and
subscriber authentication/accounting settings.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Text, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class AuthenticationType(str, Enum):
    """RADIUS authentication type"""
    PAP = "PAP"  # Password Authentication Protocol
    CHAP = "CHAP"  # Challenge Handshake Authentication Protocol
    MSCHAP = "MSCHAP"  # Microsoft CHAP
    MSCHAPV2 = "MSCHAPV2"  # Microsoft CHAP v2
    EAP = "EAP"  # Extensible Authentication Protocol


class PasswordEncryption(str, Enum):
    """How passwords are stored"""
    CLEARTEXT = "CLEARTEXT"  # Plain text (for PAP)
    NT_HASH = "NT_HASH"  # NT Hash (for MSCHAP)
    SSHA = "SSHA"  # Salted SHA
    CRYPT = "CRYPT"  # Unix crypt


class AccountingMethod(str, Enum):
    """RADIUS accounting method"""
    RADIUS = "RADIUS"  # Standard RADIUS accounting
    RADIUS_PLUS_COA = "RADIUS_PLUS_COA"  # RADIUS with CoA
    API_ONLY = "API_ONLY"  # Direct API polling only


class SessionLimitAction(str, Enum):
    """What to do when session limit exceeded"""
    REJECT = "REJECT"  # Reject new sessions
    DISCONNECT_OLDEST = "DISCONNECT_OLDEST"  # Disconnect oldest session
    ALLOW = "ALLOW"  # Allow (no limit)


class NASType(str, Enum):
    """NAS/Router vendor type"""
    MIKROTIK = "MIKROTIK"
    CISCO = "CISCO"
    UBIQUITI = "UBIQUITI"
    HUAWEI = "HUAWEI"
    JUNIPER = "JUNIPER"
    OTHER = "OTHER"


class BandwidthUnit(str, Enum):
    """Bandwidth rate limit units"""
    KBPS = "KBPS"  # Kilobits per second
    MBPS = "MBPS"  # Megabits per second
    GBPS = "GBPS"  # Gigabits per second


# =============================================================================
# RADIUS SERVER SETTINGS
# =============================================================================

class RADIUSSettings(Base):
    """Company-wide RADIUS configuration settings"""
    __tablename__ = "radius_settings"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, unique=True, index=True)

    # -------------------------------------------------------------------------
    # RADIUS SERVER CONNECTION
    # -------------------------------------------------------------------------
    # Primary server
    radius_host: Mapped[str] = mapped_column(String(255), nullable=False, default="localhost")
    radius_auth_port: Mapped[int] = mapped_column(nullable=False, default=1812)
    radius_acct_port: Mapped[int] = mapped_column(nullable=False, default=1813)
    radius_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Secondary/failover server
    radius_secondary_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radius_secondary_auth_port: Mapped[int] = mapped_column(nullable=True, default=1812)
    radius_secondary_acct_port: Mapped[int] = mapped_column(nullable=True, default=1813)
    radius_secondary_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failover_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Connection settings
    radius_timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=5)
    radius_retries: Mapped[int] = mapped_column(nullable=False, default=3)
    radius_dead_time_seconds: Mapped[int] = mapped_column(nullable=False, default=120)

    # -------------------------------------------------------------------------
    # AUTHENTICATION SETTINGS
    # -------------------------------------------------------------------------
    default_auth_type: Mapped[AuthenticationType] = mapped_column(
        SAEnum(AuthenticationType, name="authenticationtype"),
        nullable=False, default=AuthenticationType.PAP
    )
    password_encryption: Mapped[PasswordEncryption] = mapped_column(
        SAEnum(PasswordEncryption, name="passwordencryption"),
        nullable=False, default=PasswordEncryption.CLEARTEXT
    )

    # MAC authentication
    mac_auth_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    mac_auth_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mac_format: Mapped[str] = mapped_column(String(50), nullable=False, default="XX:XX:XX:XX:XX:XX")

    # Default realm/domain
    default_realm: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strip_realm: Mapped[bool] = mapped_column(nullable=False, default=True)

    # -------------------------------------------------------------------------
    # ACCOUNTING SETTINGS
    # -------------------------------------------------------------------------
    accounting_method: Mapped[AccountingMethod] = mapped_column(
        SAEnum(AccountingMethod, name="accountingmethod"),
        nullable=False, default=AccountingMethod.RADIUS
    )
    interim_update_interval_seconds: Mapped[int] = mapped_column(nullable=False, default=300)
    acct_delay_time_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Session tracking
    track_sessions: Mapped[bool] = mapped_column(nullable=False, default=True)
    session_timeout_minutes: Mapped[int] = mapped_column(nullable=False, default=0)  # 0 = no timeout
    idle_timeout_minutes: Mapped[int] = mapped_column(nullable=False, default=0)  # 0 = no timeout

    # Data usage tracking
    track_usage: Mapped[bool] = mapped_column(nullable=False, default=True)
    aggregate_usage_daily: Mapped[bool] = mapped_column(nullable=False, default=True)

    # -------------------------------------------------------------------------
    # SESSION LIMITS
    # -------------------------------------------------------------------------
    max_sessions_per_user: Mapped[int] = mapped_column(nullable=False, default=1)
    session_limit_action: Mapped[SessionLimitAction] = mapped_column(
        SAEnum(SessionLimitAction, name="sessionlimitaction"),
        nullable=False, default=SessionLimitAction.REJECT
    )
    simultaneous_use_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    # -------------------------------------------------------------------------
    # CHANGE OF AUTHORIZATION (CoA)
    # -------------------------------------------------------------------------
    coa_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    coa_port: Mapped[int] = mapped_column(nullable=False, default=3799)
    coa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    coa_timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=5)
    coa_retries: Mapped[int] = mapped_column(nullable=False, default=3)

    # -------------------------------------------------------------------------
    # BANDWIDTH CONTROL
    # -------------------------------------------------------------------------
    bandwidth_unit: Mapped[BandwidthUnit] = mapped_column(
        SAEnum(BandwidthUnit, name="bandwidthunit"),
        nullable=False, default=BandwidthUnit.MBPS
    )
    use_mikrotik_rate_limit: Mapped[bool] = mapped_column(nullable=False, default=True)
    use_wispr_bandwidth: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Burst settings
    burst_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    burst_threshold_percent: Mapped[int] = mapped_column(nullable=False, default=100)
    burst_time_seconds: Mapped[int] = mapped_column(nullable=False, default=10)

    # -------------------------------------------------------------------------
    # IP ADDRESS MANAGEMENT
    # -------------------------------------------------------------------------
    ip_pool_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    default_ip_pool: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ipv6_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    default_ipv6_pool: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Static IP settings
    static_ip_reply_attribute: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Framed-IP-Address"
    )
    static_ipv6_reply_attribute: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Framed-IPv6-Address"
    )

    # -------------------------------------------------------------------------
    # NAS DEFAULTS
    # -------------------------------------------------------------------------
    default_nas_type: Mapped[NASType] = mapped_column(
        SAEnum(NASType, name="nastype"),
        nullable=False, default=NASType.MIKROTIK
    )
    auto_add_nas: Mapped[bool] = mapped_column(nullable=False, default=False)
    default_nas_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nas_require_secret: Mapped[bool] = mapped_column(nullable=False, default=True)

    # -------------------------------------------------------------------------
    # RADIUS DATABASE
    # -------------------------------------------------------------------------
    # SQL backend settings
    radius_db_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    radius_db_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radius_db_port: Mapped[int] = mapped_column(nullable=True, default=3306)
    radius_db_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="radius")
    radius_db_user: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    radius_db_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Table names (for custom schemas)
    radcheck_table: Mapped[str] = mapped_column(String(100), nullable=False, default="radcheck")
    radreply_table: Mapped[str] = mapped_column(String(100), nullable=False, default="radreply")
    radgroupcheck_table: Mapped[str] = mapped_column(String(100), nullable=False, default="radgroupcheck")
    radgroupreply_table: Mapped[str] = mapped_column(String(100), nullable=False, default="radgroupreply")
    radacct_table: Mapped[str] = mapped_column(String(100), nullable=False, default="radacct")
    nas_table: Mapped[str] = mapped_column(String(100), nullable=False, default="nas")

    # -------------------------------------------------------------------------
    # LOGGING & DEBUGGING
    # -------------------------------------------------------------------------
    log_auth_requests: Mapped[bool] = mapped_column(nullable=False, default=True)
    log_acct_requests: Mapped[bool] = mapped_column(nullable=False, default=True)
    log_failed_auth: Mapped[bool] = mapped_column(nullable=False, default=True)
    debug_mode: Mapped[bool] = mapped_column(nullable=False, default=False)
    log_retention_days: Mapped[int] = mapped_column(nullable=False, default=90)

    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


# =============================================================================
# RADIUS ATTRIBUTE MAPPINGS
# =============================================================================

class RADIUSAttributeMapping(Base):
    """Custom RADIUS attribute mappings for different NAS types"""
    __tablename__ = "radius_attribute_mappings"
    __table_args__ = (
        UniqueConstraint("company", "nas_type", "attribute_name", name="uq_radius_attr_mapping"),
    )

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)

    nas_type: Mapped[NASType] = mapped_column(
        SAEnum(NASType, name="nastype", create_constraint=False),
        nullable=False
    )

    # Mapping
    attribute_name: Mapped[str] = mapped_column(String(100), nullable=False)
    radius_attribute: Mapped[str] = mapped_column(String(100), nullable=False)
    radius_vendor_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    radius_vendor_type: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Value formatting
    value_format: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# =============================================================================
# NAS/ROUTER CONFIGURATION
# =============================================================================

class NASConfig(Base):
    """Individual NAS/Router RADIUS configuration"""
    __tablename__ = "nas_configs"
    __table_args__ = (
        UniqueConstraint("router_id", name="uq_nas_config_router"),
    )

    id = Column(Integer, primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("routers.id"), nullable=False, index=True)

    # RADIUS client settings (override global)
    nas_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radius_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # NAS type (for attribute mapping)
    nas_type: Mapped[NASType] = mapped_column(
        SAEnum(NASType, name="nastype", create_constraint=False),
        nullable=False, default=NASType.MIKROTIK
    )

    # CoA settings
    coa_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    coa_port: Mapped[int] = mapped_column(nullable=False, default=3799)
    coa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Accounting
    interim_interval: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Custom attributes (JSON)
    custom_attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


# =============================================================================
# RADIUS DICTIONARIES
# =============================================================================

class RADIUSDictionary(Base):
    """Custom RADIUS dictionary entries for vendor-specific attributes"""
    __tablename__ = "radius_dictionaries"
    __table_args__ = (
        UniqueConstraint("vendor_id", "attribute_type", name="uq_radius_dict_attr"),
    )

    id = Column(Integer, primary_key=True)

    # Vendor
    vendor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor_id: Mapped[int] = mapped_column(nullable=False)

    # Attribute
    attribute_name: Mapped[str] = mapped_column(String(100), nullable=False)
    attribute_type: Mapped[int] = mapped_column(nullable=False)
    attribute_value_type: Mapped[str] = mapped_column(String(50), nullable=False, default="string")

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

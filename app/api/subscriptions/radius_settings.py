"""RADIUS Settings API

Configuration endpoints for RADIUS server, NAS, authentication, and accounting.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    RADIUSSettingsService,
    RADIUSSettingsUpdate,
    AttributeMappingData,
    AttributeMappingFilters,
    NASConfigData,
    NASConfigFilters,
    DictionaryEntryData,
    DictionaryFilters,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class ServerConfigSchema(BaseModel):
    """RADIUS server configuration."""
    host: Optional[str] = None
    auth_port: Optional[int] = Field(None, ge=1, le=65535)
    acct_port: Optional[int] = Field(None, ge=1, le=65535)
    secret: Optional[str] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=60)
    retries: Optional[int] = Field(None, ge=0, le=10)
    dead_time_seconds: Optional[int] = Field(None, ge=0)


class FailoverConfigSchema(BaseModel):
    """RADIUS failover configuration."""
    enabled: Optional[bool] = None
    secondary_host: Optional[str] = None
    secondary_auth_port: Optional[int] = Field(None, ge=1, le=65535)
    secondary_acct_port: Optional[int] = Field(None, ge=1, le=65535)
    secondary_secret: Optional[str] = None


class AuthConfigSchema(BaseModel):
    """Authentication configuration."""
    default_auth_type: Optional[str] = None
    password_encryption: Optional[str] = None
    mac_auth_enabled: Optional[bool] = None
    mac_auth_password: Optional[str] = None
    mac_format: Optional[str] = None
    default_realm: Optional[str] = None
    strip_realm: Optional[bool] = None


class AccountingConfigSchema(BaseModel):
    """Accounting configuration."""
    method: Optional[str] = None
    interim_update_interval_seconds: Optional[int] = Field(None, ge=60)
    acct_delay_time_enabled: Optional[bool] = None
    track_sessions: Optional[bool] = None
    session_timeout_minutes: Optional[int] = Field(None, ge=0)
    idle_timeout_minutes: Optional[int] = Field(None, ge=0)
    track_usage: Optional[bool] = None
    aggregate_usage_daily: Optional[bool] = None


class SessionLimitConfigSchema(BaseModel):
    """Session limit configuration."""
    max_sessions_per_user: Optional[int] = Field(None, ge=0)
    session_limit_action: Optional[str] = None
    simultaneous_use_enabled: Optional[bool] = None


class CoAConfigSchema(BaseModel):
    """CoA configuration."""
    enabled: Optional[bool] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    secret: Optional[str] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=60)
    retries: Optional[int] = Field(None, ge=0, le=10)


class BandwidthConfigSchema(BaseModel):
    """Bandwidth configuration."""
    unit: Optional[str] = None
    use_mikrotik_rate_limit: Optional[bool] = None
    use_wispr_bandwidth: Optional[bool] = None
    burst_enabled: Optional[bool] = None
    burst_threshold_percent: Optional[int] = Field(None, ge=0, le=200)
    burst_time_seconds: Optional[int] = Field(None, ge=0)


class IPPoolConfigSchema(BaseModel):
    """IP pool configuration."""
    ip_pool_enabled: Optional[bool] = None
    default_ip_pool: Optional[str] = None
    ipv6_enabled: Optional[bool] = None
    default_ipv6_pool: Optional[str] = None
    static_ip_reply_attribute: Optional[str] = None
    static_ipv6_reply_attribute: Optional[str] = None


class NASDefaultsConfigSchema(BaseModel):
    """NAS defaults configuration."""
    default_nas_type: Optional[str] = None
    auto_add_nas: Optional[bool] = None
    default_nas_secret: Optional[str] = None
    nas_require_secret: Optional[bool] = None


class DatabaseConfigSchema(BaseModel):
    """RADIUS database configuration."""
    enabled: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    db_name: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    radcheck_table: Optional[str] = None
    radreply_table: Optional[str] = None
    radgroupcheck_table: Optional[str] = None
    radgroupreply_table: Optional[str] = None
    radacct_table: Optional[str] = None
    nas_table: Optional[str] = None


class LoggingConfigSchema(BaseModel):
    """Logging configuration."""
    log_auth_requests: Optional[bool] = None
    log_acct_requests: Optional[bool] = None
    log_failed_auth: Optional[bool] = None
    debug_mode: Optional[bool] = None
    log_retention_days: Optional[int] = Field(None, ge=1)


class RADIUSSettingsUpdateSchema(BaseModel):
    """Complete RADIUS settings update."""
    server: Optional[ServerConfigSchema] = None
    failover: Optional[FailoverConfigSchema] = None
    authentication: Optional[AuthConfigSchema] = None
    accounting: Optional[AccountingConfigSchema] = None
    session_limits: Optional[SessionLimitConfigSchema] = None
    coa: Optional[CoAConfigSchema] = None
    bandwidth: Optional[BandwidthConfigSchema] = None
    ip_pool: Optional[IPPoolConfigSchema] = None
    nas_defaults: Optional[NASDefaultsConfigSchema] = None
    database: Optional[DatabaseConfigSchema] = None
    logging: Optional[LoggingConfigSchema] = None


class AttributeMappingSchema(BaseModel):
    """RADIUS attribute mapping."""
    nas_type: str
    attribute_name: str
    radius_attribute: str
    radius_vendor_id: Optional[int] = None
    radius_vendor_type: Optional[int] = None
    value_format: Optional[str] = None


class NASConfigCreateSchema(BaseModel):
    """NAS-specific configuration for creation."""
    router_id: int
    nas_identifier: Optional[str] = None
    radius_secret: Optional[str] = None
    nas_type: str = "MIKROTIK"
    coa_enabled: bool = True
    coa_port: int = Field(3799, ge=1, le=65535)
    coa_secret: Optional[str] = None
    interim_interval: Optional[int] = Field(None, ge=60)
    custom_attributes: Optional[Dict[str, Any]] = None


class NASConfigUpdateSchema(BaseModel):
    """NAS-specific configuration for updates (router_id cannot be changed)."""
    nas_identifier: Optional[str] = None
    radius_secret: Optional[str] = None
    nas_type: str = "MIKROTIK"
    coa_enabled: bool = True
    coa_port: int = Field(3799, ge=1, le=65535)
    coa_secret: Optional[str] = None
    interim_interval: Optional[int] = Field(None, ge=60)
    custom_attributes: Optional[Dict[str, Any]] = None


class DictionaryEntrySchema(BaseModel):
    """RADIUS dictionary entry."""
    vendor_name: str
    vendor_id: int
    attribute_name: str
    attribute_type: int
    attribute_value_type: str = "string"
    description: Optional[str] = None


class TestConnectionSchema(BaseModel):
    """Test connection request."""
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    secret: Optional[str] = None


class TestCoASchema(BaseModel):
    """Test CoA request."""
    nas_ip: str
    port: int = Field(3799, ge=1, le=65535)
    secret: Optional[str] = None
    action: str = "DISCONNECT"


# =============================================================================
# MAIN SETTINGS ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("subscriptions:read"))])
async def get_radius_settings(
    company: Optional[str] = Query(None, description="Company (null for global)"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get RADIUS configuration settings.
    """
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)

    return {
        "server": {
            "host": settings.server.host,
            "auth_port": settings.server.auth_port,
            "acct_port": settings.server.acct_port,
            "secret": "***" if settings.server.secret else None,
            "timeout_seconds": settings.server.timeout_seconds,
            "retries": settings.server.retries,
            "dead_time_seconds": settings.server.dead_time_seconds,
        },
        "failover": {
            "enabled": settings.failover.enabled,
            "secondary_host": settings.failover.secondary_host,
            "secondary_auth_port": settings.failover.secondary_auth_port,
            "secondary_acct_port": settings.failover.secondary_acct_port,
            "secondary_secret": "***" if settings.failover.secondary_secret else None,
        },
        "authentication": {
            "default_auth_type": settings.authentication.default_auth_type,
            "password_encryption": settings.authentication.password_encryption,
            "mac_auth_enabled": settings.authentication.mac_auth_enabled,
            "mac_auth_password": "***" if settings.authentication.mac_auth_password else None,
            "mac_format": settings.authentication.mac_format,
            "default_realm": settings.authentication.default_realm,
            "strip_realm": settings.authentication.strip_realm,
        },
        "accounting": {
            "method": settings.accounting.method,
            "interim_update_interval_seconds": settings.accounting.interim_update_interval_seconds,
            "acct_delay_time_enabled": settings.accounting.acct_delay_time_enabled,
            "track_sessions": settings.accounting.track_sessions,
            "session_timeout_minutes": settings.accounting.session_timeout_minutes,
            "idle_timeout_minutes": settings.accounting.idle_timeout_minutes,
            "track_usage": settings.accounting.track_usage,
            "aggregate_usage_daily": settings.accounting.aggregate_usage_daily,
        },
        "session_limits": {
            "max_sessions_per_user": settings.session_limits.max_sessions_per_user,
            "session_limit_action": settings.session_limits.session_limit_action,
            "simultaneous_use_enabled": settings.session_limits.simultaneous_use_enabled,
        },
        "coa": {
            "enabled": settings.coa.enabled,
            "port": settings.coa.port,
            "secret": "***" if settings.coa.secret else None,
            "timeout_seconds": settings.coa.timeout_seconds,
            "retries": settings.coa.retries,
        },
        "bandwidth": {
            "unit": settings.bandwidth.unit,
            "use_mikrotik_rate_limit": settings.bandwidth.use_mikrotik_rate_limit,
            "use_wispr_bandwidth": settings.bandwidth.use_wispr_bandwidth,
            "burst_enabled": settings.bandwidth.burst_enabled,
            "burst_threshold_percent": settings.bandwidth.burst_threshold_percent,
            "burst_time_seconds": settings.bandwidth.burst_time_seconds,
        },
        "ip_pool": {
            "ip_pool_enabled": settings.ip_pool.ip_pool_enabled,
            "default_ip_pool": settings.ip_pool.default_ip_pool,
            "ipv6_enabled": settings.ip_pool.ipv6_enabled,
            "default_ipv6_pool": settings.ip_pool.default_ipv6_pool,
            "static_ip_reply_attribute": settings.ip_pool.static_ip_reply_attribute,
            "static_ipv6_reply_attribute": settings.ip_pool.static_ipv6_reply_attribute,
        },
        "nas_defaults": {
            "default_nas_type": settings.nas_defaults.default_nas_type,
            "auto_add_nas": settings.nas_defaults.auto_add_nas,
            "nas_require_secret": settings.nas_defaults.nas_require_secret,
        },
        "database": {
            "enabled": settings.database.enabled,
            "host": settings.database.host,
            "port": settings.database.port,
            "db_name": settings.database.db_name,
            "radcheck_table": settings.database.radcheck_table,
            "radreply_table": settings.database.radreply_table,
            "radgroupcheck_table": settings.database.radgroupcheck_table,
            "radgroupreply_table": settings.database.radgroupreply_table,
            "radacct_table": settings.database.radacct_table,
            "nas_table": settings.database.nas_table,
        },
        "logging": {
            "log_auth_requests": settings.logging.log_auth_requests,
            "log_acct_requests": settings.logging.log_acct_requests,
            "log_failed_auth": settings.logging.log_failed_auth,
            "debug_mode": settings.logging.debug_mode,
            "log_retention_days": settings.logging.log_retention_days,
        },
    }


@router.put("", dependencies=[Depends(Require("subscriptions:admin"))])
async def update_radius_settings(
    data: RADIUSSettingsUpdateSchema,
    company: Optional[str] = Query(None, description="Company (null for global)"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Update RADIUS configuration settings.
    """
    service = RADIUSSettingsService(db, principal)

    updates = RADIUSSettingsUpdate(
        server=data.server.model_dump(exclude_unset=True) if data.server else None,
        failover=data.failover.model_dump(exclude_unset=True) if data.failover else None,
        authentication=data.authentication.model_dump(exclude_unset=True) if data.authentication else None,
        accounting=data.accounting.model_dump(exclude_unset=True) if data.accounting else None,
        session_limits=data.session_limits.model_dump(exclude_unset=True) if data.session_limits else None,
        coa=data.coa.model_dump(exclude_unset=True) if data.coa else None,
        bandwidth=data.bandwidth.model_dump(exclude_unset=True) if data.bandwidth else None,
        ip_pool=data.ip_pool.model_dump(exclude_unset=True) if data.ip_pool else None,
        nas_defaults=data.nas_defaults.model_dump(exclude_unset=True) if data.nas_defaults else None,
        database=data.database.model_dump(exclude_unset=True) if data.database else None,
        logging=data.logging.model_dump(exclude_unset=True) if data.logging else None,
    )

    service.update_settings(updates, company)
    db.commit()

    return {"success": True, "message": "RADIUS settings updated"}


@router.post("/seed-defaults", dependencies=[Depends(Require("subscriptions:admin"))])
async def seed_radius_defaults(
    company: Optional[str] = Query(None, description="Company (null for global)"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Seed default RADIUS settings if not exists.
    """
    service = RADIUSSettingsService(db, principal)
    settings = service.seed_defaults(company)
    db.commit()

    return {"success": True, "message": "RADIUS defaults seeded", "id": settings.id}


# =============================================================================
# SECTION-SPECIFIC ENDPOINTS
# =============================================================================

@router.get("/server", dependencies=[Depends(Require("subscriptions:read"))])
async def get_server_config(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get server configuration."""
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)
    return {
        "host": settings.server.host,
        "auth_port": settings.server.auth_port,
        "acct_port": settings.server.acct_port,
        "timeout_seconds": settings.server.timeout_seconds,
        "retries": settings.server.retries,
        "dead_time_seconds": settings.server.dead_time_seconds,
    }


@router.get("/authentication", dependencies=[Depends(Require("subscriptions:read"))])
async def get_auth_config(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get authentication configuration."""
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)
    return {
        "default_auth_type": settings.authentication.default_auth_type,
        "password_encryption": settings.authentication.password_encryption,
        "mac_auth_enabled": settings.authentication.mac_auth_enabled,
        "mac_format": settings.authentication.mac_format,
        "default_realm": settings.authentication.default_realm,
        "strip_realm": settings.authentication.strip_realm,
    }


@router.get("/accounting", dependencies=[Depends(Require("subscriptions:read"))])
async def get_accounting_config(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get accounting configuration."""
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)
    return {
        "method": settings.accounting.method,
        "interim_update_interval_seconds": settings.accounting.interim_update_interval_seconds,
        "acct_delay_time_enabled": settings.accounting.acct_delay_time_enabled,
        "track_sessions": settings.accounting.track_sessions,
        "session_timeout_minutes": settings.accounting.session_timeout_minutes,
        "idle_timeout_minutes": settings.accounting.idle_timeout_minutes,
        "track_usage": settings.accounting.track_usage,
        "aggregate_usage_daily": settings.accounting.aggregate_usage_daily,
    }


@router.get("/coa", dependencies=[Depends(Require("subscriptions:read"))])
async def get_coa_config(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get CoA configuration."""
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)
    return {
        "enabled": settings.coa.enabled,
        "port": settings.coa.port,
        "timeout_seconds": settings.coa.timeout_seconds,
        "retries": settings.coa.retries,
    }


@router.get("/bandwidth", dependencies=[Depends(Require("subscriptions:read"))])
async def get_bandwidth_config(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get bandwidth control configuration."""
    service = RADIUSSettingsService(db, principal)
    settings = service.get_settings(company)
    return {
        "unit": settings.bandwidth.unit,
        "use_mikrotik_rate_limit": settings.bandwidth.use_mikrotik_rate_limit,
        "use_wispr_bandwidth": settings.bandwidth.use_wispr_bandwidth,
        "burst_enabled": settings.bandwidth.burst_enabled,
        "burst_threshold_percent": settings.bandwidth.burst_threshold_percent,
        "burst_time_seconds": settings.bandwidth.burst_time_seconds,
    }


# =============================================================================
# ATTRIBUTE MAPPINGS
# =============================================================================

@router.get("/attribute-mappings", dependencies=[Depends(Require("subscriptions:read"))])
async def list_attribute_mappings(
    nas_type: Optional[str] = Query(None, description="Filter by NAS type"),
    company: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List RADIUS attribute mappings."""
    service = RADIUSSettingsService(db, principal)

    filters = AttributeMappingFilters(nas_type=nas_type)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_attribute_mappings(filters, pagination, company)

    return {
        "items": [
            {
                "id": m.id,
                "nas_type": m.nas_type.value,
                "attribute_name": m.attribute_name,
                "radius_attribute": m.radius_attribute,
                "radius_vendor_id": m.radius_vendor_id,
                "radius_vendor_type": m.radius_vendor_type,
                "value_format": m.value_format,
                "is_active": m.is_active,
            }
            for m in result.items
        ],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/attribute-mappings/{mapping_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_attribute_mapping(
    mapping_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get a single attribute mapping by ID."""
    service = RADIUSSettingsService(db, principal)

    try:
        m = service.get_attribute_mapping(mapping_id)
        return {
            "id": m.id,
            "nas_type": m.nas_type.value,
            "attribute_name": m.attribute_name,
            "radius_attribute": m.radius_attribute,
            "radius_vendor_id": m.radius_vendor_id,
            "radius_vendor_type": m.radius_vendor_type,
            "value_format": m.value_format,
            "is_active": m.is_active,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/attribute-mappings", dependencies=[Depends(Require("subscriptions:admin"))])
async def create_attribute_mapping(
    data: AttributeMappingSchema,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create attribute mapping."""
    service = RADIUSSettingsService(db, principal)

    mapping = service.create_attribute_mapping(
        AttributeMappingData(
            nas_type=data.nas_type,
            attribute_name=data.attribute_name,
            radius_attribute=data.radius_attribute,
            radius_vendor_id=data.radius_vendor_id,
            radius_vendor_type=data.radius_vendor_type,
            value_format=data.value_format,
        ),
        company,
    )
    db.commit()

    return {
        "success": True,
        "id": mapping.id,
        "message": "Attribute mapping created",
    }


@router.put("/attribute-mappings/{mapping_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def update_attribute_mapping(
    data: AttributeMappingSchema,
    mapping_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update attribute mapping."""
    service = RADIUSSettingsService(db, principal)

    try:
        service.update_attribute_mapping(
            mapping_id,
            AttributeMappingData(
                nas_type=data.nas_type,
                attribute_name=data.attribute_name,
                radius_attribute=data.radius_attribute,
                radius_vendor_id=data.radius_vendor_id,
                radius_vendor_type=data.radius_vendor_type,
                value_format=data.value_format,
            ),
        )
        db.commit()
        return {"success": True, "message": "Attribute mapping updated"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/attribute-mappings/{mapping_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def delete_attribute_mapping(
    mapping_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete attribute mapping."""
    service = RADIUSSettingsService(db, principal)

    try:
        service.delete_attribute_mapping(mapping_id)
        db.commit()
        return {"success": True, "message": "Attribute mapping deleted"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# NAS CONFIGURATION
# =============================================================================

@router.get("/nas-configs", dependencies=[Depends(Require("subscriptions:read"))])
async def list_nas_configs(
    router_id: Optional[int] = Query(None, description="Filter by router"),
    nas_type: Optional[str] = Query(None, description="Filter by NAS type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List NAS configurations."""
    service = RADIUSSettingsService(db, principal)

    filters = NASConfigFilters(router_id=router_id, nas_type=nas_type)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_nas_configs(filters, pagination)

    return {
        "items": [
            {
                "id": c.id,
                "router_id": c.router_id,
                "nas_identifier": c.nas_identifier,
                "nas_type": c.nas_type.value,
                "coa_enabled": c.coa_enabled,
                "coa_port": c.coa_port,
                "interim_interval": c.interim_interval,
                "is_active": c.is_active,
            }
            for c in result.items
        ],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/nas-configs/{config_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_nas_config(
    config_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get NAS configuration."""
    service = RADIUSSettingsService(db, principal)

    try:
        config = service.get_nas_config(config_id)
        return {
            "id": config.id,
            "router_id": config.router_id,
            "nas_identifier": config.nas_identifier,
            "nas_type": config.nas_type.value,
            "coa_enabled": config.coa_enabled,
            "coa_port": config.coa_port,
            "interim_interval": config.interim_interval,
            "custom_attributes": config.custom_attributes,
            "is_active": config.is_active,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/nas-configs", dependencies=[Depends(Require("subscriptions:admin"))])
async def create_nas_config(
    data: NASConfigCreateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create NAS configuration."""
    service = RADIUSSettingsService(db, principal)

    try:
        config = service.create_nas_config(
            NASConfigData(
                router_id=data.router_id,
                nas_identifier=data.nas_identifier,
                radius_secret=data.radius_secret,
                nas_type=data.nas_type,
                coa_enabled=data.coa_enabled,
                coa_port=data.coa_port,
                coa_secret=data.coa_secret,
                interim_interval=data.interim_interval,
                custom_attributes=data.custom_attributes,
            )
        )
        db.commit()
        return {"success": True, "id": config.id, "message": "NAS config created"}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/nas-configs/{config_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def update_nas_config(
    data: NASConfigUpdateSchema,
    config_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update NAS configuration. Note: router_id cannot be changed."""
    service = RADIUSSettingsService(db, principal)

    try:
        # Get existing config to preserve router_id
        existing = service.get_nas_config(config_id)
        service.update_nas_config(
            config_id,
            NASConfigData(
                router_id=existing.router_id,
                nas_identifier=data.nas_identifier,
                radius_secret=data.radius_secret,
                nas_type=data.nas_type,
                coa_enabled=data.coa_enabled,
                coa_port=data.coa_port,
                coa_secret=data.coa_secret,
                interim_interval=data.interim_interval,
                custom_attributes=data.custom_attributes,
            )
        )
        db.commit()
        return {"success": True, "message": "NAS config updated"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/nas-configs/{config_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def delete_nas_config(
    config_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete NAS configuration."""
    service = RADIUSSettingsService(db, principal)

    try:
        service.delete_nas_config(config_id)
        db.commit()
        return {"success": True, "message": "NAS config deleted"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# DICTIONARY
# =============================================================================

@router.get("/dictionary", dependencies=[Depends(Require("subscriptions:read"))])
async def list_dictionary_entries(
    vendor_name: Optional[str] = Query(None),
    vendor_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List RADIUS dictionary entries."""
    service = RADIUSSettingsService(db, principal)

    filters = DictionaryFilters(vendor_name=vendor_name, vendor_id=vendor_id)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = service.list_dictionary_entries(filters, pagination)

    return {
        "items": [
            {
                "id": e.id,
                "vendor_name": e.vendor_name,
                "vendor_id": e.vendor_id,
                "attribute_name": e.attribute_name,
                "attribute_type": e.attribute_type,
                "attribute_value_type": e.attribute_value_type,
                "description": e.description,
                "is_active": e.is_active,
            }
            for e in result.items
        ],
        "total": result.total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/dictionary/vendors", dependencies=[Depends(Require("subscriptions:read"))])
async def list_vendors(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List RADIUS vendors."""
    service = RADIUSSettingsService(db, principal)
    vendors = service.get_vendors()
    return {"vendors": vendors}


@router.get("/dictionary/{entry_id}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_dictionary_entry(
    entry_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get a single dictionary entry by ID."""
    service = RADIUSSettingsService(db, principal)

    try:
        e = service.get_dictionary_entry(entry_id)
        return {
            "id": e.id,
            "vendor_name": e.vendor_name,
            "vendor_id": e.vendor_id,
            "attribute_name": e.attribute_name,
            "attribute_type": e.attribute_type,
            "attribute_value_type": e.attribute_value_type,
            "description": e.description,
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dictionary", dependencies=[Depends(Require("subscriptions:admin"))])
async def create_dictionary_entry(
    data: DictionaryEntrySchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create dictionary entry."""
    service = RADIUSSettingsService(db, principal)

    entry = service.create_dictionary_entry(
        DictionaryEntryData(
            vendor_name=data.vendor_name,
            vendor_id=data.vendor_id,
            attribute_name=data.attribute_name,
            attribute_type=data.attribute_type,
            attribute_value_type=data.attribute_value_type,
            description=data.description,
        )
    )
    db.commit()

    return {"success": True, "id": entry.id, "message": "Dictionary entry created"}


@router.put("/dictionary/{entry_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def update_dictionary_entry(
    data: DictionaryEntrySchema,
    entry_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update dictionary entry."""
    service = RADIUSSettingsService(db, principal)

    try:
        service.update_dictionary_entry(
            entry_id,
            DictionaryEntryData(
                vendor_name=data.vendor_name,
                vendor_id=data.vendor_id,
                attribute_name=data.attribute_name,
                attribute_type=data.attribute_type,
                attribute_value_type=data.attribute_value_type,
                description=data.description,
            ),
        )
        db.commit()
        return {"success": True, "message": "Dictionary entry updated"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/dictionary/{entry_id}", dependencies=[Depends(Require("subscriptions:admin"))])
async def delete_dictionary_entry(
    entry_id: int = Path(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete dictionary entry."""
    service = RADIUSSettingsService(db, principal)

    try:
        service.delete_dictionary_entry(entry_id)
        db.commit()
        return {"success": True, "message": "Dictionary entry deleted"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# DIAGNOSTICS
# =============================================================================

@router.post("/test-connection", dependencies=[Depends(Require("subscriptions:admin"))])
async def test_radius_connection(
    data: Optional[TestConnectionSchema] = Body(None),
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Test RADIUS server connectivity."""
    service = RADIUSSettingsService(db, principal)

    result = service.test_radius_connection(
        host=data.host if data else None,
        port=data.port if data else None,
        secret=data.secret if data else None,
        company=company,
    )

    return {
        "success": result.success,
        "server": result.server,
        "port": result.port,
        "response_time_ms": result.response_time_ms,
        "error": result.error,
    }


@router.post("/test-coa", dependencies=[Depends(Require("subscriptions:admin"))])
async def test_coa(
    data: TestCoASchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Test CoA connectivity to a NAS."""
    service = RADIUSSettingsService(db, principal)

    result = service.test_coa(
        nas_ip=data.nas_ip,
        port=data.port,
        secret=data.secret,
        action=data.action,
    )

    return {
        "success": result.success,
        "nas_ip": result.nas_ip,
        "port": result.port,
        "action": result.action,
        "response_time_ms": result.response_time_ms,
        "error": result.error,
    }


@router.get("/health", dependencies=[Depends(Require("subscriptions:read"))])
async def get_radius_health(
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get RADIUS system health status."""
    service = RADIUSSettingsService(db, principal)
    status = service.get_health_status(company)

    return {
        "primary_server_up": status.primary_server_up,
        "secondary_server_up": status.secondary_server_up,
        "database_connected": status.database_connected,
        "active_sessions": status.active_sessions,
        "auth_requests_today": status.auth_requests_today,
        "auth_failures_today": status.auth_failures_today,
        "acct_requests_today": status.acct_requests_today,
        "last_auth_time": status.last_auth_time.isoformat() if status.last_auth_time else None,
        "last_acct_time": status.last_acct_time.isoformat() if status.last_acct_time else None,
    }


# =============================================================================
# REFERENCE DATA
# =============================================================================

@router.get("/auth-types", dependencies=[Depends(Require("subscriptions:read"))])
async def get_auth_types() -> Dict[str, Any]:
    """Get available authentication types."""
    return {
        "types": [
            {"code": "PAP", "label": "PAP", "description": "Password Authentication Protocol"},
            {"code": "CHAP", "label": "CHAP", "description": "Challenge Handshake Authentication Protocol"},
            {"code": "MSCHAP", "label": "MS-CHAP", "description": "Microsoft CHAP"},
            {"code": "MSCHAPV2", "label": "MS-CHAPv2", "description": "Microsoft CHAP version 2"},
            {"code": "EAP", "label": "EAP", "description": "Extensible Authentication Protocol"},
        ]
    }


@router.get("/nas-types", dependencies=[Depends(Require("subscriptions:read"))])
async def get_nas_types() -> Dict[str, Any]:
    """Get available NAS types."""
    return {
        "types": [
            {"code": "MIKROTIK", "label": "MikroTik", "vendor_id": 14988},
            {"code": "CISCO", "label": "Cisco", "vendor_id": 9},
            {"code": "UBIQUITI", "label": "Ubiquiti", "vendor_id": 41112},
            {"code": "HUAWEI", "label": "Huawei", "vendor_id": 2011},
            {"code": "JUNIPER", "label": "Juniper", "vendor_id": 2636},
            {"code": "OTHER", "label": "Other", "vendor_id": None},
        ]
    }


@router.get("/session-limit-actions", dependencies=[Depends(Require("subscriptions:read"))])
async def get_session_limit_actions() -> Dict[str, Any]:
    """Get available session limit actions."""
    return {
        "actions": [
            {"code": "REJECT", "label": "Reject", "description": "Reject new sessions"},
            {"code": "DISCONNECT_OLDEST", "label": "Disconnect Oldest", "description": "Disconnect oldest session"},
            {"code": "ALLOW", "label": "Allow", "description": "Allow unlimited sessions"},
        ]
    }

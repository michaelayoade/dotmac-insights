"""Service Type Configuration.

Module-owned configuration for subscription service types.
Defines rates, features, SLAs, and defaults for each service type.

This follows the module-based settings pattern where each module
owns its configuration schema rather than a centralized settings file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    "SERVICE_TYPE_CONFIG_SCHEMA",
    "ServiceTypeDefinition",
    "ServiceTypeConfig",
    "ServiceTypeConfigService",
    "get_service_type_config",
]


# =============================================================================
# SCHEMA DEFINITION (Module-owned)
# =============================================================================

SERVICE_TYPE_CONFIG_SCHEMA = {
    "version": 1,
    "namespace": "subscriptions.service_types",
    "title": "Service Type Configuration",
    "description": "Configurable settings for subscription service types",
    "properties": {
        # Internet Service Configuration
        "internet": {
            "type": "object",
            "title": "Internet Service",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "label": {"type": "string", "default": "Internet Service"},
                "icon": {"type": "string", "default": "wifi"},
                "default_billing_cycle": {"type": "string", "default": "monthly", "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"]},
                "requires_provisioning": {"type": "boolean", "default": True},
                "requires_router": {"type": "boolean", "default": True},
                "requires_ip": {"type": "boolean", "default": True},
                "access_methods": {"type": "array", "default": ["pppoe", "hotspot", "dhcp", "static"]},
                "default_access_method": {"type": "string", "default": "pppoe"},
                # SLA settings
                "sla_uptime_percent": {"type": "number", "default": 99.5},
                "sla_response_hours": {"type": "integer", "default": 4},
                "sla_resolution_hours": {"type": "integer", "default": 24},
                # Grace period
                "grace_period_days": {"type": "integer", "default": 3},
                "suspend_after_grace": {"type": "boolean", "default": True},
                # Fees
                "installation_fee": {"type": "number", "default": 10000},
                "activation_fee": {"type": "number", "default": 0},
                "early_termination_fee": {"type": "number", "default": 0},
                "reconnection_fee": {"type": "number", "default": 5000},
                # Features
                "allow_data_cap": {"type": "boolean", "default": True},
                "allow_speed_boost": {"type": "boolean", "default": True},
                "allow_ip_change": {"type": "boolean", "default": True},
                "static_ip_fee": {"type": "number", "default": 5000},
            },
        },
        "voice": {
            "type": "object",
            "title": "Voice Service",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "label": {"type": "string", "default": "Voice Service"},
                "icon": {"type": "string", "default": "phone"},
                "default_billing_cycle": {"type": "string", "default": "monthly"},
                "requires_provisioning": {"type": "boolean", "default": True},
                "requires_router": {"type": "boolean", "default": False},
                "requires_ip": {"type": "boolean", "default": False},
                "access_methods": {"type": "array", "default": ["sip", "pri", "pstn"]},
                "default_access_method": {"type": "string", "default": "sip"},
                "sla_uptime_percent": {"type": "number", "default": 99.9},
                "sla_response_hours": {"type": "integer", "default": 2},
                "sla_resolution_hours": {"type": "integer", "default": 8},
                "grace_period_days": {"type": "integer", "default": 1},
                "suspend_after_grace": {"type": "boolean", "default": True},
                "installation_fee": {"type": "number", "default": 5000},
                "activation_fee": {"type": "number", "default": 0},
                "early_termination_fee": {"type": "number", "default": 0},
                "reconnection_fee": {"type": "number", "default": 2500},
                # Voice-specific
                "call_rate_local": {"type": "number", "default": 5},
                "call_rate_mobile": {"type": "number", "default": 15},
                "call_rate_international": {"type": "number", "default": 50},
                "included_minutes": {"type": "integer", "default": 0},
            },
        },
        "bundle": {
            "type": "object",
            "title": "Bundle Service",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "label": {"type": "string", "default": "Bundle Package"},
                "icon": {"type": "string", "default": "package"},
                "default_billing_cycle": {"type": "string", "default": "monthly"},
                "requires_provisioning": {"type": "boolean", "default": True},
                "requires_router": {"type": "boolean", "default": True},
                "requires_ip": {"type": "boolean", "default": True},
                "access_methods": {"type": "array", "default": ["pppoe", "hotspot"]},
                "default_access_method": {"type": "string", "default": "pppoe"},
                "sla_uptime_percent": {"type": "number", "default": 99.5},
                "sla_response_hours": {"type": "integer", "default": 4},
                "sla_resolution_hours": {"type": "integer", "default": 24},
                "grace_period_days": {"type": "integer", "default": 5},
                "suspend_after_grace": {"type": "boolean", "default": True},
                "installation_fee": {"type": "number", "default": 15000},
                "activation_fee": {"type": "number", "default": 0},
                "early_termination_fee": {"type": "number", "default": 0},
                "reconnection_fee": {"type": "number", "default": 7500},
                # Bundle discount
                "bundle_discount_percent": {"type": "number", "default": 10},
            },
        },
        "custom": {
            "type": "object",
            "title": "Custom Service",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "label": {"type": "string", "default": "Custom Service"},
                "icon": {"type": "string", "default": "settings"},
                "default_billing_cycle": {"type": "string", "default": "monthly"},
                "requires_provisioning": {"type": "boolean", "default": False},
                "requires_router": {"type": "boolean", "default": False},
                "requires_ip": {"type": "boolean", "default": False},
                "access_methods": {"type": "array", "default": []},
                "default_access_method": {"type": "string", "default": ""},
                "sla_uptime_percent": {"type": "number", "default": 99.0},
                "sla_response_hours": {"type": "integer", "default": 8},
                "sla_resolution_hours": {"type": "integer", "default": 48},
                "grace_period_days": {"type": "integer", "default": 7},
                "suspend_after_grace": {"type": "boolean", "default": False},
                "installation_fee": {"type": "number", "default": 0},
                "activation_fee": {"type": "number", "default": 0},
                "early_termination_fee": {"type": "number", "default": 0},
                "reconnection_fee": {"type": "number", "default": 0},
            },
        },
        # Lifecycle defaults
        "lifecycle": {
            "type": "object",
            "title": "Lifecycle Settings",
            "properties": {
                "auto_activate_on_payment": {"type": "boolean", "default": True},
                "auto_suspend_on_nonpayment": {"type": "boolean", "default": True},
                "auto_cancel_after_days": {"type": "integer", "default": 30},
                "send_grace_period_notice": {"type": "boolean", "default": True},
                "send_suspension_notice": {"type": "boolean", "default": True},
                "send_cancellation_notice": {"type": "boolean", "default": True},
                "allow_self_reactivation": {"type": "boolean", "default": True},
                "require_payment_for_reactivation": {"type": "boolean", "default": True},
            },
        },
        # Upgrade/downgrade settings
        "plan_changes": {
            "type": "object",
            "title": "Plan Change Settings",
            "properties": {
                "allow_upgrades": {"type": "boolean", "default": True},
                "allow_downgrades": {"type": "boolean", "default": True},
                "upgrade_prorate": {"type": "boolean", "default": True},
                "downgrade_prorate": {"type": "boolean", "default": False},
                "upgrade_effective": {"type": "string", "default": "immediate", "enum": ["immediate", "next_cycle"]},
                "downgrade_effective": {"type": "string", "default": "next_cycle", "enum": ["immediate", "next_cycle"]},
                "upgrade_fee": {"type": "number", "default": 0},
                "downgrade_fee": {"type": "number", "default": 0},
                "min_days_before_downgrade": {"type": "integer", "default": 0},
            },
        },
        # Contract/commitment settings
        "contracts": {
            "type": "object",
            "title": "Contract Settings",
            "properties": {
                "enable_contracts": {"type": "boolean", "default": False},
                "default_commitment_months": {"type": "integer", "default": 12},
                "commitment_options": {"type": "array", "default": [1, 6, 12, 24]},
                "early_termination_fee_type": {"type": "string", "default": "fixed", "enum": ["fixed", "remaining_months", "percentage"]},
                "early_termination_fixed_fee": {"type": "number", "default": 50000},
                "early_termination_percentage": {"type": "number", "default": 50},
                "contract_discount_percent": {"type": "number", "default": 10},
            },
        },
    },
}


# =============================================================================
# CONFIGURATION DATACLASSES
# =============================================================================

@dataclass
class ServiceTypeDefinition:
    """Configuration for a specific service type."""

    type_code: str
    enabled: bool = True
    label: str = ""
    icon: str = "circle"
    default_billing_cycle: str = "monthly"

    # Provisioning requirements
    requires_provisioning: bool = True
    requires_router: bool = False
    requires_ip: bool = False
    access_methods: List[str] = field(default_factory=list)
    default_access_method: str = ""

    # SLA settings
    sla_uptime_percent: Decimal = Decimal("99.5")
    sla_response_hours: int = 4
    sla_resolution_hours: int = 24

    # Grace period
    grace_period_days: int = 3
    suspend_after_grace: bool = True

    # Fees
    installation_fee: Decimal = Decimal("0")
    activation_fee: Decimal = Decimal("0")
    early_termination_fee: Decimal = Decimal("0")
    reconnection_fee: Decimal = Decimal("0")

    # Type-specific settings (stored as dict)
    extra_settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, type_code: str, data: Dict[str, Any]) -> "ServiceTypeDefinition":
        """Create from dictionary."""
        # Extract known fields
        known_fields = {
            "enabled", "label", "icon", "default_billing_cycle",
            "requires_provisioning", "requires_router", "requires_ip",
            "access_methods", "default_access_method",
            "sla_uptime_percent", "sla_response_hours", "sla_resolution_hours",
            "grace_period_days", "suspend_after_grace",
            "installation_fee", "activation_fee", "early_termination_fee", "reconnection_fee",
        }

        extra = {k: v for k, v in data.items() if k not in known_fields}

        return cls(
            type_code=type_code,
            enabled=data.get("enabled", True),
            label=data.get("label", type_code.title()),
            icon=data.get("icon", "circle"),
            default_billing_cycle=data.get("default_billing_cycle", "monthly"),
            requires_provisioning=data.get("requires_provisioning", True),
            requires_router=data.get("requires_router", False),
            requires_ip=data.get("requires_ip", False),
            access_methods=data.get("access_methods", []),
            default_access_method=data.get("default_access_method", ""),
            sla_uptime_percent=Decimal(str(data.get("sla_uptime_percent", 99.5))),
            sla_response_hours=int(data.get("sla_response_hours", 4)),
            sla_resolution_hours=int(data.get("sla_resolution_hours", 24)),
            grace_period_days=int(data.get("grace_period_days", 3)),
            suspend_after_grace=data.get("suspend_after_grace", True),
            installation_fee=Decimal(str(data.get("installation_fee", 0))),
            activation_fee=Decimal(str(data.get("activation_fee", 0))),
            early_termination_fee=Decimal(str(data.get("early_termination_fee", 0))),
            reconnection_fee=Decimal(str(data.get("reconnection_fee", 0))),
            extra_settings=extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "enabled": self.enabled,
            "label": self.label,
            "icon": self.icon,
            "default_billing_cycle": self.default_billing_cycle,
            "requires_provisioning": self.requires_provisioning,
            "requires_router": self.requires_router,
            "requires_ip": self.requires_ip,
            "access_methods": self.access_methods,
            "default_access_method": self.default_access_method,
            "sla_uptime_percent": float(self.sla_uptime_percent),
            "sla_response_hours": self.sla_response_hours,
            "sla_resolution_hours": self.sla_resolution_hours,
            "grace_period_days": self.grace_period_days,
            "suspend_after_grace": self.suspend_after_grace,
            "installation_fee": float(self.installation_fee),
            "activation_fee": float(self.activation_fee),
            "early_termination_fee": float(self.early_termination_fee),
            "reconnection_fee": float(self.reconnection_fee),
        }
        result.update(self.extra_settings)
        return result


@dataclass
class LifecycleSettings:
    """Lifecycle automation settings."""

    auto_activate_on_payment: bool = True
    auto_suspend_on_nonpayment: bool = True
    auto_cancel_after_days: int = 30
    send_grace_period_notice: bool = True
    send_suspension_notice: bool = True
    send_cancellation_notice: bool = True
    allow_self_reactivation: bool = True
    require_payment_for_reactivation: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LifecycleSettings":
        return cls(
            auto_activate_on_payment=data.get("auto_activate_on_payment", True),
            auto_suspend_on_nonpayment=data.get("auto_suspend_on_nonpayment", True),
            auto_cancel_after_days=int(data.get("auto_cancel_after_days", 30)),
            send_grace_period_notice=data.get("send_grace_period_notice", True),
            send_suspension_notice=data.get("send_suspension_notice", True),
            send_cancellation_notice=data.get("send_cancellation_notice", True),
            allow_self_reactivation=data.get("allow_self_reactivation", True),
            require_payment_for_reactivation=data.get("require_payment_for_reactivation", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_activate_on_payment": self.auto_activate_on_payment,
            "auto_suspend_on_nonpayment": self.auto_suspend_on_nonpayment,
            "auto_cancel_after_days": self.auto_cancel_after_days,
            "send_grace_period_notice": self.send_grace_period_notice,
            "send_suspension_notice": self.send_suspension_notice,
            "send_cancellation_notice": self.send_cancellation_notice,
            "allow_self_reactivation": self.allow_self_reactivation,
            "require_payment_for_reactivation": self.require_payment_for_reactivation,
        }


@dataclass
class PlanChangeSettings:
    """Plan upgrade/downgrade settings."""

    allow_upgrades: bool = True
    allow_downgrades: bool = True
    upgrade_prorate: bool = True
    downgrade_prorate: bool = False
    upgrade_effective: str = "immediate"  # immediate, next_cycle
    downgrade_effective: str = "next_cycle"
    upgrade_fee: Decimal = Decimal("0")
    downgrade_fee: Decimal = Decimal("0")
    min_days_before_downgrade: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanChangeSettings":
        return cls(
            allow_upgrades=data.get("allow_upgrades", True),
            allow_downgrades=data.get("allow_downgrades", True),
            upgrade_prorate=data.get("upgrade_prorate", True),
            downgrade_prorate=data.get("downgrade_prorate", False),
            upgrade_effective=data.get("upgrade_effective", "immediate"),
            downgrade_effective=data.get("downgrade_effective", "next_cycle"),
            upgrade_fee=Decimal(str(data.get("upgrade_fee", 0))),
            downgrade_fee=Decimal(str(data.get("downgrade_fee", 0))),
            min_days_before_downgrade=int(data.get("min_days_before_downgrade", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_upgrades": self.allow_upgrades,
            "allow_downgrades": self.allow_downgrades,
            "upgrade_prorate": self.upgrade_prorate,
            "downgrade_prorate": self.downgrade_prorate,
            "upgrade_effective": self.upgrade_effective,
            "downgrade_effective": self.downgrade_effective,
            "upgrade_fee": float(self.upgrade_fee),
            "downgrade_fee": float(self.downgrade_fee),
            "min_days_before_downgrade": self.min_days_before_downgrade,
        }


@dataclass
class ContractSettings:
    """Contract/commitment settings."""

    enable_contracts: bool = False
    default_commitment_months: int = 12
    commitment_options: List[int] = field(default_factory=lambda: [1, 6, 12, 24])
    early_termination_fee_type: str = "fixed"  # fixed, remaining_months, percentage
    early_termination_fixed_fee: Decimal = Decimal("50000")
    early_termination_percentage: Decimal = Decimal("50")
    contract_discount_percent: Decimal = Decimal("10")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContractSettings":
        return cls(
            enable_contracts=data.get("enable_contracts", False),
            default_commitment_months=int(data.get("default_commitment_months", 12)),
            commitment_options=data.get("commitment_options", [1, 6, 12, 24]),
            early_termination_fee_type=data.get("early_termination_fee_type", "fixed"),
            early_termination_fixed_fee=Decimal(str(data.get("early_termination_fixed_fee", 50000))),
            early_termination_percentage=Decimal(str(data.get("early_termination_percentage", 50))),
            contract_discount_percent=Decimal(str(data.get("contract_discount_percent", 10))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enable_contracts": self.enable_contracts,
            "default_commitment_months": self.default_commitment_months,
            "commitment_options": self.commitment_options,
            "early_termination_fee_type": self.early_termination_fee_type,
            "early_termination_fixed_fee": float(self.early_termination_fixed_fee),
            "early_termination_percentage": float(self.early_termination_percentage),
            "contract_discount_percent": float(self.contract_discount_percent),
        }


@dataclass
class ServiceTypeConfig:
    """Complete service type configuration."""

    internet: ServiceTypeDefinition = field(default_factory=lambda: ServiceTypeDefinition(type_code="internet"))
    voice: ServiceTypeDefinition = field(default_factory=lambda: ServiceTypeDefinition(type_code="voice"))
    bundle: ServiceTypeDefinition = field(default_factory=lambda: ServiceTypeDefinition(type_code="bundle"))
    custom: ServiceTypeDefinition = field(default_factory=lambda: ServiceTypeDefinition(type_code="custom"))
    lifecycle: LifecycleSettings = field(default_factory=LifecycleSettings)
    plan_changes: PlanChangeSettings = field(default_factory=PlanChangeSettings)
    contracts: ContractSettings = field(default_factory=ContractSettings)

    def get_type(self, type_code: str) -> Optional[ServiceTypeDefinition]:
        """Get service type definition by code."""
        type_map = {
            "internet": self.internet,
            "voice": self.voice,
            "bundle": self.bundle,
            "custom": self.custom,
        }
        return type_map.get(type_code)

    def get_enabled_types(self) -> List[ServiceTypeDefinition]:
        """Get list of enabled service types."""
        return [t for t in [self.internet, self.voice, self.bundle, self.custom] if t.enabled]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceTypeConfig":
        """Create from dictionary."""
        return cls(
            internet=ServiceTypeDefinition.from_dict("internet", data.get("internet", {})),
            voice=ServiceTypeDefinition.from_dict("voice", data.get("voice", {})),
            bundle=ServiceTypeDefinition.from_dict("bundle", data.get("bundle", {})),
            custom=ServiceTypeDefinition.from_dict("custom", data.get("custom", {})),
            lifecycle=LifecycleSettings.from_dict(data.get("lifecycle", {})),
            plan_changes=PlanChangeSettings.from_dict(data.get("plan_changes", {})),
            contracts=ContractSettings.from_dict(data.get("contracts", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "internet": self.internet.to_dict(),
            "voice": self.voice.to_dict(),
            "bundle": self.bundle.to_dict(),
            "custom": self.custom.to_dict(),
            "lifecycle": self.lifecycle.to_dict(),
            "plan_changes": self.plan_changes.to_dict(),
            "contracts": self.contracts.to_dict(),
        }


# =============================================================================
# CONFIGURATION SERVICE
# =============================================================================

class ServiceTypeConfigService:
    """Service for managing service type configuration."""

    NAMESPACE = "subscriptions.service_types"

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._cache: Optional[ServiceTypeConfig] = None

    def get_config(self, use_cache: bool = True) -> ServiceTypeConfig:
        """Get service type configuration."""
        if use_cache and self._cache is not None:
            return self._cache

        from app.models.settings import SettingGroup

        setting = (
            self.db.query(SettingGroup)
            .filter(SettingGroup.namespace == self.NAMESPACE)
            .first()
        )

        if setting and setting.settings:
            config = ServiceTypeConfig.from_dict(setting.settings)
        else:
            config = ServiceTypeConfig()

        self._cache = config
        return config

    def save_config(self, config: ServiceTypeConfig) -> ServiceTypeConfig:
        """Save service type configuration."""
        from app.models.settings import SettingGroup

        setting = (
            self.db.query(SettingGroup)
            .filter(SettingGroup.namespace == self.NAMESPACE)
            .first()
        )

        if setting:
            setting.settings = config.to_dict()
            setting.updated_by_id = self.principal.id if self.principal else None
        else:
            setting = SettingGroup(
                namespace=self.NAMESPACE,
                name="Service Type Configuration",
                description="Settings for subscription service types",
                settings=config.to_dict(),
                schema=SERVICE_TYPE_CONFIG_SCHEMA,
                created_by_id=self.principal.id if self.principal else None,
            )
            self.db.add(setting)

        self.db.flush()
        self._cache = config
        return config

    def update_type(self, type_code: str, updates: Dict[str, Any]) -> ServiceTypeConfig:
        """Update a specific service type configuration."""
        config = self.get_config(use_cache=False)
        type_def = config.get_type(type_code)

        if not type_def:
            raise ValueError(f"Unknown service type: {type_code}")

        # Get current dict, merge updates, recreate
        current_dict = config.to_dict()
        current_dict[type_code].update(updates)

        new_config = ServiceTypeConfig.from_dict(current_dict)
        return self.save_config(new_config)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def get_type_definition(self, type_code: str) -> Optional[ServiceTypeDefinition]:
        """Get definition for a service type."""
        config = self.get_config()
        return config.get_type(type_code)

    def is_type_enabled(self, type_code: str) -> bool:
        """Check if a service type is enabled."""
        type_def = self.get_type_definition(type_code)
        return type_def.enabled if type_def else False

    def get_grace_period_days(self, type_code: str) -> int:
        """Get grace period for a service type."""
        type_def = self.get_type_definition(type_code)
        return type_def.grace_period_days if type_def else 3

    def get_installation_fee(self, type_code: str) -> Decimal:
        """Get installation fee for a service type."""
        type_def = self.get_type_definition(type_code)
        return type_def.installation_fee if type_def else Decimal("0")

    def get_reconnection_fee(self, type_code: str) -> Decimal:
        """Get reconnection fee for a service type."""
        type_def = self.get_type_definition(type_code)
        return type_def.reconnection_fee if type_def else Decimal("0")

    def requires_provisioning(self, type_code: str) -> bool:
        """Check if service type requires provisioning."""
        type_def = self.get_type_definition(type_code)
        return type_def.requires_provisioning if type_def else False

    def get_access_methods(self, type_code: str) -> List[str]:
        """Get available access methods for a service type."""
        type_def = self.get_type_definition(type_code)
        return type_def.access_methods if type_def else []

    def can_upgrade(self) -> bool:
        """Check if upgrades are allowed."""
        config = self.get_config()
        return config.plan_changes.allow_upgrades

    def can_downgrade(self) -> bool:
        """Check if downgrades are allowed."""
        config = self.get_config()
        return config.plan_changes.allow_downgrades

    def get_upgrade_fee(self) -> Decimal:
        """Get upgrade fee."""
        config = self.get_config()
        return config.plan_changes.upgrade_fee

    def get_downgrade_fee(self) -> Decimal:
        """Get downgrade fee."""
        config = self.get_config()
        return config.plan_changes.downgrade_fee

    def calculate_early_termination_fee(
        self,
        monthly_price: Decimal,
        remaining_months: int,
    ) -> Decimal:
        """Calculate early termination fee based on contract settings."""
        config = self.get_config()
        contracts = config.contracts

        if not contracts.enable_contracts:
            return Decimal("0")

        if contracts.early_termination_fee_type == "fixed":
            return contracts.early_termination_fixed_fee
        elif contracts.early_termination_fee_type == "remaining_months":
            return monthly_price * remaining_months
        elif contracts.early_termination_fee_type == "percentage":
            total_remaining = monthly_price * remaining_months
            return total_remaining * (contracts.early_termination_percentage / 100)

        return Decimal("0")

    def get_enabled_types_for_dropdown(self) -> List[Dict[str, str]]:
        """Get enabled types formatted for dropdown/select."""
        config = self.get_config()
        return [
            {"value": t.type_code, "label": t.label, "icon": t.icon}
            for t in config.get_enabled_types()
        ]


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_service_type_config(db: Session) -> ServiceTypeConfig:
    """Get service type configuration (convenience function)."""
    service = ServiceTypeConfigService(db)
    return service.get_config()

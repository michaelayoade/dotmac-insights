"""Field Service Billing Configuration.

Module-owned configuration for field service rates and billing settings.
Stored in SettingGroup with namespace 'field_service.billing'.

This follows the module-based settings pattern where each module
owns its configuration schema rather than a centralized settings file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    "FIELD_SERVICE_BILLING_SCHEMA",
    "FieldServiceBillingConfig",
    "FieldServiceBillingConfigService",
    "get_field_service_billing_config",
]


# =============================================================================
# SCHEMA DEFINITION (Module-owned)
# =============================================================================

FIELD_SERVICE_BILLING_SCHEMA = {
    "version": 1,
    "namespace": "field_service.billing",
    "title": "Field Service Billing Configuration",
    "description": "Configurable rates and settings for field service billing",
    "properties": {
        # General settings
        "enabled": {
            "type": "boolean",
            "default": True,
            "title": "Enable Billing",
            "description": "Enable/disable field service billing",
        },
        "default_currency": {
            "type": "string",
            "default": "NGN",
            "title": "Default Currency",
            "description": "Default currency for billing",
        },
        "tax_rate": {
            "type": "number",
            "default": 7.5,
            "title": "Tax Rate (%)",
            "description": "Default VAT/tax rate for services",
            "minimum": 0,
            "maximum": 100,
        },
        "tax_inclusive": {
            "type": "boolean",
            "default": False,
            "title": "Tax Inclusive Pricing",
            "description": "Whether quoted rates include tax",
        },

        # Labor rates
        "labor_rate_standard": {
            "type": "number",
            "default": 5000,
            "title": "Standard Labor Rate",
            "description": "Hourly rate for standard labor (per hour)",
        },
        "labor_rate_senior": {
            "type": "number",
            "default": 7500,
            "title": "Senior Technician Rate",
            "description": "Hourly rate for senior technicians",
        },
        "labor_rate_specialist": {
            "type": "number",
            "default": 10000,
            "title": "Specialist Rate",
            "description": "Hourly rate for specialists/experts",
        },
        "labor_minimum_hours": {
            "type": "number",
            "default": 1,
            "title": "Minimum Billable Hours",
            "description": "Minimum hours charged per service call",
        },
        "labor_rounding_minutes": {
            "type": "integer",
            "default": 15,
            "title": "Time Rounding (minutes)",
            "description": "Round labor time to nearest X minutes",
            "enum": [1, 5, 10, 15, 30, 60],
        },

        # Travel rates
        "travel_rate_enabled": {
            "type": "boolean",
            "default": True,
            "title": "Charge for Travel",
            "description": "Whether to bill for travel time",
        },
        "travel_rate_hourly": {
            "type": "number",
            "default": 2000,
            "title": "Travel Hourly Rate",
            "description": "Hourly rate for travel time",
        },
        "travel_rate_per_km": {
            "type": "number",
            "default": 100,
            "title": "Travel Rate per KM",
            "description": "Rate per kilometer for travel (alternative to hourly)",
        },
        "travel_billing_method": {
            "type": "string",
            "default": "hourly",
            "title": "Travel Billing Method",
            "description": "How to calculate travel charges",
            "enum": ["hourly", "per_km", "flat_rate", "none"],
        },
        "travel_flat_rate": {
            "type": "number",
            "default": 5000,
            "title": "Flat Travel Rate",
            "description": "Flat rate for travel (if billing method is flat_rate)",
        },
        "travel_free_radius_km": {
            "type": "number",
            "default": 10,
            "title": "Free Travel Radius (km)",
            "description": "No travel charge within this radius",
        },

        # Parts/Materials markup
        "parts_markup_enabled": {
            "type": "boolean",
            "default": True,
            "title": "Apply Parts Markup",
            "description": "Whether to apply markup on parts/materials",
        },
        "parts_markup_percent": {
            "type": "number",
            "default": 15,
            "title": "Parts Markup (%)",
            "description": "Markup percentage on parts cost",
            "minimum": 0,
            "maximum": 100,
        },
        "parts_minimum_markup": {
            "type": "number",
            "default": 500,
            "title": "Minimum Parts Markup",
            "description": "Minimum markup amount per order",
        },

        # Service type rates (overrides by type)
        "rate_installation": {
            "type": "number",
            "default": 0,
            "title": "Installation Rate Override",
            "description": "Fixed rate for installation (0 = use hourly)",
        },
        "rate_repair": {
            "type": "number",
            "default": 0,
            "title": "Repair Rate Override",
            "description": "Fixed rate for repairs (0 = use hourly)",
        },
        "rate_maintenance": {
            "type": "number",
            "default": 0,
            "title": "Maintenance Rate Override",
            "description": "Fixed rate for maintenance (0 = use hourly)",
        },
        "rate_inspection": {
            "type": "number",
            "default": 5000,
            "title": "Inspection Rate",
            "description": "Fixed rate for inspections/surveys",
        },
        "rate_disconnection": {
            "type": "number",
            "default": 3000,
            "title": "Disconnection Rate",
            "description": "Fixed rate for disconnections",
        },

        # Time-based multipliers
        "overtime_enabled": {
            "type": "boolean",
            "default": True,
            "title": "Enable Overtime Rates",
            "description": "Apply overtime multipliers for after-hours work",
        },
        "overtime_multiplier": {
            "type": "number",
            "default": 1.5,
            "title": "Overtime Multiplier",
            "description": "Rate multiplier for overtime hours",
        },
        "overtime_start_hour": {
            "type": "integer",
            "default": 18,
            "title": "Overtime Start Hour",
            "description": "Hour when overtime rates begin (24h format)",
            "minimum": 0,
            "maximum": 23,
        },
        "overtime_end_hour": {
            "type": "integer",
            "default": 8,
            "title": "Overtime End Hour",
            "description": "Hour when overtime rates end (24h format)",
            "minimum": 0,
            "maximum": 23,
        },
        "weekend_multiplier": {
            "type": "number",
            "default": 1.5,
            "title": "Weekend Multiplier",
            "description": "Rate multiplier for weekend work",
        },
        "holiday_multiplier": {
            "type": "number",
            "default": 2.0,
            "title": "Holiday Multiplier",
            "description": "Rate multiplier for public holiday work",
        },
        "emergency_multiplier": {
            "type": "number",
            "default": 2.0,
            "title": "Emergency Multiplier",
            "description": "Rate multiplier for emergency priority orders",
        },

        # Minimum charges
        "minimum_service_charge": {
            "type": "number",
            "default": 5000,
            "title": "Minimum Service Charge",
            "description": "Minimum charge for any service call",
        },
        "callout_fee": {
            "type": "number",
            "default": 2000,
            "title": "Callout Fee",
            "description": "Fixed callout/dispatch fee",
        },
        "callout_fee_waived_threshold": {
            "type": "number",
            "default": 20000,
            "title": "Callout Fee Waiver Threshold",
            "description": "Waive callout fee if order total exceeds this",
        },

        # Discounts
        "bulk_discount_enabled": {
            "type": "boolean",
            "default": False,
            "title": "Enable Bulk Discounts",
            "description": "Apply discounts for multiple orders",
        },
        "bulk_discount_threshold": {
            "type": "integer",
            "default": 3,
            "title": "Bulk Discount Order Count",
            "description": "Number of orders for bulk discount",
        },
        "bulk_discount_percent": {
            "type": "number",
            "default": 10,
            "title": "Bulk Discount (%)",
            "description": "Discount percentage for bulk orders",
        },
        "contract_discount_percent": {
            "type": "number",
            "default": 15,
            "title": "Contract Customer Discount (%)",
            "description": "Discount for customers with service contracts",
        },

        # Invoice settings
        "invoice_due_days": {
            "type": "integer",
            "default": 14,
            "title": "Invoice Due Days",
            "description": "Days until invoice is due",
        },
        "auto_invoice_on_complete": {
            "type": "boolean",
            "default": False,
            "title": "Auto-Invoice on Completion",
            "description": "Automatically create invoice when order completes",
        },
        "auto_post_invoice": {
            "type": "boolean",
            "default": False,
            "title": "Auto-Post Invoice",
            "description": "Automatically post invoice to GL",
        },
        "combine_orders_on_invoice": {
            "type": "boolean",
            "default": True,
            "title": "Combine Orders on Invoice",
            "description": "Combine multiple orders into single invoice",
        },
        "itemize_parts_on_invoice": {
            "type": "boolean",
            "default": True,
            "title": "Itemize Parts on Invoice",
            "description": "Show individual parts vs single line",
        },
        "show_labor_breakdown": {
            "type": "boolean",
            "default": True,
            "title": "Show Labor Breakdown",
            "description": "Show hours and rate on invoice",
        },
    },
}


# =============================================================================
# CONFIGURATION DATACLASS
# =============================================================================

@dataclass
class FieldServiceBillingConfig:
    """Typed configuration for field service billing.

    This dataclass provides typed access to all billing settings
    with sensible defaults.
    """

    # General
    enabled: bool = True
    default_currency: str = "NGN"
    tax_rate: Decimal = Decimal("7.5")
    tax_inclusive: bool = False

    # Labor rates
    labor_rate_standard: Decimal = Decimal("5000")
    labor_rate_senior: Decimal = Decimal("7500")
    labor_rate_specialist: Decimal = Decimal("10000")
    labor_minimum_hours: Decimal = Decimal("1")
    labor_rounding_minutes: int = 15

    # Travel rates
    travel_rate_enabled: bool = True
    travel_rate_hourly: Decimal = Decimal("2000")
    travel_rate_per_km: Decimal = Decimal("100")
    travel_billing_method: str = "hourly"
    travel_flat_rate: Decimal = Decimal("5000")
    travel_free_radius_km: Decimal = Decimal("10")

    # Parts markup
    parts_markup_enabled: bool = True
    parts_markup_percent: Decimal = Decimal("15")
    parts_minimum_markup: Decimal = Decimal("500")

    # Service type rates
    rate_installation: Decimal = Decimal("0")
    rate_repair: Decimal = Decimal("0")
    rate_maintenance: Decimal = Decimal("0")
    rate_inspection: Decimal = Decimal("5000")
    rate_disconnection: Decimal = Decimal("3000")

    # Time multipliers
    overtime_enabled: bool = True
    overtime_multiplier: Decimal = Decimal("1.5")
    overtime_start_hour: int = 18
    overtime_end_hour: int = 8
    weekend_multiplier: Decimal = Decimal("1.5")
    holiday_multiplier: Decimal = Decimal("2.0")
    emergency_multiplier: Decimal = Decimal("2.0")

    # Minimum charges
    minimum_service_charge: Decimal = Decimal("5000")
    callout_fee: Decimal = Decimal("2000")
    callout_fee_waived_threshold: Decimal = Decimal("20000")

    # Discounts
    bulk_discount_enabled: bool = False
    bulk_discount_threshold: int = 3
    bulk_discount_percent: Decimal = Decimal("10")
    contract_discount_percent: Decimal = Decimal("15")

    # Invoice settings
    invoice_due_days: int = 14
    auto_invoice_on_complete: bool = False
    auto_post_invoice: bool = False
    combine_orders_on_invoice: bool = True
    itemize_parts_on_invoice: bool = True
    show_labor_breakdown: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldServiceBillingConfig":
        """Create config from dictionary."""
        return cls(
            # General
            enabled=data.get("enabled", True),
            default_currency=data.get("default_currency", "NGN"),
            tax_rate=Decimal(str(data.get("tax_rate", 7.5))),
            tax_inclusive=data.get("tax_inclusive", False),
            # Labor
            labor_rate_standard=Decimal(str(data.get("labor_rate_standard", 5000))),
            labor_rate_senior=Decimal(str(data.get("labor_rate_senior", 7500))),
            labor_rate_specialist=Decimal(str(data.get("labor_rate_specialist", 10000))),
            labor_minimum_hours=Decimal(str(data.get("labor_minimum_hours", 1))),
            labor_rounding_minutes=int(data.get("labor_rounding_minutes", 15)),
            # Travel
            travel_rate_enabled=data.get("travel_rate_enabled", True),
            travel_rate_hourly=Decimal(str(data.get("travel_rate_hourly", 2000))),
            travel_rate_per_km=Decimal(str(data.get("travel_rate_per_km", 100))),
            travel_billing_method=data.get("travel_billing_method", "hourly"),
            travel_flat_rate=Decimal(str(data.get("travel_flat_rate", 5000))),
            travel_free_radius_km=Decimal(str(data.get("travel_free_radius_km", 10))),
            # Parts
            parts_markup_enabled=data.get("parts_markup_enabled", True),
            parts_markup_percent=Decimal(str(data.get("parts_markup_percent", 15))),
            parts_minimum_markup=Decimal(str(data.get("parts_minimum_markup", 500))),
            # Service type rates
            rate_installation=Decimal(str(data.get("rate_installation", 0))),
            rate_repair=Decimal(str(data.get("rate_repair", 0))),
            rate_maintenance=Decimal(str(data.get("rate_maintenance", 0))),
            rate_inspection=Decimal(str(data.get("rate_inspection", 5000))),
            rate_disconnection=Decimal(str(data.get("rate_disconnection", 3000))),
            # Time multipliers
            overtime_enabled=data.get("overtime_enabled", True),
            overtime_multiplier=Decimal(str(data.get("overtime_multiplier", 1.5))),
            overtime_start_hour=int(data.get("overtime_start_hour", 18)),
            overtime_end_hour=int(data.get("overtime_end_hour", 8)),
            weekend_multiplier=Decimal(str(data.get("weekend_multiplier", 1.5))),
            holiday_multiplier=Decimal(str(data.get("holiday_multiplier", 2.0))),
            emergency_multiplier=Decimal(str(data.get("emergency_multiplier", 2.0))),
            # Minimum charges
            minimum_service_charge=Decimal(str(data.get("minimum_service_charge", 5000))),
            callout_fee=Decimal(str(data.get("callout_fee", 2000))),
            callout_fee_waived_threshold=Decimal(str(data.get("callout_fee_waived_threshold", 20000))),
            # Discounts
            bulk_discount_enabled=data.get("bulk_discount_enabled", False),
            bulk_discount_threshold=int(data.get("bulk_discount_threshold", 3)),
            bulk_discount_percent=Decimal(str(data.get("bulk_discount_percent", 10))),
            contract_discount_percent=Decimal(str(data.get("contract_discount_percent", 15))),
            # Invoice
            invoice_due_days=int(data.get("invoice_due_days", 14)),
            auto_invoice_on_complete=data.get("auto_invoice_on_complete", False),
            auto_post_invoice=data.get("auto_post_invoice", False),
            combine_orders_on_invoice=data.get("combine_orders_on_invoice", True),
            itemize_parts_on_invoice=data.get("itemize_parts_on_invoice", True),
            show_labor_breakdown=data.get("show_labor_breakdown", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "default_currency": self.default_currency,
            "tax_rate": float(self.tax_rate),
            "tax_inclusive": self.tax_inclusive,
            "labor_rate_standard": float(self.labor_rate_standard),
            "labor_rate_senior": float(self.labor_rate_senior),
            "labor_rate_specialist": float(self.labor_rate_specialist),
            "labor_minimum_hours": float(self.labor_minimum_hours),
            "labor_rounding_minutes": self.labor_rounding_minutes,
            "travel_rate_enabled": self.travel_rate_enabled,
            "travel_rate_hourly": float(self.travel_rate_hourly),
            "travel_rate_per_km": float(self.travel_rate_per_km),
            "travel_billing_method": self.travel_billing_method,
            "travel_flat_rate": float(self.travel_flat_rate),
            "travel_free_radius_km": float(self.travel_free_radius_km),
            "parts_markup_enabled": self.parts_markup_enabled,
            "parts_markup_percent": float(self.parts_markup_percent),
            "parts_minimum_markup": float(self.parts_minimum_markup),
            "rate_installation": float(self.rate_installation),
            "rate_repair": float(self.rate_repair),
            "rate_maintenance": float(self.rate_maintenance),
            "rate_inspection": float(self.rate_inspection),
            "rate_disconnection": float(self.rate_disconnection),
            "overtime_enabled": self.overtime_enabled,
            "overtime_multiplier": float(self.overtime_multiplier),
            "overtime_start_hour": self.overtime_start_hour,
            "overtime_end_hour": self.overtime_end_hour,
            "weekend_multiplier": float(self.weekend_multiplier),
            "holiday_multiplier": float(self.holiday_multiplier),
            "emergency_multiplier": float(self.emergency_multiplier),
            "minimum_service_charge": float(self.minimum_service_charge),
            "callout_fee": float(self.callout_fee),
            "callout_fee_waived_threshold": float(self.callout_fee_waived_threshold),
            "bulk_discount_enabled": self.bulk_discount_enabled,
            "bulk_discount_threshold": self.bulk_discount_threshold,
            "bulk_discount_percent": float(self.bulk_discount_percent),
            "contract_discount_percent": float(self.contract_discount_percent),
            "invoice_due_days": self.invoice_due_days,
            "auto_invoice_on_complete": self.auto_invoice_on_complete,
            "auto_post_invoice": self.auto_post_invoice,
            "combine_orders_on_invoice": self.combine_orders_on_invoice,
            "itemize_parts_on_invoice": self.itemize_parts_on_invoice,
            "show_labor_breakdown": self.show_labor_breakdown,
        }


# =============================================================================
# CONFIGURATION SERVICE
# =============================================================================

class FieldServiceBillingConfigService:
    """Service for managing field service billing configuration.

    Provides CRUD operations and helper methods for billing config.
    Configuration is stored in SettingGroup model.
    """

    NAMESPACE = "field_service.billing"
    CACHE_KEY = "field_service_billing_config"

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._cache: Optional[FieldServiceBillingConfig] = None

    def get_config(self, use_cache: bool = True) -> FieldServiceBillingConfig:
        """Get billing configuration.

        Args:
            use_cache: If True, return cached config if available.

        Returns:
            FieldServiceBillingConfig instance.
        """
        if use_cache and self._cache is not None:
            return self._cache

        from app.models.settings import SettingGroup

        setting = (
            self.db.query(SettingGroup)
            .filter(SettingGroup.namespace == self.NAMESPACE)
            .first()
        )

        if setting and setting.settings:
            config = FieldServiceBillingConfig.from_dict(setting.settings)
        else:
            config = FieldServiceBillingConfig()

        self._cache = config
        return config

    def save_config(self, config: FieldServiceBillingConfig) -> FieldServiceBillingConfig:
        """Save billing configuration.

        Args:
            config: Configuration to save.

        Returns:
            Saved configuration.
        """
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
                name="Field Service Billing",
                description="Billing rates and settings for field services",
                settings=config.to_dict(),
                schema=FIELD_SERVICE_BILLING_SCHEMA,
                created_by_id=self.principal.id if self.principal else None,
            )
            self.db.add(setting)

        self.db.flush()
        self._cache = config
        return config

    def update_config(
        self, updates: Dict[str, Any]
    ) -> FieldServiceBillingConfig:
        """Partial update of billing configuration.

        Args:
            updates: Dictionary of fields to update.

        Returns:
            Updated configuration.
        """
        current = self.get_config(use_cache=False)
        current_dict = current.to_dict()
        current_dict.update(updates)
        new_config = FieldServiceBillingConfig.from_dict(current_dict)
        return self.save_config(new_config)

    # -------------------------------------------------------------------------
    # Rate Calculation Helpers
    # -------------------------------------------------------------------------

    def get_labor_rate(
        self,
        technician_level: str = "standard",
        is_overtime: bool = False,
        is_weekend: bool = False,
        is_holiday: bool = False,
        is_emergency: bool = False,
    ) -> Decimal:
        """Get labor rate with applicable multipliers.

        Args:
            technician_level: standard, senior, or specialist
            is_overtime: Whether work is during overtime hours
            is_weekend: Whether work is on weekend
            is_holiday: Whether work is on holiday
            is_emergency: Whether order is emergency priority

        Returns:
            Calculated hourly rate.
        """
        config = self.get_config()

        # Base rate by level
        if technician_level == "specialist":
            base_rate = config.labor_rate_specialist
        elif technician_level == "senior":
            base_rate = config.labor_rate_senior
        else:
            base_rate = config.labor_rate_standard

        # Apply multipliers (use highest applicable)
        multiplier = Decimal("1")

        if is_emergency:
            multiplier = max(multiplier, config.emergency_multiplier)
        if is_holiday:
            multiplier = max(multiplier, config.holiday_multiplier)
        if is_weekend:
            multiplier = max(multiplier, config.weekend_multiplier)
        if is_overtime and config.overtime_enabled:
            multiplier = max(multiplier, config.overtime_multiplier)

        return base_rate * multiplier

    def get_travel_charge(
        self,
        hours: Optional[Decimal] = None,
        distance_km: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate travel charge based on configuration.

        Args:
            hours: Travel time in hours.
            distance_km: Travel distance in kilometers.

        Returns:
            Travel charge amount.
        """
        config = self.get_config()

        if not config.travel_rate_enabled:
            return Decimal("0")

        if config.travel_billing_method == "none":
            return Decimal("0")

        if config.travel_billing_method == "flat_rate":
            return config.travel_flat_rate

        if config.travel_billing_method == "per_km" and distance_km:
            # Subtract free radius
            billable_km = max(Decimal("0"), distance_km - config.travel_free_radius_km)
            return billable_km * config.travel_rate_per_km

        if config.travel_billing_method == "hourly" and hours:
            return hours * config.travel_rate_hourly

        return Decimal("0")

    def apply_parts_markup(self, parts_cost: Decimal) -> Decimal:
        """Apply markup to parts cost.

        Args:
            parts_cost: Base cost of parts.

        Returns:
            Parts cost with markup applied.
        """
        config = self.get_config()

        if not config.parts_markup_enabled or parts_cost <= 0:
            return parts_cost

        markup = parts_cost * (config.parts_markup_percent / 100)
        markup = max(markup, config.parts_minimum_markup)

        return parts_cost + markup

    def get_service_type_rate(self, service_type: str) -> Optional[Decimal]:
        """Get fixed rate for a service type (if configured).

        Args:
            service_type: Type of service (installation, repair, etc.)

        Returns:
            Fixed rate or None if hourly billing applies.
        """
        config = self.get_config()

        rate_map = {
            "installation": config.rate_installation,
            "repair": config.rate_repair,
            "maintenance": config.rate_maintenance,
            "inspection": config.rate_inspection,
            "disconnection": config.rate_disconnection,
        }

        rate = rate_map.get(service_type, Decimal("0"))
        return rate if rate > 0 else None

    def round_labor_hours(self, hours: Decimal) -> Decimal:
        """Round labor hours according to configuration.

        Args:
            hours: Raw hours.

        Returns:
            Rounded hours.
        """
        config = self.get_config()
        minutes = hours * 60
        rounding = Decimal(str(config.labor_rounding_minutes))

        # Round up to nearest interval
        rounded_minutes = ((minutes + rounding - 1) // rounding) * rounding
        return rounded_minutes / 60

    def apply_minimum_hours(self, hours: Decimal) -> Decimal:
        """Apply minimum billable hours.

        Args:
            hours: Actual hours worked.

        Returns:
            Hours with minimum applied.
        """
        config = self.get_config()
        return max(hours, config.labor_minimum_hours)

    def calculate_discount(
        self,
        subtotal: Decimal,
        order_count: int = 1,
        has_contract: bool = False,
    ) -> Decimal:
        """Calculate applicable discounts.

        Args:
            subtotal: Order subtotal before discount.
            order_count: Number of orders being invoiced together.
            has_contract: Whether customer has service contract.

        Returns:
            Discount amount.
        """
        config = self.get_config()
        discount = Decimal("0")

        # Contract discount takes priority
        if has_contract and config.contract_discount_percent > 0:
            discount = subtotal * (config.contract_discount_percent / 100)
        # Bulk discount
        elif (
            config.bulk_discount_enabled
            and order_count >= config.bulk_discount_threshold
        ):
            discount = subtotal * (config.bulk_discount_percent / 100)

        return discount

    def should_waive_callout_fee(self, order_total: Decimal) -> bool:
        """Check if callout fee should be waived.

        Args:
            order_total: Total order amount.

        Returns:
            True if callout fee should be waived.
        """
        config = self.get_config()
        return order_total >= config.callout_fee_waived_threshold

    def is_overtime_hour(self, hour: int) -> bool:
        """Check if hour is during overtime period.

        Args:
            hour: Hour of day (0-23).

        Returns:
            True if hour is during overtime.
        """
        config = self.get_config()

        if not config.overtime_enabled:
            return False

        start = config.overtime_start_hour
        end = config.overtime_end_hour

        # Handle overnight period (e.g., 18:00 - 08:00)
        if start > end:
            return hour >= start or hour < end
        else:
            return start <= hour < end

    def get_invoice_due_date(self, from_date: Optional[date] = None) -> date:
        """Get invoice due date based on configuration.

        Args:
            from_date: Date to calculate from (defaults to today).

        Returns:
            Due date.
        """
        config = self.get_config()
        base = from_date or date.today()
        return base + timedelta(days=config.invoice_due_days)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_field_service_billing_config(db: Session) -> FieldServiceBillingConfig:
    """Get field service billing configuration.

    Convenience function for quick access to config.

    Args:
        db: Database session.

    Returns:
        FieldServiceBillingConfig instance.
    """
    service = FieldServiceBillingConfigService(db)
    return service.get_config()

"""Data Bundle Service Types.

Pydantic schemas for data bundle operations.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self


# =============================================================================
# Enums (mirror model enums for API layer)
# =============================================================================

class BundleType(str, Enum):
    """Type of data bundle product."""
    PREPAID = "prepaid"
    USAGE_BASED = "usage_based"
    HYBRID = "hybrid"


class ExpiryType(str, Enum):
    """How bundle expiry is handled."""
    NO_EXPIRY = "no_expiry"
    STRICT = "strict"
    ROLLOVER = "rollover"


class ExhaustionAction(str, Enum):
    """Action when bundle data is exhausted."""
    BLOCK = "block"
    THROTTLE = "throttle"
    AUTO_RENEW = "auto_renew"
    NOTIFY_ONLY = "notify_only"


class BundleStatus(str, Enum):
    """Status of a customer's bundle instance."""
    PENDING = "pending"
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# =============================================================================
# Usage Tier Schema
# =============================================================================

class UsageTier(BaseModel):
    """Single tier for usage-based pricing."""
    up_to_mb: Optional[int] = Field(
        None,
        description="Upper limit in MB for this tier (null = unlimited)"
    )
    price_per_mb: Decimal = Field(
        ...,
        ge=0,
        description="Price per MB in this tier"
    )

    @field_validator("up_to_mb")
    @classmethod
    def validate_up_to_mb(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("up_to_mb must be positive or null")
        return v


# =============================================================================
# Product Schemas
# =============================================================================

class BundleProductCreate(BaseModel):
    """Schema for creating a bundle product."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Z0-9_-]+$")
    description: Optional[str] = None
    bundle_type: BundleType = BundleType.PREPAID

    # Data allocation
    data_amount_mb: Optional[int] = Field(None, gt=0, description="For prepaid bundles")
    data_cap_mb: Optional[int] = Field(None, gt=0, description="For hybrid bundles")

    # Pricing
    price: Decimal = Field(..., ge=0)
    currency: str = Field("NGN", max_length=3)

    # Usage-based pricing
    usage_tiers: Optional[List[UsageTier]] = None
    overage_price_per_mb: Optional[Decimal] = Field(None, ge=0)

    # Expiry configuration
    expiry_type: ExpiryType = ExpiryType.STRICT
    validity_days: Optional[int] = Field(30, ge=1, le=365)
    rollover_percent: Optional[int] = Field(0, ge=0, le=100)

    # Exhaustion behavior
    exhaustion_action: ExhaustionAction = ExhaustionAction.THROTTLE
    throttle_speed_kbps: Optional[int] = Field(128, ge=1)
    auto_renew_product_id: Optional[int] = None

    # Speed limits
    download_speed_kbps: Optional[int] = Field(None, gt=0)
    upload_speed_kbps: Optional[int] = Field(None, gt=0)

    # Alert thresholds
    alert_threshold_1: int = Field(50, ge=1, le=99)
    alert_threshold_2: int = Field(80, ge=1, le=99)
    alert_threshold_3: int = Field(95, ge=1, le=99)

    # Availability
    is_active: bool = True
    display_order: int = Field(0, ge=0)
    customer_portal_visible: bool = True
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_bundle_config(self) -> Self:
        """Validate bundle configuration based on type."""
        if self.bundle_type == BundleType.PREPAID:
            if not self.data_amount_mb:
                raise ValueError("Prepaid bundles require data_amount_mb")
        elif self.bundle_type == BundleType.USAGE_BASED:
            if not self.usage_tiers:
                raise ValueError("Usage-based bundles require usage_tiers")
        elif self.bundle_type == BundleType.HYBRID:
            if not self.data_cap_mb:
                raise ValueError("Hybrid bundles require data_cap_mb")
            if not self.overage_price_per_mb:
                raise ValueError("Hybrid bundles require overage_price_per_mb")

        # Validate exhaustion action config
        if self.exhaustion_action == ExhaustionAction.THROTTLE:
            if not self.throttle_speed_kbps:
                raise ValueError("Throttle action requires throttle_speed_kbps")
        elif self.exhaustion_action == ExhaustionAction.AUTO_RENEW:
            if not self.auto_renew_product_id:
                raise ValueError("Auto-renew action requires auto_renew_product_id")

        # Validate alert thresholds are in order
        if not (self.alert_threshold_1 < self.alert_threshold_2 < self.alert_threshold_3):
            raise ValueError("Alert thresholds must be in ascending order")

        # Validate rollover config
        if self.expiry_type == ExpiryType.ROLLOVER and not self.rollover_percent:
            raise ValueError("Rollover expiry type requires rollover_percent > 0")

        return self


class BundleProductUpdate(BaseModel):
    """Schema for updating a bundle product."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    bundle_type: Optional[BundleType] = None

    # Data allocation
    data_amount_mb: Optional[int] = Field(None, gt=0)
    data_cap_mb: Optional[int] = Field(None, gt=0)

    # Pricing
    price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)

    # Usage-based pricing
    usage_tiers: Optional[List[UsageTier]] = None
    overage_price_per_mb: Optional[Decimal] = Field(None, ge=0)

    # Expiry configuration
    expiry_type: Optional[ExpiryType] = None
    validity_days: Optional[int] = Field(None, ge=1, le=365)
    rollover_percent: Optional[int] = Field(None, ge=0, le=100)

    # Exhaustion behavior
    exhaustion_action: Optional[ExhaustionAction] = None
    throttle_speed_kbps: Optional[int] = Field(None, ge=1)
    auto_renew_product_id: Optional[int] = None

    # Speed limits
    download_speed_kbps: Optional[int] = Field(None, gt=0)
    upload_speed_kbps: Optional[int] = Field(None, gt=0)

    # Alert thresholds
    alert_threshold_1: Optional[int] = Field(None, ge=1, le=99)
    alert_threshold_2: Optional[int] = Field(None, ge=1, le=99)
    alert_threshold_3: Optional[int] = Field(None, ge=1, le=99)

    # Availability
    is_active: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)
    customer_portal_visible: Optional[bool] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None


class BundleProductResponse(BaseModel):
    """Response schema for bundle product."""
    id: int
    name: str
    code: str
    description: Optional[str]
    bundle_type: str

    data_amount_mb: Optional[int]
    data_amount_gb: Optional[float]
    data_cap_mb: Optional[int]

    price: Decimal
    currency: str
    usage_tiers: Optional[List[Dict[str, Any]]]
    overage_price_per_mb: Optional[Decimal]

    expiry_type: str
    validity_days: Optional[int]
    rollover_percent: Optional[int]

    exhaustion_action: str
    throttle_speed_kbps: Optional[int]
    auto_renew_product_id: Optional[int]

    download_speed_kbps: Optional[int]
    upload_speed_kbps: Optional[int]

    alert_threshold_1: int
    alert_threshold_2: int
    alert_threshold_3: int

    is_active: bool
    display_order: int
    customer_portal_visible: bool
    category: Optional[str]
    tags: Optional[List[str]]

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Customer Bundle Schemas
# =============================================================================

class BundlePurchaseRequest(BaseModel):
    """Request to purchase a bundle."""
    product_id: int
    payment_reference: Optional[str] = None
    activate_immediately: bool = True


class BundleActivateRequest(BaseModel):
    """Request to activate a pending bundle."""
    bundle_id: int


class BundleCancelRequest(BaseModel):
    """Request to cancel a bundle."""
    bundle_id: int
    reason: Optional[str] = None


class CustomerBundleResponse(BaseModel):
    """Response schema for customer bundle."""
    id: int
    subscription_id: int
    product_id: int
    product_name: str
    product_code: str

    data_allocated_mb: int
    data_used_mb: int
    rollover_mb: int
    data_remaining_mb: int
    data_remaining_gb: float
    usage_percent: float

    status: str
    is_active: bool
    is_exhausted: bool
    is_expired: bool

    purchased_at: datetime
    activated_at: Optional[datetime]
    expires_at: Optional[datetime]
    exhausted_at: Optional[datetime]

    amount_charged: Decimal
    currency: str
    invoice_id: Optional[int]

    alert_50_sent: bool
    alert_80_sent: bool
    alert_95_sent: bool

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BundleStatusResponse(BaseModel):
    """Current bundle status for a subscription."""
    subscription_id: int
    has_active_bundle: bool
    active_bundle: Optional[CustomerBundleResponse] = None
    pending_bundles: List[CustomerBundleResponse] = []
    total_data_remaining_mb: int
    total_data_remaining_gb: float


# =============================================================================
# Usage Schemas
# =============================================================================

class UsageRecordRequest(BaseModel):
    """Request to record usage."""
    subscription_id: int
    upload_bytes: int = Field(..., ge=0)
    download_bytes: int = Field(..., ge=0)
    source: str = "RADIUS"
    session_id: Optional[str] = None
    nas_ip: Optional[str] = None


class UsageSummary(BaseModel):
    """Usage summary for a period."""
    subscription_id: int
    period_start: datetime
    period_end: datetime
    total_upload_mb: float
    total_download_mb: float
    total_usage_mb: float
    total_usage_gb: float
    bundle_charges: Decimal
    overage_charges: Decimal


# =============================================================================
# Exhaustion Handling
# =============================================================================

class ExhaustionResult(BaseModel):
    """Result of handling bundle exhaustion."""
    bundle_id: int
    action_taken: ExhaustionAction
    coa_sent: bool
    new_bundle_id: Optional[int] = None
    notification_sent: bool
    error: Optional[str] = None


# =============================================================================
# Reporting
# =============================================================================

class ProductRevenue(BaseModel):
    """Revenue summary for a product."""
    product_id: int
    product_name: str
    product_code: str
    bundle_type: str
    units_sold: int
    total_revenue: Decimal
    currency: str


class BundleAnalytics(BaseModel):
    """Analytics for bundle operations."""
    total_active_bundles: int
    total_data_allocated_gb: float
    total_data_consumed_gb: float
    average_usage_percent: float
    bundles_exhausted_today: int
    bundles_expiring_soon: int
    revenue_this_month: Decimal
    top_products: List[ProductRevenue]

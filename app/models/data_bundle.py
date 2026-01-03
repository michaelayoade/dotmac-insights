"""Data Bundle Models.

Models for prepaid data bundles, usage-based billing, and hybrid plans.
Supports:
- Prepaid: Fixed data amount (e.g., 5GB for $10)
- Usage-based: Pay per GB with tiered pricing
- Hybrid: Base plan with included data + overage charges
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.invoice import Invoice


# =============================================================================
# Enums
# =============================================================================

class BundleType(str, Enum):
    """Type of data bundle product."""
    PREPAID = "prepaid"           # Fixed data amount, one-time purchase
    USAGE_BASED = "usage_based"   # Pay per GB with optional tiers
    HYBRID = "hybrid"             # Base plan with included data + overage


class ExpiryType(str, Enum):
    """How bundle expiry is handled."""
    NO_EXPIRY = "no_expiry"       # Data valid until consumed
    STRICT = "strict"             # Expires on date, unused data lost
    ROLLOVER = "rollover"         # Unused data rolls to next period


class ExhaustionAction(str, Enum):
    """Action when bundle data is exhausted."""
    BLOCK = "block"               # Block internet access via CoA
    THROTTLE = "throttle"         # Reduce speed via CoA
    AUTO_RENEW = "auto_renew"     # Auto-purchase next bundle
    NOTIFY_ONLY = "notify_only"   # Just send notification, no action


class BundleStatus(str, Enum):
    """Status of a customer's bundle instance."""
    PENDING = "pending"           # Purchased but not yet active
    ACTIVE = "active"             # Currently active
    EXHAUSTED = "exhausted"       # Data used up
    EXPIRED = "expired"           # Validity period ended
    CANCELLED = "cancelled"       # Manually cancelled


# =============================================================================
# Data Bundle Product (Template)
# =============================================================================

class DataBundleProduct(Base):
    """Bundle product template - defines what customers can purchase.

    This is the product catalog entry. Customers purchase instances
    of these products which become CustomerBundle records.
    """
    __tablename__ = "data_bundle_products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bundle_type: Mapped[str] = mapped_column(String(20), nullable=False, default=BundleType.PREPAID.value)

    # Data allocation (for prepaid and hybrid)
    data_amount_mb: Mapped[Optional[int]] = mapped_column(nullable=True)  # Prepaid: total data
    data_cap_mb: Mapped[Optional[int]] = mapped_column(nullable=True)     # Hybrid: included data

    # Pricing
    price: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")

    # Usage-based pricing tiers (JSONB)
    # Format: [{"up_to_mb": 10240, "price_per_mb": 0.01}, {"up_to_mb": null, "price_per_mb": 0.005}]
    usage_tiers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Overage pricing for hybrid bundles
    overage_price_per_mb: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Expiry configuration
    expiry_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExpiryType.STRICT.value
    )
    validity_days: Mapped[Optional[int]] = mapped_column(nullable=True, default=30)
    rollover_percent: Mapped[Optional[int]] = mapped_column(nullable=True, default=0)

    # Exhaustion behavior
    exhaustion_action: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExhaustionAction.THROTTLE.value
    )
    throttle_speed_kbps: Mapped[Optional[int]] = mapped_column(nullable=True, default=128)
    auto_renew_product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_bundle_products.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Speed limits while bundle active
    download_speed_kbps: Mapped[Optional[int]] = mapped_column(nullable=True)
    upload_speed_kbps: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Alert thresholds (percentage)
    alert_threshold_1: Mapped[int] = mapped_column(default=50)   # First warning
    alert_threshold_2: Mapped[int] = mapped_column(default=80)   # Second warning
    alert_threshold_3: Mapped[int] = mapped_column(default=95)   # Final warning

    # Availability
    is_active: Mapped[bool] = mapped_column(default=True)
    display_order: Mapped[int] = mapped_column(default=0)
    customer_portal_visible: Mapped[bool] = mapped_column(default=True)

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    auto_renew_product = relationship(
        "DataBundleProduct",
        remote_side=[id],
        foreign_keys=[auto_renew_product_id],
    )
    customer_bundles: Mapped[List["CustomerBundle"]] = relationship(
        back_populates="product",
        foreign_keys="CustomerBundle.product_id",
    )

    def __repr__(self) -> str:
        return f"<DataBundleProduct {self.code}: {self.name}>"

    @property
    def bundle_type_enum(self) -> BundleType:
        return BundleType(self.bundle_type)

    @property
    def expiry_type_enum(self) -> ExpiryType:
        return ExpiryType(self.expiry_type)

    @property
    def exhaustion_action_enum(self) -> ExhaustionAction:
        return ExhaustionAction(self.exhaustion_action)

    @property
    def data_amount_gb(self) -> Optional[float]:
        """Data amount in GB."""
        if self.data_amount_mb:
            return self.data_amount_mb / 1024
        return None

    def get_tier_price(self, usage_mb: int) -> Decimal:
        """Calculate price for given usage based on tiers."""
        if not self.usage_tiers:
            return Decimal("0")

        tiers = sorted(self.usage_tiers, key=lambda t: t.get("up_to_mb") or float("inf"))
        total_price = Decimal("0")
        remaining = usage_mb

        for tier in tiers:
            up_to = tier.get("up_to_mb")
            price_per_mb = Decimal(str(tier.get("price_per_mb", 0)))

            if up_to is None:
                # Unlimited tier - charge all remaining
                total_price += remaining * price_per_mb
                break
            elif remaining <= up_to:
                total_price += remaining * price_per_mb
                break
            else:
                total_price += up_to * price_per_mb
                remaining -= up_to

        return total_price


# =============================================================================
# Customer Bundle Instance
# =============================================================================

class CustomerBundle(Base):
    """Customer's active bundle instance.

    Created when a customer purchases a DataBundleProduct.
    Tracks usage, status, and billing for that specific purchase.
    """
    __tablename__ = "customer_bundles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("data_bundle_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Data allocation
    data_allocated_mb: Mapped[int] = mapped_column(nullable=False, default=0)
    data_used_mb: Mapped[int] = mapped_column(nullable=False, default=0)
    rollover_mb: Mapped[int] = mapped_column(nullable=False, default=0)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BundleStatus.PENDING.value, index=True
    )

    # Dates
    purchased_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    exhausted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Billing
    amount_charged: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Alert tracking
    alert_50_sent: Mapped[bool] = mapped_column(default=False)
    alert_80_sent: Mapped[bool] = mapped_column(default=False)
    alert_95_sent: Mapped[bool] = mapped_column(default=False)
    exhaustion_alert_sent: Mapped[bool] = mapped_column(default=False)

    # Renewal tracking
    renewed_from_bundle_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customer_bundles.id", ondelete="SET NULL"),
        nullable=True,
    )
    auto_renewed: Mapped[bool] = mapped_column(default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="bundles")
    product: Mapped["DataBundleProduct"] = relationship(
        back_populates="customer_bundles",
        foreign_keys=[product_id],
    )
    invoice: Mapped[Optional["Invoice"]] = relationship()
    renewed_from: Mapped[Optional["CustomerBundle"]] = relationship(
        remote_side=[id],
        foreign_keys=[renewed_from_bundle_id],
    )
    usage_logs: Mapped[List["BundleUsageLog"]] = relationship(
        back_populates="customer_bundle",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_customer_bundles_active", "subscription_id", "status"),
        Index("ix_customer_bundles_expiry", "expires_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<CustomerBundle {self.id}: {self.status} ({self.usage_percent:.1f}% used)>"

    @property
    def status_enum(self) -> BundleStatus:
        return BundleStatus(self.status)

    @property
    def total_data_mb(self) -> int:
        """Total data available (allocated + rollover)."""
        return self.data_allocated_mb + self.rollover_mb

    @property
    def data_remaining_mb(self) -> int:
        """Remaining data in MB."""
        return max(0, self.total_data_mb - self.data_used_mb)

    @property
    def data_remaining_gb(self) -> float:
        """Remaining data in GB."""
        return self.data_remaining_mb / 1024

    @property
    def usage_percent(self) -> float:
        """Usage percentage."""
        total = self.total_data_mb
        if total <= 0:
            return 0.0
        return min(100.0, (self.data_used_mb / total) * 100)

    @property
    def is_active(self) -> bool:
        """Check if bundle is currently active."""
        return self.status == BundleStatus.ACTIVE.value

    @property
    def is_exhausted(self) -> bool:
        """Check if bundle data is exhausted."""
        return self.data_remaining_mb <= 0

    @property
    def is_expired(self) -> bool:
        """Check if bundle has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def add_usage(self, upload_bytes: int, download_bytes: int) -> int:
        """Add usage to this bundle.

        Args:
            upload_bytes: Upload traffic in bytes.
            download_bytes: Download traffic in bytes.

        Returns:
            Total MB added.
        """
        total_bytes = upload_bytes + download_bytes
        mb_used = total_bytes // (1024 * 1024)
        self.data_used_mb += mb_used
        return mb_used


# =============================================================================
# Bundle Usage Log
# =============================================================================

class BundleUsageLog(Base):
    """Detailed usage log for billing and analytics.

    Records individual usage samples from RADIUS accounting
    or other sources for audit and detailed billing.
    """
    __tablename__ = "bundle_usage_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    customer_bundle_id: Mapped[int] = mapped_column(
        ForeignKey("customer_bundles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Usage data
    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    upload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    download_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Source tracking
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="RADIUS")
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    nas_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relationships
    customer_bundle: Mapped["CustomerBundle"] = relationship(back_populates="usage_logs")

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_bundle_usage_logs_bundle_time", "customer_bundle_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        total_mb = (self.upload_bytes + self.download_bytes) / (1024 * 1024)
        return f"<BundleUsageLog {self.id}: {total_mb:.2f}MB at {self.recorded_at}>"

    @property
    def total_bytes(self) -> int:
        return self.upload_bytes + self.download_bytes

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)


# =============================================================================
# Bundle Transaction (for usage-based billing)
# =============================================================================

class BundleTransaction(Base):
    """Transaction record for usage-based billing.

    Records charges applied for usage-based bundles,
    allowing detailed billing breakdown.
    """
    __tablename__ = "bundle_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    customer_bundle_id: Mapped[int] = mapped_column(
        ForeignKey("customer_bundles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Types: PURCHASE, USAGE_CHARGE, OVERAGE_CHARGE, TOPUP, REFUND

    amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")

    # Usage context (for usage/overage charges)
    data_mb: Mapped[Optional[int]] = mapped_column(nullable=True)
    tier_applied: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rate_per_mb: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Reference
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<BundleTransaction {self.id}: {self.transaction_type} {self.amount}>"

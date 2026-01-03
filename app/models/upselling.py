"""Upselling Opportunity Model - Business Intelligence for sales."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, TYPE_CHECKING
from enum import Enum

from sqlalchemy import BigInteger, String, Text, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.party import Party
    from app.models.tariff import Tariff
    from app.models.employee import Employee
    from app.models.crm import Opportunity


class UpsellTriggerType(str, Enum):
    """Trigger types for upselling opportunities."""
    HIGH_USAGE = "high_usage"  # Consistently using >X% of plan
    BUNDLE_EXHAUSTION = "bundle_exhaustion"  # Frequently exhausting bundles
    SPEED_UPGRADE = "speed_upgrade"  # Peak usage hitting speed limits
    PLAN_MISMATCH = "plan_mismatch"  # Plan doesn't match usage pattern
    LOYALTY_UPGRADE = "loyalty_upgrade"  # Long-term customer eligible for better plan
    CONTRACT_RENEWAL = "contract_renewal"  # Contract ending soon
    FEATURE_REQUEST = "feature_request"  # Requested features in higher tier
    COMPETITOR_MATCH = "competitor_match"  # Competitor offering better deal
    SEASONAL = "seasonal"  # Seasonal promotion opportunity


class UpsellStatus(str, Enum):
    """Status of upselling opportunity."""
    NEW = "new"  # Just detected
    CONTACTED = "contacted"  # Sales reached out
    QUALIFIED = "qualified"  # Confirmed interest
    PROPOSAL_SENT = "proposal_sent"  # Quote/proposal sent
    CONVERTED = "converted"  # Successfully upgraded
    DECLINED = "declined"  # Customer declined
    EXPIRED = "expired"  # Opportunity expired


class UpsellOpportunity(Base):
    """System-generated upselling opportunity.

    Automatically detected based on customer usage patterns,
    bundle exhaustion, and other signals.
    """

    __tablename__ = "upsell_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Target
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Trigger information
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    trigger_score: Mapped[int] = mapped_column(default=50)  # 0-100 confidence score
    trigger_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)  # Evidence for recommendation

    # Current state
    current_plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_mrr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Recommendation
    recommended_tariff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tariffs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommended_bundle_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_bundle_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommended_plan_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recommended_mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Revenue impact
    monthly_revenue_increase: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    annual_revenue_increase: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    one_time_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # Setup fees, etc.

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=UpsellStatus.NEW.value, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, urgent

    # Assignment
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # CRM integration
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quotation_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Engagement tracking
    contacted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    contact_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # call, email, sms
    contact_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Outcome
    converted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    new_subscription_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    declined_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    declined_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Auto-expiry
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(foreign_keys=[subscription_id])
    party: Mapped["Party"] = relationship(foreign_keys=[party_id])
    recommended_tariff: Mapped[Optional["Tariff"]] = relationship(foreign_keys=[recommended_tariff_id])
    assigned_to: Mapped[Optional["Employee"]] = relationship(foreign_keys=[assigned_to_id])
    crm_opportunity: Mapped[Optional["Opportunity"]] = relationship(foreign_keys=[opportunity_id])

    __table_args__ = (
        Index("ix_upsell_opportunities_status_priority", "status", "priority"),
        Index("ix_upsell_opportunities_trigger_type", "trigger_type"),
        Index("ix_upsell_opportunities_assigned_status", "assigned_to_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<UpsellOpportunity {self.id}: {self.trigger_type} [{self.status}]>"

    @property
    def is_active(self) -> bool:
        """Check if opportunity is still actionable."""
        return self.status in [UpsellStatus.NEW.value, UpsellStatus.CONTACTED.value,
                               UpsellStatus.QUALIFIED.value, UpsellStatus.PROPOSAL_SENT.value]


class UpsellAnalysisRun(Base):
    """Track batch analysis runs for upselling.

    Records when analysis was run and what was found.
    """

    __tablename__ = "upsell_analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Run details
    started_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed

    # Scope
    subscriptions_analyzed: Mapped[int] = mapped_column(default=0)

    # Results by trigger type
    opportunities_found: Mapped[int] = mapped_column(default=0)
    high_usage_found: Mapped[int] = mapped_column(default=0)
    bundle_exhaustion_found: Mapped[int] = mapped_column(default=0)
    speed_upgrade_found: Mapped[int] = mapped_column(default=0)
    loyalty_upgrade_found: Mapped[int] = mapped_column(default=0)
    contract_renewal_found: Mapped[int] = mapped_column(default=0)

    # Revenue impact
    total_potential_mrr_increase: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    # Expiry processing
    opportunities_expired: Mapped[int] = mapped_column(default=0)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<UpsellAnalysisRun {self.id}: {self.status} @ {self.started_at}>"


class UpsellConversionEvent(Base):
    """Track successful upsell conversions for analytics.

    Records the details of each successful upgrade for ROI analysis.
    """

    __tablename__ = "upsell_conversion_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("upsell_opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Conversion details
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_plan: Mapped[str] = mapped_column(String(255), nullable=False)
    new_plan: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_mrr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    new_mrr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mrr_increase: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Attribution
    converted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversion_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # call, email, self-service

    # Time to convert
    days_to_convert: Mapped[int] = mapped_column(default=0)

    # Timestamps
    converted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_upsell_conversions_trigger_date", "trigger_type", "converted_at"),
    )

    def __repr__(self) -> str:
        return f"<UpsellConversionEvent {self.id}: +{self.mrr_increase}/mo>"

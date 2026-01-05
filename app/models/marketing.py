"""Marketing module models: journeys, campaigns, social posts, and consent."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.validation import SoftValidationMixin
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.party import Party


# =============================================================================
# ENUMS
# =============================================================================


class MarketingCampaignType(enum.Enum):
    EMAIL = "email"
    SOCIAL = "social"
    MULTI_CHANNEL = "multi_channel"
    JOURNEY = "journey"
    PAID_AD = "paid_ad"


class MarketingCampaignStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class JourneyStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class JourneyStepType(enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SOCIAL_POST = "social_post"
    WAIT = "wait"
    CONDITION = "condition"
    SPLIT = "split"
    WEBHOOK = "webhook"
    TASK = "task"
    EXIT = "exit"


class JourneyEnrollmentStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXITED = "exited"
    FAILED = "failed"


class SocialPlatform(enum.Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"


class SocialPostStatus(enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class EmailCampaignStatus(enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class EmailSendStatus(enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"


class ConsentChannel(enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class ConsentStatus(enum.Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"
    UNKNOWN = "unknown"


class MarketingIntegrationStatus(enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"


# =============================================================================
# CAMPAIGNS
# =============================================================================


class MarketingCampaign(SoftValidationMixin, Base):
    """Parent container for marketing initiatives."""

    __tablename__ = "marketing_campaigns"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    campaign_type: Mapped[MarketingCampaignType] = mapped_column(
        Enum(MarketingCampaignType),
        nullable=False,
        index=True,
    )
    status: Mapped[MarketingCampaignStatus] = mapped_column(
        Enum(MarketingCampaignStatus),
        nullable=False,
        server_default="draft",
        index=True,
    )

    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default="NGN")

    utm_params: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    journeys: Mapped[List["CustomerJourney"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    email_campaigns: Mapped[List["EmailCampaign"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MarketingCampaign {self.name} ({self.campaign_type.value})>"


# =============================================================================
# JOURNEYS
# =============================================================================


class JourneyTemplate(SoftValidationMixin, Base):
    """Pre-built journey blueprints."""

    __tablename__ = "journey_templates"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    template_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    is_system_template: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    journeys: Mapped[List["CustomerJourney"]] = relationship(back_populates="template")


class CustomerJourney(SoftValidationMixin, Base):
    """Active journey instance derived from a template."""

    __tablename__ = "customer_journeys"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("journey_templates.id"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("marketing_campaigns.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[JourneyStatus] = mapped_column(
        Enum(JourneyStatus),
        nullable=False,
        server_default="draft",
        index=True,
    )
    entry_trigger: Mapped[Optional[str]] = mapped_column(Text)
    exit_conditions: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    template: Mapped[Optional["JourneyTemplate"]] = relationship(back_populates="journeys")
    campaign: Mapped[Optional["MarketingCampaign"]] = relationship(back_populates="journeys")
    steps: Mapped[List["JourneyStep"]] = relationship(
        back_populates="journey",
        order_by="JourneyStep.step_order",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[List["JourneyEnrollment"]] = relationship(
        back_populates="journey",
        cascade="all, delete-orphan",
    )


class JourneyStep(SoftValidationMixin, Base):
    """Individual journey step."""

    __tablename__ = "journey_steps"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    journey_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_journeys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[JourneyStepType] = mapped_column(Enum(JourneyStepType), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(Text)

    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    delay_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    content: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    email_template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("email_templates.id"),
        nullable=True,
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(Text)
    condition_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    journey: Mapped["CustomerJourney"] = relationship(back_populates="steps")
    email_template: Mapped[Optional["EmailTemplate"]] = relationship()


class JourneyEnrollment(SoftValidationMixin, Base):
    """Represents a party enrolled in a journey."""

    __tablename__ = "journey_enrollments"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    journey_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_journeys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[JourneyEnrollmentStatus] = mapped_column(
        Enum(JourneyEnrollmentStatus),
        nullable=False,
        server_default="active",
        index=True,
    )
    current_step_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("journey_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    engagement: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    journey: Mapped["CustomerJourney"] = relationship(back_populates="enrollments")
    party: Mapped["Party"] = relationship()
    current_step: Mapped[Optional["JourneyStep"]] = relationship()


# =============================================================================
# SOCIAL
# =============================================================================


class SocialAccount(SoftValidationMixin, Base):
    """Connected social media account."""

    __tablename__ = "social_accounts"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    platform: Mapped[SocialPlatform] = mapped_column(Enum(SocialPlatform), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    profile_url: Mapped[Optional[str]] = mapped_column(Text)

    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    stats: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    posts: Mapped[List["SocialPost"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("platform", "account_id", name="uq_social_account_platform_id"),
    )


class SocialPost(SoftValidationMixin, Base):
    """Scheduled or published social post."""

    __tablename__ = "social_posts"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    status: Mapped[SocialPostStatus] = mapped_column(
        Enum(SocialPostStatus),
        nullable=False,
        server_default="draft",
        index=True,
    )
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255))
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    account: Mapped["SocialAccount"] = relationship(back_populates="posts")


# =============================================================================
# EMAIL
# =============================================================================


class EmailTemplate(SoftValidationMixin, Base):
    """Reusable email template."""

    __tablename__ = "email_templates"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    variables: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    is_system_template: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class EmailCampaign(SoftValidationMixin, Base):
    """One-off or scheduled email campaign."""

    __tablename__ = "email_campaigns"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("email_templates.id"),
        nullable=False,
        index=True,
    )
    audience_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("marketing_audiences.id"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("marketing_campaigns.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[EmailCampaignStatus] = mapped_column(
        Enum(EmailCampaignStatus),
        nullable=False,
        server_default="draft",
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="UTC")
    send_window_start: Mapped[Optional[int]] = mapped_column(Integer)
    send_window_end: Mapped[Optional[int]] = mapped_column(Integer)

    metrics: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    template: Mapped["EmailTemplate"] = relationship()
    audience: Mapped[Optional["MarketingAudience"]] = relationship()
    campaign: Mapped[Optional["MarketingCampaign"]] = relationship(back_populates="email_campaigns")
    sends: Mapped[List["EmailSend"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class EmailSend(SoftValidationMixin, Base):
    """Individual send record for an email campaign."""

    __tablename__ = "email_sends"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    campaign_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("email_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[EmailSendStatus] = mapped_column(
        Enum(EmailSendStatus),
        nullable=False,
        server_default="queued",
        index=True,
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255))

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    tracking: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    campaign: Mapped["EmailCampaign"] = relationship(back_populates="sends")
    party: Mapped["Party"] = relationship()


class MarketingAudience(SoftValidationMixin, Base):
    """Target segment definition for marketing campaigns."""

    __tablename__ = "marketing_audiences"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    filter_criteria: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


# =============================================================================
# INTEGRATIONS + CONSENT
# =============================================================================


class MarketingIntegration(SoftValidationMixin, Base):
    """External platform connection metadata."""

    __tablename__ = "marketing_integrations"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    integration_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[MarketingIntegrationStatus] = mapped_column(
        Enum(MarketingIntegrationStatus),
        nullable=False,
        server_default="disconnected",
        index=True,
    )
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class MarketingConsent(SoftValidationMixin, Base):
    """Consent state per party and channel."""

    __tablename__ = "marketing_consents"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id"),
        nullable=False,
        index=True,
    )
    channel: Mapped[ConsentChannel] = mapped_column(Enum(ConsentChannel), nullable=False, index=True)
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus),
        nullable=False,
        server_default="unknown",
        index=True,
    )
    source: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship()

    __table_args__ = (
        UniqueConstraint("party_id", "channel", name="uq_marketing_consent_party_channel"),
    )


class SuppressionEntry(SoftValidationMixin, Base):
    """Global opt-out or suppression record."""

    __tablename__ = "marketing_suppressions"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id"),
        nullable=False,
        index=True,
    )
    channel: Mapped[ConsentChannel] = mapped_column(Enum(ConsentChannel), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship()

    __table_args__ = (
        UniqueConstraint("party_id", "channel", name="uq_marketing_suppression_party_channel"),
    )


class MarketingWebhookEvent(SoftValidationMixin, Base):
    """Webhook event record for idempotency checks."""

    __tablename__ = "marketing_webhook_events"
    __soft_validation_scope__ = "marketing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("platform", "event_id", name="uq_marketing_webhook_platform_event"),
        Index("ix_marketing_webhook_platform_received", "platform", "received_at"),
    )

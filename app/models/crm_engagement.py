"""CRM Engagement Models - Nurture sequences, segments, custom fields, and communication.

These models support comprehensive CRM journeys:
- Custom field definitions for CRM entities
- Nurture sequences for drip campaigns
- Contact segments for targeted outreach
- Proactive communication tracking
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Identity,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now


# =============================================================================
# CUSTOM FIELD DEFINITIONS
# =============================================================================

class CRMFieldType(enum.Enum):
    """Field types for custom CRM fields."""
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    CURRENCY = "currency"


class CRMFieldEntity(enum.Enum):
    """Entities that can have custom fields."""
    PARTY = "party"
    LEAD = "lead"
    OPPORTUNITY = "opportunity"
    ACTIVITY = "activity"
    CAMPAIGN = "campaign"


class CRMCustomFieldDefinition(Base):
    """Custom field definitions for CRM entities."""
    __tablename__ = "crm_custom_field_definitions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    # Field identity
    field_key: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "industry", "budget_range"
    entity_type: Mapped[CRMFieldEntity] = mapped_column(Enum(CRMFieldEntity), nullable=False)

    # Display
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    placeholder: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(Text)
    group: Mapped[Optional[str]] = mapped_column(Text)  # For grouping fields in UI

    # Type and validation
    field_type: Mapped[CRMFieldType] = mapped_column(Enum(CRMFieldType), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    default_value: Mapped[Optional[str]] = mapped_column(Text)
    validation_regex: Mapped[Optional[str]] = mapped_column(Text)
    min_value: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    max_value: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    min_length: Mapped[Optional[int]] = mapped_column(Integer)
    max_length: Mapped[Optional[int]] = mapped_column(Integer)

    # Options for select/multiselect
    options: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )  # [{value: "x", label: "X", color: "#fff"}]

    # Ordering and visibility
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    show_in_list: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    show_in_detail: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("field_key", "entity_type", name="uq_crm_custom_field_key_entity"),
        Index("ix_crm_custom_field_entity", "entity_type"),
    )


# =============================================================================
# NURTURE SEQUENCES (Drip Campaigns)
# =============================================================================

class NurtureSequenceStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class NurtureStepType(enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    TASK = "task"  # Create a follow-up task
    WAIT = "wait"  # Delay before next step
    CONDITION = "condition"  # Branch based on engagement
    WEBHOOK = "webhook"  # External trigger


class NurtureSequence(Base):
    """Drip campaign / nurture sequence definition."""
    __tablename__ = "nurture_sequences"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[NurtureSequenceStatus] = mapped_column(
        Enum(NurtureSequenceStatus),
        nullable=False,
        server_default="draft",
    )

    # Targeting
    target_segment_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("contact_segments.id"),
        nullable=True,
    )
    entry_trigger: Mapped[Optional[str]] = mapped_column(Text)  # e.g., "lead_created", "form_submitted"
    entry_conditions: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Settings
    allow_reentry: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    exit_on_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    exit_on_conversion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    respect_contact_preferences: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    timezone_aware: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    send_window_start: Mapped[Optional[int]] = mapped_column(Integer)  # Hour of day (0-23)
    send_window_end: Mapped[Optional[int]] = mapped_column(Integer)
    exclude_weekends: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Campaign linking
    campaign_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("campaigns.id"), nullable=True)

    # Metrics (denormalized for performance)
    total_enrolled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_converted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_unsubscribed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=True)

    # Relationships
    steps: Mapped[List["NurtureSequenceStep"]] = relationship(
        back_populates="sequence",
        order_by="NurtureSequenceStep.step_order",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[List["NurtureEnrollment"]] = relationship(back_populates="sequence")


class NurtureSequenceStep(Base):
    """Individual step in a nurture sequence."""
    __tablename__ = "nurture_sequence_steps"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("nurture_sequences.id", ondelete="CASCADE"),
        nullable=False,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[NurtureStepType] = mapped_column(Enum(NurtureStepType), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)

    # Timing
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    delay_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Content (for email/sms)
    subject: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    template_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # Link to email template

    # For condition steps
    condition_field: Mapped[Optional[str]] = mapped_column(Text)  # e.g., "email_opened", "link_clicked"
    condition_operator: Mapped[Optional[str]] = mapped_column(Text)  # equals, contains, gt, lt
    condition_value: Mapped[Optional[str]] = mapped_column(Text)
    true_step_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # Jump to this step if true
    false_step_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # Jump to this step if false

    # For task steps
    task_type: Mapped[Optional[str]] = mapped_column(Text)  # call, email, meeting
    task_assignee_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=True)
    task_priority: Mapped[Optional[str]] = mapped_column(Text, server_default="medium")

    # For webhook steps
    webhook_url: Mapped[Optional[str]] = mapped_column(Text)
    webhook_method: Mapped[Optional[str]] = mapped_column(Text, server_default="POST")
    webhook_headers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    webhook_payload: Mapped[Optional[str]] = mapped_column(Text)

    # A/B testing
    is_ab_test: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    ab_variant: Mapped[Optional[str]] = mapped_column(Text)  # A, B, C, etc.
    ab_weight: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))  # percentage

    # Metrics
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Relationship
    sequence: Mapped["NurtureSequence"] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_nurture_step_sequence_order", "sequence_id", "step_order"),
    )


class NurtureEnrollmentStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CONVERTED = "converted"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    EXITED = "exited"


class NurtureEnrollment(Base):
    """Contact enrollment in a nurture sequence."""
    __tablename__ = "nurture_enrollments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("nurture_sequences.id", ondelete="CASCADE"),
        nullable=False,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[NurtureEnrollmentStatus] = mapped_column(
        Enum(NurtureEnrollmentStatus),
        nullable=False,
        server_default="active",
    )

    # Progress
    current_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("nurture_sequence_steps.id"), nullable=True)
    next_step_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    steps_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Engagement tracking
    emails_sent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    emails_opened: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    links_clicked: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    replies_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Entry/exit
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    exit_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Source tracking
    source: Mapped[Optional[str]] = mapped_column(Text)  # manual, trigger, segment_sync
    source_id: Mapped[Optional[str]] = mapped_column(Text)  # ID of triggering event

    # Relationships
    sequence: Mapped["NurtureSequence"] = relationship(back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint("sequence_id", "party_id", name="uq_nurture_enrollment_sequence_party"),
        Index("ix_nurture_enrollment_status", "status"),
        Index("ix_nurture_enrollment_next_step", "next_step_at"),
    )


# =============================================================================
# CONTACT SEGMENTS
# =============================================================================

class SegmentType(enum.Enum):
    STATIC = "static"  # Manually managed list
    DYNAMIC = "dynamic"  # Query-based, auto-updated


class ContactSegment(Base):
    """Contact segments for targeted outreach."""
    __tablename__ = "contact_segments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    segment_type: Mapped[SegmentType] = mapped_column(Enum(SegmentType), nullable=False, server_default="static")

    # For dynamic segments: filter criteria
    filter_criteria: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # {field: "role", operator: "equals", value: "lead", and: [...]}

    # Settings
    auto_refresh: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    refresh_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("24"))
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Denormalized counts
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=True)

    # Relationships
    members: Mapped[List["SegmentMembership"]] = relationship(back_populates="segment", cascade="all, delete-orphan")


class SegmentMembership(Base):
    """Membership in a contact segment."""
    __tablename__ = "segment_memberships"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    segment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contact_segments.id", ondelete="CASCADE"),
        nullable=False,
    )
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )

    # For dynamic segments, track match reason
    matched_criteria: Mapped[Optional[str]] = mapped_column(Text)
    match_score: Mapped[Optional[int]] = mapped_column(Integer)  # For ranked segments

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    added_by: Mapped[Optional[str]] = mapped_column(Text)  # manual, sync, import

    # Relationships
    segment: Mapped["ContactSegment"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("segment_id", "party_id", name="uq_segment_membership"),
        Index("ix_segment_membership_party", "party_id"),
    )


# =============================================================================
# LEAD SCORING RULES
# =============================================================================

class LeadScoringRuleType(enum.Enum):
    DEMOGRAPHIC = "demographic"  # Based on profile data
    BEHAVIORAL = "behavioral"  # Based on actions
    ENGAGEMENT = "engagement"  # Based on communication
    FIRMOGRAPHIC = "firmographic"  # Company-based (for B2B)
    DECAY = "decay"  # Score reduction over time


class LeadScoringRule(Base):
    """Automated lead scoring rules."""
    __tablename__ = "lead_scoring_rules"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    rule_type: Mapped[LeadScoringRuleType] = mapped_column(Enum(LeadScoringRuleType), nullable=False)

    # Condition
    field: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "party.linkedin_url", "activity.type"
    operator: Mapped[str] = mapped_column(Text, nullable=False)  # equals, contains, exists, gt, lt
    value: Mapped[Optional[str]] = mapped_column(Text)

    # Score impact
    score_change: Mapped[int] = mapped_column(Integer, nullable=False)  # +10, -5, etc.
    max_times: Mapped[Optional[int]] = mapped_column(Integer)  # Limit times this rule can apply
    cooldown_hours: Mapped[Optional[int]] = mapped_column(Integer)  # Hours before rule can apply again

    # For decay rules
    decay_days: Mapped[Optional[int]] = mapped_column(Integer)  # Days of inactivity before decay
    decay_percentage: Mapped[Optional[int]] = mapped_column(Integer)  # Percentage to reduce

    # Priority
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now())

    __table_args__ = (
        Index("ix_lead_scoring_rule_active", "is_active", "priority"),
    )


# =============================================================================
# COMMUNICATION TRACKING
# =============================================================================

class ProactiveCommunication(Base):
    """Track proactive outreach communications."""
    __tablename__ = "proactive_communications"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Communication details
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # email, sms, call, linkedin
    direction: Mapped[str] = mapped_column(Text, nullable=False, server_default="outbound")  # outbound, inbound
    subject: Mapped[Optional[str]] = mapped_column(Text)
    content_preview: Mapped[Optional[str]] = mapped_column(Text)  # First 500 chars

    # Source
    source_type: Mapped[Optional[str]] = mapped_column(Text)  # nurture_sequence, campaign, manual
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    nurture_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("nurture_sequence_steps.id"), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")  # pending, sent, delivered, opened, clicked, replied, bounced, failed
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Engagement metrics
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    links_clicked: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Sent by
    sent_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    __table_args__ = (
        Index("ix_proactive_comm_party", "party_id"),
        Index("ix_proactive_comm_status", "status"),
        Index("ix_proactive_comm_sent_at", "sent_at"),
    )

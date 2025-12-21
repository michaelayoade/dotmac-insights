"""Support/Helpdesk Settings Models

Comprehensive support configuration including SLA defaults, routing strategies,
auto-close policies, escalation rules, and notification settings.
"""
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Time,
    Numeric, Text, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class DefaultRoutingStrategy(str, Enum):
    """Default ticket routing strategy"""
    ROUND_ROBIN = "ROUND_ROBIN"  # Distribute evenly
    LEAST_BUSY = "LEAST_BUSY"  # Agent with fewest open tickets
    SKILL_BASED = "SKILL_BASED"  # Match skills to ticket type
    LOAD_BALANCED = "LOAD_BALANCED"  # Based on capacity utilization
    MANUAL = "MANUAL"  # No auto-assignment


class TicketAutoCloseAction(str, Enum):
    """What to do when auto-closing"""
    CLOSE = "CLOSE"  # Close the ticket
    ARCHIVE = "ARCHIVE"  # Archive the ticket
    NOTIFY_ONLY = "NOTIFY_ONLY"  # Just notify, don't close


class EscalationTrigger(str, Enum):
    """What triggers escalation"""
    SLA_BREACH = "SLA_BREACH"  # SLA target breached
    SLA_WARNING = "SLA_WARNING"  # SLA warning threshold
    IDLE_TIME = "IDLE_TIME"  # No activity for X hours
    CUSTOMER_ESCALATION = "CUSTOMER_ESCALATION"  # Customer requested
    REOPEN_COUNT = "REOPEN_COUNT"  # Ticket reopened X times


class NotificationChannel(str, Enum):
    """Channels for sending notifications"""
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"
    SMS = "SMS"
    SLACK = "SLACK"
    WEBHOOK = "WEBHOOK"


class TicketPriorityDefault(str, Enum):
    """Default priority for new tickets"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class CSATSurveyTrigger(str, Enum):
    """When to send CSAT surveys"""
    ON_RESOLVE = "ON_RESOLVE"  # When ticket resolved
    ON_CLOSE = "ON_CLOSE"  # When ticket closed
    MANUAL = "MANUAL"  # Manual trigger only
    DISABLED = "DISABLED"  # No surveys


class WorkingHoursType(str, Enum):
    """Type of business hours"""
    STANDARD = "STANDARD"  # Mon-Fri 9-5
    EXTENDED = "EXTENDED"  # Mon-Sat 8-8
    ROUND_THE_CLOCK = "ROUND_THE_CLOCK"  # 24x7
    CUSTOM = "CUSTOM"  # Custom schedule


# =============================================================================
# SUPPORT SETTINGS MODEL
# =============================================================================

class SupportSettings(Base):
    """Company-wide support/helpdesk configuration settings"""
    __tablename__ = "support_settings"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, unique=True, index=True)

    # -------------------------------------------------------------------------
    # BUSINESS HOURS
    # -------------------------------------------------------------------------
    working_hours_type: Mapped[WorkingHoursType] = mapped_column(
        SAEnum(WorkingHoursType, name="workinghourstype"),
        nullable=False, default=WorkingHoursType.STANDARD
    )
    timezone = Column(String(50), nullable=False, default="Africa/Lagos")

    # Weekly schedule (JSON: {"MONDAY": {"start": "09:00", "end": "17:00", "closed": false}, ...})
    weekly_schedule = Column(JSON, nullable=False, default={
        "MONDAY": {"start": "09:00", "end": "17:00", "closed": False},
        "TUESDAY": {"start": "09:00", "end": "17:00", "closed": False},
        "WEDNESDAY": {"start": "09:00", "end": "17:00", "closed": False},
        "THURSDAY": {"start": "09:00", "end": "17:00", "closed": False},
        "FRIDAY": {"start": "09:00", "end": "17:00", "closed": False},
        "SATURDAY": {"start": "00:00", "end": "00:00", "closed": True},
        "SUNDAY": {"start": "00:00", "end": "00:00", "closed": True},
    })

    # Holiday calendar reference
    holiday_calendar_id = Column(Integer, nullable=True)  # Reference to holiday calendar

    # -------------------------------------------------------------------------
    # SLA DEFAULTS
    # -------------------------------------------------------------------------
    default_sla_policy_id = Column(Integer, nullable=True)  # FK to sla_policies.id - not enforced in model
    sla_warning_threshold_percent = Column(Integer, nullable=False, default=80)  # Warn at 80% of target
    sla_include_holidays = Column(Boolean, nullable=False, default=False)  # Count holidays in SLA
    sla_include_weekends = Column(Boolean, nullable=False, default=False)  # Count weekends in SLA

    # Default targets (hours) when no SLA policy matches
    default_first_response_hours = Column(Numeric(6, 2), nullable=False, default=Decimal("4.00"))
    default_resolution_hours = Column(Numeric(6, 2), nullable=False, default=Decimal("24.00"))

    # -------------------------------------------------------------------------
    # TICKET ROUTING
    # -------------------------------------------------------------------------
    default_routing_strategy: Mapped[DefaultRoutingStrategy] = mapped_column(
        SAEnum(DefaultRoutingStrategy, name="defaultroutingstrategy"),
        nullable=False, default=DefaultRoutingStrategy.ROUND_ROBIN
    )
    default_team_id = Column(Integer, nullable=True)  # FK to teams.id - not enforced in model
    fallback_team_id = Column(Integer, nullable=True)  # FK to teams.id - not enforced in model
    auto_assign_enabled = Column(Boolean, nullable=False, default=True)

    # Routing limits
    max_tickets_per_agent = Column(Integer, nullable=False, default=20)
    rebalance_threshold_percent = Column(Integer, nullable=False, default=30)  # Rebalance if agent exceeds avg by X%

    # -------------------------------------------------------------------------
    # TICKET DEFAULTS
    # -------------------------------------------------------------------------
    default_priority: Mapped[TicketPriorityDefault] = mapped_column(
        SAEnum(TicketPriorityDefault, name="ticketprioritydefault"),
        nullable=False, default=TicketPriorityDefault.MEDIUM
    )
    default_ticket_type = Column(String(50), nullable=True)  # Default ticket type/category
    allow_customer_priority_selection = Column(Boolean, nullable=False, default=False)
    allow_customer_team_selection = Column(Boolean, nullable=False, default=False)

    # -------------------------------------------------------------------------
    # AUTO-CLOSE SETTINGS
    # -------------------------------------------------------------------------
    auto_close_enabled = Column(Boolean, nullable=False, default=True)
    auto_close_resolved_days = Column(Integer, nullable=False, default=7)  # Days after resolved
    auto_close_action: Mapped[TicketAutoCloseAction] = mapped_column(
        SAEnum(TicketAutoCloseAction, name="ticketautocloseaction"),
        nullable=False, default=TicketAutoCloseAction.CLOSE
    )
    auto_close_notify_customer = Column(Boolean, nullable=False, default=True)

    # Reopen settings
    allow_customer_reopen = Column(Boolean, nullable=False, default=True)
    reopen_window_days = Column(Integer, nullable=False, default=7)  # Days after close customer can reopen
    max_reopens_allowed = Column(Integer, nullable=False, default=3)

    # -------------------------------------------------------------------------
    # ESCALATION DEFAULTS
    # -------------------------------------------------------------------------
    escalation_enabled = Column(Boolean, nullable=False, default=True)
    default_escalation_team_id = Column(Integer, nullable=True)  # FK to teams.id - not enforced in model
    escalation_notify_manager = Column(Boolean, nullable=False, default=True)

    # Idle ticket escalation
    idle_escalation_enabled = Column(Boolean, nullable=False, default=True)
    idle_hours_before_escalation = Column(Integer, nullable=False, default=48)

    # Reopen escalation
    reopen_escalation_enabled = Column(Boolean, nullable=False, default=True)
    reopen_count_for_escalation = Column(Integer, nullable=False, default=2)

    # -------------------------------------------------------------------------
    # CSAT / CUSTOMER FEEDBACK
    # -------------------------------------------------------------------------
    csat_enabled = Column(Boolean, nullable=False, default=True)
    csat_survey_trigger: Mapped[CSATSurveyTrigger] = mapped_column(
        SAEnum(CSATSurveyTrigger, name="csatsurveytrigger"),
        nullable=False, default=CSATSurveyTrigger.ON_RESOLVE
    )
    csat_delay_hours = Column(Integer, nullable=False, default=24)  # Hours after trigger before sending
    csat_reminder_enabled = Column(Boolean, nullable=False, default=True)
    csat_reminder_days = Column(Integer, nullable=False, default=3)  # Days before reminder
    csat_survey_expiry_days = Column(Integer, nullable=False, default=14)  # Days before survey expires
    default_csat_survey_id = Column(Integer, nullable=True)  # FK to csat_surveys.id - not enforced in model

    # -------------------------------------------------------------------------
    # CUSTOMER PORTAL
    # -------------------------------------------------------------------------
    portal_enabled = Column(Boolean, nullable=False, default=True)
    portal_ticket_creation_enabled = Column(Boolean, nullable=False, default=True)
    portal_show_ticket_history = Column(Boolean, nullable=False, default=True)
    portal_show_knowledge_base = Column(Boolean, nullable=False, default=True)
    portal_show_faq = Column(Boolean, nullable=False, default=True)
    portal_require_login = Column(Boolean, nullable=False, default=True)

    # -------------------------------------------------------------------------
    # KNOWLEDGE BASE
    # -------------------------------------------------------------------------
    kb_enabled = Column(Boolean, nullable=False, default=True)
    kb_public_access = Column(Boolean, nullable=False, default=True)  # Public or authenticated only
    kb_suggest_articles_on_create = Column(Boolean, nullable=False, default=True)
    kb_track_article_helpfulness = Column(Boolean, nullable=False, default=True)

    # -------------------------------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------------------------------
    notification_channels = Column(JSON, nullable=False, default=["EMAIL", "IN_APP"])

    # Event notifications (JSON: {"ticket_created": true, "ticket_assigned": true, ...})
    notification_events = Column(JSON, nullable=False, default={
        "ticket_created": True,
        "ticket_assigned": True,
        "ticket_replied": True,
        "ticket_resolved": True,
        "ticket_closed": True,
        "ticket_reopened": True,
        "sla_warning": True,
        "sla_breach": True,
        "ticket_escalated": True,
        "customer_replied": True,
    })

    # Who gets notified
    notify_assigned_agent = Column(Boolean, nullable=False, default=True)
    notify_team_on_unassigned = Column(Boolean, nullable=False, default=True)
    notify_customer_on_status_change = Column(Boolean, nullable=False, default=True)
    notify_customer_on_reply = Column(Boolean, nullable=False, default=True)

    # -------------------------------------------------------------------------
    # QUEUE MANAGEMENT
    # -------------------------------------------------------------------------
    unassigned_warning_minutes = Column(Integer, nullable=False, default=30)  # Warn if unassigned > X mins
    overdue_highlight_enabled = Column(Boolean, nullable=False, default=True)
    queue_refresh_seconds = Column(Integer, nullable=False, default=60)  # Auto-refresh interval

    # -------------------------------------------------------------------------
    # INTEGRATIONS
    # -------------------------------------------------------------------------
    email_to_ticket_enabled = Column(Boolean, nullable=False, default=True)
    email_reply_to_address = Column(String(255), nullable=True)  # Reply-to for ticket emails

    # External system sync
    sync_to_erpnext = Column(Boolean, nullable=False, default=False)
    sync_to_splynx = Column(Boolean, nullable=False, default=False)
    sync_to_chatwoot = Column(Boolean, nullable=False, default=False)

    # -------------------------------------------------------------------------
    # DATA RETENTION
    # -------------------------------------------------------------------------
    archive_closed_tickets_days = Column(Integer, nullable=False, default=365)  # Archive after X days
    delete_archived_tickets_days = Column(Integer, nullable=False, default=0)  # 0 = never delete

    # -------------------------------------------------------------------------
    # DISPLAY & FORMATTING
    # -------------------------------------------------------------------------
    ticket_id_prefix = Column(String(10), nullable=False, default="TKT")
    ticket_id_min_digits = Column(Integer, nullable=False, default=6)
    date_format = Column(String(20), nullable=False, default="DD/MM/YYYY")
    time_format = Column(String(10), nullable=False, default="HH:mm")

    # -------------------------------------------------------------------------
    # TIMESTAMPS & AUDIT
    # -------------------------------------------------------------------------
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    # Note: Other relationships removed - access via FKs directly


# =============================================================================
# ESCALATION POLICY
# =============================================================================

class EscalationPolicy(Base):
    """Multi-level escalation configuration"""
    __tablename__ = "escalation_policies"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Matching conditions (JSON: [{"field": "priority", "operator": "equals", "value": "URGENT"}, ...])
    conditions = Column(JSON, nullable=False, default=[])
    priority = Column(Integer, nullable=False, default=100)  # Lower = higher priority

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    levels = relationship("EscalationLevel", back_populates="policy", cascade="all, delete-orphan", order_by="EscalationLevel.level")
    created_by = relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        UniqueConstraint("company", "name", name="uq_escalation_policy_company_name"),
    )


class EscalationLevel(Base):
    """Individual escalation level within a policy"""
    __tablename__ = "escalation_levels"

    id = Column(Integer, primary_key=True)
    policy_id = Column(Integer, ForeignKey("escalation_policies.id", ondelete="CASCADE"), nullable=False, index=True)

    level = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    trigger: Mapped[EscalationTrigger] = mapped_column(
        SAEnum(EscalationTrigger, name="escalationtrigger"),
        nullable=False, default=EscalationTrigger.SLA_BREACH
    )
    trigger_hours = Column(Integer, nullable=False, default=0)  # Hours after trigger condition

    # Target
    escalate_to_team_id = Column(Integer, nullable=True)  # FK to teams.id - not enforced in model
    escalate_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Actions
    notify_current_assignee = Column(Boolean, nullable=False, default=True)
    notify_team_lead = Column(Boolean, nullable=False, default=True)
    reassign_ticket = Column(Boolean, nullable=False, default=False)
    change_priority = Column(Boolean, nullable=False, default=False)
    new_priority = Column(String(20), nullable=True)  # If change_priority is True

    # Notification template
    notification_template = Column(Text, nullable=True)

    # Relationships
    policy = relationship("EscalationPolicy", back_populates="levels")
    escalate_to_user = relationship("User", foreign_keys=[escalate_to_user_id])
    # Note: escalate_to_team removed - access via FK directly

    __table_args__ = (
        UniqueConstraint("policy_id", "level", name="uq_escalation_level_policy_level"),
    )


# =============================================================================
# SUPPORT QUEUE
# =============================================================================

class SupportQueue(Base):
    """Custom ticket queues/views"""
    __tablename__ = "support_queues"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Queue type
    queue_type = Column(String(20), nullable=False, default="CUSTOM")  # SYSTEM, CUSTOM

    # Filter conditions (JSON: [{"field": "status", "operator": "in", "value": ["OPEN", "PENDING"]}, ...])
    filters = Column(JSON, nullable=False, default=[])

    # Sort order
    sort_by = Column(String(50), nullable=False, default="created_at")
    sort_direction = Column(String(4), nullable=False, default="DESC")

    # Visibility
    is_public = Column(Boolean, nullable=False, default=True)  # Visible to all agents
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # For private queues

    # Display
    display_order = Column(Integer, nullable=False, default=100)
    icon = Column(String(50), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])

    __table_args__ = (
        UniqueConstraint("company", "name", name="uq_support_queue_company_name"),
    )


# =============================================================================
# TICKET FIELD CONFIGURATION
# =============================================================================

class TicketFieldConfig(Base):
    """Custom field configuration for tickets"""
    __tablename__ = "ticket_field_configs"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)

    field_name = Column(String(100), nullable=False)
    field_key = Column(String(50), nullable=False)  # Unique key for the field
    field_type = Column(String(20), nullable=False)  # TEXT, NUMBER, DROPDOWN, MULTISELECT, DATE, DATETIME, CHECKBOX, URL, EMAIL

    # For dropdown/multiselect
    options = Column(JSON, nullable=True)  # [{"value": "opt1", "label": "Option 1"}, ...]

    # Validation
    is_required = Column(Boolean, nullable=False, default=False)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    validation_regex = Column(String(255), nullable=True)
    default_value = Column(String(255), nullable=True)

    # Display
    display_order = Column(Integer, nullable=False, default=100)
    show_in_list = Column(Boolean, nullable=False, default=False)
    show_in_create_form = Column(Boolean, nullable=False, default=True)
    show_in_customer_portal = Column(Boolean, nullable=False, default=False)

    # Applicability
    applies_to_types = Column(JSON, nullable=True)  # List of ticket types, null = all

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company", "field_key", name="uq_ticket_field_config_company_key"),
    )


# =============================================================================
# EMAIL TEMPLATE
# =============================================================================

class SupportEmailTemplate(Base):
    """Email templates for support notifications"""
    __tablename__ = "support_email_templates"

    id = Column(Integer, primary_key=True)
    company = Column(String(255), nullable=True, index=True)

    name = Column(String(100), nullable=False)
    template_type = Column(String(50), nullable=False, index=True)  # TICKET_CREATED, TICKET_REPLIED, SLA_WARNING, etc.

    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)  # Plain text fallback

    # Placeholders supported (for reference)
    supported_placeholders = Column(JSON, nullable=False, default=[
        "{{ticket_id}}", "{{ticket_subject}}", "{{customer_name}}",
        "{{agent_name}}", "{{ticket_status}}", "{{ticket_priority}}",
        "{{company_name}}", "{{portal_url}}", "{{ticket_url}}"
    ])

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company", "template_type", name="uq_support_email_template_company_type"),
    )

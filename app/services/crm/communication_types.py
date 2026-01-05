"""Type definitions for CRM communication service.

These dataclasses define the contract for proactive communication operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


__all__ = [
    "CommunicationFilters",
    "CommunicationCreateData",
    "CommunicationUpdateData",
    "CommunicationScheduleData",
    "CommunicationMetrics",
    "CommunicationSummary",
    "ChannelPerformance",
    "ContactPreferences",
    "BulkCommunicationResult",
]


@dataclass
class CommunicationFilters:
    """Filters for listing communications."""

    search: Optional[str] = None
    channel: Optional[str] = None  # email, sms, whatsapp, call
    status: Optional[str] = None  # pending, sent, delivered, opened, clicked, failed
    party_id: Optional[int] = None
    campaign_id: Optional[int] = None
    sequence_id: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    sent_after: Optional[datetime] = None
    sent_before: Optional[datetime] = None


@dataclass
class CommunicationCreateData:
    """Data for creating a communication."""

    party_id: int
    channel: str  # email, sms, whatsapp, call
    communication_type: str = "outreach"  # outreach, follow_up, notification, marketing

    # Content
    subject: Optional[str] = None
    content: str = ""
    template_id: Optional[int] = None

    # Scheduling
    scheduled_at: Optional[datetime] = None  # None = send immediately

    # Context
    campaign_id: Optional[int] = None
    sequence_id: Optional[int] = None
    opportunity_id: Optional[int] = None

    # Personalization
    personalization_data: Dict[str, Any] = field(default_factory=dict)

    # Settings
    priority: str = "normal"  # low, normal, high, urgent
    track_opens: bool = True
    track_clicks: bool = True


@dataclass
class CommunicationUpdateData:
    """Data for updating a communication."""

    subject: Optional[str] = None
    content: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    priority: Optional[str] = None


@dataclass
class CommunicationScheduleData:
    """Data for bulk scheduling communications."""

    party_ids: List[int]
    channel: str
    subject: Optional[str] = None
    content: str = ""
    template_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    campaign_id: Optional[int] = None
    respect_preferences: bool = True
    respect_frequency_limits: bool = True


@dataclass
class CommunicationMetrics:
    """Metrics for a single communication."""

    communication_id: int
    party_id: int
    party_name: str
    channel: str
    status: str

    # Timing
    created_at: datetime
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]

    # Engagement
    open_count: int
    click_count: int
    links_clicked: List[str]
    time_to_open_seconds: Optional[int]

    # Response
    replied: bool
    reply_at: Optional[datetime]
    converted: bool


@dataclass
class CommunicationSummary:
    """Summary of all communications."""

    total_communications: int
    pending_count: int
    sent_count: int
    delivered_count: int
    opened_count: int
    clicked_count: int
    failed_count: int

    # Rates
    delivery_rate: float
    open_rate: float
    click_rate: float
    reply_rate: float

    # By channel
    by_channel: Dict[str, Dict[str, int]]  # {channel: {status: count}}

    # Time-based
    sent_today: int
    sent_this_week: int
    sent_this_month: int

    # Top performers
    top_templates: List[Dict[str, Any]]
    best_sending_times: List[Dict[str, Any]]


@dataclass
class ChannelPerformance:
    """Performance metrics for a communication channel."""

    channel: str
    total_sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    failed: int

    delivery_rate: float
    open_rate: float
    click_rate: float
    reply_rate: float
    failure_rate: float

    avg_time_to_open_minutes: Optional[float]
    best_day_of_week: Optional[str]
    best_hour_of_day: Optional[int]

    # Trend
    trend_vs_last_period: float  # percentage change


@dataclass
class ContactPreferences:
    """Communication preferences for a contact."""

    party_id: int
    party_name: str

    preferred_channel: Optional[str]
    do_not_contact: bool
    contact_frequency_limit: Optional[int]

    # Derived preferences
    best_contact_time: Optional[str]
    responsive_channels: List[str]
    avg_response_time_hours: Optional[float]

    # History
    total_communications: int
    last_contacted_at: Optional[datetime]
    last_response_at: Optional[datetime]
    days_since_contact: Optional[int]

    # Engagement
    overall_open_rate: float
    overall_click_rate: float
    overall_reply_rate: float


@dataclass
class BulkCommunicationResult:
    """Result of bulk communication operation."""

    total_requested: int
    scheduled_count: int
    skipped_do_not_contact: int
    skipped_frequency_limit: int
    skipped_no_contact_info: int
    failed_count: int

    scheduled_ids: List[int]
    skipped_party_ids: List[int]
    failure_details: List[Dict[str, Any]]

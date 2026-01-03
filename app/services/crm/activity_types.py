"""Type definitions for activity service.

These dataclasses define the contract for CRM activity operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


__all__ = [
    "ActivityFilters",
    "ActivityCreateData",
    "ActivityUpdateData",
    "CallLogData",
    "ActivitySummary",
    "ActivityTimeline",
]


@dataclass
class ActivityFilters:
    """Filters for listing activities."""

    search: Optional[str] = None
    activity_type: Optional[str] = None  # call, meeting, email, task, note, demo, follow_up
    status: Optional[str] = None  # planned, completed, cancelled
    party_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    owner_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: Optional[str] = None  # low, medium, high
    scheduled_after: Optional[datetime] = None
    scheduled_before: Optional[datetime] = None
    completed_after: Optional[datetime] = None
    completed_before: Optional[datetime] = None
    has_reminder: Optional[bool] = None


@dataclass
class ActivityCreateData:
    """Data for creating an activity."""

    activity_type: str  # call, meeting, email, task, note, demo, follow_up
    subject: str
    description: Optional[str] = None
    status: str = "planned"
    party_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    owner_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: str = "medium"
    reminder_at: Optional[datetime] = None

    # Call-specific
    call_direction: Optional[str] = None  # inbound, outbound
    call_outcome: Optional[str] = None

    # Email-specific
    email_message_id: Optional[str] = None


@dataclass
class ActivityUpdateData:
    """Data for updating an activity (all fields optional)."""

    subject: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: Optional[str] = None
    reminder_at: Optional[datetime] = None
    call_outcome: Optional[str] = None


@dataclass
class CallLogData:
    """Data for logging a call activity."""

    subject: str
    party_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    direction: str = "outbound"  # inbound, outbound
    outcome: Optional[str] = None  # connected, voicemail, no_answer, busy
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    owner_id: Optional[int] = None
    scheduled_follow_up: Optional[datetime] = None


@dataclass
class ActivitySummary:
    """Summary statistics for activities."""

    total_count: int
    planned_count: int
    completed_count: int
    cancelled_count: int
    overdue_count: int
    completion_rate: float
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    avg_duration_minutes: float


@dataclass
class ActivityTimeline:
    """Timeline of activities for an entity."""

    entity_type: str  # party, opportunity
    entity_id: int
    activities: List[Dict]  # List of serialized activities
    total_count: int

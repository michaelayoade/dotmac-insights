"""Type definitions for nurture sequence service.

These dataclasses define the contract for nurture sequence operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


__all__ = [
    "NurtureSequenceFilters",
    "NurtureSequenceCreateData",
    "NurtureSequenceUpdateData",
    "NurtureStepCreateData",
    "NurtureStepUpdateData",
    "EnrollmentCreateData",
    "NurtureSequenceSummary",
    "NurtureSequenceMetrics",
    "EnrollmentProgress",
]


@dataclass
class NurtureSequenceFilters:
    """Filters for listing nurture sequences."""

    search: Optional[str] = None
    status: Optional[str] = None
    campaign_id: Optional[int] = None
    created_by: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


@dataclass
class NurtureSequenceCreateData:
    """Data for creating a nurture sequence."""

    name: str
    description: Optional[str] = None
    target_segment_id: Optional[int] = None
    entry_trigger: Optional[str] = None
    entry_conditions: Dict[str, Any] = field(default_factory=dict)

    # Settings
    allow_reentry: bool = False
    exit_on_reply: bool = True
    exit_on_conversion: bool = True
    respect_contact_preferences: bool = True
    timezone_aware: bool = True
    send_window_start: Optional[int] = None  # 0-23
    send_window_end: Optional[int] = None
    exclude_weekends: bool = False

    campaign_id: Optional[int] = None


@dataclass
class NurtureSequenceUpdateData:
    """Data for updating a nurture sequence."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    target_segment_id: Optional[int] = None
    entry_trigger: Optional[str] = None
    entry_conditions: Optional[Dict[str, Any]] = None

    allow_reentry: Optional[bool] = None
    exit_on_reply: Optional[bool] = None
    exit_on_conversion: Optional[bool] = None
    respect_contact_preferences: Optional[bool] = None
    timezone_aware: Optional[bool] = None
    send_window_start: Optional[int] = None
    send_window_end: Optional[int] = None
    exclude_weekends: Optional[bool] = None


@dataclass
class NurtureStepCreateData:
    """Data for creating a nurture step."""

    step_type: str  # email, sms, task, wait, condition, webhook
    step_order: int
    name: Optional[str] = None

    # Timing
    delay_days: int = 0
    delay_hours: int = 0
    delay_minutes: int = 0

    # Content
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[int] = None

    # Condition fields
    condition_field: Optional[str] = None
    condition_operator: Optional[str] = None
    condition_value: Optional[str] = None
    true_step_id: Optional[int] = None
    false_step_id: Optional[int] = None

    # Task fields
    task_type: Optional[str] = None
    task_assignee_id: Optional[int] = None
    task_priority: str = "medium"

    # Webhook fields
    webhook_url: Optional[str] = None
    webhook_method: str = "POST"
    webhook_headers: Dict[str, str] = field(default_factory=dict)
    webhook_payload: Optional[str] = None

    # A/B testing
    is_ab_test: bool = False
    ab_variant: Optional[str] = None
    ab_weight: int = 100


@dataclass
class NurtureStepUpdateData:
    """Data for updating a nurture step."""

    name: Optional[str] = None
    step_order: Optional[int] = None
    delay_days: Optional[int] = None
    delay_hours: Optional[int] = None
    delay_minutes: Optional[int] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class EnrollmentCreateData:
    """Data for enrolling a contact in a sequence."""

    party_id: int
    source: str = "manual"
    source_id: Optional[str] = None


@dataclass
class NurtureSequenceSummary:
    """Summary of all nurture sequences."""

    total_sequences: int
    active_sequences: int
    draft_sequences: int
    paused_sequences: int
    total_enrolled: int
    total_completed: int
    avg_conversion_rate: float


@dataclass
class NurtureSequenceMetrics:
    """Metrics for a single nurture sequence."""

    sequence_id: int
    sequence_name: str
    status: str
    total_steps: int
    total_enrolled: int
    active_enrolled: int
    completed: int
    converted: int
    unsubscribed: int
    conversion_rate: float
    completion_rate: float
    avg_time_to_complete_days: Optional[float]
    step_metrics: List[Dict[str, Any]]  # Per-step open/click rates


@dataclass
class EnrollmentProgress:
    """Progress of a contact through a sequence."""

    enrollment_id: int
    party_id: int
    party_name: str
    sequence_id: int
    sequence_name: str
    status: str
    current_step: int
    total_steps: int
    progress_percent: float
    next_step_at: Optional[datetime]
    emails_sent: int
    emails_opened: int
    open_rate: float
    enrolled_at: datetime
    completed_at: Optional[datetime]

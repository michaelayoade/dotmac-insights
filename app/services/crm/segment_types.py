"""Type definitions for contact segmentation service.

These dataclasses define the contract for segmentation operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


__all__ = [
    "SegmentFilters",
    "SegmentCreateData",
    "SegmentUpdateData",
    "SegmentRuleData",
    "SegmentMembershipData",
    "SegmentSummary",
    "SegmentAnalytics",
    "MembershipChange",
]


@dataclass
class SegmentFilters:
    """Filters for listing segments."""

    search: Optional[str] = None
    segment_type: Optional[str] = None  # static, dynamic
    is_active: Optional[bool] = None
    created_by: Optional[int] = None
    has_members: Optional[bool] = None


@dataclass
class SegmentRuleData:
    """A single rule in a dynamic segment."""

    field: str  # e.g., "party_type", "engagement_score", "tags"
    operator: str  # equals, not_equals, contains, gt, lt, gte, lte, in, not_in
    value: Any
    conjunction: str = "AND"  # AND, OR


@dataclass
class SegmentCreateData:
    """Data for creating a segment."""

    name: str
    description: Optional[str] = None
    segment_type: str = "static"  # static, dynamic

    # For dynamic segments
    rules: List[SegmentRuleData] = field(default_factory=list)
    rule_conjunction: str = "AND"  # How to combine rules

    # Settings
    auto_refresh: bool = True
    refresh_interval_hours: int = 24
    is_active: bool = True

    # Initial members for static segments
    party_ids: List[int] = field(default_factory=list)


@dataclass
class SegmentUpdateData:
    """Data for updating a segment."""

    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[List[SegmentRuleData]] = None
    rule_conjunction: Optional[str] = None
    auto_refresh: Optional[bool] = None
    refresh_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class SegmentMembershipData:
    """Data for adding/removing segment members."""

    party_ids: List[int]
    source: str = "manual"  # manual, import, automation


@dataclass
class SegmentSummary:
    """Summary of all segments."""

    total_segments: int
    active_segments: int
    static_segments: int
    dynamic_segments: int
    total_members: int
    avg_segment_size: float
    largest_segment_name: Optional[str]
    largest_segment_size: int


@dataclass
class SegmentAnalytics:
    """Analytics for a single segment."""

    segment_id: int
    segment_name: str
    segment_type: str
    member_count: int
    member_growth_30d: int
    member_growth_rate: float

    # Member composition
    party_type_breakdown: Dict[str, int]
    engagement_score_distribution: Dict[str, int]  # low, medium, high
    preferred_channel_breakdown: Dict[str, int]

    # Engagement metrics
    avg_engagement_score: float
    contacts_with_email: int
    contacts_with_phone: int
    do_not_contact_count: int

    # Timeline
    created_at: datetime
    last_refreshed_at: Optional[datetime]
    next_refresh_at: Optional[datetime]


@dataclass
class MembershipChange:
    """Record of a membership change."""

    party_id: int
    party_name: str
    action: str  # added, removed
    source: str
    changed_at: datetime
    changed_by: Optional[int]

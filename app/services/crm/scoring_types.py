"""Type definitions for lead scoring service.

These dataclasses define the contract for lead scoring operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


__all__ = [
    "ScoringRuleFilters",
    "ScoringRuleCreateData",
    "ScoringRuleUpdateData",
    "ScoringCondition",
    "ScoreAdjustment",
    "LeadScoreResult",
    "ScoringRuleSummary",
    "ScoreDistribution",
    "ScoreHistory",
]


@dataclass
class ScoringRuleFilters:
    """Filters for listing scoring rules."""

    search: Optional[str] = None
    rule_type: Optional[str] = None  # attribute, behavior, engagement
    is_active: Optional[bool] = None
    category: Optional[str] = None


@dataclass
class ScoringCondition:
    """A condition that must be met for a scoring rule."""

    field: str  # e.g., "party_type", "engagement_score", "industry"
    operator: str  # equals, contains, gt, lt, in, etc.
    value: Any


@dataclass
class ScoringRuleCreateData:
    """Data for creating a scoring rule."""

    name: str
    description: Optional[str] = None
    rule_type: str = "attribute"  # attribute, behavior, engagement
    category: Optional[str] = None  # demographic, firmographic, behavioral, engagement

    # Conditions (all must match for rule to apply)
    conditions: List[ScoringCondition] = field(default_factory=list)

    # Score to add/subtract when conditions match
    score_change: int = 0

    # Score decay settings
    decay_enabled: bool = False
    decay_days: int = 30
    decay_amount: int = 0

    # Priority for rule ordering
    priority: int = 100
    is_active: bool = True


@dataclass
class ScoringRuleUpdateData:
    """Data for updating a scoring rule."""

    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    category: Optional[str] = None
    conditions: Optional[List[ScoringCondition]] = None
    score_change: Optional[int] = None
    decay_enabled: Optional[bool] = None
    decay_days: Optional[int] = None
    decay_amount: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class ScoreAdjustment:
    """Record of a score adjustment."""

    rule_id: int
    rule_name: str
    rule_type: str
    score_change: int
    reason: str
    applied_at: datetime


@dataclass
class LeadScoreResult:
    """Result of scoring a lead."""

    party_id: int
    party_name: str
    previous_score: int
    new_score: int
    score_change: int
    adjustments: List[ScoreAdjustment]
    grade: str  # A, B, C, D, F based on thresholds
    qualified: bool  # Based on qualification threshold
    calculated_at: datetime


@dataclass
class ScoringRuleSummary:
    """Summary of scoring rules."""

    total_rules: int
    active_rules: int
    rules_by_type: Dict[str, int]
    rules_by_category: Dict[str, int]
    avg_score_change: float
    top_scoring_rules: List[Dict[str, Any]]


@dataclass
class ScoreDistribution:
    """Distribution of lead scores across the database."""

    total_leads: int
    scored_leads: int
    unscored_leads: int
    avg_score: float
    median_score: float
    min_score: int
    max_score: int

    # Distribution buckets
    grade_a_count: int  # 80-100
    grade_b_count: int  # 60-79
    grade_c_count: int  # 40-59
    grade_d_count: int  # 20-39
    grade_f_count: int  # 0-19

    qualified_count: int
    unqualified_count: int


@dataclass
class ScoreHistory:
    """Historical score data for a lead."""

    party_id: int
    party_name: str
    current_score: int
    current_grade: str

    # Score over time
    score_timeline: List[Dict[str, Any]]  # [{date, score, change, rule_name}]

    # Adjustment summary
    total_positive_adjustments: int
    total_negative_adjustments: int
    net_change_30d: int
    net_change_90d: int

    # Rule breakdown
    rules_applied: List[Dict[str, Any]]  # [{rule_id, rule_name, times_applied, total_impact}]

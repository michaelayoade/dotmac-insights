"""Type definitions for opportunity service.

These dataclasses define the contract for opportunity operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


__all__ = [
    "OpportunityFilters",
    "OpportunityCreateData",
    "OpportunityUpdateData",
    "PipelineSummary",
    "StageSummary",
]


@dataclass
class OpportunityFilters:
    """Filters for listing opportunities."""

    search: Optional[str] = None
    status: Optional[str] = None  # open, won, lost
    stage_id: Optional[int] = None
    party_id: Optional[int] = None
    owner_id: Optional[int] = None
    sales_person_id: Optional[int] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    expected_close_before: Optional[date] = None
    expected_close_after: Optional[date] = None
    campaign_id: Optional[int] = None
    source: Optional[str] = None


@dataclass
class OpportunityCreateData:
    """Data for creating an opportunity."""

    name: str
    party_id: int
    description: Optional[str] = None
    stage_id: Optional[int] = None
    deal_value: Decimal = Decimal("0")
    probability: int = 0
    currency: str = "NGN"
    expected_close_date: Optional[date] = None
    owner_id: Optional[int] = None
    sales_person_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None


@dataclass
class OpportunityUpdateData:
    """Data for updating an opportunity (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    party_id: Optional[int] = None
    stage_id: Optional[int] = None
    deal_value: Optional[Decimal] = None
    probability: Optional[int] = None
    currency: Optional[str] = None
    expected_close_date: Optional[date] = None
    owner_id: Optional[int] = None
    sales_person_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None
    campaign_id: Optional[int] = None
    lost_reason: Optional[str] = None
    competitor: Optional[str] = None


@dataclass
class StageSummary:
    """Summary stats for a pipeline stage."""

    stage_id: int
    stage_name: str
    color: Optional[str]
    probability: int
    count: int
    value: Decimal


@dataclass
class PipelineSummary:
    """Pipeline summary with stage breakdown."""

    total_opportunities: int
    total_value: Decimal
    weighted_value: Decimal
    won_count: int
    won_value: Decimal
    lost_count: int
    by_stage: List[StageSummary]
    avg_deal_size: Decimal
    win_rate: float

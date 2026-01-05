"""Type definitions for campaign service.

These dataclasses define the contract for campaign operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional


__all__ = [
    "CampaignFilters",
    "CampaignCreateData",
    "CampaignUpdateData",
    "CampaignROI",
    "CampaignPerformance",
    "CampaignSummary",
]


@dataclass
class CampaignFilters:
    """Filters for listing campaigns."""

    search: Optional[str] = None
    campaign_type: Optional[str] = None  # email, social, event, etc.
    is_active: Optional[bool] = None
    start_date_from: Optional[date] = None
    start_date_to: Optional[date] = None
    end_date_from: Optional[date] = None
    end_date_to: Optional[date] = None
    min_budget: Optional[Decimal] = None
    max_budget: Optional[Decimal] = None


@dataclass
class CampaignCreateData:
    """Data for creating a campaign."""

    name: str
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currency: str = "NGN"
    budget: Decimal = Decimal("0")


@dataclass
class CampaignUpdateData:
    """Data for updating a campaign (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    is_active: Optional[bool] = None


@dataclass
class CampaignROI:
    """Campaign ROI calculation."""

    campaign_id: int
    campaign_name: str
    budget: Decimal
    actual_cost: Decimal
    revenue_generated: Decimal
    roi_percentage: float  # (revenue - cost) / cost * 100
    cost_per_lead: Decimal
    cost_per_opportunity: Decimal


@dataclass
class CampaignPerformance:
    """Campaign performance metrics."""

    campaign_id: int
    campaign_name: str
    leads_generated: int
    opportunities_generated: int
    deals_won: int
    revenue_generated: Decimal
    conversion_rate: float  # leads to opportunities
    win_rate: float  # opportunities to deals


@dataclass
class CampaignSummary:
    """Summary statistics for campaigns."""

    total_campaigns: int
    active_campaigns: int
    total_budget: Decimal
    total_spent: Decimal
    total_leads: int
    total_opportunities: int
    total_revenue: Decimal
    overall_roi: float
    by_type: Dict[str, int]

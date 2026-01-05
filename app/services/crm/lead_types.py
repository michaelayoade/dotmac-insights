"""Type definitions for lead service.

These dataclasses define the contract for lead operations.
Leads are Party + PartyRole(role="lead") - NOT ERPNextLead.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


__all__ = [
    "LeadFilters",
    "LeadCreateData",
    "LeadUpdateData",
    "LeadScoreUpdate",
    "LeadConversionData",
    "LeadSummary",
    "LeadFunnel",
    "Lead",
]


@dataclass
class LeadFilters:
    """Filters for listing leads."""

    search: Optional[str] = None
    status: Optional[str] = None  # active, inactive, suspended (PartyRole status)
    qualification: Optional[str] = None
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    owner_id: Optional[int] = None  # owner_party_id
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


@dataclass
class LeadCreateData:
    """Data for creating a lead (Party + PartyRole)."""

    # Party fields
    name: str
    type: str = "person"  # person or organization
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None  # For organizations
    trading_name: Optional[str] = None  # For organizations
    notes: Optional[str] = None
    tags: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    # PartyRole (lead) fields
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None
    owner_party_id: Optional[int] = None


@dataclass
class LeadUpdateData:
    """Data for updating a lead (all fields optional)."""

    # Party fields
    name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[Dict[str, Any]]] = None
    custom_fields: Optional[Dict[str, Any]] = None

    # PartyRole (lead) fields
    status: Optional[str] = None  # active, inactive, suspended
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None
    owner_party_id: Optional[int] = None


@dataclass
class LeadScoreUpdate:
    """Data for updating lead score."""

    score: int
    reason: Optional[str] = None


@dataclass
class LeadConversionData:
    """Data for lead conversion to opportunity or customer."""

    # For opportunity conversion
    opportunity_name: Optional[str] = None
    deal_value: Optional[float] = None
    stage_id: Optional[int] = None
    expected_close_date: Optional[datetime] = None

    # For customer conversion
    customer_tier: Optional[str] = None
    payment_terms: Optional[str] = None


@dataclass
class Lead:
    """Composite lead object (Party + PartyRole)."""

    # Party info
    party_id: int
    name: str
    type: str
    primary_email: Optional[str]
    primary_phone: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    notes: Optional[str]
    tags: List[Dict[str, Any]]
    custom_fields: Dict[str, Any]
    created_at: datetime

    # PartyRole (lead) info
    role_id: int
    status: str
    source: Optional[str]
    source_campaign: Optional[str]
    qualification: Optional[str]
    lead_score: Optional[int]
    owner_party_id: Optional[int]
    role_since: datetime


@dataclass
class LeadSummary:
    """Summary statistics for leads."""

    total_leads: int
    active_leads: int
    qualified_leads: int
    unqualified_leads: int
    converted_leads: int
    avg_score: float
    by_source: Dict[str, int]
    by_qualification: Dict[str, int]


@dataclass
class LeadFunnel:
    """Lead funnel breakdown."""

    new: int
    contacted: int
    qualified: int
    proposal: int
    converted: int
    lost: int

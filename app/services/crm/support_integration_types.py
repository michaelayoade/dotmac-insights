"""Type definitions for Support-CRM integration service.

These dataclasses define the contract for bridging Support and CRM modules.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


__all__ = [
    "LeadFromConversationData",
    "LeadFromTicketData",
    "OpportunityFromTicketData",
    "TicketOpportunityLink",
    "PartyEnrichment",
    "SupportSummary",
    "RelatedEntities",
]


@dataclass
class LeadFromConversationData:
    """Data for creating a lead from a conversation."""

    lead_name: Optional[str] = None  # Defaults to contact name
    company_name: Optional[str] = None
    source: str = "inbox"
    qualification: Optional[str] = None
    owner_party_id: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class LeadFromTicketData:
    """Data for creating a lead from a ticket."""

    lead_name: Optional[str] = None  # Defaults to ticket contact
    company_name: Optional[str] = None
    source: str = "support"
    qualification: Optional[str] = None
    owner_party_id: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class OpportunityFromTicketData:
    """Data for creating an opportunity from a ticket."""

    opportunity_name: Optional[str] = None  # Defaults to ticket subject
    stage_id: Optional[int] = None
    deal_value: Decimal = Decimal("0")
    expected_close_date: Optional[datetime] = None
    source: str = "support"
    owner_id: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class TicketOpportunityLink:
    """Link between a ticket and an opportunity."""

    ticket_id: int
    opportunity_id: int
    created_at: datetime
    created_by: Optional[int] = None


@dataclass
class PartyEnrichment:
    """Enriched party data from support history."""

    party_id: int
    ticket_count: int
    open_ticket_count: int
    resolved_ticket_count: int
    avg_response_time_hours: Optional[float]
    avg_resolution_time_hours: Optional[float]
    satisfaction_score: Optional[float]  # CSAT average
    first_contact_date: Optional[datetime]
    last_contact_date: Optional[datetime]
    total_conversations: int
    tags: List[str]


@dataclass
class SupportSummary:
    """Support summary for a party or opportunity."""

    entity_type: str  # party or opportunity
    entity_id: int
    open_tickets: int
    resolved_tickets: int
    total_tickets: int
    csat_avg: Optional[float]
    avg_response_time_hours: Optional[float]
    recent_tickets: List[Dict[str, Any]]


@dataclass
class RelatedEntities:
    """Cross-module search results."""

    query: str
    leads: List[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]
    tickets: List[Dict[str, Any]]
    conversations: List[Dict[str, Any]]
    total_results: int

"""Type definitions for ticket service.

These dataclasses define the contract for ticket operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.ticket import TicketPriority, TicketStatus

__all__ = [
    "TicketFilters",
    "TicketCreateData",
    "TicketUpdateData",
    "CommentData",
    "ActivityData",
    "AssignmentData",
    "SLAUpdateData",
    "DependencyData",
    "CommunicationData",
    "MergeData",
    "SplitData",
    "BulkUpdateData",
    "BulkResult",
]


@dataclass
class TicketFilters:
    """Filters for listing tickets."""

    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    customer_account_id: Optional[int] = None
    party_id: Optional[int] = None
    ticket_type: Optional[str] = None
    assigned_to: Optional[str] = None
    search: Optional[str] = None
    overdue_only: bool = False
    unassigned_only: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class TicketCreateData:
    """Data for creating a ticket."""

    subject: str
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    description: Optional[str] = None
    ticket_type: Optional[str] = None
    issue_type: Optional[str] = None
    customer_account_id: Optional[int] = None
    party_id: Optional[int] = None
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    resolution_by: Optional[datetime] = None
    response_by: Optional[datetime] = None
    resolution_team: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    region: Optional[str] = None
    base_station: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    watchers: List[int] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    parent_ticket_id: Optional[int] = None


@dataclass
class TicketUpdateData:
    """Data for updating a ticket (all fields optional)."""

    subject: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    ticket_type: Optional[str] = None
    issue_type: Optional[str] = None
    customer_account_id: Optional[int] = None
    party_id: Optional[int] = None
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    resolution_by: Optional[datetime] = None
    response_by: Optional[datetime] = None
    resolution_team: Optional[str] = None
    resolution: Optional[str] = None
    resolution_details: Optional[str] = None
    resolution_date: Optional[datetime] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    region: Optional[str] = None
    base_station: Optional[str] = None
    tags: Optional[List[str]] = None
    watchers: Optional[List[int]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    parent_ticket_id: Optional[int] = None
    merged_into_id: Optional[int] = None


@dataclass
class CommentData:
    """Data for creating/updating a ticket comment."""

    comment: str
    comment_type: Optional[str] = None
    commented_by: Optional[str] = None
    commented_by_name: Optional[str] = None
    is_public: bool = True
    comment_date: Optional[datetime] = None


@dataclass
class ActivityData:
    """Data for creating/updating a ticket activity."""

    activity: str
    activity_type: Optional[str] = None
    owner: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    activity_date: Optional[datetime] = None


@dataclass
class AssignmentData:
    """Data for assigning a ticket."""

    team_id: Optional[int] = None
    member_id: Optional[int] = None
    employee_id: Optional[int] = None
    assigned_to: Optional[str] = None
    agent_id: Optional[int] = None


@dataclass
class SLAUpdateData:
    """Data for updating ticket SLA dates."""

    response_by: Optional[datetime] = None
    resolution_by: Optional[datetime] = None
    reason: Optional[str] = None


@dataclass
class DependencyData:
    """Data for creating/updating a ticket dependency."""

    depends_on_ticket_id: Optional[int] = None
    depends_on_erpnext_id: Optional[str] = None
    depends_on_subject: Optional[str] = None
    depends_on_status: Optional[str] = None


@dataclass
class CommunicationData:
    """Data for creating/updating a ticket communication."""

    communication_type: Optional[str] = None
    communication_medium: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    sender: Optional[str] = None
    sender_full_name: Optional[str] = None
    recipients: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    sent_or_received: Optional[str] = None
    read_receipt: bool = False
    delivery_status: Optional[str] = None
    communication_date: Optional[datetime] = None


@dataclass
class MergeData:
    """Data for merging tickets."""

    source_ticket_ids: List[int] = field(default_factory=list)
    close_source_tickets: bool = True


@dataclass
class SplitData:
    """Data for splitting/creating a sub-ticket."""

    subject: str = ""
    description: Optional[str] = None
    copy_tags: bool = True
    copy_custom_fields: bool = False


@dataclass
class BulkUpdateData:
    """Data for bulk updating tickets."""

    ids: List[int] = field(default_factory=list)
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[str] = None
    assigned_employee_id: Optional[int] = None


@dataclass
class BulkResult:
    """Result of a bulk operation."""

    updated_count: int = 0
    deleted_count: int = 0
    failed_ids: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

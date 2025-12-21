"""
Unified Ticket Model

Consolidates all support ticket entities into a single source of truth:
- Ticket (current HD tickets from ERPNext, Splynx)
- Conversation (Chatwoot conversations)
- OmniConversation (cross-channel inbox)

Ticket Lifecycle: open → in_progress → waiting → resolved → closed
"""
from __future__ import annotations

from sqlalchemy import (
    String, Text, Enum, DateTime, ForeignKey, Boolean, Integer,
    Float, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.unified_contact import UnifiedContact
    from app.models.employee import Employee
    from app.models.ticket import Ticket
    from app.models.conversation import Conversation
    from app.models.agent import Team


# =============================================================================
# ENUMS
# =============================================================================

class TicketType(enum.Enum):
    """Type of support ticket."""
    SUPPORT = "support"              # General support request
    TECHNICAL = "technical"          # Technical issue
    BILLING = "billing"              # Billing/payment issue
    SERVICE = "service"              # Service request (install, move, etc.)
    COMPLAINT = "complaint"          # Customer complaint
    INQUIRY = "inquiry"              # General inquiry
    FEATURE_REQUEST = "feature"      # Feature request
    BUG = "bug"                      # Bug report


class TicketSource(enum.Enum):
    """Origin system of the ticket."""
    ERPNEXT = "erpnext"
    SPLYNX = "splynx"
    CHATWOOT = "chatwoot"
    EMAIL = "email"
    PHONE = "phone"
    WEB = "web"
    API = "api"
    INTERNAL = "internal"


class TicketStatus(enum.Enum):
    """Ticket lifecycle status."""
    OPEN = "open"                    # New, unassigned
    IN_PROGRESS = "in_progress"      # Being worked on
    WAITING = "waiting"              # Waiting for customer response
    ON_HOLD = "on_hold"              # Paused (external dependency)
    RESOLVED = "resolved"            # Solution provided
    CLOSED = "closed"                # Confirmed closed
    REOPENED = "reopened"            # Reopened after close


class TicketPriority(enum.Enum):
    """Ticket urgency level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class TicketChannel(enum.Enum):
    """Communication channel for the ticket."""
    EMAIL = "email"
    PHONE = "phone"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    WEB_FORM = "web_form"
    API = "api"
    IN_PERSON = "in_person"


# =============================================================================
# UNIFIED TICKET MODEL
# =============================================================================

class UnifiedTicket(Base):
    """
    Unified ticket record - single source of truth for all support data.

    Replaces/consolidates: Ticket, Conversation, OmniConversation

    This model serves as the canonical record. Data can flow:
    - Inbound: External systems → UnifiedTicket (via sync)
    - Outbound: UnifiedTicket → External systems (via dual-write)
    - Local: Created directly in unified system
    """

    __tablename__ = "unified_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ==========================================================================
    # TYPE & CLASSIFICATION
    # ==========================================================================

    ticket_type: Mapped[TicketType] = mapped_column(
        Enum(TicketType),
        default=TicketType.SUPPORT,
        index=True
    )
    source: Mapped[TicketSource] = mapped_column(
        Enum(TicketSource),
        default=TicketSource.INTERNAL,
        index=True
    )
    channel: Mapped[Optional[TicketChannel]] = mapped_column(
        Enum(TicketChannel),
        nullable=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus),
        default=TicketStatus.OPEN,
        index=True
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority),
        default=TicketPriority.MEDIUM,
        index=True
    )

    # ==========================================================================
    # TICKET INFO
    # ==========================================================================

    # Display number (auto-generated or from source)
    ticket_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=True
    )

    subject: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Category/Classification
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ==========================================================================
    # CUSTOMER/CONTACT REFERENCE
    # ==========================================================================

    # Primary link to unified contact
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Denormalized for quick access (updated via triggers/app logic)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ==========================================================================
    # ASSIGNMENT & OWNERSHIP
    # ==========================================================================

    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
        index=True
    )
    assigned_team: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # TEXT for display
    assigned_team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id"), nullable=True, index=True
    )  # FK for local queries
    assigned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Creator (if internal)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True
    )

    # ==========================================================================
    # SLA TRACKING
    # ==========================================================================

    # SLA targets
    response_by: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    resolution_by: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    # Actual times
    first_response_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # SLA breach flags
    response_sla_breached: Mapped[bool] = mapped_column(default=False)
    resolution_sla_breached: Mapped[bool] = mapped_column(default=False)

    # Time tracking (in seconds)
    first_response_time_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    resolution_time_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_time_open_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)

    # ==========================================================================
    # RESOLUTION
    # ==========================================================================

    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # CSAT
    csat_sent: Mapped[bool] = mapped_column(default=False)
    csat_rating: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5
    csat_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ==========================================================================
    # EXTERNAL SYSTEM IDS
    # ==========================================================================

    # Source system IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    chatwoot_conversation_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)

    # Legacy table links (for migration/backfill)
    legacy_ticket_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    legacy_conversation_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    legacy_omni_conversation_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)

    # ==========================================================================
    # LOCATION/CONTEXT
    # ==========================================================================

    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    base_station: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ==========================================================================
    # METADATA & TAGS
    # ==========================================================================

    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ["escalated", "vip"]
    labels: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # Chatwoot labels
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Message/activity counts
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    public_reply_count: Mapped[int] = mapped_column(Integer, default=0)
    internal_note_count: Mapped[int] = mapped_column(Integer, default=0)

    # ==========================================================================
    # TICKET RELATIONSHIPS
    # ==========================================================================

    # Parent ticket (for sub-tickets)
    parent_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_tickets.id"),
        nullable=True,
        index=True
    )

    # Merged tickets tracking
    merged_into_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_tickets.id"),
        nullable=True
    )
    merged_ticket_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ==========================================================================
    # SYNC & OUTBOUND TRACKING
    # ==========================================================================

    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Outbound sync hashes (for change detection)
    splynx_sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    erpnext_sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chatwoot_sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Last successful outbound sync times
    last_synced_to_splynx: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_synced_to_erpnext: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_synced_to_chatwoot: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Write-back status tracking
    write_back_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    write_back_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_back_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ==========================================================================
    # AUDIT & SOFT DELETE
    # ==========================================================================

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(
        foreign_keys=[unified_contact_id]
    )
    assigned_to: Mapped[Optional["Employee"]] = relationship(
        back_populates="assigned_unified_tickets",
        foreign_keys=[assigned_to_id]
    )
    assigned_team_rel: Mapped[Optional["Team"]] = relationship(
        "Team",
        foreign_keys=[assigned_team_id],
        backref="unified_tickets"
    )
    created_by: Mapped[Optional["Employee"]] = relationship(
        back_populates="created_unified_tickets",
        foreign_keys=[created_by_id]
    )

    # Self-referential relationships
    parent_ticket: Mapped[Optional["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        remote_side="[UnifiedTicket.id]",
        foreign_keys="[UnifiedTicket.parent_ticket_id]"
    )
    sub_tickets: Mapped[List["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        foreign_keys="[UnifiedTicket.parent_ticket_id]",
        back_populates="parent_ticket"
    )

    merged_into: Mapped[Optional["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        remote_side="[UnifiedTicket.id]",
        foreign_keys="[UnifiedTicket.merged_into_id]"
    )

    # ==========================================================================
    # TABLE CONFIGURATION
    # ==========================================================================

    __table_args__ = (
        # Composite indexes for common queries
        Index("ix_unified_tickets_status_priority", "status", "priority"),
        Index("ix_unified_tickets_assigned_status", "assigned_to_id", "status"),
        Index("ix_unified_tickets_contact_status", "unified_contact_id", "status"),
        Index("ix_unified_tickets_source_status", "source", "status"),
        Index("ix_unified_tickets_created_status", "created_at", "status"),
        Index("ix_unified_tickets_sla_response", "response_by", "response_sla_breached"),
        Index("ix_unified_tickets_sla_resolution", "resolution_by", "resolution_sla_breached"),
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        return f"<UnifiedTicket {self.id}: {self.ticket_number} ({self.status.value})>"

    @property
    def is_open(self) -> bool:
        """Check if ticket is in an open state."""
        return self.status in (
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING,
            TicketStatus.REOPENED
        )

    @property
    def is_closed(self) -> bool:
        """Check if ticket is fully closed."""
        return self.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)

    @property
    def is_overdue_response(self) -> bool:
        """Check if response SLA is breached."""
        if self.first_response_at or not self.response_by:
            return False
        return utc_now() > self.response_by

    @property
    def is_overdue_resolution(self) -> bool:
        """Check if resolution SLA is breached."""
        if self.resolved_at or not self.resolution_by:
            return False
        return utc_now() > self.resolution_by

    @property
    def first_response_time_hours(self) -> Optional[float]:
        """First response time in hours."""
        if self.first_response_time_seconds:
            return self.first_response_time_seconds / 3600
        return None

    @property
    def resolution_time_hours(self) -> Optional[float]:
        """Resolution time in hours."""
        if self.resolution_time_seconds:
            return self.resolution_time_seconds / 3600
        return None

    def assign(self, employee_id: int, team: Optional[str] = None) -> None:
        """Assign ticket to an agent."""
        self.assigned_to_id = employee_id
        if team:
            self.assigned_team = team
        self.assigned_at = datetime.utcnow()
        if self.status == TicketStatus.OPEN:
            self.status = TicketStatus.IN_PROGRESS

    def resolve(self, resolution: str, resolution_type: Optional[str] = None) -> None:
        """Mark ticket as resolved."""
        self.status = TicketStatus.RESOLVED
        self.resolution = resolution
        self.resolution_type = resolution_type
        self.resolved_at = datetime.utcnow()
        if self.created_at:
            self.resolution_time_seconds = int(
                (self.resolved_at - self.created_at).total_seconds()
            )

    def close(self) -> None:
        """Close the ticket (after resolution confirmed)."""
        self.status = TicketStatus.CLOSED
        self.closed_at = datetime.utcnow()

    def reopen(self) -> None:
        """Reopen a closed ticket."""
        self.status = TicketStatus.REOPENED
        self.resolved_at = None
        self.closed_at = None

    def record_first_response(self) -> None:
        """Record first response time."""
        if not self.first_response_at:
            self.first_response_at = datetime.utcnow()
            if self.created_at:
                self.first_response_time_seconds = int(
                    (self.first_response_at - self.created_at).total_seconds()
                )
            # Check SLA breach
            if self.response_by and self.first_response_at > self.response_by:
                self.response_sla_breached = True

    def soft_delete(self, deleted_by: Optional[int] = None) -> None:
        """Soft delete the ticket."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = deleted_by

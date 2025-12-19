from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.utils.datetime_utils import utc_now
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.project import Project
    from app.models.expense import Expense
    from app.models.unified_ticket import UnifiedTicket


class TicketStatus(enum.Enum):
    OPEN = "open"
    REPLIED = "replied"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class TicketPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketSource(enum.Enum):
    ERPNEXT = "erpnext"
    SPLYNX = "splynx"
    CHATWOOT = "chatwoot"


class Ticket(SoftDeleteMixin, Base):
    """HD Tickets (Help Desk) from ERPNext and other sources."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    splynx_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    # Source system
    source: Mapped[TicketSource] = mapped_column(Enum(TicketSource), default=TicketSource.ERPNEXT, index=True)

    # FK Relationships
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)

    # Link to UnifiedTicket (for dual-write sync)
    unified_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_tickets.id"),
        nullable=True,
        index=True
    )

    # ERPNext references (for linking)
    erpnext_customer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    erpnext_project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Ticket details
    ticket_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    issue_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status & Priority
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.MEDIUM, index=True)

    # Assignment - Employee FKs
    assigned_employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    resolution_team: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Legacy/String fields for non-linked data
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raised_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Customer info from ticket (for matching when no FK)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Location info
    region: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_station: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # SLA tracking
    response_by: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolution_by: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    agreement_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_responded_on: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Resolution
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Feedback
    feedback_rating: Mapped[Optional[int]] = mapped_column(nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    opening_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    resolution_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Sync metadata / audit
    origin_system: Mapped[str] = mapped_column(String(50), default="external")
    write_back_status: Mapped[str] = mapped_column(String(50), default="synced")
    write_back_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_back_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    # is_deleted, deleted_at, deleted_by_id inherited from SoftDeleteMixin
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="tickets")
    employee: Mapped[Optional[Employee]] = relationship(
        back_populates="tickets", foreign_keys=[employee_id]
    )
    assigned_employee: Mapped[Optional[Employee]] = relationship(
        foreign_keys=[assigned_employee_id]
    )
    project: Mapped[Optional[Project]] = relationship(back_populates="tickets")

    # Link to UnifiedTicket (for dual-write sync)
    unified_ticket: Mapped[Optional["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        foreign_keys=[unified_ticket_id],
        backref="legacy_ticket"
    )

    # Child tables
    comments: Mapped[List["HDTicketComment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    activities: Mapped[List["HDTicketActivity"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    communications: Mapped[List["TicketCommunication"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    depends_on: Mapped[List["HDTicketDependency"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", foreign_keys="HDTicketDependency.ticket_id"
    )
    # Expense claims linked to this ticket
    expenses: Mapped[List["Expense"]] = relationship(
        back_populates="ticket"
    )

    # Enhancements (Phase 3)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # simple tag names
    watchers: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # user IDs watching the ticket
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # field_key -> value
    merged_into_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    merged_tickets: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # ticket IDs merged into this
    parent_ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    csat_sent: Mapped[bool] = mapped_column(default=False)
    csat_response_id: Mapped[Optional[int]] = mapped_column(ForeignKey("csat_responses.id", ondelete="SET NULL"), nullable=True)

    merged_into: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", remote_side=[id], foreign_keys=[merged_into_id]
    )
    parent_ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", remote_side=[id], foreign_keys=[parent_ticket_id]
    )

    def __repr__(self) -> str:
        return f"<Ticket {self.ticket_number} - {self.status.value}>"

    @property
    def is_overdue(self) -> bool:
        """Check if ticket is overdue based on resolution_by SLA."""
        if self.resolution_by and self.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return utc_now() > self.resolution_by
        return False

    @property
    def time_to_resolution_hours(self) -> Optional[float]:
        """Calculate time from opening to resolution in hours."""
        if self.opening_date and self.resolution_date:
            delta = self.resolution_date - self.opening_date
            return delta.total_seconds() / 3600
        return None


# ============= HD TICKET COMMENT (Child Table) =============

class HDTicketComment(Base):
    """Comments on HD Tickets from ERPNext.

    This is the HD Ticket Comment child table that stores
    comments/replies on tickets.
    """

    __tablename__ = "hd_ticket_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Comment content
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Comment, Info, etc.

    # Author info
    commented_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commented_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Visibility
    is_public: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    comment_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    ticket: Mapped["Ticket"] = relationship(back_populates="comments")

    def __repr__(self) -> str:
        return f"<HDTicketComment {self.id} by {self.commented_by}>"


# ============= HD TICKET ACTIVITY (Child Table) =============

class HDTicketActivity(Base):
    """Activity log entries for HD Tickets from ERPNext.

    Tracks status changes, assignments, and other activities on tickets.
    """

    __tablename__ = "hd_ticket_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Activity info
    activity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Status Change, Assignment, etc.
    activity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Who performed the activity
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status tracking
    from_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    activity_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    ticket: Mapped["Ticket"] = relationship(back_populates="activities")

    def __repr__(self) -> str:
        return f"<HDTicketActivity {self.id} - {self.activity_type}>"


# ============= COMMUNICATION (Linked emails/messages) =============

class TicketCommunication(Base):
    """Communications linked to HD Tickets from ERPNext.

    Stores email communications, phone logs, and other messages
    linked to tickets via the Communication doctype.
    """

    __tablename__ = "ticket_communications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext reference
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Communication details
    communication_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Email, Phone, Chat, etc.
    communication_medium: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Email, Phone, etc.

    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sender/Recipient
    sender: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sender_full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipients: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bcc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Direction
    sent_or_received: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Sent, Received

    # Status
    read_receipt: Mapped[bool] = mapped_column(default=False)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    communication_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationship
    ticket: Mapped["Ticket"] = relationship(back_populates="communications")

    def __repr__(self) -> str:
        return f"<TicketCommunication {self.erpnext_id} - {self.communication_type}>"


# ============= HD TICKET DEPENDENCY (Depends On Child Table) =============

class HDTicketDependency(Base):
    """Ticket dependencies from ERPNext's 'Depends On' child table.

    Tracks which tickets depend on other tickets (blockers).
    """

    __tablename__ = "hd_ticket_dependencies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # The ticket this depends on
    depends_on_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    depends_on_erpnext_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    depends_on_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    depends_on_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Relationships
    ticket: Mapped["Ticket"] = relationship(
        back_populates="depends_on", foreign_keys=[ticket_id]
    )
    depends_on_ticket: Mapped[Optional["Ticket"]] = relationship(
        foreign_keys=[depends_on_ticket_id]
    )

    def __repr__(self) -> str:
        return f"<HDTicketDependency {self.ticket_id} depends on {self.depends_on_erpnext_id}>"

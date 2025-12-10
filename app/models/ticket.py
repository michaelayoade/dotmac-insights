from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.project import Project


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


class Ticket(Base):
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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
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

    def __repr__(self) -> str:
        return f"<Ticket {self.ticket_number} - {self.status.value}>"

    @property
    def is_overdue(self) -> bool:
        """Check if ticket is overdue based on resolution_by SLA."""
        if self.resolution_by and self.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return datetime.utcnow() > self.resolution_by
        return False

    @property
    def time_to_resolution_hours(self) -> Optional[float]:
        """Calculate time from opening to resolution in hours."""
        if self.opening_date and self.resolution_date:
            delta = self.resolution_date - self.opening_date
            return delta.total_seconds() / 3600
        return None

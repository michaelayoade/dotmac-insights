"""
CRM Models - Opportunities, Activities, Contacts

Customer Lifecycle: Lead → Opportunity → Quotation → Order → Invoice → Retention
"""
from __future__ import annotations

from sqlalchemy import String, Text, Enum, Date, DateTime, ForeignKey, Boolean, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.sales import ERPNextLead, Quotation, SalesOrder, SalesPerson
    from app.models.employee import Employee
    from app.models.unified_contact import UnifiedContact


# ============= OPPORTUNITY STAGE =============
class OpportunityStage(Base):
    """Configurable pipeline stages for opportunities."""

    __tablename__ = "opportunity_stages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sequence: Mapped[int] = mapped_column(default=0, index=True)
    probability: Mapped[int] = mapped_column(default=0)  # 0-100%

    # Stage type
    is_won: Mapped[bool] = mapped_column(default=False)
    is_lost: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Display
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "emerald", "amber"

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    opportunities: Mapped[List["Opportunity"]] = relationship(back_populates="stage_rel")

    def __repr__(self) -> str:
        return f"<OpportunityStage {self.name} ({self.probability}%)>"


# ============= OPPORTUNITY STATUS =============
class OpportunityStatus(enum.Enum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class Opportunity(Base):
    """Sales opportunities / deals in the pipeline."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Opportunity info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source - either a lead or existing customer
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("erpnext_leads.id"), nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    # Link to unified contact (replaces lead_id/customer_id after migration)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Pipeline
    stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunity_stages.id"), nullable=True, index=True)
    status: Mapped[OpportunityStatus] = mapped_column(Enum(OpportunityStatus), default=OpportunityStatus.OPEN, index=True)

    # Deal value
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    deal_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    probability: Mapped[int] = mapped_column(default=0)  # 0-100%, can override stage probability
    weighted_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))  # deal_value * probability/100

    # Dates
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    actual_close_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Owner
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    sales_person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales_persons.id"), nullable=True, index=True)

    # Source/Campaign (TEXT fields for ERPNext sync)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., "Website", "Referral"
    campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Campaign FK (for local queries)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True, index=True
    )

    # Lost reason (if status = lost)
    lost_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Linked documents
    quotation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quotations.id"), nullable=True)
    sales_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales_orders.id"), nullable=True)

    # ERPNext sync
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead: Mapped[Optional["ERPNextLead"]] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])
    stage_rel: Mapped[Optional["OpportunityStage"]] = relationship(back_populates="opportunities")
    owner: Mapped[Optional["Employee"]] = relationship()
    sales_person: Mapped[Optional["SalesPerson"]] = relationship()
    quotation: Mapped[Optional["Quotation"]] = relationship()
    sales_order: Mapped[Optional["SalesOrder"]] = relationship()
    campaign_rel: Mapped[Optional["Campaign"]] = relationship(
        "Campaign",
        foreign_keys=[campaign_id],
        backref="opportunities"
    )
    activities: Mapped[List["Activity"]] = relationship(back_populates="opportunity")

    def __repr__(self) -> str:
        return f"<Opportunity {self.name} ({self.status.value})>"

    def update_weighted_value(self) -> None:
        """Recalculate weighted value based on deal value and probability."""
        self.weighted_value = self.deal_value * Decimal(self.probability) / Decimal("100")


# ============= ACTIVITY TYPE =============
class ActivityType(enum.Enum):
    CALL = "call"
    MEETING = "meeting"
    EMAIL = "email"
    TASK = "task"
    NOTE = "note"
    DEMO = "demo"
    FOLLOW_UP = "follow_up"


class ActivityStatus(enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Activity(Base):
    """Activities/interactions (calls, meetings, emails, tasks) linked to leads, customers, or opportunities."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Activity info
    activity_type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[ActivityStatus] = mapped_column(Enum(ActivityStatus), default=ActivityStatus.PLANNED, index=True)

    # Linked entities (at least one should be set)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("erpnext_leads.id"), nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)

    # Link to unified contact (replaces lead_id/customer_id/contact_id after migration)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Owner/Assignee
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # Call-specific
    call_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # inbound/outbound
    call_outcome: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Email-specific
    email_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Priority
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="medium")  # low/medium/high

    # Reminder
    reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead: Mapped[Optional["ERPNextLead"]] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="activities")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="activities")
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])
    owner: Mapped[Optional["Employee"]] = relationship(foreign_keys=[owner_id])
    assigned_to: Mapped[Optional["Employee"]] = relationship(foreign_keys=[assigned_to_id])

    def __repr__(self) -> str:
        return f"<Activity {self.activity_type.value}: {self.subject}>"


# ============= CONTACT =============
class Contact(Base):
    """
    Contacts - multiple contacts per customer/lead.

    DEPRECATED: This model will be replaced by UnifiedContact with contact_type=PERSON.
    Use unified_contact_id to link to the new UnifiedContact model.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Linked to customer or lead (legacy)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("erpnext_leads.id"), nullable=True, index=True)

    # Link to unified contact (migration target)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Contact info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Contact details
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Role/Position
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "CEO", "IT Manager"
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Flags
    is_primary: Mapped[bool] = mapped_column(default=False, index=True)
    is_billing_contact: Mapped[bool] = mapped_column(default=False)
    is_decision_maker: Mapped[bool] = mapped_column(default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    unsubscribed: Mapped[bool] = mapped_column(default=False)  # Email opt-out

    # Social
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ERPNext sync
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship()
    lead: Mapped[Optional["ERPNextLead"]] = relationship()
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])
    activities: Mapped[List["Activity"]] = relationship(back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact {self.full_name}>"


# ============= LEAD SOURCE =============
class LeadSource(Base):
    """Configurable lead sources for attribution tracking."""

    __tablename__ = "lead_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tracking
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LeadSource {self.name}>"


# ============= CAMPAIGN =============
class Campaign(Base):
    """Marketing campaigns for lead/opportunity attribution."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Campaign type
    campaign_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # email, social, event, etc.

    # Dates
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Budget
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # Metrics (calculated)
    leads_generated: Mapped[int] = mapped_column(default=0)
    opportunities_generated: Mapped[int] = mapped_column(default=0)
    revenue_generated: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # ERPNext sync
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Campaign {self.name}>"

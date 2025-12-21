"""
Unified Contact Model

Consolidates all contact-related entities into a single source of truth:
- Customer (status=prospect removed - use contact_type=lead instead)
- ERPNextLead (deprecated - migrate to UnifiedContact with type=lead)
- Contact (CRM) (deprecated - migrate to UnifiedContact with parent_id)
- InboxContact (deprecated - migrate to UnifiedContact)

Contact Lifecycle: lead → prospect → customer → churned
Account vs Person: Organizations can have multiple person contacts (parent_id relationship)
"""
from __future__ import annotations

from sqlalchemy import (
    String, Text, Enum, Date, DateTime, ForeignKey, Boolean, Integer,
    Float, Numeric, Index, JSON, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, date
from app.utils.datetime_utils import utc_now
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.pop import Pop
    from app.models.employee import Employee


# =============================================================================
# ENUMS
# =============================================================================

class ContactType(enum.Enum):
    """Type of contact record."""
    LEAD = "lead"              # Pre-qualification prospect
    PROSPECT = "prospect"      # Qualified lead, not yet customer
    CUSTOMER = "customer"      # Active paying customer
    CHURNED = "churned"        # Former customer
    PERSON = "person"          # Individual contact at an organization


class ContactCategory(enum.Enum):
    """Business category."""
    RESIDENTIAL = "residential"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"


class ContactStatus(enum.Enum):
    """Operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DO_NOT_CONTACT = "do_not_contact"


class BillingType(enum.Enum):
    """Billing arrangement."""
    PREPAID = "prepaid"
    PREPAID_MONTHLY = "prepaid_monthly"
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class LeadQualification(enum.Enum):
    """Lead qualification status."""
    UNQUALIFIED = "unqualified"
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    QUALIFIED = "qualified"


# =============================================================================
# UNIFIED CONTACT MODEL
# =============================================================================

class UnifiedContact(Base):
    """
    Unified contact record - single source of truth for all contact data.

    Replaces: Customer, ERPNextLead, Contact (CRM), InboxContact

    Contact Type Guidelines:
    ========================
    - LEAD: Pre-sale prospect (replaces ERPNextLead)
        - is_organization=False for individuals, True for company leads
        - parent_id=NULL (standalone)

    - PROSPECT: Qualified lead in sales pipeline
        - Same as lead, just further along funnel
        - parent_id=NULL (standalone)

    - CUSTOMER: Active paying customer (replaces Customer table)
        - B2C individual: is_organization=False, parent_id=NULL
        - B2B company: is_organization=True, parent_id=NULL
        - parent_id=NULL (customers are top-level accounts)

    - CHURNED: Former customer
        - Same structure as customer, just different type

    - PERSON: Individual contact AT an organization (replaces CRM Contact)
        - ALWAYS is_organization=False
        - SHOULD have parent_id pointing to an organization
        - Examples: billing contact, decision maker, technical contact
        - Used for B2B where company is the customer but you track individuals

    Key Distinction:
    ===============
    - B2C individual customer → type=customer, is_organization=False, parent_id=NULL
    - B2B company customer → type=customer, is_organization=True, parent_id=NULL
    - Person at B2B company → type=person, is_organization=False, parent_id=<company_id>
    """

    __tablename__ = "unified_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ==========================================================================
    # TYPE & CLASSIFICATION
    # ==========================================================================

    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType),
        default=ContactType.LEAD,
        index=True
    )
    category: Mapped[ContactCategory] = mapped_column(
        Enum(ContactCategory),
        default=ContactCategory.RESIDENTIAL
    )
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus),
        default=ContactStatus.ACTIVE,
        index=True
    )

    # ==========================================================================
    # HIERARCHY (Person belongs to Organization)
    # ==========================================================================

    # If this is a person contact, parent_id points to the organization
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )
    is_organization: Mapped[bool] = mapped_column(default=False, index=True)

    # Person-specific fields (when is_organization=False and parent_id is set)
    is_primary_contact: Mapped[bool] = mapped_column(default=False)
    is_billing_contact: Mapped[bool] = mapped_column(default=False)
    is_decision_maker: Mapped[bool] = mapped_column(default=False)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Job title
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ==========================================================================
    # BASIC INFO
    # ==========================================================================

    # For organizations: company name; For persons: full name
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Person name parts (when not organization)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Company name (when is_organization=True or for lead's company)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # ==========================================================================
    # CONTACT DETAILS
    # ==========================================================================

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    email_secondary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    phone_secondary: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ==========================================================================
    # ADDRESS
    # ==========================================================================

    address_line1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Nigeria")

    # Geolocation
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    gps_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ==========================================================================
    # EXTERNAL SYSTEM IDS (Integration Links)
    # ==========================================================================

    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    zoho_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    # Legacy IDs for migration
    legacy_customer_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    legacy_lead_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    legacy_contact_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    legacy_inbox_contact_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)

    # ==========================================================================
    # ACCOUNT/BILLING INFO (for customers)
    # ==========================================================================

    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billing_type: Mapped[Optional[BillingType]] = mapped_column(Enum(BillingType), nullable=True)

    # Financial metrics
    mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    total_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    outstanding_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Billing status (from Splynx)
    blocking_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    days_until_blocking: Mapped[Optional[int]] = mapped_column(nullable=True)
    deposit_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # ==========================================================================
    # LEAD/SALES INFO
    # ==========================================================================

    lead_qualification: Mapped[Optional[LeadQualification]] = mapped_column(
        Enum(LeadQualification),
        nullable=True
    )
    lead_score: Mapped[Optional[int]] = mapped_column(nullable=True)  # 0-100

    # Source & Attribution
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    source_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Industry/Market
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    market_segment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    territory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # ==========================================================================
    # OWNERSHIP & ASSIGNMENT
    # ==========================================================================

    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
        index=True
    )
    sales_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_manager: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Location/POP (for ISP customers)
    pop_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pops.id"),
        nullable=True,
        index=True
    )
    base_station: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # ==========================================================================
    # LIFECYCLE DATES
    # ==========================================================================

    # Lead dates
    first_contact_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    # Conversion dates
    qualified_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    conversion_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # Lead → Customer

    # Customer dates
    signup_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    activation_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    contract_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Churn dates
    cancellation_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    churn_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ==========================================================================
    # COMMUNICATION PREFERENCES
    # ==========================================================================

    email_opt_in: Mapped[bool] = mapped_column(default=True)
    sms_opt_in: Mapped[bool] = mapped_column(default=True)
    whatsapp_opt_in: Mapped[bool] = mapped_column(default=True)
    phone_opt_in: Mapped[bool] = mapped_column(default=True)

    preferred_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="en")
    preferred_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # email, phone, whatsapp

    # ==========================================================================
    # TAGS & METADATA
    # ==========================================================================

    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ["vip", "enterprise"]
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Flexible extra data
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ==========================================================================
    # STATS (Denormalized for performance)
    # ==========================================================================

    total_conversations: Mapped[int] = mapped_column(Integer, default=0)
    total_tickets: Mapped[int] = mapped_column(Integer, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_invoices: Mapped[int] = mapped_column(Integer, default=0)

    # NPS/Satisfaction
    nps_score: Mapped[Optional[int]] = mapped_column(nullable=True)  # -100 to 100
    satisfaction_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-5

    # ==========================================================================
    # SYNC & AUDIT
    # ==========================================================================

    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Outbound sync tracking (for idempotency)
    splynx_sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    erpnext_sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_synced_to_splynx: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_synced_to_erpnext: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    # Self-referential: Organization → Persons
    child_contacts: Mapped[List["UnifiedContact"]] = relationship(
        "UnifiedContact",
        back_populates="parent",
        foreign_keys="[UnifiedContact.parent_id]"
    )
    parent: Mapped[Optional["UnifiedContact"]] = relationship(
        "UnifiedContact",
        back_populates="child_contacts",
        remote_side="[UnifiedContact.id]",
        foreign_keys="[UnifiedContact.parent_id]"
    )

    owner: Mapped[Optional["Employee"]] = relationship(foreign_keys=[owner_id])
    pop: Mapped[Optional["Pop"]] = relationship()

    # ==========================================================================
    # TABLE CONFIGURATION
    # ==========================================================================

    __table_args__ = (
        # Composite indexes for common queries
        Index("ix_unified_contacts_type_status", "contact_type", "status"),
        Index("ix_unified_contacts_email_type", "email", "contact_type"),
        Index("ix_unified_contacts_phone_type", "phone", "contact_type"),
        Index("ix_unified_contacts_owner_type", "owner_id", "contact_type"),
        Index("ix_unified_contacts_territory", "territory"),
        Index("ix_unified_contacts_source", "source"),

        # NOTE: We intentionally do NOT enforce parent_id requirement at DB level.
        # The 'person' contact_type CAN exist without a parent in these cases:
        #   - B2C individual customers (is_organization=False, contact_type=customer)
        #   - Standalone leads/prospects (contact_type=lead/prospect)
        #   - Contacts imported before their org exists
        # Application layer enforces parent requirement only when:
        #   - contact_type='person' AND the record is explicitly tied to an organization
        # See: app/api/contacts/schemas.py for validation rules
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        return f"<UnifiedContact {self.id}: {self.name} ({self.contact_type.value})>"

    @property
    def full_name(self) -> str:
        """Get full name for persons, or name for organizations."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name

    @property
    def is_lead(self) -> bool:
        return self.contact_type == ContactType.LEAD

    @property
    def is_prospect(self) -> bool:
        return self.contact_type == ContactType.PROSPECT

    @property
    def is_customer(self) -> bool:
        return self.contact_type == ContactType.CUSTOMER

    @property
    def is_churned(self) -> bool:
        return self.contact_type == ContactType.CHURNED

    @property
    def is_person(self) -> bool:
        return self.contact_type == ContactType.PERSON

    @property
    def tenure_days(self) -> int:
        """Days since becoming customer."""
        if not self.conversion_date:
            return 0
        end_date = self.cancellation_date or utc_now()
        return (end_date - self.conversion_date).days

    def convert_to_customer(self) -> None:
        """Convert lead/prospect to customer."""
        self.contact_type = ContactType.CUSTOMER
        self.conversion_date = utc_now()

    def mark_churned(self, reason: Optional[str] = None) -> None:
        """Mark customer as churned."""
        self.contact_type = ContactType.CHURNED
        self.cancellation_date = utc_now()
        self.churn_reason = reason

    def qualify_lead(self, qualification: LeadQualification) -> None:
        """Update lead qualification."""
        self.lead_qualification = qualification
        if qualification == LeadQualification.QUALIFIED:
            self.contact_type = ContactType.PROSPECT
            self.qualified_date = utc_now()

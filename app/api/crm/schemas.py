"""
CRM Contact API Schemas

Consolidated schemas for all contact types: lead, prospect, customer, churned, person.
"""
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# =============================================================================
# ENUMS (matching model enums)
# =============================================================================

class ContactTypeEnum(str, Enum):
    LEAD = "lead"
    PROSPECT = "prospect"
    CUSTOMER = "customer"
    CHURNED = "churned"
    PERSON = "person"


class ContactCategoryEnum(str, Enum):
    RESIDENTIAL = "residential"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"


class ContactStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DO_NOT_CONTACT = "do_not_contact"


class BillingTypeEnum(str, Enum):
    PREPAID = "prepaid"
    PREPAID_MONTHLY = "prepaid_monthly"
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class LeadQualificationEnum(str, Enum):
    UNQUALIFIED = "unqualified"
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    QUALIFIED = "qualified"


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class ContactBase(BaseModel):
    """Base fields for creating/updating contacts."""
    # Type & Classification
    contact_type: ContactTypeEnum = ContactTypeEnum.LEAD
    category: ContactCategoryEnum = ContactCategoryEnum.RESIDENTIAL
    status: ContactStatusEnum = ContactStatusEnum.ACTIVE

    # Hierarchy
    parent_id: Optional[int] = None
    is_organization: bool = False
    is_primary_contact: bool = False
    is_billing_contact: bool = False
    is_decision_maker: bool = False
    designation: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)

    # Basic Info
    name: str = Field(..., max_length=255)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)

    # Contact Details
    email: Optional[str] = Field(None, max_length=255)
    email_secondary: Optional[str] = Field(None, max_length=255)
    billing_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)
    mobile: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=255)

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field("Nigeria", max_length=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_raw: Optional[str] = Field(None, max_length=255)

    # External System IDs
    erpnext_id: Optional[str] = Field(None, max_length=255)
    zoho_id: Optional[str] = Field(None, max_length=100)

    # Account/Billing Info
    account_number: Optional[str] = Field(None, max_length=100)
    contract_number: Optional[str] = Field(None, max_length=100)
    vat_id: Optional[str] = Field(None, max_length=100)
    billing_type: Optional[BillingTypeEnum] = None
    mrr: Optional[Decimal] = None
    credit_limit: Optional[Decimal] = None

    # Lead/Sales Info
    lead_qualification: Optional[LeadQualificationEnum] = None
    lead_score: Optional[int] = Field(None, ge=0, le=100)
    source: Optional[str] = Field(None, max_length=255)
    source_campaign: Optional[str] = Field(None, max_length=255)
    referrer: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    market_segment: Optional[str] = Field(None, max_length=255)
    territory: Optional[str] = Field(None, max_length=255)

    # Ownership & Assignment
    owner_id: Optional[int] = None
    sales_person: Optional[str] = Field(None, max_length=255)
    account_manager: Optional[str] = Field(None, max_length=255)

    # Communication Preferences
    email_opt_in: bool = True
    sms_opt_in: bool = True
    whatsapp_opt_in: bool = True
    phone_opt_in: bool = True
    preferred_language: Optional[str] = Field("en", max_length=10)
    preferred_channel: Optional[str] = Field(None, max_length=50)

    # Tags & Metadata
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    """Schema for creating a new contact."""
    pass


class ContactUpdate(BaseModel):
    """Schema for updating a contact (all fields optional)."""
    # Type & Classification
    contact_type: Optional[ContactTypeEnum] = None
    category: Optional[ContactCategoryEnum] = None
    status: Optional[ContactStatusEnum] = None

    # Hierarchy
    parent_id: Optional[int] = None
    is_organization: Optional[bool] = None
    is_primary_contact: Optional[bool] = None
    is_billing_contact: Optional[bool] = None
    is_decision_maker: Optional[bool] = None
    designation: Optional[str] = None
    department: Optional[str] = None

    # Basic Info
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None

    # Contact Details
    email: Optional[str] = None
    email_secondary: Optional[str] = None
    billing_email: Optional[str] = None
    phone: Optional[str] = None
    phone_secondary: Optional[str] = None
    mobile: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_raw: Optional[str] = None

    # External System IDs
    erpnext_id: Optional[str] = None
    zoho_id: Optional[str] = None

    # Account/Billing Info
    account_number: Optional[str] = None
    contract_number: Optional[str] = None
    vat_id: Optional[str] = None
    billing_type: Optional[BillingTypeEnum] = None
    mrr: Optional[Decimal] = None
    credit_limit: Optional[Decimal] = None

    # Lead/Sales Info
    lead_qualification: Optional[LeadQualificationEnum] = None
    lead_score: Optional[int] = None
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    referrer: Optional[str] = None
    industry: Optional[str] = None
    market_segment: Optional[str] = None
    territory: Optional[str] = None

    # Ownership & Assignment
    owner_id: Optional[int] = None
    sales_person: Optional[str] = None
    account_manager: Optional[str] = None

    # Communication Preferences
    email_opt_in: Optional[bool] = None
    sms_opt_in: Optional[bool] = None
    whatsapp_opt_in: Optional[bool] = None
    phone_opt_in: Optional[bool] = None
    preferred_language: Optional[str] = None
    preferred_channel: Optional[str] = None

    # Tags & Metadata
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = None


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class ContactResponse(BaseModel):
    """Full contact response."""
    id: int

    # Type & Classification
    contact_type: ContactTypeEnum
    category: ContactCategoryEnum
    status: ContactStatusEnum

    # Hierarchy
    parent_id: Optional[int]
    is_organization: bool
    is_primary_contact: bool
    is_billing_contact: bool
    is_decision_maker: bool
    designation: Optional[str]
    department: Optional[str]

    # Basic Info
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    company_name: Optional[str]
    full_name: Optional[str] = None

    # Contact Details
    email: Optional[str]
    email_secondary: Optional[str]
    billing_email: Optional[str]
    phone: Optional[str]
    phone_secondary: Optional[str]
    mobile: Optional[str]
    website: Optional[str]
    linkedin_url: Optional[str]

    # Address
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    # External System IDs
    erpnext_id: Optional[str]
    zoho_id: Optional[str]

    # Account/Billing Info
    account_number: Optional[str]
    contract_number: Optional[str]
    billing_type: Optional[BillingTypeEnum]
    mrr: Optional[Decimal]
    total_revenue: Optional[Decimal]
    outstanding_balance: Optional[Decimal]
    credit_limit: Optional[Decimal]
    deposit_balance: Optional[Decimal]

    # Lead/Sales Info
    lead_qualification: Optional[LeadQualificationEnum]
    lead_score: Optional[int]
    source: Optional[str]
    source_campaign: Optional[str]
    territory: Optional[str]

    # Ownership
    owner_id: Optional[int]
    sales_person: Optional[str]
    account_manager: Optional[str]

    # Lifecycle Dates
    first_contact_date: Optional[datetime]
    last_contact_date: Optional[datetime]
    qualified_date: Optional[datetime]
    conversion_date: Optional[datetime]
    signup_date: Optional[datetime]
    activation_date: Optional[datetime]
    cancellation_date: Optional[datetime]
    churn_reason: Optional[str]

    # Communication Preferences
    email_opt_in: bool
    sms_opt_in: bool
    whatsapp_opt_in: bool
    phone_opt_in: bool
    preferred_language: Optional[str]
    preferred_channel: Optional[str]

    # Tags & Metadata
    tags: Optional[List[str]]
    custom_fields: Optional[dict]
    notes: Optional[str]

    # Stats
    total_conversations: int
    total_tickets: int
    total_orders: int
    total_invoices: int
    nps_score: Optional[int]
    satisfaction_score: Optional[float]

    # Audit
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactSummary(BaseModel):
    """Compact contact summary for lists."""
    id: int
    contact_type: ContactTypeEnum
    category: ContactCategoryEnum
    status: ContactStatusEnum
    name: str
    is_organization: Optional[bool]
    is_primary_contact: Optional[bool]
    is_billing_contact: Optional[bool]
    is_decision_maker: Optional[bool]
    designation: Optional[str]
    department: Optional[str]
    company_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    website: Optional[str]
    city: Optional[str]
    state: Optional[str]
    territory: Optional[str]
    owner_id: Optional[int]
    lead_qualification: Optional[LeadQualificationEnum]
    lead_score: Optional[int]
    source: Optional[str]
    mrr: Optional[Decimal]
    outstanding_balance: Optional[Decimal]
    last_contact_date: Optional[datetime]
    cancellation_date: Optional[datetime]
    churn_reason: Optional[str]
    tags: Optional[List[str]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactListResponse(BaseModel):
    """Paginated list response.

    Uses standardized pagination envelope: {data, total, limit, offset}
    """
    data: List[ContactSummary]
    total: int
    limit: int
    offset: int

    @computed_field
    def items(self) -> List[ContactSummary]:
        """Alias for data (backward compatibility)."""
        return self.data

    @computed_field
    def page(self) -> int:
        """Page number for backward compatibility."""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1

    @computed_field
    def page_size(self) -> int:
        """Page size alias for backward compatibility."""
        return self.limit

    @computed_field
    def total_pages(self) -> int:
        """Total pages for backward compatibility."""
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 1


class PersonContactResponse(BaseModel):
    """Person contact associated with an organization."""
    id: int
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    designation: Optional[str]
    department: Optional[str]
    is_primary_contact: bool
    is_billing_contact: bool
    is_decision_maker: bool

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# LIFECYCLE SCHEMAS
# =============================================================================

class QualifyLeadRequest(BaseModel):
    """Request to qualify a lead."""
    qualification: LeadQualificationEnum
    lead_score: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class ConvertToCustomerRequest(BaseModel):
    """Request to convert lead/prospect to customer."""
    account_number: Optional[str] = None
    billing_type: Optional[BillingTypeEnum] = None
    mrr: Optional[Decimal] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    notes: Optional[str] = None


class MarkChurnedRequest(BaseModel):
    """Request to mark a customer as churned."""
    reason: str = Field(..., max_length=255)
    notes: Optional[str] = None


class AssignOwnerRequest(BaseModel):
    """Request to assign contact to owner."""
    owner_id: int
    notes: Optional[str] = None


# =============================================================================
# BULK OPERATION SCHEMAS
# =============================================================================

class BulkUpdateRequest(BaseModel):
    """Bulk update request."""
    contact_ids: List[int]
    updates: ContactUpdate


class BulkAssignRequest(BaseModel):
    """Bulk assignment request."""
    contact_ids: List[int]
    owner_id: int


class BulkTagRequest(BaseModel):
    """Bulk tag operation."""
    contact_ids: List[int]
    tags: List[str]
    operation: str = Field(..., pattern="^(add|remove|set)$")


class MergeContactsRequest(BaseModel):
    """Merge duplicate contacts request."""
    primary_contact_id: int
    duplicate_contact_ids: List[int]
    merge_strategy: str = Field("keep_primary", pattern="^(keep_primary|merge_all|manual)$")


# =============================================================================
# IMPORT/EXPORT SCHEMAS
# =============================================================================

class ImportContactRow(BaseModel):
    """Single row for import."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    contact_type: Optional[ContactTypeEnum] = ContactTypeEnum.LEAD
    category: Optional[ContactCategoryEnum] = ContactCategoryEnum.RESIDENTIAL
    source: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "Nigeria"
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ImportContactsRequest(BaseModel):
    """Bulk import request."""
    contacts: List[ImportContactRow]
    owner_id: Optional[int] = None
    default_source: Optional[str] = None
    skip_duplicates: bool = True
    duplicate_check_field: str = Field("email", pattern="^(email|phone|name)$")


class ImportContactsResponse(BaseModel):
    """Bulk import response."""
    total_submitted: int
    created: int
    skipped: int
    errors: List[dict]


# =============================================================================
# BACKWARD COMPATIBILITY ALIASES
# =============================================================================

# Keep old names for backward compatibility during migration
UnifiedContactCreate = ContactCreate
UnifiedContactUpdate = ContactUpdate
UnifiedContactResponse = ContactResponse
UnifiedContactSummary = ContactSummary
UnifiedContactListResponse = ContactListResponse

"""Type definitions for subscriber service.

These dataclasses define the contract for subscriber operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.party import Party, PartyRole, CustomerAccount
    from app.models.subscription import Subscription
    from app.models.payment_subscription import PaymentSubscription
    from app.models.invoice import Invoice
    from app.models.ticket import Ticket


__all__ = [
    "SubscriberFilters",
    "SubscriberCreateData",
    "SubscriberUpdateData",
    "Subscriber360Data",
    "SubscriberStats",
    "SubscriberServiceSummary",
    "SubscriberFinancialSummary",
    "SubscriberSupportSummary",
    "SubscriberUsageSummary",
]


@dataclass
class SubscriberFilters:
    """Filters for listing subscribers."""

    search: Optional[str] = None
    status: Optional[str] = None  # active, inactive, blocked
    party_type: Optional[str] = None  # person, organization
    has_active_subscription: Optional[bool] = None
    subscription_status: Optional[str] = None
    service_type: Optional[str] = None  # internet, voice, bundle
    account_tier: Optional[str] = None  # standard, premium, enterprise
    has_outstanding_balance: Optional[bool] = None
    created_after: Optional[date] = None
    created_before: Optional[date] = None
    tag: Optional[str] = None


@dataclass
class SubscriberCreateData:
    """Data for creating a subscriber.

    Creates a Party with 'subscriber' role, optionally with CustomerAccount.
    """

    # Party fields
    party_type: str  # person, organization
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None

    # Contact info
    emails: List[Dict[str, Any]] = field(default_factory=list)
    phones: List[Dict[str, Any]] = field(default_factory=list)
    addresses: List[Dict[str, Any]] = field(default_factory=list)

    # Additional
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = "en"
    tax_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    external_ids: Dict[str, Any] = field(default_factory=dict)

    # CustomerAccount fields (optional - creates account if provided)
    create_account: bool = True
    account_tier: str = "standard"
    billing_type: Optional[str] = None
    billing_email: Optional[str] = None
    billing_cycle: Optional[str] = "monthly"
    payment_terms: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    currency: str = "NGN"

    # Link to existing customer account (for subscriber under business account)
    customer_account_id: Optional[int] = None


@dataclass
class SubscriberUpdateData:
    """Data for updating a subscriber (all fields optional)."""

    # Party fields
    status: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None

    # Contact info
    emails: Optional[List[Dict[str, Any]]] = None
    phones: Optional[List[Dict[str, Any]]] = None
    addresses: Optional[List[Dict[str, Any]]] = None

    # Additional
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    tax_id: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    external_ids: Optional[Dict[str, Any]] = None

    # CustomerAccount fields
    account_tier: Optional[str] = None
    billing_type: Optional[str] = None
    billing_email: Optional[str] = None
    billing_cycle: Optional[str] = None
    payment_terms: Optional[str] = None
    credit_limit: Optional[Decimal] = None


@dataclass
class SubscriberServiceSummary:
    """Summary of subscriber's services."""

    total_subscriptions: int = 0
    active_subscriptions: int = 0
    suspended_subscriptions: int = 0
    cancelled_subscriptions: int = 0

    # By service type
    internet_count: int = 0
    voice_count: int = 0
    bundle_count: int = 0

    # Payment subscriptions (recurring billing)
    payment_subscriptions: int = 0
    active_payment_subscriptions: int = 0

    # Aggregates
    total_mrr: Decimal = Decimal("0")
    total_speed_mbps: int = 0


@dataclass
class SubscriberFinancialSummary:
    """Summary of subscriber's financial status."""

    # Account receivable
    outstanding_balance: Decimal = Decimal("0")
    overdue_amount: Decimal = Decimal("0")
    current_amount: Decimal = Decimal("0")

    # Revenue
    total_revenue: Decimal = Decimal("0")
    mrr: Decimal = Decimal("0")
    ltv: Decimal = Decimal("0")

    # Invoices
    total_invoices: int = 0
    open_invoices: int = 0
    overdue_invoices: int = 0

    # Payments
    total_payments: int = 0
    last_payment_date: Optional[datetime] = None
    last_payment_amount: Optional[Decimal] = None

    # Credit
    credit_limit: Optional[Decimal] = None
    available_credit: Optional[Decimal] = None


@dataclass
class SubscriberSupportSummary:
    """Summary of subscriber's support history."""

    total_tickets: int = 0
    open_tickets: int = 0
    resolved_tickets: int = 0

    # By priority
    urgent_tickets: int = 0
    high_priority_tickets: int = 0

    # Metrics
    avg_resolution_hours: Optional[float] = None
    csat_score: Optional[float] = None

    # Recent activity
    last_ticket_date: Optional[datetime] = None
    last_ticket_subject: Optional[str] = None


@dataclass
class SubscriberUsageSummary:
    """Summary of subscriber's usage and sessions."""

    # Active sessions
    active_sessions: int = 0
    online_since: Optional[datetime] = None

    # Current period usage
    download_bytes: int = 0
    upload_bytes: int = 0
    total_bytes: int = 0

    # Data cap
    data_cap_bytes: Optional[int] = None
    data_used_percent: Optional[float] = None

    # Session history
    total_sessions_30d: int = 0
    avg_session_duration_mins: Optional[float] = None


@dataclass
class SubscriberStats:
    """Aggregate statistics for subscriber dashboard."""

    total_subscribers: int = 0
    active_subscribers: int = 0
    inactive_subscribers: int = 0
    blocked_subscribers: int = 0

    # Growth
    new_this_month: int = 0
    churned_this_month: int = 0
    net_growth: int = 0

    # By type
    person_count: int = 0
    organization_count: int = 0

    # Financial
    total_mrr: Decimal = Decimal("0")
    total_outstanding: Decimal = Decimal("0")
    total_overdue: Decimal = Decimal("0")


@dataclass
class Subscriber360Data:
    """Comprehensive 360-degree view of a subscriber.

    Aggregates data from multiple services into a single view.
    """

    # Core identity
    party: "Party"
    roles: List["PartyRole"] = field(default_factory=list)

    # Account (if exists)
    customer_account: Optional["CustomerAccount"] = None
    parent_account: Optional["CustomerAccount"] = None

    # Related subscribers (for business accounts)
    related_subscribers: List["Party"] = field(default_factory=list)

    # Services
    subscriptions: List["Subscription"] = field(default_factory=list)
    payment_subscriptions: List["PaymentSubscription"] = field(default_factory=list)
    service_summary: SubscriberServiceSummary = field(
        default_factory=SubscriberServiceSummary
    )

    # Financial
    invoices: List["Invoice"] = field(default_factory=list)
    recent_payments: List[Dict[str, Any]] = field(default_factory=list)
    financial_summary: SubscriberFinancialSummary = field(
        default_factory=SubscriberFinancialSummary
    )

    # Support
    tickets: List["Ticket"] = field(default_factory=list)
    support_summary: SubscriberSupportSummary = field(
        default_factory=SubscriberSupportSummary
    )

    # Usage
    active_sessions: List[Dict[str, Any]] = field(default_factory=list)
    usage_summary: SubscriberUsageSummary = field(
        default_factory=SubscriberUsageSummary
    )

    # Transactions
    recent_transactions: List[Dict[str, Any]] = field(default_factory=list)

    # Timeline / Activity
    recent_activity: List[Dict[str, Any]] = field(default_factory=list)

    # Notes and attachments
    notes: List[Dict[str, Any]] = field(default_factory=list)

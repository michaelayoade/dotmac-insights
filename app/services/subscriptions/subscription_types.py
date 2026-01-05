"""Type definitions for subscription service.

These dataclasses define the contract for subscription operations.
They are framework-agnostic (no Pydantic, no FastAPI).

Covers the complete subscription lifecycle:
- Core CRUD operations
- Network/provisioning configuration
- Status management (state machine)
- Usage tracking
- RADIUS/NAS integration
- Financial integration
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional


__all__ = [
    # Core subscription types
    "SubscriptionFilters",
    "SubscriptionCreateData",
    "SubscriptionUpdateData",
    "NetworkAssignmentData",
    "ProvisioningConfigData",
    "StatusTransition",
    "SubscriptionStats",
    # Provisioning types
    "ProvisioningRequest",
    "ProvisioningResult",
    "ProvisioningLogFilters",
    "ProvisioningLogEntry",
    "RouterConnectionTest",
    # Usage types
    "UsageFilters",
    "UsageRecord",
    "UsageSummary",
    "DataCapStatus",
    # RADIUS types
    "RADIUSUserConfig",
    "RADIUSRateLimit",
    "RADIUSSessionInfo",
    # Financial types
    "SubscriptionInvoiceData",
    "SubscriptionBillingInfo",
    # Billing types (daily/recurring)
    "DailyBillingConfig",
    "DailyBillingResult",
    "BillingRunSummary",
    "BillableSubscription",
    "ChargeRequest",
    "ChargeResult",
    # Session types (RADIUS/NAS)
    "ActiveSession",
    "SessionFilters",
    "SessionHistory",
    "DisconnectRequest",
    "DisconnectResult",
    "SessionStats",
]


@dataclass
class SubscriptionFilters:
    """Filters for listing subscriptions."""

    search: Optional[str] = None
    status: Optional[str] = None  # active, suspended, cancelled, pending
    service_type: Optional[str] = None  # internet, voice, custom, bundle
    party_id: Optional[int] = None
    router_id: Optional[int] = None
    tariff_id: Optional[int] = None
    billing_cycle: Optional[str] = None  # monthly, quarterly, yearly
    has_router: Optional[bool] = None  # filter for assigned/unassigned
    is_provisioned: Optional[bool] = None


@dataclass
class SubscriptionCreateData:
    """Data for creating a subscription."""

    # Required
    party_id: int
    plan_name: str
    price: Decimal

    # Plan details
    tariff_id: Optional[int] = None
    service_type: str = "internet"
    plan_code: Optional[str] = None
    description: Optional[str] = None
    currency: str = "NGN"
    billing_cycle: str = "monthly"

    # Speed (for internet plans)
    download_speed: Optional[int] = None
    upload_speed: Optional[int] = None
    data_cap: Optional[int] = None

    # Network assignment
    router_id: Optional[int] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None

    # Provisioning
    access_method: Optional[str] = None  # pppoe, hotspot, dhcp, ipoe, static
    ppp_username: Optional[str] = None
    ppp_password: Optional[str] = None

    # Dates
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Initial status (default PENDING)
    status: str = "pending"

    # External ID (Splynx)
    splynx_id: Optional[int] = None
    splynx_tariff_id: Optional[int] = None


@dataclass
class SubscriptionUpdateData:
    """Data for updating a subscription (all fields optional)."""

    plan_name: Optional[str] = None
    plan_code: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    billing_cycle: Optional[str] = None

    tariff_id: Optional[int] = None
    service_type: Optional[str] = None

    download_speed: Optional[int] = None
    upload_speed: Optional[int] = None
    data_cap: Optional[int] = None

    # Dates
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class NetworkAssignmentData:
    """Data for assigning network resources to a subscription."""

    router_id: Optional[int] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None


@dataclass
class ProvisioningConfigData:
    """Data for configuring provisioning settings."""

    router_id: Optional[int] = None
    access_method: Optional[str] = None  # pppoe, hotspot, dhcp, ipoe, static
    ppp_username: Optional[str] = None
    ppp_password: Optional[str] = None


@dataclass
class StatusTransition:
    """Represents a valid status transition."""

    target_status: str
    label: str
    color: str  # emerald, amber, red, etc.


@dataclass
class SubscriptionStats:
    """Subscription statistics summary."""

    active: int = 0
    suspended: int = 0
    pending: int = 0
    cancelled: int = 0
    total: int = 0
    mrr: Decimal = field(default_factory=lambda: Decimal("0"))
    new_this_month: int = 0
    provisioned: int = 0
    pending_provisioning: int = 0
    failed_provisioning: int = 0


# =============================================================================
# Provisioning Types
# =============================================================================

@dataclass
class ProvisioningRequest:
    """Request to provision a subscription."""

    subscription_id: int
    force: bool = False  # Force re-provision even if already provisioned
    triggered_by: str = "system"  # user, system, celery, sync


@dataclass
class ProvisioningResult:
    """Result of a provisioning operation."""

    success: bool
    action: str  # provision, deprovision, update, suspend, unsuspend, disconnect
    message: str
    log_id: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    can_retry: bool = False


@dataclass
class ProvisioningLogFilters:
    """Filters for listing provisioning logs."""

    subscription_id: Optional[int] = None
    router_id: Optional[int] = None
    action: Optional[str] = None  # CREATE, UPDATE, DELETE, SUSPEND, UNSUSPEND, DISCONNECT
    status: Optional[str] = None  # PENDING, SUCCESS, FAILED, RETRYING
    access_method: Optional[str] = None
    triggered_by: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    failed_only: bool = False


@dataclass
class ProvisioningLogEntry:
    """Provisioning log entry summary."""

    id: int
    subscription_id: int
    router_id: Optional[int]
    action: str
    status: str
    access_method: Optional[str]
    triggered_by: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    error_message: Optional[str]
    error_type: Optional[str]
    retry_count: int
    can_retry: bool


@dataclass
class RouterConnectionTest:
    """Result of testing router connection."""

    router_id: int
    router_title: str
    success: bool
    message: str
    routeros_version: Optional[str] = None
    uptime: Optional[str] = None
    response_time_ms: Optional[int] = None


# =============================================================================
# Usage Types
# =============================================================================

@dataclass
class UsageFilters:
    """Filters for listing usage records."""

    subscription_id: Optional[int] = None
    party_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


@dataclass
class UsageRecord:
    """Daily usage record."""

    id: int
    subscription_id: int
    usage_date: date
    upload_bytes: int
    download_bytes: int
    total_bytes: int
    upload_gb: float
    download_gb: float
    total_gb: float


@dataclass
class UsageSummary:
    """Usage summary for a period."""

    subscription_id: int
    period_start: date
    period_end: date
    total_upload_gb: float
    total_download_gb: float
    total_gb: float
    daily_average_gb: float
    peak_day: Optional[date] = None
    peak_day_gb: float = 0.0


@dataclass
class DataCapStatus:
    """Data cap status for a subscription."""

    subscription_id: int
    data_cap_gb: Optional[float]  # None means unlimited
    used_gb: float
    remaining_gb: Optional[float]  # None if unlimited
    usage_percent: Optional[float]  # None if unlimited
    is_exceeded: bool
    billing_cycle_start: date
    billing_cycle_end: date


# =============================================================================
# RADIUS Types
# =============================================================================

@dataclass
class RADIUSUserConfig:
    """RADIUS user configuration."""

    username: str
    password: Optional[str] = None  # Cleartext or hashed
    download_speed_mbps: Optional[int] = None
    upload_speed_mbps: Optional[int] = None
    ip_address: Optional[str] = None
    subscription_id: Optional[int] = None
    is_suspended: bool = False


@dataclass
class RADIUSRateLimit:
    """RADIUS rate limit configuration."""

    download_mbps: int
    upload_mbps: int
    burst_download_mbps: Optional[int] = None
    burst_upload_mbps: Optional[int] = None
    burst_threshold_mbps: Optional[int] = None
    burst_time_seconds: Optional[int] = None

    @property
    def mikrotik_rate_limit(self) -> str:
        """Format as MikroTik-Rate-Limit attribute value."""
        if self.burst_download_mbps:
            return (
                f"{self.download_mbps}M/{self.upload_mbps}M "
                f"{self.burst_download_mbps}M/{self.burst_upload_mbps}M "
                f"{self.burst_threshold_mbps}M/{self.burst_threshold_mbps}M "
                f"{self.burst_time_seconds}/{self.burst_time_seconds}"
            )
        return f"{self.download_mbps}M/{self.upload_mbps}M"


@dataclass
class RADIUSSessionInfo:
    """Active RADIUS session information."""

    username: str
    nas_ip: str
    session_id: str
    framed_ip: Optional[str] = None
    called_station_id: Optional[str] = None
    calling_station_id: Optional[str] = None  # MAC address
    session_start: Optional[datetime] = None
    session_time_seconds: Optional[int] = None
    input_octets: Optional[int] = None
    output_octets: Optional[int] = None


# =============================================================================
# Financial Types
# =============================================================================

@dataclass
class SubscriptionInvoiceData:
    """Data for generating subscription invoice."""

    subscription_id: int
    party_id: int
    amount: Decimal
    currency: str
    description: str
    billing_period_start: date
    billing_period_end: date
    due_date: date
    tariff_name: Optional[str] = None
    prorated: bool = False
    proration_days: Optional[int] = None


@dataclass
class SubscriptionBillingInfo:
    """Billing information for a subscription."""

    subscription_id: int
    party_id: int
    plan_name: str
    price: Decimal
    currency: str
    billing_cycle: str  # daily, weekly, monthly, quarterly, yearly
    next_billing_date: Optional[date] = None
    last_invoice_date: Optional[date] = None
    last_invoice_id: Optional[int] = None
    last_payment_date: Optional[date] = None
    last_payment_id: Optional[int] = None
    outstanding_balance: Decimal = field(default_factory=lambda: Decimal("0"))
    is_payment_subscription_linked: bool = False
    payment_subscription_id: Optional[int] = None


# =============================================================================
# Billing Types (Daily/Recurring)
# =============================================================================

@dataclass
class DailyBillingConfig:
    """Configuration for daily billing."""

    subscription_id: int
    enabled: bool = True
    billing_type: str = "fixed"  # fixed, usage_based, hybrid
    fixed_daily_amount: Optional[Decimal] = None
    usage_rate_per_gb: Optional[Decimal] = None
    included_gb_per_day: Optional[Decimal] = None
    auto_charge: bool = True  # Automatically charge via payment subscription
    generate_invoice: bool = True


@dataclass
class DailyBillingResult:
    """Result of a daily billing run."""

    subscription_id: int
    billing_date: date
    success: bool
    billing_type: str
    fixed_amount: Decimal
    usage_amount: Decimal
    total_amount: Decimal
    currency: str
    invoice_id: Optional[int] = None
    charge_reference: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BillingRunSummary:
    """Summary of a billing run (daily, weekly, monthly)."""

    run_id: str
    run_type: str  # daily, weekly, monthly
    run_date: date
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_subscriptions: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "NGN"
    error_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BillableSubscription:
    """Subscription ready for billing."""

    subscription_id: int
    party_id: int
    plan_name: str
    billing_cycle: str
    price: Decimal
    currency: str
    next_billing_date: date
    payment_subscription_id: Optional[int] = None
    has_auto_charge: bool = False


@dataclass
class ChargeRequest:
    """Request to charge a subscription."""

    subscription_id: int
    amount: Decimal
    currency: str
    description: str
    billing_date: date
    billing_type: str  # fixed, usage, hybrid
    invoice_id: Optional[int] = None
    payment_subscription_id: Optional[int] = None
    idempotency_key: Optional[str] = None


@dataclass
class ChargeResult:
    """Result of a charge attempt."""

    success: bool
    subscription_id: int
    amount: Decimal
    currency: str
    reference: Optional[str] = None
    gateway_response: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False


# =============================================================================
# Session Types (RADIUS/NAS)
# =============================================================================

@dataclass
class ActiveSession:
    """Active RADIUS session information."""

    session_id: str
    username: str
    nas_ip: str
    nas_port_id: Optional[str] = None
    framed_ip: Optional[str] = None
    calling_station_id: Optional[str] = None  # MAC address
    called_station_id: Optional[str] = None
    session_start: Optional[datetime] = None
    session_duration_seconds: int = 0
    input_octets: int = 0
    output_octets: int = 0
    input_packets: int = 0
    output_packets: int = 0
    terminate_cause: Optional[str] = None
    # Linked subscription info
    subscription_id: Optional[int] = None
    party_id: Optional[int] = None
    plan_name: Optional[str] = None


@dataclass
class SessionFilters:
    """Filters for listing sessions."""

    username: Optional[str] = None
    nas_ip: Optional[str] = None
    framed_ip: Optional[str] = None
    subscription_id: Optional[int] = None
    party_id: Optional[int] = None
    active_only: bool = True
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


@dataclass
class SessionHistory:
    """Historical session record."""

    session_id: str
    username: str
    nas_ip: str
    framed_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    session_start: Optional[datetime] = None
    session_stop: Optional[datetime] = None
    session_duration_seconds: int = 0
    input_octets: int = 0
    output_octets: int = 0
    terminate_cause: Optional[str] = None
    subscription_id: Optional[int] = None


@dataclass
class DisconnectRequest:
    """Request to disconnect a session."""

    session_id: Optional[str] = None
    username: Optional[str] = None
    nas_ip: Optional[str] = None
    framed_ip: Optional[str] = None
    reason: str = "admin_disconnect"


@dataclass
class DisconnectResult:
    """Result of disconnect operation."""

    success: bool
    session_id: Optional[str] = None
    username: Optional[str] = None
    message: str = ""
    error_code: Optional[str] = None


@dataclass
class SessionStats:
    """Session statistics summary."""

    total_active: int = 0
    total_today: int = 0
    total_upload_gb: float = 0.0
    total_download_gb: float = 0.0
    avg_session_duration_minutes: float = 0.0
    unique_users: int = 0
    sessions_by_nas: Dict[str, int] = field(default_factory=dict)
    top_users_by_traffic: List[Dict[str, Any]] = field(default_factory=list)

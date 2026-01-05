"""Service Lifecycle Type Definitions.

Comprehensive types for managing the full service provider lifecycle:
- Extended lifecycle states beyond basic status
- Suspension tracking with reasons
- Auto-blocking rules and policies
- Grace period management
- Lifecycle events and transitions

This module is framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Callable


__all__ = [
    # Enums
    "ServiceLifecycleState",
    "SuspensionReason",
    "TerminationReason",
    "BlockingTrigger",
    "LifecycleAction",
    # Policies
    "GracePeriodPolicy",
    "AutoBlockingRule",
    "AutoBlockingPolicy",
    "ReactivationPolicy",
    # Events & Transitions
    "LifecycleEvent",
    "LifecycleTransition",
    "StateTransitionResult",
    # Service data
    "ServiceLifecycleData",
    "SubscriberServiceSummary",
    "SuspensionDetails",
    "GracePeriodStatus",
    "BlockingCheckResult",
    # Filters & Requests
    "LifecycleFilters",
    "SuspendRequest",
    "ReactivateRequest",
    "TerminateRequest",
    "ExtendGraceRequest",
    # Stats
    "LifecycleStats",
    "BlockingStats",
]


# =============================================================================
# ENUMS
# =============================================================================

class ServiceLifecycleState(str, Enum):
    """Extended lifecycle states for service subscriptions.

    State Machine:

    PENDING_ACTIVATION ──► PROVISIONING ──► ACTIVE
           │                    │              │
           ▼                    ▼              ▼
       CANCELLED            FAILED        SUSPENDED
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                        GRACE_PERIOD ◄──── (auto)        ACTIVE (reactivate)
                              │
                              ▼
                         TERMINATED
    """
    # Initial states
    PENDING_ACTIVATION = "pending_activation"
    PROVISIONING = "provisioning"
    PROVISION_FAILED = "provision_failed"

    # Active states
    ACTIVE = "active"

    # Suspension states
    SUSPENDED = "suspended"
    GRACE_PERIOD = "grace_period"

    # Terminal states
    TERMINATED = "terminated"
    CANCELLED = "cancelled"

    @property
    def is_active(self) -> bool:
        """Check if state represents active service."""
        return self == ServiceLifecycleState.ACTIVE

    @property
    def is_suspended(self) -> bool:
        """Check if state represents suspended service."""
        return self in (
            ServiceLifecycleState.SUSPENDED,
            ServiceLifecycleState.GRACE_PERIOD,
        )

    @property
    def is_terminal(self) -> bool:
        """Check if state is terminal (no further transitions)."""
        return self in (
            ServiceLifecycleState.TERMINATED,
            ServiceLifecycleState.CANCELLED,
        )

    @property
    def allows_reactivation(self) -> bool:
        """Check if state allows reactivation."""
        return self in (
            ServiceLifecycleState.SUSPENDED,
            ServiceLifecycleState.GRACE_PERIOD,
        )

    @property
    def display_label(self) -> str:
        """Human-readable label."""
        labels = {
            "pending_activation": "Pending Activation",
            "provisioning": "Provisioning",
            "provision_failed": "Provisioning Failed",
            "active": "Active",
            "suspended": "Suspended",
            "grace_period": "Grace Period",
            "terminated": "Terminated",
            "cancelled": "Cancelled",
        }
        return labels.get(self.value, self.value.replace("_", " ").title())

    @property
    def color(self) -> str:
        """UI color class."""
        colors = {
            "pending_activation": "amber",
            "provisioning": "blue",
            "provision_failed": "red",
            "active": "emerald",
            "suspended": "orange",
            "grace_period": "red",
            "terminated": "gray",
            "cancelled": "gray",
        }
        return colors.get(self.value, "gray")


class SuspensionReason(str, Enum):
    """Reasons for service suspension."""

    PAYMENT_OVERDUE = "payment_overdue"
    USAGE_EXCEEDED = "usage_exceeded"
    ABUSE = "abuse"
    TOS_VIOLATION = "tos_violation"
    FRAUD = "fraud"
    ADMIN_ACTION = "admin_action"
    CUSTOMER_REQUEST = "customer_request"
    SCHEDULED_MAINTENANCE = "scheduled_maintenance"
    CONTRACT_EXPIRED = "contract_expired"

    @property
    def display_label(self) -> str:
        labels = {
            "payment_overdue": "Payment Overdue",
            "usage_exceeded": "Usage Limit Exceeded",
            "abuse": "Abuse Detected",
            "tos_violation": "Terms of Service Violation",
            "fraud": "Fraud Detected",
            "admin_action": "Administrative Action",
            "customer_request": "Customer Requested",
            "scheduled_maintenance": "Scheduled Maintenance",
            "contract_expired": "Contract Expired",
        }
        return labels.get(self.value, self.value.replace("_", " ").title())

    @property
    def allows_self_reactivation(self) -> bool:
        """Check if customer can self-reactivate."""
        return self in (
            SuspensionReason.PAYMENT_OVERDUE,
            SuspensionReason.USAGE_EXCEEDED,
            SuspensionReason.CUSTOMER_REQUEST,
            SuspensionReason.CONTRACT_EXPIRED,
        )

    @property
    def requires_payment(self) -> bool:
        """Check if reactivation requires payment."""
        return self in (
            SuspensionReason.PAYMENT_OVERDUE,
            SuspensionReason.CONTRACT_EXPIRED,
        )

    @property
    def severity(self) -> int:
        """Severity level (1-5)."""
        severities = {
            "payment_overdue": 2,
            "usage_exceeded": 2,
            "abuse": 4,
            "tos_violation": 4,
            "fraud": 5,
            "admin_action": 3,
            "customer_request": 1,
            "scheduled_maintenance": 1,
            "contract_expired": 2,
        }
        return severities.get(self.value, 3)


class TerminationReason(str, Enum):
    """Reasons for service termination."""

    GRACE_PERIOD_EXPIRED = "grace_period_expired"
    NON_PAYMENT = "non_payment"
    ABUSE = "abuse"
    FRAUD = "fraud"
    CUSTOMER_REQUEST = "customer_request"
    CONTRACT_END = "contract_end"
    ADMIN_ACTION = "admin_action"
    BUSINESS_CLOSURE = "business_closure"

    @property
    def display_label(self) -> str:
        labels = {
            "grace_period_expired": "Grace Period Expired",
            "non_payment": "Non-Payment",
            "abuse": "Abuse",
            "fraud": "Fraud",
            "customer_request": "Customer Requested",
            "contract_end": "Contract End",
            "admin_action": "Administrative Action",
            "business_closure": "Business Closure",
        }
        return labels.get(self.value, self.value.replace("_", " ").title())


class BlockingTrigger(str, Enum):
    """Triggers for auto-blocking."""

    PAYMENT_OVERDUE = "payment_overdue"
    INVOICE_OVERDUE = "invoice_overdue"
    USAGE_THRESHOLD = "usage_threshold"
    DATA_CAP_EXCEEDED = "data_cap_exceeded"
    CONTRACT_EXPIRED = "contract_expired"
    MANUAL = "manual"

    @property
    def display_label(self) -> str:
        return self.value.replace("_", " ").title()


class LifecycleAction(str, Enum):
    """Actions that can be performed on service lifecycle."""

    ACTIVATE = "activate"
    PROVISION = "provision"
    SUSPEND = "suspend"
    REACTIVATE = "reactivate"
    ENTER_GRACE = "enter_grace"
    EXTEND_GRACE = "extend_grace"
    TERMINATE = "terminate"
    CANCEL = "cancel"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    RENEW = "renew"


# =============================================================================
# POLICIES
# =============================================================================

@dataclass
class GracePeriodPolicy:
    """Policy for grace period management."""

    # Duration
    duration_days: int = 14

    # Extensions
    max_extensions: int = 2
    extension_days: int = 7

    # Actions during grace
    allow_reduced_service: bool = True  # Allow degraded service during grace
    reduced_speed_percent: int = 50  # Speed reduction during grace

    # Notifications
    notify_on_entry: bool = True
    notify_days_before_termination: List[int] = field(default_factory=lambda: [7, 3, 1])

    # Auto-termination
    auto_terminate: bool = True

    # Requirements for reactivation
    require_full_payment: bool = True
    require_reconnection_fee: bool = False
    reconnection_fee: Decimal = field(default_factory=lambda: Decimal("0"))

    def get_termination_date(self, grace_start: datetime) -> datetime:
        """Calculate termination date from grace period start."""
        return grace_start + timedelta(days=self.duration_days)


@dataclass
class AutoBlockingRule:
    """Single auto-blocking rule."""

    id: Optional[str] = None
    name: str = ""
    description: str = ""

    # Trigger conditions
    trigger: BlockingTrigger = BlockingTrigger.PAYMENT_OVERDUE

    # Thresholds
    days_overdue: int = 0  # For payment-based triggers
    usage_threshold_percent: int = 100  # For usage-based triggers
    amount_threshold: Optional[Decimal] = None  # Minimum amount to trigger

    # Action
    suspension_reason: SuspensionReason = SuspensionReason.PAYMENT_OVERDUE

    # Grace period
    apply_grace_period: bool = True
    grace_period_days: int = 14

    # Notifications
    notify_before_days: List[int] = field(default_factory=lambda: [7, 3, 1])

    # Enabled
    enabled: bool = True

    # Priority (lower = higher priority)
    priority: int = 100


@dataclass
class AutoBlockingPolicy:
    """Complete auto-blocking policy with multiple rules."""

    # Global settings
    enabled: bool = True

    # Default grace period
    default_grace_period: GracePeriodPolicy = field(default_factory=GracePeriodPolicy)

    # Rules (ordered by priority)
    rules: List[AutoBlockingRule] = field(default_factory=list)

    # Exemptions
    exempt_party_ids: List[int] = field(default_factory=list)
    exempt_account_tiers: List[str] = field(default_factory=list)  # e.g., ["enterprise", "vip"]

    # Retry settings
    check_interval_hours: int = 24  # How often to run checks

    # Limits
    max_suspensions_before_terminate: int = 3

    def get_active_rules(self) -> List[AutoBlockingRule]:
        """Get enabled rules sorted by priority."""
        return sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: r.priority
        )


@dataclass
class ReactivationPolicy:
    """Policy for service reactivation."""

    # Payment requirements
    require_outstanding_payment: bool = True
    require_next_period_payment: bool = False

    # Fees
    charge_reconnection_fee: bool = True
    reconnection_fee: Decimal = field(default_factory=lambda: Decimal("5000"))
    waive_fee_for_quick_payment: bool = True
    quick_payment_hours: int = 24  # Hours to pay to waive fee

    # Approval
    require_approval: bool = False
    approval_reasons: List[SuspensionReason] = field(
        default_factory=lambda: [
            SuspensionReason.ABUSE,
            SuspensionReason.FRAUD,
            SuspensionReason.TOS_VIOLATION,
        ]
    )

    # Provisioning
    auto_provision_on_reactivate: bool = True


# =============================================================================
# EVENTS & TRANSITIONS
# =============================================================================

@dataclass
class LifecycleEvent:
    """A lifecycle event that occurred."""

    id: Optional[int] = None
    subscription_id: int = 0
    party_id: int = 0

    # Event details
    action: LifecycleAction = LifecycleAction.ACTIVATE
    from_state: Optional[ServiceLifecycleState] = None
    to_state: Optional[ServiceLifecycleState] = None

    # Context
    reason: Optional[str] = None
    suspension_reason: Optional[SuspensionReason] = None
    termination_reason: Optional[TerminationReason] = None

    # Metadata
    triggered_by: str = "system"  # system, user, scheduler, api
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LifecycleTransition:
    """A valid state transition."""

    from_state: ServiceLifecycleState
    to_state: ServiceLifecycleState
    action: LifecycleAction
    label: str
    color: str
    requires_reason: bool = False
    requires_approval: bool = False
    requires_payment: bool = False


@dataclass
class StateTransitionResult:
    """Result of a state transition attempt."""

    success: bool
    subscription_id: int

    # States
    old_state: ServiceLifecycleState
    new_state: ServiceLifecycleState

    # Details
    action: LifecycleAction
    reason: Optional[str] = None

    # If failed
    error: Optional[str] = None
    error_code: Optional[str] = None

    # Side effects
    provisioning_triggered: bool = False
    notification_sent: bool = False
    invoice_generated: bool = False

    # Event record
    event_id: Optional[int] = None


# =============================================================================
# SERVICE DATA
# =============================================================================

@dataclass
class SuspensionDetails:
    """Details about a suspension."""

    reason: SuspensionReason
    suspended_at: datetime
    suspended_by: Optional[str] = None  # user email or "system"

    # Grace period
    grace_period_starts_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    grace_extensions_used: int = 0

    # History
    suspension_count: int = 1
    previous_suspensions: List[Dict[str, Any]] = field(default_factory=list)

    # Reactivation requirements
    outstanding_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    reconnection_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    requires_approval: bool = False

    @property
    def days_suspended(self) -> int:
        """Days since suspension."""
        return (datetime.utcnow() - self.suspended_at).days

    @property
    def days_until_termination(self) -> Optional[int]:
        """Days until auto-termination."""
        if self.grace_period_ends_at:
            delta = self.grace_period_ends_at - datetime.utcnow()
            return max(0, delta.days)
        return None

    @property
    def is_in_grace_period(self) -> bool:
        """Check if currently in grace period."""
        if not self.grace_period_starts_at or not self.grace_period_ends_at:
            return False
        now = datetime.utcnow()
        return self.grace_period_starts_at <= now < self.grace_period_ends_at


@dataclass
class GracePeriodStatus:
    """Current grace period status."""

    is_active: bool = False

    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    days_remaining: int = 0
    days_elapsed: int = 0

    extensions_used: int = 0
    extensions_available: int = 0

    termination_scheduled: bool = False
    termination_date: Optional[datetime] = None

    # What's needed to exit grace
    outstanding_balance: Decimal = field(default_factory=lambda: Decimal("0"))
    reconnection_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    total_to_reactivate: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class BlockingCheckResult:
    """Result of checking if subscription should be blocked."""

    should_block: bool = False

    # Matching rules
    triggered_rules: List[AutoBlockingRule] = field(default_factory=list)
    primary_rule: Optional[AutoBlockingRule] = None

    # Details
    suspension_reason: Optional[SuspensionReason] = None

    # Financial
    outstanding_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    days_overdue: int = 0

    # Usage
    usage_percent: float = 0.0
    data_used_gb: float = 0.0
    data_cap_gb: Optional[float] = None

    # Already blocked?
    already_suspended: bool = False
    current_state: Optional[ServiceLifecycleState] = None


@dataclass
class ServiceLifecycleData:
    """Complete lifecycle data for a service."""

    subscription_id: int
    party_id: int

    # Current state
    state: ServiceLifecycleState = ServiceLifecycleState.PENDING_ACTIVATION

    # Suspension info
    is_suspended: bool = False
    suspension_details: Optional[SuspensionDetails] = None

    # Grace period
    grace_period_status: Optional[GracePeriodStatus] = None

    # History
    suspension_count: int = 0
    last_state_change: Optional[datetime] = None

    # Available actions
    available_actions: List[LifecycleAction] = field(default_factory=list)

    # Blocking info
    blocking_check: Optional[BlockingCheckResult] = None


@dataclass
class SubscriberServiceSummary:
    """Summary of all services for a subscriber."""

    subscriber_id: int
    party_id: int

    # Counts by state
    total_services: int = 0
    active_services: int = 0
    suspended_services: int = 0
    in_grace_services: int = 0
    terminated_services: int = 0

    # At-risk
    services_at_risk: int = 0  # About to be suspended
    services_in_grace: List[int] = field(default_factory=list)  # Subscription IDs in grace

    # Financial
    total_outstanding: Decimal = field(default_factory=lambda: Decimal("0"))
    total_mrr: Decimal = field(default_factory=lambda: Decimal("0"))

    # Services list
    services: List[ServiceLifecycleData] = field(default_factory=list)


# =============================================================================
# FILTERS & REQUESTS
# =============================================================================

@dataclass
class LifecycleFilters:
    """Filters for lifecycle queries."""

    party_id: Optional[int] = None
    subscription_id: Optional[int] = None

    # State filters
    states: Optional[List[ServiceLifecycleState]] = None
    is_suspended: Optional[bool] = None
    is_in_grace: Optional[bool] = None
    is_at_risk: Optional[bool] = None

    # Suspension filters
    suspension_reason: Optional[SuspensionReason] = None
    suspended_after: Optional[datetime] = None
    suspended_before: Optional[datetime] = None

    # Grace period filters
    grace_ends_before: Optional[datetime] = None
    grace_ends_after: Optional[datetime] = None

    # Payment filters
    has_outstanding_balance: Optional[bool] = None
    min_outstanding: Optional[Decimal] = None


@dataclass
class SuspendRequest:
    """Request to suspend a service."""

    subscription_id: int
    reason: SuspensionReason

    notes: Optional[str] = None

    # Grace period options
    apply_grace_period: bool = True
    grace_period_days: Optional[int] = None  # Override default

    # Notification
    send_notification: bool = True

    # Scheduling
    effective_immediately: bool = True
    scheduled_for: Optional[datetime] = None

    # Provisioning
    deprovision: bool = True


@dataclass
class ReactivateRequest:
    """Request to reactivate a suspended service."""

    subscription_id: int

    notes: Optional[str] = None

    # Payment handling
    waive_outstanding: bool = False
    waive_reconnection_fee: bool = False
    payment_reference: Optional[str] = None

    # Provisioning
    reprovision: bool = True

    # Override checks
    force: bool = False  # Skip payment checks


@dataclass
class TerminateRequest:
    """Request to terminate a service."""

    subscription_id: int
    reason: TerminationReason

    notes: Optional[str] = None

    # Financial
    issue_final_invoice: bool = True
    apply_early_termination_fee: bool = True
    issue_prorated_credit: bool = True

    # Provisioning
    deprovision: bool = True

    # Data handling
    retain_data_days: int = 30


@dataclass
class ExtendGraceRequest:
    """Request to extend grace period."""

    subscription_id: int

    extension_days: int = 7
    reason: str = ""

    # Notification
    send_notification: bool = True


# =============================================================================
# STATS
# =============================================================================

@dataclass
class LifecycleStats:
    """Lifecycle statistics."""

    # By state
    total_subscriptions: int = 0
    pending_activation: int = 0
    provisioning: int = 0
    active: int = 0
    suspended: int = 0
    in_grace: int = 0
    terminated: int = 0
    cancelled: int = 0

    # Trends (this month)
    activations_this_month: int = 0
    suspensions_this_month: int = 0
    reactivations_this_month: int = 0
    terminations_this_month: int = 0

    # At-risk
    services_at_risk: int = 0
    grace_periods_ending_soon: int = 0  # Within 3 days

    # Financial impact
    suspended_mrr: Decimal = field(default_factory=lambda: Decimal("0"))
    at_risk_mrr: Decimal = field(default_factory=lambda: Decimal("0"))

    # By suspension reason
    suspensions_by_reason: Dict[str, int] = field(default_factory=dict)


@dataclass
class BlockingStats:
    """Auto-blocking statistics."""

    # Checks run
    checks_today: int = 0
    checks_this_week: int = 0

    # Actions taken
    suspensions_today: int = 0
    suspensions_this_week: int = 0
    grace_entries_today: int = 0
    terminations_today: int = 0

    # By trigger
    by_trigger: Dict[str, int] = field(default_factory=dict)

    # Pending
    pending_suspensions: int = 0
    pending_terminations: int = 0

    # Financial
    blocked_revenue: Decimal = field(default_factory=lambda: Decimal("0"))

"""Subscriber services module.

This module provides services for subscriber/customer management:
- SubscriberService: Subscriber lifecycle and 360 view aggregation
- LifecycleService: Full service lifecycle state machine
- AutoBlockingService: Automated blocking rules engine
- LifecycleScheduler: Scheduled lifecycle tasks
"""
from .subscriber_service import SubscriberService
from .subscriber_types import (
    SubscriberFilters,
    SubscriberCreateData,
    SubscriberUpdateData,
    Subscriber360Data,
    SubscriberStats,
    SubscriberServiceSummary,
    SubscriberFinancialSummary,
    SubscriberSupportSummary,
    SubscriberUsageSummary,
)

# Lifecycle types
from .lifecycle_types import (
    ServiceLifecycleState,
    SuspensionReason,
    TerminationReason,
    BlockingTrigger,
    LifecycleAction,
    GracePeriodPolicy,
    AutoBlockingRule,
    AutoBlockingPolicy,
    ReactivationPolicy,
    LifecycleEvent,
    LifecycleTransition,
    StateTransitionResult,
    SuspensionDetails,
    GracePeriodStatus,
    ServiceLifecycleData,
    SubscriberServiceSummary as SubscriberServicesSummary,
    SuspendRequest,
    ReactivateRequest,
    TerminateRequest,
    ExtendGraceRequest,
    LifecycleStats,
    BlockingStats,
)

# Lifecycle services
from .lifecycle_service import LifecycleService
from .auto_blocking_service import (
    AutoBlockingService,
    BlockingRunResult,
    SubscriptionBlockingCheck,
)
from .lifecycle_scheduler import (
    LifecycleScheduler,
    ScheduledTaskResult,
    DailyReportData,
)

__all__ = [
    # Subscriber service
    "SubscriberService",
    "SubscriberFilters",
    "SubscriberCreateData",
    "SubscriberUpdateData",
    "Subscriber360Data",
    "SubscriberStats",
    "SubscriberServiceSummary",
    "SubscriberFinancialSummary",
    "SubscriberSupportSummary",
    "SubscriberUsageSummary",
    # Lifecycle types
    "ServiceLifecycleState",
    "SuspensionReason",
    "TerminationReason",
    "BlockingTrigger",
    "LifecycleAction",
    "GracePeriodPolicy",
    "AutoBlockingRule",
    "AutoBlockingPolicy",
    "ReactivationPolicy",
    "LifecycleEvent",
    "LifecycleTransition",
    "StateTransitionResult",
    "SuspensionDetails",
    "GracePeriodStatus",
    "ServiceLifecycleData",
    "SubscriberServicesSummary",
    "SuspendRequest",
    "ReactivateRequest",
    "TerminateRequest",
    "ExtendGraceRequest",
    "LifecycleStats",
    "BlockingStats",
    # Lifecycle services
    "LifecycleService",
    "AutoBlockingService",
    "BlockingRunResult",
    "SubscriptionBlockingCheck",
    "LifecycleScheduler",
    "ScheduledTaskResult",
    "DailyReportData",
]

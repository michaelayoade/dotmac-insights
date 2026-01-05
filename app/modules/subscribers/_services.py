"""
Subscriber web service facade.

This module provides a web-facing service that wraps domain services
for subscriber management, providing a unified interface for routes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.subscribers import (
    SubscriberService,
    SubscriberFilters,
    SubscriberCreateData,
    SubscriberUpdateData,
    Subscriber360Data,
    SubscriberStats,
    # Lifecycle
    LifecycleService,
    AutoBlockingService,
    ServiceLifecycleState,
    SuspensionReason,
    TerminationReason,
    SuspendRequest,
    ReactivateRequest,
    TerminateRequest,
    ExtendGraceRequest,
    ServiceLifecycleData,
    StateTransitionResult,
    LifecycleStats,
)
from app.services.subscriptions import (
    SubscriptionService,
    SubscriptionFilters,
    TariffService,
    UsageService,
    SessionService,
)
from app.services.types import PaginatedResult, PaginationParams
from app.models.party import Party, CustomerAccount
from app.models.subscription import Subscription

if TYPE_CHECKING:
    from app.auth import Principal


class SubscriberWebService:
    """Web-facing service for subscriber management.

    Wraps domain services and provides convenience methods for routes.
    """

    def __init__(
        self,
        db: Session,
        user_id: Optional[int] = None,
        principal: Optional["Principal"] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.principal = principal

        # Initialize domain services
        self._subscriber_svc = SubscriberService(db, principal)
        self._subscription_svc = SubscriptionService(db, principal)
        self._tariff_svc = TariffService(db, principal)
        self._usage_svc = UsageService(db, principal)
        self._session_svc = SessionService(db, principal=principal)

        # Lifecycle services
        self._lifecycle_svc = LifecycleService(db, principal)
        self._blocking_svc = AutoBlockingService(db, principal)

    # -------------------------------------------------------------------------
    # Subscriber CRUD
    # -------------------------------------------------------------------------

    def list_subscribers(
        self,
        filters: Optional[SubscriberFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Party]:
        """List subscribers with filters and pagination."""
        return self._subscriber_svc.list_subscribers(
            filters=filters,
            pagination=pagination,
            include_account=True,
        )

    def get_subscriber(self, party_id: int) -> Party:
        """Get a subscriber by ID."""
        return self._subscriber_svc.get_subscriber(party_id)

    def get_customer_account(self, party_id: int) -> Optional[CustomerAccount]:
        """Get customer account for a party."""
        return self._subscriber_svc.get_customer_account(party_id)

    def create_subscriber(self, data: SubscriberCreateData) -> Party:
        """Create a new subscriber."""
        return self._subscriber_svc.create_subscriber(data)

    def update_subscriber(self, party_id: int, data: SubscriberUpdateData) -> Party:
        """Update a subscriber."""
        return self._subscriber_svc.update_subscriber(party_id, data)

    def delete_subscriber(self, party_id: int) -> None:
        """Delete (deactivate) a subscriber."""
        self._subscriber_svc.delete_subscriber(party_id)

    # -------------------------------------------------------------------------
    # 360 View
    # -------------------------------------------------------------------------

    def get_subscriber_360(self, party_id: int) -> Subscriber360Data:
        """Get comprehensive 360 view of a subscriber."""
        return self._subscriber_svc.get_subscriber_360(party_id)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> SubscriberStats:
        """Get subscriber statistics."""
        return self._subscriber_svc.get_stats()

    # -------------------------------------------------------------------------
    # Subscription Helpers (for subscriber context)
    # -------------------------------------------------------------------------

    def get_subscriber_subscriptions(self, party_id: int) -> List[Any]:
        """Get all subscriptions for a subscriber."""
        filters = SubscriptionFilters(party_id=party_id)
        result = self._subscription_svc.list_subscriptions(filters=filters)
        return result.items

    def get_active_subscriptions_count(self, party_id: int) -> int:
        """Get count of active subscriptions for a subscriber."""
        filters = SubscriptionFilters(party_id=party_id, status="active")
        result = self._subscription_svc.list_subscriptions(filters=filters)
        return result.total

    # -------------------------------------------------------------------------
    # Quick Actions
    # -------------------------------------------------------------------------

    def block_subscriber(self, party_id: int, reason: Optional[str] = None) -> Party:
        """Block a subscriber."""
        data = SubscriberUpdateData(status="blocked")
        if reason:
            party = self.get_subscriber(party_id)
            notes = party.notes or ""
            notes += f"\n[BLOCKED] {reason}"
            data.notes = notes.strip()
        return self.update_subscriber(party_id, data)

    def unblock_subscriber(self, party_id: int) -> Party:
        """Unblock a subscriber."""
        data = SubscriberUpdateData(status="active")
        return self.update_subscriber(party_id, data)

    def get_subscriber_summary(self, party_id: int) -> Dict[str, Any]:
        """Get a quick summary for a subscriber (for list views)."""
        account = self.get_customer_account(party_id)
        active_subs = self.get_active_subscriptions_count(party_id)

        return {
            "active_subscriptions": active_subs,
            "account_number": account.account_number if account else None,
            "tier": account.tier if account else None,
            "mrr": float(account.mrr) if account and account.mrr else 0,
            "outstanding_balance": float(account.outstanding_balance) if account and account.outstanding_balance else 0,
        }

    # -------------------------------------------------------------------------
    # Service Lifecycle Management
    # -------------------------------------------------------------------------

    def get_service_lifecycle(self, subscription_id: int) -> ServiceLifecycleData:
        """Get lifecycle data for a service/subscription."""
        return self._lifecycle_svc.get_lifecycle_data(subscription_id)

    def get_subscriber_services_lifecycle(self, party_id: int) -> List[ServiceLifecycleData]:
        """Get lifecycle data for all services of a subscriber."""
        subscriptions = self.get_subscriber_subscriptions(party_id)
        return [
            self._lifecycle_svc.get_lifecycle_data(sub.id)
            for sub in subscriptions
        ]

    def suspend_service(
        self,
        subscription_id: int,
        reason: SuspensionReason,
        notes: Optional[str] = None,
        apply_grace_period: bool = True,
        grace_period_days: Optional[int] = None,
    ) -> StateTransitionResult:
        """Suspend a service."""
        request = SuspendRequest(
            subscription_id=subscription_id,
            reason=reason,
            notes=notes,
            apply_grace_period=apply_grace_period,
            grace_period_days=grace_period_days,
            send_notification=True,
            deprovision=True,
        )
        return self._lifecycle_svc.suspend(request)

    def reactivate_service(
        self,
        subscription_id: int,
        notes: Optional[str] = None,
        waive_outstanding: bool = False,
        waive_reconnection_fee: bool = False,
        force: bool = False,
    ) -> StateTransitionResult:
        """Reactivate a suspended service."""
        request = ReactivateRequest(
            subscription_id=subscription_id,
            notes=notes,
            waive_outstanding=waive_outstanding,
            waive_reconnection_fee=waive_reconnection_fee,
            force=force,
            reprovision=True,
        )
        return self._lifecycle_svc.reactivate(request)

    def terminate_service(
        self,
        subscription_id: int,
        reason: TerminationReason,
        notes: Optional[str] = None,
    ) -> StateTransitionResult:
        """Terminate a service permanently."""
        request = TerminateRequest(
            subscription_id=subscription_id,
            reason=reason,
            notes=notes,
            issue_final_invoice=True,
            apply_early_termination_fee=True,
            issue_prorated_credit=True,
            deprovision=True,
        )
        return self._lifecycle_svc.terminate(request)

    def extend_grace_period(
        self,
        subscription_id: int,
        days: int = 7,
        reason: str = "",
    ) -> StateTransitionResult:
        """Extend grace period for a service."""
        request = ExtendGraceRequest(
            subscription_id=subscription_id,
            extension_days=days,
            reason=reason,
            send_notification=True,
        )
        return self._lifecycle_svc.extend_grace_period(request)

    def activate_service(
        self,
        subscription_id: int,
        notes: Optional[str] = None,
    ) -> StateTransitionResult:
        """Activate a pending service."""
        return self._lifecycle_svc.activate(subscription_id, notes=notes)

    def get_lifecycle_stats(self) -> LifecycleStats:
        """Get lifecycle statistics."""
        return self._lifecycle_svc.get_stats()

    def get_suspension_reasons(self) -> List[Dict[str, str]]:
        """Get list of suspension reasons for UI."""
        return [
            {"value": r.value, "label": r.display_label}
            for r in SuspensionReason
        ]

    def get_termination_reasons(self) -> List[Dict[str, str]]:
        """Get list of termination reasons for UI."""
        return [
            {"value": r.value, "label": r.display_label}
            for r in TerminationReason
        ]

    def check_blocking_status(self, subscription_id: int) -> Dict[str, Any]:
        """Check if a service should be blocked based on rules."""
        check = self._blocking_svc.check_subscription(subscription_id)
        return {
            "should_block": check.should_block,
            "primary_reason": check.primary_reason.value if check.primary_reason else None,
            "outstanding_amount": float(check.outstanding_amount),
            "days_overdue": check.days_overdue,
            "triggered_rules": [r.name for r in check.triggered_rules],
        }

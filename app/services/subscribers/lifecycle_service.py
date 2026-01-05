"""Service Lifecycle Management.

Core service for managing the full service provider lifecycle:
- State machine with valid transitions
- Suspension with reasons and tracking
- Grace period management
- Termination handling
- Reactivation with requirements
- Integration with provisioning and billing

This service orchestrates lifecycle changes and ensures
business rules are followed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.party import Party
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams
from app.services.base import paginate

from .lifecycle_types import (
    ServiceLifecycleState,
    SuspensionReason,
    TerminationReason,
    LifecycleAction,
    GracePeriodPolicy,
    AutoBlockingPolicy,
    ReactivationPolicy,
    LifecycleEvent,
    LifecycleTransition,
    StateTransitionResult,
    SuspensionDetails,
    GracePeriodStatus,
    ServiceLifecycleData,
    SubscriberServiceSummary,
    LifecycleFilters,
    SuspendRequest,
    ReactivateRequest,
    TerminateRequest,
    ExtendGraceRequest,
    LifecycleStats,
)

if TYPE_CHECKING:
    from app.auth import Principal


__all__ = ["LifecycleService"]


# =============================================================================
# STATE MACHINE DEFINITION
# =============================================================================

# Valid transitions: from_state -> list of (to_state, action, label, color)
STATE_MACHINE: Dict[ServiceLifecycleState, List[LifecycleTransition]] = {
    ServiceLifecycleState.PENDING_ACTIVATION: [
        LifecycleTransition(
            ServiceLifecycleState.PENDING_ACTIVATION,
            ServiceLifecycleState.PROVISIONING,
            LifecycleAction.PROVISION,
            "Start Provisioning",
            "blue",
        ),
        LifecycleTransition(
            ServiceLifecycleState.PENDING_ACTIVATION,
            ServiceLifecycleState.ACTIVE,
            LifecycleAction.ACTIVATE,
            "Activate",
            "emerald",
        ),
        LifecycleTransition(
            ServiceLifecycleState.PENDING_ACTIVATION,
            ServiceLifecycleState.CANCELLED,
            LifecycleAction.CANCEL,
            "Cancel",
            "red",
        ),
    ],
    ServiceLifecycleState.PROVISIONING: [
        LifecycleTransition(
            ServiceLifecycleState.PROVISIONING,
            ServiceLifecycleState.ACTIVE,
            LifecycleAction.ACTIVATE,
            "Activation Complete",
            "emerald",
        ),
        LifecycleTransition(
            ServiceLifecycleState.PROVISIONING,
            ServiceLifecycleState.PROVISION_FAILED,
            LifecycleAction.PROVISION,
            "Provisioning Failed",
            "red",
        ),
        LifecycleTransition(
            ServiceLifecycleState.PROVISIONING,
            ServiceLifecycleState.CANCELLED,
            LifecycleAction.CANCEL,
            "Cancel",
            "red",
        ),
    ],
    ServiceLifecycleState.PROVISION_FAILED: [
        LifecycleTransition(
            ServiceLifecycleState.PROVISION_FAILED,
            ServiceLifecycleState.PROVISIONING,
            LifecycleAction.PROVISION,
            "Retry Provisioning",
            "blue",
        ),
        LifecycleTransition(
            ServiceLifecycleState.PROVISION_FAILED,
            ServiceLifecycleState.CANCELLED,
            LifecycleAction.CANCEL,
            "Cancel",
            "red",
        ),
    ],
    ServiceLifecycleState.ACTIVE: [
        LifecycleTransition(
            ServiceLifecycleState.ACTIVE,
            ServiceLifecycleState.SUSPENDED,
            LifecycleAction.SUSPEND,
            "Suspend",
            "amber",
            requires_reason=True,
        ),
        LifecycleTransition(
            ServiceLifecycleState.ACTIVE,
            ServiceLifecycleState.CANCELLED,
            LifecycleAction.CANCEL,
            "Cancel",
            "red",
        ),
        LifecycleTransition(
            ServiceLifecycleState.ACTIVE,
            ServiceLifecycleState.TERMINATED,
            LifecycleAction.TERMINATE,
            "Terminate",
            "red",
            requires_reason=True,
        ),
    ],
    ServiceLifecycleState.SUSPENDED: [
        LifecycleTransition(
            ServiceLifecycleState.SUSPENDED,
            ServiceLifecycleState.ACTIVE,
            LifecycleAction.REACTIVATE,
            "Reactivate",
            "emerald",
            requires_payment=True,
        ),
        LifecycleTransition(
            ServiceLifecycleState.SUSPENDED,
            ServiceLifecycleState.GRACE_PERIOD,
            LifecycleAction.ENTER_GRACE,
            "Enter Grace Period",
            "orange",
        ),
        LifecycleTransition(
            ServiceLifecycleState.SUSPENDED,
            ServiceLifecycleState.TERMINATED,
            LifecycleAction.TERMINATE,
            "Terminate",
            "red",
        ),
    ],
    ServiceLifecycleState.GRACE_PERIOD: [
        LifecycleTransition(
            ServiceLifecycleState.GRACE_PERIOD,
            ServiceLifecycleState.ACTIVE,
            LifecycleAction.REACTIVATE,
            "Reactivate",
            "emerald",
            requires_payment=True,
        ),
        LifecycleTransition(
            ServiceLifecycleState.GRACE_PERIOD,
            ServiceLifecycleState.GRACE_PERIOD,
            LifecycleAction.EXTEND_GRACE,
            "Extend Grace Period",
            "orange",
        ),
        LifecycleTransition(
            ServiceLifecycleState.GRACE_PERIOD,
            ServiceLifecycleState.TERMINATED,
            LifecycleAction.TERMINATE,
            "Terminate",
            "red",
        ),
    ],
    ServiceLifecycleState.TERMINATED: [],  # Terminal state
    ServiceLifecycleState.CANCELLED: [],  # Terminal state
}


# =============================================================================
# LIFECYCLE SERVICE
# =============================================================================

class LifecycleService:
    """Service for managing subscription lifecycle.

    Handles all lifecycle transitions including:
    - Activation and provisioning
    - Suspension with reasons
    - Grace period management
    - Reactivation with requirements
    - Termination handling
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        grace_policy: Optional[GracePeriodPolicy] = None,
        reactivation_policy: Optional[ReactivationPolicy] = None,
    ):
        self.db = db
        self.principal = principal
        self.grace_policy = grace_policy or GracePeriodPolicy()
        self.reactivation_policy = reactivation_policy or ReactivationPolicy()

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------

    def get_current_state(self, subscription_id: int) -> ServiceLifecycleState:
        """Get current lifecycle state for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            Current ServiceLifecycleState.

        Raises:
            NotFoundError: If subscription not found.
        """
        sub = self._get_subscription(subscription_id)
        return self._get_lifecycle_state(sub)

    def get_available_transitions(
        self, subscription_id: int
    ) -> List[LifecycleTransition]:
        """Get available transitions for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            List of available transitions.
        """
        sub = self._get_subscription(subscription_id)
        current_state = self._get_lifecycle_state(sub)
        return STATE_MACHINE.get(current_state, [])

    def can_transition(
        self,
        subscription_id: int,
        target_state: ServiceLifecycleState,
    ) -> Tuple[bool, Optional[str]]:
        """Check if transition to target state is allowed.

        Args:
            subscription_id: The subscription ID.
            target_state: Target state.

        Returns:
            Tuple of (allowed, reason if not allowed).
        """
        sub = self._get_subscription(subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Check if transition exists
        transitions = STATE_MACHINE.get(current_state, [])
        matching = [t for t in transitions if t.to_state == target_state]

        if not matching:
            return False, f"Cannot transition from {current_state.value} to {target_state.value}"

        transition = matching[0]

        # Check requirements
        if transition.requires_payment:
            outstanding = self._get_outstanding_amount(sub)
            if outstanding > 0:
                return False, f"Outstanding balance of {outstanding} must be paid first"

        return True, None

    # -------------------------------------------------------------------------
    # Lifecycle Actions
    # -------------------------------------------------------------------------

    def activate(
        self,
        subscription_id: int,
        notes: Optional[str] = None,
        trigger_provisioning: bool = True,
    ) -> StateTransitionResult:
        """Activate a subscription.

        Args:
            subscription_id: The subscription ID.
            notes: Optional notes.
            trigger_provisioning: Whether to trigger provisioning.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Validate transition
        allowed, reason = self.can_transition(subscription_id, ServiceLifecycleState.ACTIVE)
        if not allowed:
            return StateTransitionResult(
                success=False,
                subscription_id=subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.ACTIVATE,
                error=reason,
            )

        # Perform transition
        self._set_lifecycle_state(sub, ServiceLifecycleState.ACTIVE)
        sub.status = SubscriptionStatus.ACTIVE
        sub.start_date = sub.start_date or datetime.now(timezone.utc)

        # Clear suspension info
        self._clear_suspension(sub)

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.ACTIVATE,
            current_state,
            ServiceLifecycleState.ACTIVE,
            notes=notes,
        )

        # Trigger provisioning if needed
        provisioning_triggered = False
        if trigger_provisioning and not sub.provisioned_at:
            provisioning_triggered = self._trigger_provisioning(sub)

        return StateTransitionResult(
            success=True,
            subscription_id=subscription_id,
            old_state=current_state,
            new_state=ServiceLifecycleState.ACTIVE,
            action=LifecycleAction.ACTIVATE,
            reason=notes,
            provisioning_triggered=provisioning_triggered,
            event_id=event.id,
        )

    def suspend(self, request: SuspendRequest) -> StateTransitionResult:
        """Suspend a subscription.

        Args:
            request: Suspension request details.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(request.subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Validate transition
        if current_state.is_terminal:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.SUSPEND,
                error="Cannot suspend terminated or cancelled subscription",
            )

        if current_state == ServiceLifecycleState.SUSPENDED:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.SUSPEND,
                error="Subscription is already suspended",
            )

        now = datetime.now(timezone.utc)

        # Determine target state
        target_state = ServiceLifecycleState.SUSPENDED
        if request.apply_grace_period:
            target_state = ServiceLifecycleState.GRACE_PERIOD

        # Perform transition
        self._set_lifecycle_state(sub, target_state)
        sub.status = SubscriptionStatus.SUSPENDED

        # Set suspension details
        sub.suspension_reason = request.reason.value
        sub.suspended_at = now
        sub.suspended_by = self._get_actor_name()
        sub.suspension_count = (sub.suspension_count or 0) + 1
        sub.suspension_notes = request.notes

        # Set grace period if applicable
        if request.apply_grace_period:
            grace_days = request.grace_period_days or self.grace_policy.duration_days
            sub.grace_period_starts_at = now
            sub.grace_period_ends_at = now + timedelta(days=grace_days)
            sub.grace_extensions_used = 0

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.SUSPEND,
            current_state,
            target_state,
            notes=request.notes,
            suspension_reason=request.reason,
        )

        # Trigger deprovisioning if requested
        if request.deprovision:
            self._trigger_deprovisioning(sub)

        # Send notification
        notification_sent = False
        if request.send_notification:
            notification_sent = self._send_suspension_notification(sub, request.reason)

        return StateTransitionResult(
            success=True,
            subscription_id=request.subscription_id,
            old_state=current_state,
            new_state=target_state,
            action=LifecycleAction.SUSPEND,
            reason=request.notes,
            notification_sent=notification_sent,
            event_id=event.id,
        )

    def reactivate(self, request: ReactivateRequest) -> StateTransitionResult:
        """Reactivate a suspended subscription.

        Args:
            request: Reactivation request details.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(request.subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Validate can reactivate
        if not current_state.allows_reactivation:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.REACTIVATE,
                error=f"Cannot reactivate from state: {current_state.value}",
            )

        # Check payment requirements unless forced
        if not request.force:
            outstanding = self._get_outstanding_amount(sub)
            if outstanding > 0 and not request.waive_outstanding:
                if self.reactivation_policy.require_outstanding_payment:
                    return StateTransitionResult(
                        success=False,
                        subscription_id=request.subscription_id,
                        old_state=current_state,
                        new_state=current_state,
                        action=LifecycleAction.REACTIVATE,
                        error=f"Outstanding balance of {outstanding} must be paid first",
                        error_code="PAYMENT_REQUIRED",
                    )

            # Check approval requirements
            if sub.suspension_reason:
                reason = SuspensionReason(sub.suspension_reason)
                if reason in self.reactivation_policy.approval_reasons:
                    if self.reactivation_policy.require_approval:
                        return StateTransitionResult(
                            success=False,
                            subscription_id=request.subscription_id,
                            old_state=current_state,
                            new_state=current_state,
                            action=LifecycleAction.REACTIVATE,
                            error=f"Reactivation requires approval for suspension reason: {reason.display_label}",
                            error_code="APPROVAL_REQUIRED",
                        )

        # Perform transition
        self._set_lifecycle_state(sub, ServiceLifecycleState.ACTIVE)
        sub.status = SubscriptionStatus.ACTIVE

        # Clear suspension info
        self._clear_suspension(sub)

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.REACTIVATE,
            current_state,
            ServiceLifecycleState.ACTIVE,
            notes=request.notes,
        )

        # Trigger reprovisioning if requested
        provisioning_triggered = False
        if request.reprovision and self.reactivation_policy.auto_provision_on_reactivate:
            provisioning_triggered = self._trigger_provisioning(sub)

        # Charge reconnection fee if applicable
        if self.reactivation_policy.charge_reconnection_fee and not request.waive_reconnection_fee:
            self._charge_reconnection_fee(sub)

        return StateTransitionResult(
            success=True,
            subscription_id=request.subscription_id,
            old_state=current_state,
            new_state=ServiceLifecycleState.ACTIVE,
            action=LifecycleAction.REACTIVATE,
            reason=request.notes,
            provisioning_triggered=provisioning_triggered,
            event_id=event.id,
        )

    def terminate(self, request: TerminateRequest) -> StateTransitionResult:
        """Terminate a subscription permanently.

        Args:
            request: Termination request details.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(request.subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Validate not already terminated
        if current_state.is_terminal:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.TERMINATE,
                error="Subscription is already terminated or cancelled",
            )

        now = datetime.now(timezone.utc)

        # Perform transition
        self._set_lifecycle_state(sub, ServiceLifecycleState.TERMINATED)
        sub.status = SubscriptionStatus.CANCELLED
        sub.termination_reason = request.reason.value
        sub.terminated_at = now
        sub.terminated_by = self._get_actor_name()
        sub.termination_notes = request.notes
        sub.cancelled_date = now

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.TERMINATE,
            current_state,
            ServiceLifecycleState.TERMINATED,
            notes=request.notes,
            termination_reason=request.reason,
        )

        # Trigger deprovisioning
        if request.deprovision:
            self._trigger_deprovisioning(sub)

        # Handle financials
        invoice_generated = False
        if request.issue_final_invoice:
            invoice_generated = self._generate_final_invoice(sub)

        if request.apply_early_termination_fee:
            self._apply_early_termination_fee(sub)

        if request.issue_prorated_credit:
            self._issue_prorated_credit(sub)

        return StateTransitionResult(
            success=True,
            subscription_id=request.subscription_id,
            old_state=current_state,
            new_state=ServiceLifecycleState.TERMINATED,
            action=LifecycleAction.TERMINATE,
            reason=request.notes,
            invoice_generated=invoice_generated,
            event_id=event.id,
        )

    def extend_grace_period(self, request: ExtendGraceRequest) -> StateTransitionResult:
        """Extend grace period for a subscription.

        Args:
            request: Extension request details.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(request.subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Validate in grace period
        if current_state != ServiceLifecycleState.GRACE_PERIOD:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.EXTEND_GRACE,
                error="Subscription is not in grace period",
            )

        # Check extension limits
        extensions_used = sub.grace_extensions_used or 0
        if extensions_used >= self.grace_policy.max_extensions:
            return StateTransitionResult(
                success=False,
                subscription_id=request.subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.EXTEND_GRACE,
                error=f"Maximum {self.grace_policy.max_extensions} extensions already used",
            )

        # Extend grace period
        if sub.grace_period_ends_at:
            sub.grace_period_ends_at = sub.grace_period_ends_at + timedelta(days=request.extension_days)
        else:
            sub.grace_period_ends_at = datetime.now(timezone.utc) + timedelta(days=request.extension_days)

        sub.grace_extensions_used = extensions_used + 1

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.EXTEND_GRACE,
            current_state,
            current_state,
            notes=request.reason,
            metadata={"extension_days": request.extension_days},
        )

        # Send notification
        notification_sent = False
        if request.send_notification:
            notification_sent = self._send_grace_extension_notification(sub, request.extension_days)

        return StateTransitionResult(
            success=True,
            subscription_id=request.subscription_id,
            old_state=current_state,
            new_state=current_state,
            action=LifecycleAction.EXTEND_GRACE,
            reason=request.reason,
            notification_sent=notification_sent,
            event_id=event.id,
        )

    def enter_grace_period(
        self,
        subscription_id: int,
        notes: Optional[str] = None,
    ) -> StateTransitionResult:
        """Move suspended subscription to grace period.

        Args:
            subscription_id: The subscription ID.
            notes: Optional notes.

        Returns:
            StateTransitionResult.
        """
        sub = self._get_subscription(subscription_id)
        current_state = self._get_lifecycle_state(sub)

        if current_state != ServiceLifecycleState.SUSPENDED:
            return StateTransitionResult(
                success=False,
                subscription_id=subscription_id,
                old_state=current_state,
                new_state=current_state,
                action=LifecycleAction.ENTER_GRACE,
                error="Subscription must be suspended to enter grace period",
            )

        now = datetime.now(timezone.utc)

        # Set grace period
        self._set_lifecycle_state(sub, ServiceLifecycleState.GRACE_PERIOD)
        sub.grace_period_starts_at = now
        sub.grace_period_ends_at = now + timedelta(days=self.grace_policy.duration_days)
        sub.grace_extensions_used = 0

        # Record event
        event = self._record_event(
            sub,
            LifecycleAction.ENTER_GRACE,
            current_state,
            ServiceLifecycleState.GRACE_PERIOD,
            notes=notes,
        )

        return StateTransitionResult(
            success=True,
            subscription_id=subscription_id,
            old_state=current_state,
            new_state=ServiceLifecycleState.GRACE_PERIOD,
            action=LifecycleAction.ENTER_GRACE,
            reason=notes,
            event_id=event.id,
        )

    # -------------------------------------------------------------------------
    # Lifecycle Data Retrieval
    # -------------------------------------------------------------------------

    def get_lifecycle_data(self, subscription_id: int) -> ServiceLifecycleData:
        """Get complete lifecycle data for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            ServiceLifecycleData.
        """
        sub = self._get_subscription(subscription_id)
        current_state = self._get_lifecycle_state(sub)

        # Build suspension details
        suspension_details = None
        if current_state.is_suspended and sub.suspended_at:
            suspension_details = SuspensionDetails(
                reason=SuspensionReason(sub.suspension_reason) if sub.suspension_reason else SuspensionReason.ADMIN_ACTION,
                suspended_at=sub.suspended_at,
                suspended_by=sub.suspended_by,
                grace_period_starts_at=sub.grace_period_starts_at,
                grace_period_ends_at=sub.grace_period_ends_at,
                grace_extensions_used=sub.grace_extensions_used or 0,
                suspension_count=sub.suspension_count or 1,
                outstanding_amount=self._get_outstanding_amount(sub),
                reconnection_fee=self.reactivation_policy.reconnection_fee if self.reactivation_policy.charge_reconnection_fee else Decimal("0"),
            )

        # Build grace period status
        grace_status = None
        if current_state == ServiceLifecycleState.GRACE_PERIOD:
            now = datetime.now(timezone.utc)
            grace_status = GracePeriodStatus(
                is_active=True,
                starts_at=sub.grace_period_starts_at,
                ends_at=sub.grace_period_ends_at,
                days_remaining=max(0, (sub.grace_period_ends_at - now).days) if sub.grace_period_ends_at else 0,
                days_elapsed=(now - sub.grace_period_starts_at).days if sub.grace_period_starts_at else 0,
                extensions_used=sub.grace_extensions_used or 0,
                extensions_available=max(0, self.grace_policy.max_extensions - (sub.grace_extensions_used or 0)),
                termination_scheduled=self.grace_policy.auto_terminate,
                termination_date=sub.grace_period_ends_at,
                outstanding_balance=self._get_outstanding_amount(sub),
                reconnection_fee=self.reactivation_policy.reconnection_fee if self.reactivation_policy.charge_reconnection_fee else Decimal("0"),
            )
            if grace_status.outstanding_balance or grace_status.reconnection_fee:
                grace_status.total_to_reactivate = grace_status.outstanding_balance + grace_status.reconnection_fee

        # Get available actions
        transitions = STATE_MACHINE.get(current_state, [])
        available_actions = [t.action for t in transitions]

        return ServiceLifecycleData(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            state=current_state,
            is_suspended=current_state.is_suspended,
            suspension_details=suspension_details,
            grace_period_status=grace_status,
            suspension_count=sub.suspension_count or 0,
            last_state_change=sub.last_lifecycle_at,
            available_actions=available_actions,
        )

    def get_subscriber_services_summary(self, party_id: int) -> SubscriberServiceSummary:
        """Get summary of all services for a subscriber.

        Args:
            party_id: The party ID.

        Returns:
            SubscriberServiceSummary.
        """
        subs = self.db.query(Subscription).filter(
            Subscription.party_id == party_id
        ).all()

        summary = SubscriberServiceSummary(
            subscriber_id=party_id,
            party_id=party_id,
            total_services=len(subs),
        )

        for sub in subs:
            state = self._get_lifecycle_state(sub)
            lifecycle_data = self.get_lifecycle_data(sub.id)
            summary.services.append(lifecycle_data)

            if state == ServiceLifecycleState.ACTIVE:
                summary.active_services += 1
                summary.total_mrr += Decimal(str(sub.mrr))
            elif state == ServiceLifecycleState.SUSPENDED:
                summary.suspended_services += 1
            elif state == ServiceLifecycleState.GRACE_PERIOD:
                summary.in_grace_services += 1
                summary.services_in_grace.append(sub.id)
            elif state.is_terminal:
                summary.terminated_services += 1

        # Calculate total outstanding
        summary.total_outstanding = sum(
            (s.suspension_details.outstanding_amount if s.suspension_details else Decimal("0"))
            for s in summary.services
        )

        return summary

    def get_stats(self) -> LifecycleStats:
        """Get lifecycle statistics.

        Returns:
            LifecycleStats.
        """
        # Count by lifecycle state
        stats = LifecycleStats()

        all_subs = self.db.query(Subscription).all()
        stats.total_subscriptions = len(all_subs)

        for sub in all_subs:
            state = self._get_lifecycle_state(sub)
            if state == ServiceLifecycleState.PENDING_ACTIVATION:
                stats.pending_activation += 1
            elif state == ServiceLifecycleState.PROVISIONING:
                stats.provisioning += 1
            elif state == ServiceLifecycleState.ACTIVE:
                stats.active += 1
            elif state == ServiceLifecycleState.SUSPENDED:
                stats.suspended += 1
                stats.suspended_mrr += Decimal(str(sub.price or 0))
                if sub.suspension_reason:
                    reason = sub.suspension_reason
                    stats.suspensions_by_reason[reason] = stats.suspensions_by_reason.get(reason, 0) + 1
            elif state == ServiceLifecycleState.GRACE_PERIOD:
                stats.in_grace += 1
                stats.suspended_mrr += Decimal(str(sub.price or 0))
                # Check if ending soon (within 3 days)
                if sub.grace_period_ends_at:
                    days_left = (sub.grace_period_ends_at - datetime.now(timezone.utc)).days
                    if days_left <= 3:
                        stats.grace_periods_ending_soon += 1
            elif state == ServiceLifecycleState.TERMINATED:
                stats.terminated += 1
            elif state == ServiceLifecycleState.CANCELLED:
                stats.cancelled += 1

        return stats

    def list_services_by_state(
        self,
        state: ServiceLifecycleState,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Subscription]:
        """List subscriptions in a specific lifecycle state.

        Args:
            state: The lifecycle state to filter by.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult of Subscriptions.
        """
        # Map lifecycle state to query conditions
        if state == ServiceLifecycleState.ACTIVE:
            query = self.db.query(Subscription).filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                or_(
                    Subscription.lifecycle_state == "active",
                    Subscription.lifecycle_state.is_(None),
                ),
            )
        elif state == ServiceLifecycleState.SUSPENDED:
            query = self.db.query(Subscription).filter(
                Subscription.lifecycle_state == "suspended"
            )
        elif state == ServiceLifecycleState.GRACE_PERIOD:
            query = self.db.query(Subscription).filter(
                Subscription.lifecycle_state == "grace_period"
            )
        elif state.is_terminal:
            query = self.db.query(Subscription).filter(
                Subscription.lifecycle_state.in_(["terminated", "cancelled"])
            )
        else:
            query = self.db.query(Subscription).filter(
                Subscription.lifecycle_state == state.value
            )

        query = query.order_by(Subscription.updated_at.desc())
        return paginate(query, pagination)

    def list_grace_period_expiring(
        self,
        within_days: int = 3,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Subscription]:
        """List subscriptions with grace periods expiring soon.

        Args:
            within_days: Days until expiration.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult of Subscriptions.
        """
        cutoff = datetime.now(timezone.utc) + timedelta(days=within_days)

        query = self.db.query(Subscription).filter(
            Subscription.lifecycle_state == "grace_period",
            Subscription.grace_period_ends_at.isnot(None),
            Subscription.grace_period_ends_at <= cutoff,
        ).order_by(Subscription.grace_period_ends_at.asc())

        return paginate(query, pagination)

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _get_subscription(self, subscription_id: int) -> Subscription:
        """Get subscription by ID."""
        sub = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        if not sub:
            raise NotFoundError(f"Subscription {subscription_id} not found")
        return sub

    def _get_lifecycle_state(self, sub: Subscription) -> ServiceLifecycleState:
        """Get lifecycle state from subscription, with fallback mapping."""
        # Check explicit lifecycle_state first
        if hasattr(sub, 'lifecycle_state') and sub.lifecycle_state:
            try:
                return ServiceLifecycleState(sub.lifecycle_state)
            except ValueError:
                pass

        # Fall back to mapping from status
        status_map = {
            SubscriptionStatus.PENDING: ServiceLifecycleState.PENDING_ACTIVATION,
            SubscriptionStatus.ACTIVE: ServiceLifecycleState.ACTIVE,
            SubscriptionStatus.SUSPENDED: ServiceLifecycleState.SUSPENDED,
            SubscriptionStatus.CANCELLED: ServiceLifecycleState.CANCELLED,
        }
        return status_map.get(sub.status, ServiceLifecycleState.PENDING_ACTIVATION)

    def _set_lifecycle_state(self, sub: Subscription, state: ServiceLifecycleState) -> None:
        """Set lifecycle state on subscription."""
        if hasattr(sub, 'lifecycle_state'):
            sub.lifecycle_state = state.value
        if hasattr(sub, 'last_lifecycle_action'):
            sub.last_lifecycle_action = state.value
        if hasattr(sub, 'last_lifecycle_at'):
            sub.last_lifecycle_at = datetime.now(timezone.utc)

    def _clear_suspension(self, sub: Subscription) -> None:
        """Clear suspension-related fields."""
        sub.suspension_reason = None
        sub.suspended_at = None
        sub.suspended_by = None
        sub.suspension_notes = None
        sub.grace_period_starts_at = None
        sub.grace_period_ends_at = None

    def _get_actor_name(self) -> str:
        """Get name of current actor (user or system)."""
        if self.principal:
            return self.principal.email or f"user:{self.principal.id}"
        return "system"

    def _get_outstanding_amount(self, sub: Subscription) -> Decimal:
        """Get outstanding balance for subscription."""
        # This would integrate with billing service
        # For now, return 0
        return Decimal("0")

    def _record_event(
        self,
        sub: Subscription,
        action: LifecycleAction,
        from_state: ServiceLifecycleState,
        to_state: ServiceLifecycleState,
        notes: Optional[str] = None,
        suspension_reason: Optional[SuspensionReason] = None,
        termination_reason: Optional[TerminationReason] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LifecycleEvent:
        """Record a lifecycle event."""
        from app.services.subscriptions.service_transactions import (
            ServiceTransactionService,
            ServiceTransactionCreateData,
        )

        # Map action to transaction type
        action_type_map = {
            LifecycleAction.ACTIVATE: "activation",
            LifecycleAction.SUSPEND: "suspension",
            LifecycleAction.REACTIVATE: "reactivation",
            LifecycleAction.TERMINATE: "cancellation",
            LifecycleAction.CANCEL: "cancellation",
            LifecycleAction.ENTER_GRACE: "suspension",
            LifecycleAction.EXTEND_GRACE: "suspension",
        }

        txn_type = action_type_map.get(action, "activation")
        description = f"Lifecycle: {action.value} ({from_state.value} → {to_state.value})"

        # Create service transaction
        txn_service = ServiceTransactionService(self.db, self.principal)
        txn_data = ServiceTransactionCreateData(
            subscription_id=sub.id,
            party_id=sub.party_id,
            transaction_type=txn_type,
            description=description,
            reason=notes,
            old_value=from_state.value,
            new_value=to_state.value,
            metadata={
                "action": action.value,
                "suspension_reason": suspension_reason.value if suspension_reason else None,
                "termination_reason": termination_reason.value if termination_reason else None,
                **(metadata or {}),
            },
        )
        txn = txn_service.create_transaction(txn_data)

        return LifecycleEvent(
            id=txn.get("id"),
            subscription_id=sub.id,
            party_id=sub.party_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            reason=notes,
            suspension_reason=suspension_reason,
            termination_reason=termination_reason,
            triggered_by="user" if self.principal else "system",
            user_id=self.principal.id if self.principal else None,
            metadata=metadata or {},
        )

    def _trigger_provisioning(self, sub: Subscription) -> bool:
        """Trigger provisioning for subscription."""
        # Integration with provisioning service
        # For now, just mark as provisioned
        sub.provisioned_at = datetime.now(timezone.utc)
        return True

    def _trigger_deprovisioning(self, sub: Subscription) -> bool:
        """Trigger deprovisioning for subscription."""
        # Integration with provisioning service
        return True

    def _send_suspension_notification(
        self,
        sub: Subscription,
        reason: SuspensionReason,
    ) -> bool:
        """Send suspension notification."""
        # Integration with notification service
        return True

    def _send_grace_extension_notification(
        self,
        sub: Subscription,
        days: int,
    ) -> bool:
        """Send grace period extension notification."""
        # Integration with notification service
        return True

    def _charge_reconnection_fee(self, sub: Subscription) -> None:
        """Charge reconnection fee for reactivation."""
        # Integration with billing service
        pass

    def _generate_final_invoice(self, sub: Subscription) -> bool:
        """Generate final invoice for termination."""
        # Integration with billing service
        return True

    def _apply_early_termination_fee(self, sub: Subscription) -> None:
        """Apply early termination fee."""
        # Integration with billing service
        pass

    def _issue_prorated_credit(self, sub: Subscription) -> None:
        """Issue prorated credit for unused service."""
        # Integration with billing service
        pass

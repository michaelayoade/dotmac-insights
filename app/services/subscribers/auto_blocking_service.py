"""Auto-Blocking Rules Engine.

Automated service blocking based on configurable rules:
- Payment overdue detection
- Usage limit enforcement
- Contract expiration checks
- Scheduled checks and actions

This service runs periodically to identify services that should
be suspended or terminated based on business rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.party import Party, CustomerAccount

from .lifecycle_types import (
    ServiceLifecycleState,
    SuspensionReason,
    TerminationReason,
    BlockingTrigger,
    AutoBlockingRule,
    AutoBlockingPolicy,
    GracePeriodPolicy,
    BlockingCheckResult,
    SuspendRequest,
    TerminateRequest,
    BlockingStats,
)
from .lifecycle_service import LifecycleService

if TYPE_CHECKING:
    from app.auth import Principal


__all__ = [
    "AutoBlockingService",
    "BlockingRunResult",
    "SubscriptionBlockingCheck",
]


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class SubscriptionBlockingCheck:
    """Result of checking a single subscription."""

    subscription_id: int
    party_id: int
    plan_name: str

    # Current state
    current_state: ServiceLifecycleState
    already_blocked: bool = False

    # Check results
    should_block: bool = False
    triggered_rules: List[AutoBlockingRule] = field(default_factory=list)
    primary_reason: Optional[SuspensionReason] = None

    # Financial details
    outstanding_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    days_overdue: int = 0
    oldest_overdue_invoice_id: Optional[int] = None
    oldest_overdue_invoice_date: Optional[date] = None

    # Usage details
    usage_percent: float = 0.0
    data_used_gb: float = 0.0
    data_cap_gb: Optional[float] = None

    # Action taken
    action_taken: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BlockingRunResult:
    """Result of a blocking run."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    # Counts
    subscriptions_checked: int = 0
    already_blocked: int = 0
    newly_blocked: int = 0
    entered_grace: int = 0
    terminated: int = 0
    errors: int = 0
    skipped: int = 0

    # Financial impact
    blocked_mrr: Decimal = field(default_factory=lambda: Decimal("0"))

    # Details
    checks: List[SubscriptionBlockingCheck] = field(default_factory=list)
    errors_detail: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0


# =============================================================================
# DEFAULT RULES
# =============================================================================

DEFAULT_BLOCKING_RULES = [
    # Payment overdue - 7 days
    AutoBlockingRule(
        id="payment_overdue_7",
        name="Payment Overdue (7 days)",
        description="Suspend services with invoices overdue by 7 or more days",
        trigger=BlockingTrigger.INVOICE_OVERDUE,
        days_overdue=7,
        suspension_reason=SuspensionReason.PAYMENT_OVERDUE,
        apply_grace_period=True,
        grace_period_days=14,
        notify_before_days=[3, 1],
        enabled=True,
        priority=10,
    ),
    # Payment overdue - 30 days (enter grace)
    AutoBlockingRule(
        id="payment_overdue_30_grace",
        name="Payment Overdue (30 days) - Grace Period",
        description="Enter grace period for services with invoices overdue by 30+ days",
        trigger=BlockingTrigger.INVOICE_OVERDUE,
        days_overdue=30,
        suspension_reason=SuspensionReason.PAYMENT_OVERDUE,
        apply_grace_period=True,
        grace_period_days=7,
        notify_before_days=[7, 3, 1],
        enabled=True,
        priority=20,
    ),
    # Data cap exceeded
    AutoBlockingRule(
        id="data_cap_exceeded",
        name="Data Cap Exceeded",
        description="Suspend services that exceed their data cap",
        trigger=BlockingTrigger.DATA_CAP_EXCEEDED,
        usage_threshold_percent=100,
        suspension_reason=SuspensionReason.USAGE_EXCEEDED,
        apply_grace_period=False,  # Immediate suspension
        grace_period_days=0,
        enabled=True,
        priority=50,
    ),
    # Contract expired
    AutoBlockingRule(
        id="contract_expired",
        name="Contract Expired",
        description="Suspend services with expired contracts",
        trigger=BlockingTrigger.CONTRACT_EXPIRED,
        days_overdue=0,
        suspension_reason=SuspensionReason.CONTRACT_EXPIRED,
        apply_grace_period=True,
        grace_period_days=7,
        enabled=True,
        priority=30,
    ),
]


# =============================================================================
# AUTO-BLOCKING SERVICE
# =============================================================================

class AutoBlockingService:
    """Service for automated service blocking.

    Runs checks against subscriptions and applies blocking rules
    based on payment status, usage limits, and contract terms.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        policy: Optional[AutoBlockingPolicy] = None,
    ):
        self.db = db
        self.principal = principal
        self.policy = policy or AutoBlockingPolicy(
            enabled=True,
            rules=DEFAULT_BLOCKING_RULES,
        )
        self.lifecycle_service = LifecycleService(
            db, principal,
            grace_policy=self.policy.default_grace_period,
        )

    # -------------------------------------------------------------------------
    # Blocking Runs
    # -------------------------------------------------------------------------

    def run_blocking_check(
        self,
        dry_run: bool = False,
        party_ids: Optional[List[int]] = None,
        subscription_ids: Optional[List[int]] = None,
    ) -> BlockingRunResult:
        """Run blocking check on all or selected subscriptions.

        Args:
            dry_run: If True, don't actually suspend, just report.
            party_ids: Optional list of party IDs to check.
            subscription_ids: Optional list of subscription IDs to check.

        Returns:
            BlockingRunResult with details.
        """
        import uuid

        if not self.policy.enabled:
            return BlockingRunResult(
                run_id=str(uuid.uuid4()),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )

        result = BlockingRunResult(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )

        # Get subscriptions to check
        query = self.db.query(Subscription).options(
            joinedload(Subscription.party),
        ).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
        )

        if party_ids:
            query = query.filter(Subscription.party_id.in_(party_ids))
        if subscription_ids:
            query = query.filter(Subscription.id.in_(subscription_ids))

        # Exclude exempt parties
        if self.policy.exempt_party_ids:
            query = query.filter(~Subscription.party_id.in_(self.policy.exempt_party_ids))

        subscriptions = query.all()
        result.subscriptions_checked = len(subscriptions)

        active_rules = self.policy.get_active_rules()

        for sub in subscriptions:
            try:
                check = self._check_subscription(sub, active_rules)
                result.checks.append(check)

                if check.already_blocked:
                    result.already_blocked += 1
                    continue

                if check.should_block and not dry_run:
                    # Apply blocking
                    action_result = self._apply_blocking(sub, check)
                    check.action_taken = action_result

                    if "suspended" in action_result.lower():
                        result.newly_blocked += 1
                        result.blocked_mrr += Decimal(str(sub.price or 0))
                    elif "grace" in action_result.lower():
                        result.entered_grace += 1
                        result.blocked_mrr += Decimal(str(sub.price or 0))

                elif not check.should_block:
                    result.skipped += 1

            except Exception as e:
                result.errors += 1
                result.errors_detail.append({
                    "subscription_id": sub.id,
                    "error": str(e),
                })

        result.completed_at = datetime.now(timezone.utc)
        return result

    def check_subscription(
        self,
        subscription_id: int,
    ) -> SubscriptionBlockingCheck:
        """Check a single subscription for blocking.

        Args:
            subscription_id: The subscription ID.

        Returns:
            SubscriptionBlockingCheck result.
        """
        sub = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()

        if not sub:
            return SubscriptionBlockingCheck(
                subscription_id=subscription_id,
                party_id=0,
                plan_name="Unknown",
                current_state=ServiceLifecycleState.PENDING_ACTIVATION,
                error="Subscription not found",
            )

        active_rules = self.policy.get_active_rules()
        return self._check_subscription(sub, active_rules)

    def run_grace_expiration_check(
        self,
        dry_run: bool = False,
    ) -> BlockingRunResult:
        """Check for expired grace periods and terminate.

        Args:
            dry_run: If True, don't actually terminate.

        Returns:
            BlockingRunResult.
        """
        import uuid

        result = BlockingRunResult(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )

        now = datetime.now(timezone.utc)

        # Find expired grace periods
        expired = self.db.query(Subscription).filter(
            Subscription.lifecycle_state == "grace_period",
            Subscription.grace_period_ends_at.isnot(None),
            Subscription.grace_period_ends_at <= now,
        ).all()

        result.subscriptions_checked = len(expired)

        for sub in expired:
            try:
                check = SubscriptionBlockingCheck(
                    subscription_id=sub.id,
                    party_id=sub.party_id,
                    plan_name=sub.plan_name,
                    current_state=ServiceLifecycleState.GRACE_PERIOD,
                    should_block=True,
                    primary_reason=SuspensionReason.PAYMENT_OVERDUE,
                )

                if not dry_run:
                    # Terminate the subscription
                    terminate_result = self.lifecycle_service.terminate(
                        TerminateRequest(
                            subscription_id=sub.id,
                            reason=TerminationReason.GRACE_PERIOD_EXPIRED,
                            notes="Automatic termination: grace period expired",
                        )
                    )
                    if terminate_result.success:
                        check.action_taken = "terminated"
                        result.terminated += 1
                    else:
                        check.error = terminate_result.error
                        result.errors += 1

                result.checks.append(check)

            except Exception as e:
                result.errors += 1
                result.errors_detail.append({
                    "subscription_id": sub.id,
                    "error": str(e),
                })

        result.completed_at = datetime.now(timezone.utc)
        return result

    # -------------------------------------------------------------------------
    # Individual Checks
    # -------------------------------------------------------------------------

    def _check_subscription(
        self,
        sub: Subscription,
        rules: List[AutoBlockingRule],
    ) -> SubscriptionBlockingCheck:
        """Check subscription against blocking rules."""
        current_state = self.lifecycle_service.get_current_state(sub.id)

        check = SubscriptionBlockingCheck(
            subscription_id=sub.id,
            party_id=sub.party_id,
            plan_name=sub.plan_name,
            current_state=current_state,
            already_blocked=current_state.is_suspended or current_state.is_terminal,
        )

        if check.already_blocked:
            return check

        # Run each rule
        for rule in rules:
            triggered, details = self._evaluate_rule(sub, rule)
            if triggered:
                check.triggered_rules.append(rule)
                check.should_block = True

                # Capture details from first triggered rule
                if not check.primary_reason:
                    check.primary_reason = rule.suspension_reason
                    check.outstanding_amount = details.get("outstanding_amount", Decimal("0"))
                    check.days_overdue = details.get("days_overdue", 0)
                    check.oldest_overdue_invoice_id = details.get("oldest_invoice_id")
                    check.oldest_overdue_invoice_date = details.get("oldest_invoice_date")
                    check.usage_percent = details.get("usage_percent", 0.0)
                    check.data_used_gb = details.get("data_used_gb", 0.0)
                    check.data_cap_gb = details.get("data_cap_gb")

        return check

    def _evaluate_rule(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate a single rule against subscription.

        Returns:
            Tuple of (triggered, details dict).
        """
        if rule.trigger == BlockingTrigger.INVOICE_OVERDUE:
            return self._check_invoice_overdue(sub, rule)
        elif rule.trigger == BlockingTrigger.PAYMENT_OVERDUE:
            return self._check_payment_overdue(sub, rule)
        elif rule.trigger == BlockingTrigger.DATA_CAP_EXCEEDED:
            return self._check_data_cap(sub, rule)
        elif rule.trigger == BlockingTrigger.CONTRACT_EXPIRED:
            return self._check_contract_expired(sub, rule)
        elif rule.trigger == BlockingTrigger.USAGE_THRESHOLD:
            return self._check_usage_threshold(sub, rule)

        return False, {}

    def _check_invoice_overdue(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check for overdue invoices."""
        today = date.today()
        cutoff = today - timedelta(days=rule.days_overdue)

        # Find overdue invoices for this party
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.customer_account_id.in_(
                self.db.query(CustomerAccount.id).filter(
                    CustomerAccount.party_id == sub.party_id
                )
            ),
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
            Invoice.due_date < cutoff,
        ).order_by(Invoice.due_date.asc()).all()

        if not overdue_invoices:
            return False, {}

        # Calculate total outstanding
        total_outstanding = sum(
            (inv.total_amount or Decimal("0")) - (inv.amount_paid or Decimal("0"))
            for inv in overdue_invoices
        )

        # Check amount threshold
        if rule.amount_threshold and total_outstanding < rule.amount_threshold:
            return False, {}

        oldest = overdue_invoices[0]
        days_overdue = (today - oldest.due_date).days

        return True, {
            "outstanding_amount": total_outstanding,
            "days_overdue": days_overdue,
            "oldest_invoice_id": oldest.id,
            "oldest_invoice_date": oldest.due_date,
            "invoice_count": len(overdue_invoices),
        }

    def _check_payment_overdue(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check for general payment overdue (similar to invoice but broader)."""
        # Delegate to invoice check for now
        return self._check_invoice_overdue(sub, rule)

    def _check_data_cap(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if data cap exceeded."""
        if not sub.data_cap:
            return False, {}

        # Get current usage from usage service
        # For now, approximate from session data or return False
        data_cap_gb = sub.data_cap / 1024 if sub.data_cap > 1000 else sub.data_cap

        # Would integrate with usage service here
        # current_usage_gb = usage_service.get_current_period_usage(sub.id)
        current_usage_gb = 0  # Placeholder

        usage_percent = (current_usage_gb / data_cap_gb * 100) if data_cap_gb > 0 else 0

        if usage_percent >= rule.usage_threshold_percent:
            return True, {
                "usage_percent": usage_percent,
                "data_used_gb": current_usage_gb,
                "data_cap_gb": data_cap_gb,
            }

        return False, {}

    def _check_contract_expired(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if contract/subscription has expired."""
        if not sub.end_date:
            return False, {}

        now = datetime.now(timezone.utc)
        if isinstance(sub.end_date, date) and not isinstance(sub.end_date, datetime):
            end_dt = datetime.combine(sub.end_date, datetime.min.time(), tzinfo=timezone.utc)
        else:
            end_dt = sub.end_date if sub.end_date.tzinfo else sub.end_date.replace(tzinfo=timezone.utc)

        if end_dt < now:
            days_expired = (now - end_dt).days
            return True, {
                "days_expired": days_expired,
                "end_date": sub.end_date,
            }

        return False, {}

    def _check_usage_threshold(
        self,
        sub: Subscription,
        rule: AutoBlockingRule,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if usage threshold exceeded."""
        return self._check_data_cap(sub, rule)

    # -------------------------------------------------------------------------
    # Apply Blocking
    # -------------------------------------------------------------------------

    def _apply_blocking(
        self,
        sub: Subscription,
        check: SubscriptionBlockingCheck,
    ) -> str:
        """Apply blocking action based on check result."""
        if not check.triggered_rules:
            return "no_action"

        primary_rule = check.triggered_rules[0]

        # Create suspend request
        request = SuspendRequest(
            subscription_id=sub.id,
            reason=check.primary_reason or SuspensionReason.ADMIN_ACTION,
            notes=f"Auto-blocked by rule: {primary_rule.name}",
            apply_grace_period=primary_rule.apply_grace_period,
            grace_period_days=primary_rule.grace_period_days if primary_rule.apply_grace_period else None,
            send_notification=True,
            deprovision=True,
        )

        result = self.lifecycle_service.suspend(request)

        if result.success:
            if primary_rule.apply_grace_period:
                return f"suspended_with_grace ({primary_rule.grace_period_days} days)"
            return "suspended"
        else:
            return f"failed: {result.error}"

    # -------------------------------------------------------------------------
    # Stats and Reporting
    # -------------------------------------------------------------------------

    def get_blocking_stats(self) -> BlockingStats:
        """Get auto-blocking statistics."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        stats = BlockingStats()

        # Count suspended subscriptions
        suspended = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED,
        ).all()

        # Categorize by suspension date
        for sub in suspended:
            if hasattr(sub, 'suspended_at') and sub.suspended_at:
                suspended_date = sub.suspended_at.date() if isinstance(sub.suspended_at, datetime) else sub.suspended_at
                if suspended_date == today:
                    stats.suspensions_today += 1
                if suspended_date >= week_start:
                    stats.suspensions_this_week += 1

            # Count by reason
            if hasattr(sub, 'suspension_reason') and sub.suspension_reason:
                reason = sub.suspension_reason
                stats.by_trigger[reason] = stats.by_trigger.get(reason, 0) + 1

            # Calculate blocked revenue
            stats.blocked_revenue += Decimal(str(sub.price or 0))

        # Count in grace period
        in_grace = self.db.query(Subscription).filter(
            Subscription.lifecycle_state == "grace_period",
        ).count()
        stats.pending_terminations = in_grace

        return stats

    def get_at_risk_subscriptions(
        self,
        days_to_suspension: int = 3,
    ) -> List[SubscriptionBlockingCheck]:
        """Get subscriptions at risk of suspension.

        Args:
            days_to_suspension: Days before suspension.

        Returns:
            List of at-risk subscription checks.
        """
        results = []

        # Find subscriptions with invoices approaching overdue threshold
        active_rules = self.policy.get_active_rules()

        # Get active subscriptions
        subs = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).all()

        for sub in subs:
            # Check if any rule would trigger within days_to_suspension
            for rule in active_rules:
                if rule.trigger in (BlockingTrigger.INVOICE_OVERDUE, BlockingTrigger.PAYMENT_OVERDUE):
                    # Check if invoice will be overdue enough soon
                    approaching_threshold = rule.days_overdue - days_to_suspension

                    today = date.today()
                    cutoff = today - timedelta(days=approaching_threshold)

                    overdue_invoices = self.db.query(Invoice).filter(
                        Invoice.customer_account_id.in_(
                            self.db.query(CustomerAccount.id).filter(
                                CustomerAccount.party_id == sub.party_id
                            )
                        ),
                        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                        Invoice.due_date < cutoff,
                    ).first()

                    if overdue_invoices:
                        check = self._check_subscription(sub, [rule])
                        if not check.should_block:  # Not yet blocked but at risk
                            check.should_block = False  # Mark as at-risk
                            results.append(check)
                        break

        return results

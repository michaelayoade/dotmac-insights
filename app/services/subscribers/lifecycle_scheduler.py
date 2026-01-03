"""Lifecycle Scheduler Service.

Scheduled tasks for automated lifecycle management:
- Daily blocking checks
- Grace period expiration checks
- Notification scheduling
- Reporting

Can be integrated with Celery, APScheduler, or cron jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import logging

from sqlalchemy.orm import Session

from .lifecycle_types import (
    AutoBlockingPolicy,
    GracePeriodPolicy,
    LifecycleStats,
    BlockingStats,
)
from .lifecycle_service import LifecycleService
from .auto_blocking_service import AutoBlockingService, BlockingRunResult

if TYPE_CHECKING:
    from app.auth import Principal


__all__ = [
    "LifecycleScheduler",
    "ScheduledTaskResult",
    "DailyReportData",
]

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class ScheduledTaskResult:
    """Result of a scheduled task execution."""

    task_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    success: bool = True
    error: Optional[str] = None

    # Metrics
    items_processed: int = 0
    items_affected: int = 0

    # Details
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0


@dataclass
class DailyReportData:
    """Data for daily lifecycle report."""

    report_date: date
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Lifecycle stats
    lifecycle_stats: Optional[LifecycleStats] = None
    blocking_stats: Optional[BlockingStats] = None

    # Today's actions
    suspensions_today: int = 0
    reactivations_today: int = 0
    terminations_today: int = 0
    grace_entries_today: int = 0

    # At-risk
    at_risk_count: int = 0
    at_risk_mrr: Decimal = field(default_factory=lambda: Decimal("0"))

    # Grace period
    grace_expiring_tomorrow: int = 0
    grace_expiring_this_week: int = 0

    # Financial impact
    suspended_mrr: Decimal = field(default_factory=lambda: Decimal("0"))
    terminated_mrr_today: Decimal = field(default_factory=lambda: Decimal("0"))


# =============================================================================
# LIFECYCLE SCHEDULER
# =============================================================================

class LifecycleScheduler:
    """Scheduler for automated lifecycle tasks.

    Provides methods that can be called by:
    - Celery beat
    - APScheduler
    - Cron jobs via CLI
    - Manual trigger
    """

    def __init__(
        self,
        db: Session,
        policy: Optional[AutoBlockingPolicy] = None,
        grace_policy: Optional[GracePeriodPolicy] = None,
    ):
        self.db = db
        self.policy = policy or AutoBlockingPolicy(enabled=True)
        self.grace_policy = grace_policy or GracePeriodPolicy()
        self.lifecycle_service = LifecycleService(db, grace_policy=self.grace_policy)
        self.blocking_service = AutoBlockingService(db, policy=self.policy)

    # -------------------------------------------------------------------------
    # Scheduled Tasks
    # -------------------------------------------------------------------------

    def run_daily_blocking_check(self) -> ScheduledTaskResult:
        """Run daily auto-blocking check.

        This should be scheduled to run once per day.
        """
        result = ScheduledTaskResult(
            task_name="daily_blocking_check",
            started_at=datetime.now(timezone.utc),
        )

        try:
            logger.info("Starting daily blocking check")

            blocking_result = self.blocking_service.run_blocking_check(dry_run=False)

            result.completed_at = datetime.now(timezone.utc)
            result.items_processed = blocking_result.subscriptions_checked
            result.items_affected = blocking_result.newly_blocked + blocking_result.entered_grace
            result.details = {
                "run_id": blocking_result.run_id,
                "subscriptions_checked": blocking_result.subscriptions_checked,
                "already_blocked": blocking_result.already_blocked,
                "newly_blocked": blocking_result.newly_blocked,
                "entered_grace": blocking_result.entered_grace,
                "skipped": blocking_result.skipped,
                "errors": blocking_result.errors,
                "blocked_mrr": float(blocking_result.blocked_mrr),
                "duration_seconds": blocking_result.duration_seconds,
            }

            logger.info(
                f"Daily blocking check complete: "
                f"{blocking_result.newly_blocked} blocked, "
                f"{blocking_result.entered_grace} entered grace"
            )

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"Daily blocking check failed: {e}")

        return result

    def run_grace_expiration_check(self) -> ScheduledTaskResult:
        """Run grace period expiration check.

        Terminates subscriptions whose grace period has expired.
        This should be scheduled to run at least once per day.
        """
        result = ScheduledTaskResult(
            task_name="grace_expiration_check",
            started_at=datetime.now(timezone.utc),
        )

        try:
            logger.info("Starting grace expiration check")

            blocking_result = self.blocking_service.run_grace_expiration_check(dry_run=False)

            result.completed_at = datetime.now(timezone.utc)
            result.items_processed = blocking_result.subscriptions_checked
            result.items_affected = blocking_result.terminated
            result.details = {
                "run_id": blocking_result.run_id,
                "expired_checked": blocking_result.subscriptions_checked,
                "terminated": blocking_result.terminated,
                "errors": blocking_result.errors,
            }

            logger.info(
                f"Grace expiration check complete: "
                f"{blocking_result.terminated} terminated"
            )

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"Grace expiration check failed: {e}")

        return result

    def run_notification_check(self) -> ScheduledTaskResult:
        """Check and send pending lifecycle notifications.

        Sends reminders for:
        - Grace period ending soon
        - Payment due to avoid suspension
        - Upcoming termination
        """
        from app.models.subscription import Subscription

        result = ScheduledTaskResult(
            task_name="notification_check",
            started_at=datetime.now(timezone.utc),
        )

        try:
            logger.info("Starting notification check")

            notifications_sent = 0
            now = datetime.now(timezone.utc)

            # Find grace periods ending soon (within notification days)
            for notify_days in self.grace_policy.notify_days_before_termination:
                target_date = now + timedelta(days=notify_days)
                target_start = target_date.replace(hour=0, minute=0, second=0)
                target_end = target_date.replace(hour=23, minute=59, second=59)

                expiring = self.db.query(Subscription).filter(
                    Subscription.lifecycle_state == "grace_period",
                    Subscription.grace_period_ends_at >= target_start,
                    Subscription.grace_period_ends_at <= target_end,
                ).all()

                for sub in expiring:
                    # Send notification (integrate with notification service)
                    self._send_grace_warning_notification(sub, notify_days)
                    notifications_sent += 1

            result.completed_at = datetime.now(timezone.utc)
            result.items_affected = notifications_sent
            result.details = {
                "notifications_sent": notifications_sent,
            }

            logger.info(f"Notification check complete: {notifications_sent} sent")

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"Notification check failed: {e}")

        return result

    def generate_daily_report(self) -> DailyReportData:
        """Generate daily lifecycle report.

        Returns summary of lifecycle state and actions.
        """
        from app.models.subscription import Subscription, SubscriptionStatus

        today = date.today()
        now = datetime.now(timezone.utc)
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)

        report = DailyReportData(
            report_date=today,
            generated_at=now,
        )

        # Get lifecycle stats
        report.lifecycle_stats = self.lifecycle_service.get_stats()
        report.blocking_stats = self.blocking_service.get_blocking_stats()

        # Count today's actions (from service transactions)
        # This would query service_transactions for today
        # For now, use blocking stats
        if report.blocking_stats:
            report.suspensions_today = report.blocking_stats.suspensions_today

        # Calculate suspended MRR
        suspended_subs = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.SUSPENDED,
        ).all()

        report.suspended_mrr = sum(
            Decimal(str(s.price or 0))
            for s in suspended_subs
        )

        # Grace expiring soon
        grace_expiring = self.db.query(Subscription).filter(
            Subscription.lifecycle_state == "grace_period",
            Subscription.grace_period_ends_at.isnot(None),
        ).all()

        for sub in grace_expiring:
            if sub.grace_period_ends_at:
                exp_date = sub.grace_period_ends_at.date() if isinstance(sub.grace_period_ends_at, datetime) else sub.grace_period_ends_at
                if exp_date == tomorrow:
                    report.grace_expiring_tomorrow += 1
                if exp_date <= week_end:
                    report.grace_expiring_this_week += 1

        # At-risk subscriptions
        at_risk = self.blocking_service.get_at_risk_subscriptions(days_to_suspension=3)
        report.at_risk_count = len(at_risk)

        return report

    # -------------------------------------------------------------------------
    # Run All Tasks
    # -------------------------------------------------------------------------

    def run_all_daily_tasks(self) -> List[ScheduledTaskResult]:
        """Run all daily scheduled tasks.

        Returns list of results for each task.
        """
        results = []

        # 1. Blocking check
        results.append(self.run_daily_blocking_check())

        # 2. Grace expiration check
        results.append(self.run_grace_expiration_check())

        # 3. Notification check
        results.append(self.run_notification_check())

        return results

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _send_grace_warning_notification(
        self,
        sub: "Subscription",
        days_remaining: int,
    ) -> bool:
        """Send grace period warning notification."""
        # Integration with notification service
        # For now, just log
        logger.info(
            f"Would send grace warning for subscription {sub.id}: "
            f"{days_remaining} days until termination"
        )
        return True


# =============================================================================
# CLI COMMANDS (for cron integration)
# =============================================================================

def run_blocking_check_cli():
    """CLI entry point for blocking check."""
    from app.database import get_session

    with get_session() as db:
        scheduler = LifecycleScheduler(db)
        result = scheduler.run_daily_blocking_check()
        print(f"Blocking check: {result.items_affected} affected, {result.duration_seconds:.2f}s")
        if not result.success:
            print(f"Error: {result.error}")
            return 1
        return 0


def run_grace_check_cli():
    """CLI entry point for grace expiration check."""
    from app.database import get_session

    with get_session() as db:
        scheduler = LifecycleScheduler(db)
        result = scheduler.run_grace_expiration_check()
        print(f"Grace check: {result.items_affected} terminated, {result.duration_seconds:.2f}s")
        if not result.success:
            print(f"Error: {result.error}")
            return 1
        return 0


def generate_daily_report_cli():
    """CLI entry point for daily report generation."""
    from app.database import get_session

    with get_session() as db:
        scheduler = LifecycleScheduler(db)
        report = scheduler.generate_daily_report()

        print(f"\n=== Lifecycle Daily Report ({report.report_date}) ===\n")

        if report.lifecycle_stats:
            print("Subscription States:")
            print(f"  Active:     {report.lifecycle_stats.active}")
            print(f"  Suspended:  {report.lifecycle_stats.suspended}")
            print(f"  In Grace:   {report.lifecycle_stats.in_grace}")
            print(f"  Terminated: {report.lifecycle_stats.terminated}")
            print()

        print("Today's Actions:")
        print(f"  Suspensions:  {report.suspensions_today}")
        print(f"  Terminations: {report.terminations_today}")
        print()

        print("At Risk:")
        print(f"  Services at risk:           {report.at_risk_count}")
        print(f"  Grace expiring tomorrow:    {report.grace_expiring_tomorrow}")
        print(f"  Grace expiring this week:   {report.grace_expiring_this_week}")
        print()

        print("Financial Impact:")
        print(f"  Suspended MRR: {report.suspended_mrr}")

        return 0

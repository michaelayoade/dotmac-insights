"""Celery tasks for performance module - scorecard computation and period processing."""
import structlog
from typing import Optional, List
import redis

from app.worker import celery_app
from app.config import settings
from app.database import SessionLocal
from app.services.metrics_computation_service import MetricsComputationService
from app.services.performance_service import PerformanceService

logger = structlog.get_logger()

# Redis client for distributed locks
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for locks."""
    global _redis_client
    if _redis_client is None:
        redis_url = settings.redis_url or "redis://localhost:6379/0"
        _redis_client = redis.from_url(redis_url)
    return _redis_client


class TaskLock:
    """Distributed lock using Redis to prevent concurrent task execution."""

    def __init__(self, lock_name: str, timeout: int = 1800):  # 30 min default
        self.lock_name = f"celery_lock:performance:{lock_name}"
        self.timeout = timeout
        self.redis = get_redis_client()
        self._lock = None

    def __enter__(self):
        self._lock = self.redis.lock(self.lock_name, timeout=self.timeout)
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise TaskLockError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            try:
                self._lock.release()
            except redis.exceptions.LockError:
                pass


class TaskLockError(Exception):
    """Raised when a task lock cannot be acquired."""
    pass


@celery_app.task(
    name="performance.compute_scorecard",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def compute_scorecard(self, scorecard_id: int):
    """
    Compute metrics for a single employee scorecard.

    Args:
        scorecard_id: The scorecard instance ID to compute

    Returns:
        Dict with computation results
    """
    logger.info("compute_scorecard_started", scorecard_id=scorecard_id)

    try:
        with TaskLock(f"scorecard_{scorecard_id}", timeout=300):  # 5 min per scorecard
            db = SessionLocal()
            try:
                service = MetricsComputationService(db)
                result = service.compute_scorecard(scorecard_id)

                if result.get("success"):
                    logger.info(
                        "compute_scorecard_completed",
                        scorecard_id=scorecard_id,
                        total_score=result.get("total_score"),
                        rating=result.get("rating"),
                    )
                else:
                    logger.error(
                        "compute_scorecard_failed",
                        scorecard_id=scorecard_id,
                        error=result.get("error"),
                    )

                return result

            finally:
                db.close()

    except TaskLockError:
        logger.warning("compute_scorecard_locked", scorecard_id=scorecard_id)
        return {"success": False, "error": "Task already running"}

    except Exception as exc:
        logger.error("compute_scorecard_error", scorecard_id=scorecard_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="performance.compute_period_metrics",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def compute_period_metrics(self, period_id: int):
    """
    Compute all scorecards for an evaluation period.

    This is the main entry point for bulk computation triggered when
    a period transitions to the scoring phase.

    Args:
        period_id: The evaluation period ID

    Returns:
        Dict with total, computed, failed counts
    """
    logger.info("compute_period_metrics_started", period_id=period_id)

    try:
        with TaskLock(f"period_{period_id}", timeout=3600):  # 1 hour for full period
            db = SessionLocal()
            try:
                service = MetricsComputationService(db)
                result = service.compute_period(period_id)

                logger.info(
                    "compute_period_metrics_completed",
                    period_id=period_id,
                    total=result.get("total"),
                    computed=result.get("computed"),
                    failed=result.get("failed"),
                )

                # If we have errors, log them
                for error in result.get("errors", []):
                    logger.warning(
                        "scorecard_computation_error",
                        period_id=period_id,
                        scorecard_id=error.get("scorecard_id"),
                        error=error.get("error"),
                    )

                return result

            finally:
                db.close()

    except TaskLockError:
        logger.warning("compute_period_locked", period_id=period_id)
        return {"success": False, "error": "Period computation already running"}

    except Exception as exc:
        logger.error("compute_period_error", period_id=period_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="performance.generate_snapshots")
def generate_snapshots(period_id: int):
    """
    Generate denormalized performance snapshots for analytics after period finalization.

    Args:
        period_id: The finalized period ID

    Returns:
        Dict with snapshot count
    """
    logger.info("generate_snapshots_started", period_id=period_id)

    db = SessionLocal()
    try:
        service = PerformanceService(db)
        result = service.generate_snapshots(period_id)

        logger.info(
            "generate_snapshots_completed",
            period_id=period_id,
            snapshots_created=result.get("snapshots_created"),
        )

        return result

    except Exception as exc:
        logger.error("generate_snapshots_error", period_id=period_id, error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.check_scoring_deadlines")
def check_scoring_deadlines():
    """
    Daily task to auto-transition periods past their end date to scoring phase.

    Scheduled via Celery beat.
    """
    from datetime import date
    from app.models.performance import EvaluationPeriod, EvaluationPeriodStatus

    logger.info("check_scoring_deadlines_started")

    db = SessionLocal()
    try:
        today = date.today()

        # Find active periods past their end date
        periods = db.query(EvaluationPeriod).filter(
            EvaluationPeriod.status == EvaluationPeriodStatus.ACTIVE,
            EvaluationPeriod.end_date < today,
        ).all()

        transitioned = 0
        for period in periods:
            period.status = EvaluationPeriodStatus.SCORING
            transitioned += 1

            # Trigger computation
            compute_period_metrics.delay(period.id)

            logger.info(
                "period_auto_transitioned_to_scoring",
                period_id=period.id,
                period_code=period.code,
            )

        db.commit()

        logger.info(
            "check_scoring_deadlines_completed",
            periods_transitioned=transitioned,
        )

        return {"transitioned": transitioned}

    except Exception as exc:
        logger.error("check_scoring_deadlines_error", error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.check_review_deadlines")
def check_review_deadlines():
    """
    Daily task to check for periods past their review deadline and send reminders.

    Scheduled via Celery beat.
    """
    from datetime import date
    from app.models.performance import EvaluationPeriod, EvaluationPeriodStatus
    from app.services.performance_notification_service import PerformanceNotificationService

    logger.info("check_review_deadlines_started")

    db = SessionLocal()
    try:
        today = date.today()

        # Find periods in scoring/review past their review deadline
        periods = db.query(EvaluationPeriod).filter(
            EvaluationPeriod.status.in_([
                EvaluationPeriodStatus.SCORING,
                EvaluationPeriodStatus.REVIEW,
            ]),
            EvaluationPeriod.review_deadline.isnot(None),
            EvaluationPeriod.review_deadline < today,
        ).all()

        notification_service = PerformanceNotificationService(db)
        managers_notified = 0

        for period in periods:
            logger.warning(
                "period_past_review_deadline",
                period_id=period.id,
                period_code=period.code,
                review_deadline=period.review_deadline.isoformat(),
            )
            # Send reminder notifications to managers with pending reviews
            result = notification_service.send_bulk_review_reminders(period.id)
            managers_notified += result.get("managers_notified", 0)

        logger.info(
            "check_review_deadlines_completed",
            periods_past_deadline=len(periods),
            managers_notified=managers_notified,
        )

        return {"periods_past_deadline": len(periods), "managers_notified": managers_notified}

    except Exception as exc:
        logger.error("check_review_deadlines_error", error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.send_scorecard_notification")
def send_scorecard_notification(scorecard_id: int, notification_type: str):
    """
    Send notification about scorecard status change.

    Args:
        scorecard_id: The scorecard ID
        notification_type: Type of notification (computed, approved, finalized, etc.)
    """
    from app.models.performance import EmployeeScorecardInstance, EvaluationPeriod
    from app.models.employee import Employee
    from app.services.performance_notification_service import PerformanceNotificationService

    logger.info(
        "send_scorecard_notification",
        scorecard_id=scorecard_id,
        notification_type=notification_type,
    )

    db = SessionLocal()
    try:
        scorecard = db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.id == scorecard_id
        ).first()

        if not scorecard:
            return {"success": False, "error": "Scorecard not found"}

        period = db.query(EvaluationPeriod).filter(
            EvaluationPeriod.id == scorecard.evaluation_period_id
        ).first()

        if not period:
            return {"success": False, "error": "Period not found"}

        employee = db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
        notification_service = PerformanceNotificationService(db)

        # Route to appropriate notification method based on type
        result = None
        if notification_type == "generated":
            result = notification_service.notify_scorecard_generated(scorecard, period)
        elif notification_type == "computed":
            result = notification_service.notify_scorecard_computed(scorecard, period)
        elif notification_type == "approved":
            result = notification_service.notify_scorecard_approved(scorecard, period, None)
        elif notification_type == "finalized":
            result = notification_service.notify_scorecard_finalized(scorecard, period)
        elif notification_type == "rating_published":
            result = notification_service.notify_rating_published(scorecard, period)
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
            return {"success": False, "error": f"Unknown notification type: {notification_type}"}

        logger.info(
            "scorecard_notification_sent",
            scorecard_id=scorecard_id,
            employee_name=employee.name if employee else "Unknown",
            notification_type=notification_type,
        )

        return result or {"success": True, "notification_type": notification_type}

    except Exception as exc:
        logger.error(
            "send_scorecard_notification_error",
            scorecard_id=scorecard_id,
            error=str(exc),
        )
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.send_weekly_summaries")
def send_weekly_summaries():
    """
    Weekly task to send performance summaries to managers with active evaluations.

    Scheduled via Celery beat to run every Monday morning.
    """
    from app.models.performance import EvaluationPeriod, EvaluationPeriodStatus
    from app.models.employee import Employee
    from app.services.performance_notification_service import PerformanceNotificationService

    logger.info("send_weekly_summaries_started")

    db = SessionLocal()
    try:
        # Find active periods
        active_periods = db.query(EvaluationPeriod).filter(
            EvaluationPeriod.status.in_([
                EvaluationPeriodStatus.ACTIVE,
                EvaluationPeriodStatus.SCORING,
                EvaluationPeriodStatus.REVIEW,
            ])
        ).all()

        if not active_periods:
            logger.info("send_weekly_summaries_no_active_periods")
            return {"success": True, "message": "No active periods"}

        # Filter to only those who have direct reports
        manager_ids = set()
        notification_service = PerformanceNotificationService(db)
        for emp in db.query(Employee).filter(Employee.reports_to.isnot(None)).all():
            manager = db.query(Employee).filter(Employee.name == emp.reports_to).first()
            manager_user_id = notification_service._get_user_id_for_employee(manager)
            if manager_user_id:
                manager_ids.add(manager_user_id)
        summaries_sent = 0

        for period in active_periods:
            for manager_user_id in manager_ids:
                try:
                    notification_service.send_weekly_summary(manager_user_id, period.id)
                    summaries_sent += 1
                except Exception as e:
                    logger.error(
                        "weekly_summary_error",
                        manager_user_id=manager_user_id,
                        period_id=period.id,
                        error=str(e),
                    )

        logger.info(
            "send_weekly_summaries_completed",
            periods=len(active_periods),
            summaries_sent=summaries_sent,
        )

        return {
            "success": True,
            "periods": len(active_periods),
            "summaries_sent": summaries_sent,
        }

    except Exception as exc:
        logger.error("send_weekly_summaries_error", error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.check_period_closing")
def check_period_closing():
    """
    Daily task to warn about periods ending soon.

    Sends warnings 7 days and 3 days before period end.
    Scheduled via Celery beat.
    """
    from datetime import date, timedelta
    from app.models.performance import EvaluationPeriod, EvaluationPeriodStatus
    from app.services.performance_notification_service import PerformanceNotificationService

    logger.info("check_period_closing_started")

    db = SessionLocal()
    try:
        today = date.today()
        warning_days = [7, 3]  # Send warnings at 7 days and 3 days before end

        notification_service = PerformanceNotificationService(db)
        warnings_sent = 0

        for days in warning_days:
            target_end_date = today + timedelta(days=days)

            # Find periods ending on the target date
            periods = db.query(EvaluationPeriod).filter(
                EvaluationPeriod.status == EvaluationPeriodStatus.ACTIVE,
                EvaluationPeriod.end_date == target_end_date,
            ).all()

            for period in periods:
                result = notification_service.notify_period_closing(period, days)
                if result.get("success") != False:
                    warnings_sent += 1
                    logger.info(
                        "period_closing_warning_sent",
                        period_id=period.id,
                        period_code=period.code,
                        days_remaining=days,
                    )

        logger.info(
            "check_period_closing_completed",
            warnings_sent=warnings_sent,
        )

        return {"success": True, "warnings_sent": warnings_sent}

    except Exception as exc:
        logger.error("check_period_closing_error", error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="performance.generate_period_report")
def generate_period_report(period_id: int, email_recipients: Optional[List[str]] = None):
    """
    Generate and optionally email a comprehensive period report.

    Args:
        period_id: The evaluation period ID
        email_recipients: Optional list of email addresses to send report to
    """
    from app.services.performance_notification_service import PerformanceNotificationService
    from app.models.notification import EmailQueue, NotificationStatus

    logger.info("generate_period_report_started", period_id=period_id)

    db = SessionLocal()
    try:
        notification_service = PerformanceNotificationService(db)
        report_data = notification_service.generate_period_report_data(period_id)

        if "error" in report_data:
            return {"success": False, "error": report_data["error"]}

        # If email recipients specified, queue the report email
        if email_recipients:
            from app.models.performance import EvaluationPeriod

            period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
            period_name = period.name if period else f"Period {period_id}"

            # Render email body using Jinja2 template
            from app.templates.environment import get_template_env
            env = get_template_env()
            email_template = env.get_template("emails/performance/period_report.html.j2")
            body_html = email_template.render(
                period_name=period_name,
                summary=report_data["summary"],
                scores=report_data["scores"],
                distribution=report_data["distribution"],
                generated_at=report_data["generated_at"],
            )

            for email in email_recipients:
                email_item = EmailQueue(
                    to_email=email,
                    subject=f"Performance Report: {period_name}",
                    body_html=body_html,
                    event_type="performance_report",
                    entity_type="evaluation_period",
                    entity_id=period_id,
                    status=NotificationStatus.PENDING,
                )
                db.add(email_item)

            db.commit()
            logger.info(
                "period_report_emails_queued",
                period_id=period_id,
                recipients=len(email_recipients),
            )

        logger.info("generate_period_report_completed", period_id=period_id)

        return {
            "success": True,
            "report": report_data,
            "emails_queued": len(email_recipients) if email_recipients else 0,
        }

    except Exception as exc:
        logger.error("generate_period_report_error", period_id=period_id, error=str(exc))
        return {"success": False, "error": str(exc)}

    finally:
        db.close()

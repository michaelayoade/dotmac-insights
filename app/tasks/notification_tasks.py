"""Celery tasks for notification and webhook delivery."""
from datetime import datetime, timedelta
from typing import Optional
import structlog

from app.worker import celery_app
from app.database import SessionLocal
from app.services.notification_service import NotificationService
from app.models.notification import WebhookDelivery, NotificationStatus, EmailQueue

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_pending_webhooks(self, batch_size: int = 50):
    """Process pending webhook deliveries.

    Fetches webhooks that are pending and due for delivery/retry,
    then attempts to deliver each one.

    Args:
        batch_size: Maximum number of webhooks to process in this run
    """
    task_name = "process_pending_webhooks"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0
    succeeded = 0
    failed = 0

    try:
        service = NotificationService(db)
        pending = service.get_pending_deliveries(limit=batch_size)

        logger.info(
            "webhooks_to_process",
            task=task_name,
            count=len(pending),
        )

        for delivery in pending:
            try:
                success = service.deliver_webhook(delivery.id)
                processed += 1
                if success:
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "webhook_delivery_error",
                    delivery_id=delivery.id,
                    error=str(e),
                )
                failed += 1

        logger.info(
            "task_completed",
            task=task_name,
            processed=processed,
            succeeded=succeeded,
            failed=failed,
        )

        return {
            "status": "success",
            "task": task_name,
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def deliver_single_webhook(self, delivery_id: int):
    """Deliver a single webhook immediately.

    Used for immediate delivery when a webhook is queued,
    rather than waiting for the periodic batch processor.

    Args:
        delivery_id: ID of the WebhookDelivery to send
    """
    task_name = "deliver_single_webhook"
    logger.info("task_started", task=task_name, delivery_id=delivery_id)

    db = SessionLocal()
    try:
        service = NotificationService(db)
        success = service.deliver_webhook(delivery_id)

        logger.info(
            "task_completed",
            task=task_name,
            delivery_id=delivery_id,
            success=success,
        )

        return {
            "status": "success" if success else "failed",
            "task": task_name,
            "delivery_id": delivery_id,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, delivery_id=delivery_id, error=str(e))
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_email_queue(self, batch_size: int = 20):
    """Process pending emails in the queue.

    Fetches emails that are pending and attempts to send each one.
    This is a placeholder - actual email sending requires SMTP configuration.

    Args:
        batch_size: Maximum number of emails to process in this run
    """
    task_name = "process_email_queue"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0
    succeeded = 0
    failed = 0

    try:
        # Get pending emails ordered by priority and creation time
        pending_emails = db.query(EmailQueue).filter(
            EmailQueue.status == NotificationStatus.PENDING,
        ).order_by(
            EmailQueue.priority,
            EmailQueue.created_at,
        ).limit(batch_size).all()

        logger.info(
            "emails_to_process",
            task=task_name,
            count=len(pending_emails),
        )

        for email in pending_emails:
            try:
                # TODO: Implement actual email sending via SMTP/SendGrid/etc.
                # For now, just mark as sent for testing
                email.attempt_count += 1
                email.last_attempt_at = datetime.utcnow()

                # Placeholder - would call email service here
                # success = email_service.send(email)

                # For now, log that we would send
                logger.info(
                    "email_would_send",
                    email_id=email.id,
                    to=email.to_email,
                    subject=email.subject,
                )

                # Mark as pending until real implementation
                # email.status = NotificationStatus.SENT
                # email.sent_at = datetime.utcnow()
                processed += 1

            except Exception as e:
                logger.error(
                    "email_send_error",
                    email_id=email.id,
                    error=str(e),
                )
                email.error_message = str(e)[:1000]
                failed += 1

        db.commit()

        logger.info(
            "task_completed",
            task=task_name,
            processed=processed,
            succeeded=succeeded,
            failed=failed,
        )

        return {
            "status": "success",
            "task": task_name,
            "processed": processed,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task
def cleanup_old_deliveries(days: int = 30):
    """Clean up old webhook delivery records.

    Removes delivered/failed webhook records older than specified days
    to prevent table bloat.

    Args:
        days: Delete records older than this many days
    """
    task_name = "cleanup_old_deliveries"
    logger.info("task_started", task=task_name, days=days)

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Delete old delivered webhooks
        deleted = db.query(WebhookDelivery).filter(
            WebhookDelivery.status.in_([
                NotificationStatus.DELIVERED,
                NotificationStatus.FAILED,
            ]),
            WebhookDelivery.created_at < cutoff,
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(
            "task_completed",
            task=task_name,
            deleted=deleted,
        )

        return {
            "status": "success",
            "task": task_name,
            "deleted": deleted,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()

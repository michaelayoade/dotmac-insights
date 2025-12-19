"""
Celery tasks for contacts domain.

Includes:
- Reconciliation task: compares UnifiedContact with external systems
- Outbound sync retry task: retries failed outbound syncs
"""
import logging
from datetime import datetime, timedelta

from app.worker import celery_app
from app.database import SessionLocal
from app.feature_flags import feature_flags

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.contacts_tasks.run_contacts_reconciliation",
    max_retries=3,
    default_retry_delay=60,
)
def run_contacts_reconciliation(self):
    """
    Run contacts reconciliation against external systems.

    Compares UnifiedContact data with legacy Customer table (and eventually
    Splynx/ERPNext APIs) to detect drift.

    Updates Prometheus metrics with drift percentages.

    Recommended schedule: Every hour or daily depending on sync frequency.
    """
    if not feature_flags.CONTACTS_RECONCILIATION_ENABLED:
        logger.info("Contacts reconciliation skipped - feature flag disabled")
        return {"status": "skipped", "reason": "feature_flag_disabled"}

    logger.info("Starting contacts reconciliation task")

    db = SessionLocal()
    try:
        from app.services.contacts_reconciliation import ContactsReconciliationService

        service = ContactsReconciliationService(db)
        reports = service.run_full_reconciliation()

        # Convert reports to serializable format
        result = {
            "status": "completed",
            "run_at": datetime.utcnow().isoformat(),
            "reports": {
                system: report.to_dict()
                for system, report in reports.items()
            }
        }

        logger.info(f"Contacts reconciliation completed: {len(reports)} systems checked")
        return result

    except Exception as e:
        logger.error(f"Contacts reconciliation failed: {e}")
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.tasks.contacts_tasks.retry_failed_outbound_syncs",
    max_retries=3,
    default_retry_delay=60,
)
def retry_failed_outbound_syncs(self, max_retries: int = 5, batch_size: int = 100):
    """
    Retry failed outbound sync operations.

    Picks up failed syncs from outbound_sync_log table and retries them.

    Args:
        max_retries: Maximum retry attempts per sync
        batch_size: Number of syncs to process per run

    Recommended schedule: Every 5-15 minutes.
    """
    if not feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED:
        logger.info("Outbound sync retry skipped - feature flag disabled")
        return {"status": "skipped", "reason": "feature_flag_disabled"}

    logger.info("Starting outbound sync retry task")

    db = SessionLocal()
    try:
        from sqlalchemy import select
        from app.models.outbound_sync import OutboundSyncLog, SyncStatus
        from app.models.unified_contact import UnifiedContact
        from app.services.outbound_sync import OutboundSyncService

        # Find failed syncs that haven't exceeded max retries
        failed_syncs = db.execute(
            select(OutboundSyncLog).where(
                OutboundSyncLog.status == SyncStatus.FAILED.value,
                OutboundSyncLog.retry_count < max_retries,
                OutboundSyncLog.entity_type == "unified_contact",
            ).order_by(OutboundSyncLog.created_at).limit(batch_size)
        ).scalars().all()

        retried = 0
        succeeded = 0
        failed = 0

        sync_service = OutboundSyncService(db)

        for sync_log in failed_syncs:
            try:
                # Get the contact
                contact = db.execute(
                    select(UnifiedContact).where(UnifiedContact.id == sync_log.entity_id)
                ).scalar_one_or_none()

                if not contact:
                    logger.warning(f"Contact {sync_log.entity_id} not found for retry")
                    sync_log.error_message = "Contact not found"
                    sync_log.retry_count += 1
                    failed += 1
                    continue

                # Retry the sync using existing log (no new log created)
                result_log = sync_service.retry_log(sync_log, contact)

                retried += 1
                if result_log.status == SyncStatus.SUCCESS.value:
                    succeeded += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to retry sync {sync_log.id}: {e}")
                sync_log.error_message = str(e)
                sync_log.retry_count += 1
                failed += 1

        db.commit()

        result = {
            "status": "completed",
            "run_at": datetime.utcnow().isoformat(),
            "retried": retried,
            "succeeded": succeeded,
            "failed": failed,
        }

        logger.info(f"Outbound sync retry completed: {retried} retried, {succeeded} succeeded, {failed} failed")
        return result

    except Exception as e:
        logger.error(f"Outbound sync retry task failed: {e}")
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(name="app.tasks.contacts_tasks.get_drift_summary")
def get_drift_summary():
    """
    Get a quick summary of current drift status.

    Lighter weight than full reconciliation - just counts.
    Useful for health checks and dashboards.
    """
    db = SessionLocal()
    try:
        from app.services.contacts_reconciliation import ContactsReconciliationService

        service = ContactsReconciliationService(db)
        summary = service.get_drift_summary()

        return {
            "status": "completed",
            "run_at": datetime.utcnow().isoformat(),
            "summary": summary,
        }
    finally:
        db.close()

"""Celery tasks for asset management.

Scheduled tasks for:
- Automatic periodic depreciation posting
- Maintenance reminders and alerts
- Warranty expiry notifications
- Insurance expiry notifications
"""
from datetime import date, datetime
from typing import Optional
import structlog

from app.worker import celery_app
from app.database import SessionLocal
from app.services.assets import (
    DepreciationService,
    AssetMaintenanceService,
)

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def post_periodic_depreciation(self, as_of_date: Optional[str] = None):
    """Post all due depreciation entries.

    This task should be run monthly (e.g., on the 1st of each month)
    to automatically post depreciation for all assets with schedules
    due on or before the specified date.

    Args:
        as_of_date: Date to post depreciation as of (ISO format: YYYY-MM-DD).
                   Defaults to today.
    """
    task_name = "post_periodic_depreciation"
    target_date = date.fromisoformat(as_of_date) if as_of_date else date.today()

    logger.info(
        "task_started",
        task=task_name,
        as_of_date=target_date.isoformat(),
    )

    db = SessionLocal()
    try:
        service = DepreciationService(db)

        # Get all pending depreciation entries
        pending = service.get_pending_depreciation(as_of_date=target_date)

        if not pending:
            logger.info(
                "task_completed",
                task=task_name,
                message="No pending depreciation entries",
                posted=0,
            )
            return {
                "status": "success",
                "task": task_name,
                "posted": 0,
                "total_depreciation": 0,
            }

        # Collect schedule IDs for batch posting
        schedule_ids = [p.schedule_id for p in pending]

        logger.info(
            "depreciation_entries_found",
            task=task_name,
            count=len(schedule_ids),
        )

        # Post in batch
        result = service.post_depreciation_batch(schedule_ids)
        db.commit()

        logger.info(
            "task_completed",
            task=task_name,
            posted=result.schedules_posted,
            total_depreciation=float(result.total_depreciation),
            journal_entry_id=result.journal_entry_id,
        )

        return {
            "status": "success",
            "task": task_name,
            "posted": result.schedules_posted,
            "total_depreciation": float(result.total_depreciation),
            "journal_entry_id": result.journal_entry_id,
            "journal_entry_number": result.journal_entry_number,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def post_asset_depreciation(self, schedule_id: int):
    """Post a single depreciation entry.

    Used for on-demand depreciation posting for a specific schedule.

    Args:
        schedule_id: ID of the depreciation schedule to post.
    """
    task_name = "post_asset_depreciation"
    logger.info("task_started", task=task_name, schedule_id=schedule_id)

    db = SessionLocal()
    try:
        service = DepreciationService(db)
        result = service.post_depreciation(schedule_id)
        db.commit()

        logger.info(
            "task_completed",
            task=task_name,
            schedule_id=schedule_id,
            journal_entry_id=result.journal_entry_id,
            depreciation_amount=float(result.total_depreciation),
        )

        return {
            "status": "success",
            "task": task_name,
            "schedule_id": schedule_id,
            "journal_entry_id": result.journal_entry_id,
            "journal_entry_number": result.journal_entry_number,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, schedule_id=schedule_id, error=str(e))
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task
def send_maintenance_alerts(days_ahead: int = 7):
    """Send alerts for assets requiring maintenance.

    This task should be run daily to notify relevant personnel
    about assets that need maintenance.

    Args:
        days_ahead: Number of days to look ahead for due maintenance.
    """
    task_name = "send_maintenance_alerts"
    logger.info("task_started", task=task_name, days_ahead=days_ahead)

    db = SessionLocal()
    try:
        service = AssetMaintenanceService(db)
        assets = service.get_due_maintenance(days_ahead=days_ahead)

        if not assets:
            logger.info(
                "task_completed",
                task=task_name,
                message="No assets requiring maintenance",
                count=0,
            )
            return {
                "status": "success",
                "task": task_name,
                "alerts_sent": 0,
            }

        # Log the assets requiring maintenance
        # In a real implementation, this would send emails/notifications
        for asset in assets:
            logger.info(
                "maintenance_alert",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                location=asset.location,
                custodian=asset.custodian,
            )

        # TODO: Integrate with notification service to send actual alerts
        # notification_service.send_maintenance_alerts(assets)

        logger.info(
            "task_completed",
            task=task_name,
            alerts_sent=len(assets),
        )

        return {
            "status": "success",
            "task": task_name,
            "alerts_sent": len(assets),
            "asset_ids": [a.id for a in assets],
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "failed", "task": task_name, "error": str(e)}
    finally:
        db.close()


@celery_app.task
def send_warranty_expiry_alerts(days_ahead: int = 30):
    """Send alerts for assets with expiring warranties.

    This task should be run daily to notify about warranties
    that will expire within the specified number of days.

    Args:
        days_ahead: Number of days to look ahead for expiring warranties.
    """
    task_name = "send_warranty_expiry_alerts"
    logger.info("task_started", task=task_name, days_ahead=days_ahead)

    db = SessionLocal()
    try:
        service = AssetMaintenanceService(db)
        assets = service.get_expiring_warranties(days_ahead=days_ahead)

        if not assets:
            logger.info(
                "task_completed",
                task=task_name,
                message="No warranties expiring soon",
                count=0,
            )
            return {
                "status": "success",
                "task": task_name,
                "alerts_sent": 0,
            }

        today = date.today()
        for asset in assets:
            days_remaining = (asset.warranty_expiry_date - today).days
            logger.info(
                "warranty_expiry_alert",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                warranty_expiry_date=asset.warranty_expiry_date.isoformat(),
                days_remaining=days_remaining,
                supplier=asset.supplier,
            )

        # TODO: Integrate with notification service to send actual alerts
        # notification_service.send_warranty_alerts(assets)

        logger.info(
            "task_completed",
            task=task_name,
            alerts_sent=len(assets),
        )

        return {
            "status": "success",
            "task": task_name,
            "alerts_sent": len(assets),
            "asset_ids": [a.id for a in assets],
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "failed", "task": task_name, "error": str(e)}
    finally:
        db.close()


@celery_app.task
def send_insurance_expiry_alerts(days_ahead: int = 30):
    """Send alerts for assets with expiring insurance.

    This task should be run daily to notify about insurance policies
    that will expire within the specified number of days.

    Args:
        days_ahead: Number of days to look ahead for expiring insurance.
    """
    task_name = "send_insurance_expiry_alerts"
    logger.info("task_started", task=task_name, days_ahead=days_ahead)

    db = SessionLocal()
    try:
        service = AssetMaintenanceService(db)
        assets = service.get_expiring_insurance(days_ahead=days_ahead)

        if not assets:
            logger.info(
                "task_completed",
                task=task_name,
                message="No insurance expiring soon",
                count=0,
            )
            return {
                "status": "success",
                "task": task_name,
                "alerts_sent": 0,
            }

        today = date.today()
        for asset in assets:
            days_remaining = (asset.insurance_end_date - today).days
            logger.info(
                "insurance_expiry_alert",
                asset_id=asset.id,
                asset_name=asset.asset_name,
                insurance_end_date=asset.insurance_end_date.isoformat(),
                days_remaining=days_remaining,
                insured_value=float(asset.insured_value),
                comprehensive_insurance=asset.comprehensive_insurance,
            )

        # TODO: Integrate with notification service to send actual alerts
        # notification_service.send_insurance_alerts(assets)

        logger.info(
            "task_completed",
            task=task_name,
            alerts_sent=len(assets),
        )

        return {
            "status": "success",
            "task": task_name,
            "alerts_sent": len(assets),
            "asset_ids": [a.id for a in assets],
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "failed", "task": task_name, "error": str(e)}
    finally:
        db.close()


@celery_app.task
def generate_asset_alert_summary():
    """Generate a summary of all asset alerts.

    This task provides an overview of maintenance, warranty,
    and insurance alerts. Useful for daily digest emails.
    """
    task_name = "generate_asset_alert_summary"
    logger.info("task_started", task=task_name)

    db = SessionLocal()
    try:
        service = AssetMaintenanceService(db)
        summary = service.get_alert_summary(days_ahead=30)

        logger.info(
            "task_completed",
            task=task_name,
            **summary,
        )

        return {
            "status": "success",
            "task": task_name,
            "summary": summary,
        }

    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "failed", "task": task_name, "error": str(e)}
    finally:
        db.close()

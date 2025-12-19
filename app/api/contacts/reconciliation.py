"""
Contacts Reconciliation Dashboard Endpoints

Provides API endpoints for viewing reconciliation status,
drift reports, and triggering manual reconciliation runs.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth import Require
from app.feature_flags import feature_flags

router = APIRouter()


@router.get(
    "/drift-summary",
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_drift_summary(db: Session = Depends(get_db)):
    """
    Get a quick summary of current drift status.

    Returns counts of unified contacts, linked customers, and orphans.
    This is a lightweight check suitable for health dashboards.
    """
    from app.services.contacts_reconciliation import ContactsReconciliationService

    service = ContactsReconciliationService(db)
    summary = service.get_drift_summary()

    return {
        "status": "ok",
        "data": summary,
    }


@router.get(
    "/status",
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_reconciliation_status(db: Session = Depends(get_db)):
    """
    Get the current reconciliation status and feature flag states.
    """
    from sqlalchemy import select, func
    from app.models.outbound_sync import OutboundSyncLog, SyncStatus
    from app.models.unified_contact import UnifiedContact, ContactType

    # Get sync log stats
    pending_syncs = db.execute(
        select(func.count(OutboundSyncLog.id)).where(
            OutboundSyncLog.status == SyncStatus.PENDING.value
        )
    ).scalar() or 0

    failed_syncs = db.execute(
        select(func.count(OutboundSyncLog.id)).where(
            OutboundSyncLog.status == SyncStatus.FAILED.value
        )
    ).scalar() or 0

    from sqlalchemy import text

    successful_syncs_24h = db.execute(
        select(func.count(OutboundSyncLog.id)).where(
            OutboundSyncLog.status == SyncStatus.SUCCESS.value,
            OutboundSyncLog.completed_at >= func.now() - func.cast(text("interval '24 hours'"), func.interval())
        )
    ).scalar() or 0

    # Get contact counts
    total_contacts = db.execute(
        select(func.count(UnifiedContact.id))
    ).scalar() or 0

    customer_contacts = db.execute(
        select(func.count(UnifiedContact.id)).where(
            UnifiedContact.contact_type.in_([ContactType.CUSTOMER, ContactType.CHURNED])
        )
    ).scalar() or 0

    return {
        "status": "ok",
        "feature_flags": {
            "dual_write_enabled": feature_flags.CONTACTS_DUAL_WRITE_ENABLED,
            "outbound_sync_enabled": feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED,
            "reconciliation_enabled": feature_flags.CONTACTS_RECONCILIATION_ENABLED,
        },
        "sync_stats": {
            "pending": pending_syncs,
            "failed": failed_syncs,
            "successful_24h": successful_syncs_24h,
        },
        "contact_stats": {
            "total": total_contacts,
            "customers": customer_contacts,
        },
    }


@router.post(
    "/run",
    dependencies=[Depends(Require("contacts:write"))],
)
async def trigger_reconciliation(
    background_tasks: BackgroundTasks,
    sync: bool = False,
    db: Session = Depends(get_db)
):
    """
    Trigger a reconciliation run.

    Args:
        sync: If True, run synchronously and return results.
              If False (default), queue as background task.
    """
    if not feature_flags.CONTACTS_RECONCILIATION_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Reconciliation is disabled. Set FF_CONTACTS_RECONCILIATION_ENABLED=true"
        )

    if sync:
        # Run synchronously
        from app.services.contacts_reconciliation import ContactsReconciliationService

        service = ContactsReconciliationService(db)
        reports = service.run_full_reconciliation()

        return {
            "status": "completed",
            "reports": {
                system: report.to_dict()
                for system, report in reports.items()
            }
        }
    else:
        # Queue as Celery task
        from app.tasks.contacts_tasks import run_contacts_reconciliation

        task = run_contacts_reconciliation.delay()

        return {
            "status": "queued",
            "task_id": task.id,
            "message": "Reconciliation task queued. Check /api/contacts/reconciliation/task/{task_id} for results."
        }


@router.get(
    "/task/{task_id}",
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_reconciliation_task_status(task_id: str):
    """
    Get the status/result of a reconciliation task.
    """
    from app.worker import celery_app

    result = celery_app.AsyncResult(task_id)

    if result.ready():
        if result.successful():
            return {
                "status": "completed",
                "result": result.get(),
            }
        else:
            return {
                "status": "failed",
                "error": str(result.result),
            }
    else:
        return {
            "status": result.status.lower(),
            "message": "Task is still processing",
        }


@router.get(
    "/sync-log",
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_sync_log(
    status: Optional[str] = None,
    target_system: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get outbound sync log entries.

    Useful for debugging sync issues.
    """
    from sqlalchemy import select, desc
    from app.models.outbound_sync import OutboundSyncLog

    query = select(OutboundSyncLog)

    if status:
        query = query.where(OutboundSyncLog.status == status)
    if target_system:
        query = query.where(OutboundSyncLog.target_system == target_system)

    query = query.order_by(desc(OutboundSyncLog.created_at)).offset(offset).limit(limit)

    logs = db.execute(query).scalars().all()

    return {
        "status": "ok",
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "target_system": log.target_system,
                "operation": log.operation,
                "status": log.status,
                "external_id": log.external_id,
                "error_message": log.error_message,
                "retry_count": log.retry_count,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            }
            for log in logs
        ]
    }

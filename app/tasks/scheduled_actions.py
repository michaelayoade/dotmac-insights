"""Pre-built scheduled actions for common workflow scenarios.

These Celery tasks are designed to be scheduled for future execution
via the ScheduledTaskService. Each task includes logic to:
1. Execute the action
2. Update the scheduled_tasks tracking record
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from app.worker import celery_app
from app.database import SessionLocal

logger = structlog.get_logger(__name__)


def _update_scheduled_task_status(
    celery_task_id: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Update the scheduled_tasks record after execution."""
    try:
        from app.services.scheduled_task_service import ScheduledTaskService

        with SessionLocal() as db:
            service = ScheduledTaskService(db)
            service.mark_executed(
                celery_task_id=celery_task_id,
                result=result,
                error=error,
            )
            db.commit()
    except Exception as e:
        logger.warning(
            "failed_to_update_scheduled_task",
            celery_task_id=celery_task_id,
            error=str(e),
        )


@celery_app.task(
    name="scheduled.send_reminder",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_reminder(
    self,
    entity_type: str,
    entity_id: int,
    user_id: int,
    message: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a reminder notification to a user.

    Args:
        entity_type: Type of entity (lead, ticket, approval, etc.)
        entity_id: ID of the entity
        user_id: User to notify
        message: Reminder message
        title: Optional notification title

    Returns:
        Result summary
    """
    try:
        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationEventType

        with SessionLocal() as db:
            notification_service = NotificationService(db)

            # Create in-app notification
            notification_service.emit_event(
                event_type=NotificationEventType.CUSTOM,
                payload={
                    "title": title or f"Reminder: {entity_type.title()}",
                    "message": message,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "action_url": _get_entity_url(entity_type, entity_id),
                },
                entity_type=entity_type,
                entity_id=entity_id,
                user_ids=[user_id],
            )
            db.commit()

        result = {
            "status": "sent",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_id": user_id,
            "sent_at": datetime.utcnow().isoformat(),
        }

        _update_scheduled_task_status(self.request.id, result=result)
        logger.info("reminder_sent", **result)
        return result

    except Exception as e:
        error = str(e)
        _update_scheduled_task_status(self.request.id, error=error)
        logger.error("reminder_failed", error=error, exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    name="scheduled.auto_close_ticket",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def auto_close_ticket(
    self,
    ticket_id: int,
    reason: str = "Auto-closed due to inactivity",
) -> Dict[str, Any]:
    """
    Auto-close a ticket if no response within SLA.

    Args:
        ticket_id: Ticket ID to close
        reason: Reason for closure

    Returns:
        Result summary
    """
    try:
        from app.models.ticket import Ticket, TicketStatus

        with SessionLocal() as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

            if not ticket:
                result = {"status": "not_found", "ticket_id": ticket_id}
                _update_scheduled_task_status(self.request.id, result=result)
                return result

            # Only close if still open
            if ticket.status in [TicketStatus.OPEN, TicketStatus.ON_HOLD, TicketStatus.REPLIED]:
                ticket.status = TicketStatus.CLOSED
                ticket.resolution = reason
                ticket.resolution_date = datetime.utcnow()
                db.commit()

                result = {
                    "status": "closed",
                    "ticket_id": ticket_id,
                    "reason": reason,
                    "closed_at": datetime.utcnow().isoformat(),
                }
            else:
                result = {
                    "status": "already_resolved",
                    "ticket_id": ticket_id,
                    "current_status": ticket.status,
                }

        _update_scheduled_task_status(self.request.id, result=result)
        logger.info("auto_close_ticket_result", **result)
        return result

    except Exception as e:
        error = str(e)
        _update_scheduled_task_status(self.request.id, error=error)
        logger.error("auto_close_ticket_failed", ticket_id=ticket_id, error=error, exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    name="scheduled.escalate_approval",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def escalate_approval(
    self,
    doctype: str,
    document_id: int,
) -> Dict[str, Any]:
    """
    Escalate an approval if not acted upon within timeout.

    Args:
        doctype: Document type
        document_id: Document ID

    Returns:
        Result summary
    """
    try:
        from app.services.approval_engine import ApprovalEngine

        with SessionLocal() as db:
            engine = ApprovalEngine(db)

            # Check if still pending
            approval_status = engine.get_approval_status(doctype, document_id)

            if not approval_status:
                result = {
                    "status": "not_found",
                    "doctype": doctype,
                    "document_id": document_id,
                }
            elif approval_status.get("status") != "pending":
                result = {
                    "status": "already_resolved",
                    "doctype": doctype,
                    "document_id": document_id,
                    "current_status": approval_status.get("status"),
                }
            else:
                # Trigger escalation
                escalated = engine.check_and_escalate()
                result = {
                    "status": "escalated",
                    "doctype": doctype,
                    "document_id": document_id,
                    "escalated_at": datetime.utcnow().isoformat(),
                }

            db.commit()

        _update_scheduled_task_status(self.request.id, result=result)
        logger.info("escalate_approval_result", **result)
        return result

    except Exception as e:
        error = str(e)
        _update_scheduled_task_status(self.request.id, error=error)
        logger.error(
            "escalate_approval_failed",
            doctype=doctype,
            document_id=document_id,
            error=error,
            exc_info=True,
        )
        raise self.retry(exc=e)

@celery_app.task(
    name="scheduled.expire_workflow_task",
    bind=True,
    max_retries=1,
)
def expire_workflow_task(
    self,
    workflow_task_id: int,
) -> Dict[str, Any]:
    """
    Mark a workflow task as expired after its deadline.

    Args:
        workflow_task_id: WorkflowTask ID to expire

    Returns:
        Result summary
    """
    try:
        from app.models.workflow_task import WorkflowTask, WorkflowTaskStatus

        with SessionLocal() as db:
            task = db.query(WorkflowTask).filter(WorkflowTask.id == workflow_task_id).first()

            if not task:
                result = {"status": "not_found", "workflow_task_id": workflow_task_id}
            elif task.status != WorkflowTaskStatus.PENDING.value:
                result = {
                    "status": "already_resolved",
                    "workflow_task_id": workflow_task_id,
                    "current_status": task.status,
                }
            else:
                task.status = WorkflowTaskStatus.EXPIRED.value
                task.updated_at = datetime.utcnow()
                result = {
                    "status": "expired",
                    "workflow_task_id": workflow_task_id,
                    "expired_at": datetime.utcnow().isoformat(),
                }

            db.commit()

        _update_scheduled_task_status(self.request.id, result=result)
        logger.info("expire_workflow_task_result", **result)
        return result

    except Exception as e:
        error = str(e)
        _update_scheduled_task_status(self.request.id, error=error)
        logger.error(
            "expire_workflow_task_failed",
            workflow_task_id=workflow_task_id,
            error=error,
            exc_info=True,
        )
        raise


def _get_entity_url(entity_type: str, entity_id: int) -> str:
    """Generate URL for an entity."""
    url_map = {
        "ticket": f"/support/tickets/{entity_id}",
        "approval": f"/accounting/approvals/{entity_id}",
        "invoice": f"/sales/invoices/{entity_id}",
        "expense_claim": f"/expenses/claims/{entity_id}",
        "cash_advance": f"/expenses/advances/{entity_id}",
        "scorecard": f"/performance/reviews/{entity_id}",
        "conversation": f"/inbox/conversations/{entity_id}",
    }
    return url_map.get(entity_type, f"/{entity_type}/{entity_id}")

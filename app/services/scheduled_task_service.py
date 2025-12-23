"""Service for scheduling delayed Celery tasks with tracking."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog
from celery import Task as CeleryTask
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.scheduled_task import ScheduledTask, ScheduledTaskStatus
from app.worker import celery_app

logger = structlog.get_logger(__name__)


class ScheduledTaskService:
    """
    Service for scheduling delayed Celery tasks with database tracking.

    Provides:
    - Schedule tasks for future execution using Celery's eta parameter
    - Track scheduled tasks in database for visibility
    - Cancel pending scheduled tasks
    - Query scheduled tasks by source entity
    """

    def __init__(self, db: Session):
        self.db = db

    def schedule(
        self,
        task: CeleryTask,
        eta: datetime,
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        created_by_id: Optional[int] = None,
    ) -> ScheduledTask:
        """
        Schedule a Celery task for future execution with database tracking.

        Args:
            task: The Celery task to schedule
            eta: When the task should execute
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            source_type: Entity type this task relates to
            source_id: Entity ID this task relates to
            created_by_id: User who scheduled this task

        Returns:
            ScheduledTask record for tracking

        Example:
            from app.tasks.scheduled_actions import send_reminder
            from datetime import datetime, timedelta

            service = ScheduledTaskService(db)
            scheduled = service.schedule(
                task=send_reminder,
                eta=datetime.utcnow() + timedelta(days=3),
                kwargs={"entity_type": "lead", "entity_id": 123, "message": "Follow up"},
                source_type="lead",
                source_id=123,
                created_by_id=current_user.id,
            )
        """
        kwargs = kwargs or {}

        # Schedule the task with Celery
        result = task.apply_async(args=args, kwargs=kwargs, eta=eta)

        # Create tracking record
        scheduled_task = ScheduledTask(
            celery_task_id=result.id,
            task_name=task.name,
            scheduled_for=eta,
            status=ScheduledTaskStatus.SCHEDULED.value,
            source_type=source_type,
            source_id=source_id,
            payload={"args": list(args), "kwargs": kwargs},
            created_by_id=created_by_id,
        )

        self.db.add(scheduled_task)
        self.db.flush()

        logger.info(
            "task_scheduled",
            scheduled_task_id=scheduled_task.id,
            celery_task_id=result.id,
            task_name=task.name,
            eta=eta.isoformat(),
            source_type=source_type,
            source_id=source_id,
        )

        return scheduled_task

    def cancel(
        self,
        scheduled_task_id: int,
        cancelled_by_id: int,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Cancel a scheduled task.

        Uses Celery's revoke() to cancel the pending task.

        Args:
            scheduled_task_id: ID of the ScheduledTask to cancel
            cancelled_by_id: User who is cancelling
            reason: Optional reason for cancellation

        Returns:
            True if cancelled, False if not found or already executed
        """
        scheduled_task = (
            self.db.query(ScheduledTask)
            .filter(ScheduledTask.id == scheduled_task_id)
            .first()
        )

        if not scheduled_task:
            return False

        if scheduled_task.status != ScheduledTaskStatus.SCHEDULED.value:
            logger.warning(
                "cannot_cancel_task",
                scheduled_task_id=scheduled_task_id,
                current_status=scheduled_task.status,
            )
            return False

        # Revoke the Celery task
        try:
            celery_app.control.revoke(
                scheduled_task.celery_task_id,
                terminate=True,
                signal="SIGTERM",
            )
        except Exception as e:
            logger.warning(
                "celery_revoke_failed",
                celery_task_id=scheduled_task.celery_task_id,
                error=str(e),
            )
            # Continue to update status even if revoke fails

        # Update tracking record
        scheduled_task.status = ScheduledTaskStatus.CANCELLED.value
        scheduled_task.cancelled_at = datetime.utcnow()
        scheduled_task.cancelled_by_id = cancelled_by_id
        scheduled_task.cancellation_reason = reason

        logger.info(
            "task_cancelled",
            scheduled_task_id=scheduled_task_id,
            celery_task_id=scheduled_task.celery_task_id,
            cancelled_by_id=cancelled_by_id,
            reason=reason,
        )

        return True

    def cancel_for_source(
        self,
        source_type: str,
        source_id: int,
        cancelled_by_id: Optional[int] = None,
    ) -> int:
        """
        Cancel all pending scheduled tasks for a given source entity.

        Args:
            source_type: Entity type
            source_id: Entity ID
            cancelled_by_id: User who is cancelling (optional)

        Returns:
            Number of tasks cancelled
        """
        pending_tasks = (
            self.db.query(ScheduledTask)
            .filter(
                ScheduledTask.source_type == source_type,
                ScheduledTask.source_id == source_id,
                ScheduledTask.status == ScheduledTaskStatus.SCHEDULED.value,
            )
            .all()
        )

        cancelled_count = 0
        for task in pending_tasks:
            # Revoke Celery task
            try:
                celery_app.control.revoke(
                    task.celery_task_id,
                    terminate=True,
                    signal="SIGTERM",
                )
            except Exception as e:
                logger.warning(
                    "celery_revoke_failed",
                    celery_task_id=task.celery_task_id,
                    error=str(e),
                )

            # Update record
            task.status = ScheduledTaskStatus.CANCELLED.value
            task.cancelled_at = datetime.utcnow()
            task.cancelled_by_id = cancelled_by_id
            task.cancellation_reason = f"Source entity {source_type}:{source_id} cancelled"
            cancelled_count += 1

        if cancelled_count > 0:
            logger.info(
                "tasks_cancelled_for_source",
                source_type=source_type,
                source_id=source_id,
                count=cancelled_count,
            )

        return cancelled_count

    def get_pending_for_source(
        self,
        source_type: str,
        source_id: int,
        created_by_id: Optional[int] = None,
    ) -> List[ScheduledTask]:
        """Get all pending scheduled tasks for a source entity."""
        query = (
            self.db.query(ScheduledTask)
            .filter(
                ScheduledTask.source_type == source_type,
                ScheduledTask.source_id == source_id,
                ScheduledTask.status == ScheduledTaskStatus.SCHEDULED.value,
            )
        )
        if created_by_id is not None:
            query = query.filter(ScheduledTask.created_by_id == created_by_id)
        return query.order_by(ScheduledTask.scheduled_for.asc()).all()

    def get_by_id(self, scheduled_task_id: int) -> Optional[ScheduledTask]:
        """Get a scheduled task by ID."""
        return (
            self.db.query(ScheduledTask)
            .filter(ScheduledTask.id == scheduled_task_id)
            .first()
        )

    def get_by_celery_id(self, celery_task_id: str) -> Optional[ScheduledTask]:
        """Get a scheduled task by Celery task ID."""
        return (
            self.db.query(ScheduledTask)
            .filter(ScheduledTask.celery_task_id == celery_task_id)
            .first()
        )

    def mark_executed(
        self,
        celery_task_id: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[ScheduledTask]:
        """
        Mark a scheduled task as executed.

        Called by task wrappers after execution completes.

        Args:
            celery_task_id: The Celery task ID
            result: Task result (if successful)
            error: Error message (if failed)

        Returns:
            Updated ScheduledTask or None if not found
        """
        scheduled_task = self.get_by_celery_id(celery_task_id)
        if not scheduled_task:
            return None

        scheduled_task.executed_at = datetime.utcnow()

        if error:
            scheduled_task.status = ScheduledTaskStatus.FAILED.value
            scheduled_task.error = error
        else:
            scheduled_task.status = ScheduledTaskStatus.EXECUTED.value
            scheduled_task.result = result

        logger.info(
            "scheduled_task_executed",
            scheduled_task_id=scheduled_task.id,
            celery_task_id=celery_task_id,
            status=scheduled_task.status,
        )

        return scheduled_task

    def list_scheduled(
        self,
        status: Optional[str] = None,
        task_name: Optional[str] = None,
        source_type: Optional[str] = None,
        created_by_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ScheduledTask]:
        """
        List scheduled tasks with optional filters.

        Args:
            status: Filter by status
            task_name: Filter by task name
            source_type: Filter by source type
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of ScheduledTask objects
        """
        query = self.db.query(ScheduledTask)

        if status:
            query = query.filter(ScheduledTask.status == status)

        if task_name:
            query = query.filter(ScheduledTask.task_name == task_name)

        if source_type:
            query = query.filter(ScheduledTask.source_type == source_type)

        if created_by_id is not None:
            query = query.filter(ScheduledTask.created_by_id == created_by_id)

        return (
            query.order_by(ScheduledTask.scheduled_for.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

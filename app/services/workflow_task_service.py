"""Service for managing unified workflow tasks."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models.workflow_task import (
    WorkflowTask,
    WorkflowTaskStatus,
    WorkflowTaskPriority,
    WorkflowTaskModule,
)

logger = structlog.get_logger(__name__)


class WorkflowTaskService:
    """
    Service for managing unified workflow tasks.

    Provides CRUD operations and queries for the workflow_tasks table,
    which aggregates human action items from all modules.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_task(
        self,
        source_type: str,
        source_id: int,
        title: str,
        module: str,
        assignee_user_id: Optional[int] = None,
        assignee_employee_id: Optional[int] = None,
        assignee_team_id: Optional[int] = None,
        assigned_by_id: Optional[int] = None,
        description: Optional[str] = None,
        action_url: Optional[str] = None,
        priority: str = "medium",
        due_at: Optional[datetime] = None,
        company: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowTask:
        """
        Create a new workflow task.

        Args:
            source_type: Type of source entity (approval, ticket, etc.)
            source_id: ID of the source entity
            title: Task title
            module: Module that owns this task
            assignee_user_id: User assigned to this task
            assignee_employee_id: Employee assigned to this task
            assignee_team_id: Team assigned to this task
            assigned_by_id: User who assigned this task
            description: Optional task description
            action_url: URL to take action on this task
            priority: Task priority (low, medium, high, urgent)
            due_at: When the task is due
            company: Company context
            metadata: Additional context data

        Returns:
            Created WorkflowTask
        """
        # Check for existing task with same source and assignee
        existing = self.get_task_for_source(
            source_type=source_type,
            source_id=source_id,
            assignee_user_id=assignee_user_id,
        )
        if existing and existing.status == WorkflowTaskStatus.PENDING.value:
            logger.debug(
                "task_already_exists",
                source_type=source_type,
                source_id=source_id,
                task_id=existing.id,
            )
            return existing

        task = WorkflowTask(
            source_type=source_type,
            source_id=source_id,
            title=title,
            description=description,
            action_url=action_url,
            assignee_user_id=assignee_user_id,
            assignee_employee_id=assignee_employee_id,
            assignee_team_id=assignee_team_id,
            assigned_by_id=assigned_by_id,
            priority=priority,
            due_at=due_at,
            module=module,
            company=company,
            task_metadata=metadata,
        )

        self.db.add(task)
        self.db.flush()

        logger.info(
            "workflow_task_created",
            task_id=task.id,
            source_type=source_type,
            source_id=source_id,
            assignee_user_id=assignee_user_id,
            module=module,
        )

        return task

    def complete_task(
        self,
        source_type: str,
        source_id: int,
        completed_by_id: int,
        assignee_user_id: Optional[int] = None,
    ) -> Optional[WorkflowTask]:
        """
        Mark a task as completed when its source is actioned.

        Args:
            source_type: Type of source entity
            source_id: ID of the source entity
            completed_by_id: User who completed the task
            assignee_user_id: If specified, only complete task for this user

        Returns:
            Updated WorkflowTask or None if not found
        """
        query = self.db.query(WorkflowTask).filter(
            WorkflowTask.source_type == source_type,
            WorkflowTask.source_id == source_id,
            WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
        )

        if assignee_user_id:
            query = query.filter(WorkflowTask.assignee_user_id == assignee_user_id)

        task = query.first()
        if not task:
            return None

        task.status = WorkflowTaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        task.completed_by_id = completed_by_id

        logger.info(
            "workflow_task_completed",
            task_id=task.id,
            source_type=source_type,
            source_id=source_id,
            completed_by_id=completed_by_id,
        )

        return task

    def cancel_tasks_for_source(
        self,
        source_type: str,
        source_id: int,
    ) -> int:
        """
        Cancel all pending tasks for a source entity.

        Called when the source is deleted, rejected, or otherwise invalidated.

        Args:
            source_type: Type of source entity
            source_id: ID of the source entity

        Returns:
            Number of tasks cancelled
        """
        count = (
            self.db.query(WorkflowTask)
            .filter(
                WorkflowTask.source_type == source_type,
                WorkflowTask.source_id == source_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            )
            .update(
                {
                    "status": WorkflowTaskStatus.CANCELLED.value,
                    "updated_at": datetime.utcnow(),
                }
            )
        )

        if count > 0:
            logger.info(
                "workflow_tasks_cancelled",
                source_type=source_type,
                source_id=source_id,
                count=count,
            )

        return count

    def get_task_for_source(
        self,
        source_type: str,
        source_id: int,
        assignee_user_id: Optional[int] = None,
    ) -> Optional[WorkflowTask]:
        """Get a task by source reference."""
        query = self.db.query(WorkflowTask).filter(
            WorkflowTask.source_type == source_type,
            WorkflowTask.source_id == source_id,
        )
        if assignee_user_id:
            query = query.filter(WorkflowTask.assignee_user_id == assignee_user_id)
        return query.first()

    def get_my_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        module: Optional[str] = None,
        priority: Optional[str] = None,
        overdue_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowTask]:
        """
        Get tasks assigned to a user.

        Args:
            user_id: User ID to get tasks for
            status: Filter by status
            module: Filter by module
            priority: Filter by priority
            overdue_only: Only return overdue tasks
            limit: Maximum number of tasks to return
            offset: Offset for pagination

        Returns:
            List of WorkflowTask objects
        """
        query = self._apply_task_filters(
            self.db.query(WorkflowTask),
            user_id=user_id,
            status=status,
            module=module,
            priority=priority,
            overdue_only=overdue_only,
        )

        # Order by: urgent first, then by due date (soonest first), then by created
        query = query.order_by(
            # Priority order: urgent=1, high=2, medium=3, low=4
            case(
                (WorkflowTask.priority == "urgent", 1),
                (WorkflowTask.priority == "high", 2),
                (WorkflowTask.priority == "medium", 3),
                else_=4,
            ),
            WorkflowTask.due_at.asc().nullslast(),
            WorkflowTask.created_at.desc(),
        )

        return query.offset(offset).limit(limit).all()

    def count_my_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        module: Optional[str] = None,
        priority: Optional[str] = None,
        overdue_only: bool = False,
    ) -> int:
        """Count tasks assigned to a user with optional filters."""
        query = self._apply_task_filters(
            self.db.query(func.count(WorkflowTask.id)),
            user_id=user_id,
            status=status,
            module=module,
            priority=priority,
            overdue_only=overdue_only,
        )
        return int(query.scalar() or 0)

    def _apply_task_filters(
        self,
        query,
        user_id: int,
        status: Optional[str] = None,
        module: Optional[str] = None,
        priority: Optional[str] = None,
        overdue_only: bool = False,
    ):
        query = query.filter(WorkflowTask.assignee_user_id == user_id)

        if status:
            query = query.filter(WorkflowTask.status == status)
        else:
            query = query.filter(
                WorkflowTask.status.in_([
                    WorkflowTaskStatus.PENDING.value,
                    WorkflowTaskStatus.IN_PROGRESS.value,
                ])
            )

        if module:
            query = query.filter(WorkflowTask.module == module)

        if priority:
            query = query.filter(WorkflowTask.priority == priority)

        if overdue_only:
            query = query.filter(
                WorkflowTask.due_at.isnot(None),
                WorkflowTask.due_at < datetime.utcnow(),
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            )

        return query

    def get_task_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get task counts by module and status for a user.

        Returns:
            Dictionary with counts by status and module
        """
        now = datetime.utcnow()

        # Total pending
        pending_count = (
            self.db.query(func.count(WorkflowTask.id))
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            )
            .scalar()
            or 0
        )

        # Overdue
        overdue_count = (
            self.db.query(func.count(WorkflowTask.id))
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
                WorkflowTask.due_at.isnot(None),
                WorkflowTask.due_at < now,
            )
            .scalar()
            or 0
        )

        # Due today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        due_today_count = (
            self.db.query(func.count(WorkflowTask.id))
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
                WorkflowTask.due_at.between(today_start, today_end),
            )
            .scalar()
            or 0
        )

        # Completed today
        completed_today_count = (
            self.db.query(func.count(WorkflowTask.id))
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.COMPLETED.value,
                WorkflowTask.completed_at.between(today_start, today_end),
            )
            .scalar()
            or 0
        )

        # By module
        by_module = (
            self.db.query(
                WorkflowTask.module,
                func.count(WorkflowTask.id).label("count"),
            )
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            )
            .group_by(WorkflowTask.module)
            .all()
        )

        # By priority
        by_priority = (
            self.db.query(
                WorkflowTask.priority,
                func.count(WorkflowTask.id).label("count"),
            )
            .filter(
                WorkflowTask.assignee_user_id == user_id,
                WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            )
            .group_by(WorkflowTask.priority)
            .all()
        )

        return {
            "pending": pending_count,
            "overdue": overdue_count,
            "due_today": due_today_count,
            "completed_today": completed_today_count,
            "by_module": {m: c for m, c in by_module},
            "by_priority": {p: c for p, c in by_priority},
        }

    def get_overdue_tasks(
        self,
        user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[WorkflowTask]:
        """Get all overdue tasks, optionally filtered by user."""
        query = self.db.query(WorkflowTask).filter(
            WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
            WorkflowTask.due_at.isnot(None),
            WorkflowTask.due_at < datetime.utcnow(),
        )

        if user_id:
            query = query.filter(WorkflowTask.assignee_user_id == user_id)

        return query.order_by(WorkflowTask.due_at.asc()).limit(limit).all()

    def update_task_status(
        self,
        task_id: int,
        status: str,
        user_id: int,
    ) -> Optional[WorkflowTask]:
        """Update task status."""
        task = self.db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            return None

        old_status = task.status
        task.status = status
        task.updated_at = datetime.utcnow()

        if status == WorkflowTaskStatus.COMPLETED.value:
            task.completed_at = datetime.utcnow()
            task.completed_by_id = user_id

        logger.info(
            "workflow_task_status_updated",
            task_id=task_id,
            old_status=old_status,
            new_status=status,
            user_id=user_id,
        )

        return task

    def snooze_task(
        self,
        task_id: int,
        new_due_at: datetime,
        user_id: int,
    ) -> Optional[WorkflowTask]:
        """Reschedule a task's due date."""
        task = self.db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            return None

        old_due = task.due_at
        task.due_at = new_due_at
        task.updated_at = datetime.utcnow()

        logger.info(
            "workflow_task_snoozed",
            task_id=task_id,
            old_due=old_due.isoformat() if old_due else None,
            new_due=new_due_at.isoformat(),
            user_id=user_id,
        )

        return task

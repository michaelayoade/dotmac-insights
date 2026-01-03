"""Milestone service for project milestones.

This service handles:
- CRUD operations for milestones
- Status transitions with validation
- Task assignment to milestones
- Progress calculations
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.project import (
    Project,
    Milestone,
    MilestoneStatus,
    ProjectActivityType,
)
from app.models.task import Task, TaskStatus

from .activities import ActivityService
from .errors import (
    MilestoneNotFoundError,
    MilestoneStatusError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from .milestone_types import (
    MilestoneFilters,
    MilestoneCreateData,
    MilestoneUpdateData,
    MilestoneProgress,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["MilestoneService"]

# Valid status transitions
VALID_MILESTONE_TRANSITIONS = {
    MilestoneStatus.PLANNED: {
        MilestoneStatus.IN_PROGRESS,
        MilestoneStatus.ON_HOLD,
    },
    MilestoneStatus.IN_PROGRESS: {
        MilestoneStatus.COMPLETED,
        MilestoneStatus.ON_HOLD,
    },
    MilestoneStatus.ON_HOLD: {
        MilestoneStatus.PLANNED,
        MilestoneStatus.IN_PROGRESS,
    },
    MilestoneStatus.COMPLETED: set(),  # Cannot transition from completed
}


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """Convert value to Decimal with default fallback."""
    return Decimal(str(val)) if val is not None else default


class MilestoneService:
    """Service for managing project milestones.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        self._activity_service: Optional[ActivityService] = None

    @property
    def activity_service(self) -> ActivityService:
        """Get activity service (lazy loaded)."""
        if self._activity_service is None:
            self._activity_service = ActivityService(self.db, self.principal)
        return self._activity_service

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def list_project_milestones(
        self,
        project_id: int,
        filters: Optional[MilestoneFilters] = None,
    ) -> List[Milestone]:
        """List milestones for a project.

        Args:
            project_id: ID of the project
            filters: Optional filters

        Returns:
            List of milestones

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        # Verify project exists
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id, Project.is_deleted == False)
            .first()
        )
        if not project:
            raise ProjectNotFoundError(project_id)

        if filters is None:
            filters = MilestoneFilters()

        query = self.db.query(Milestone).filter(
            Milestone.project_id == project_id,
            Milestone.is_deleted == False,
        )

        # Apply filters
        if filters.status:
            query = query.filter(Milestone.status == filters.status)

        if filters.overdue_only:
            today = date.today()
            query = query.filter(
                Milestone.planned_end_date < today,
                Milestone.status.notin_([MilestoneStatus.COMPLETED]),
            )

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(Milestone.name.ilike(search_term))

        # Apply sorting
        sort_column = getattr(Milestone, filters.sort_by, Milestone.idx)
        if filters.sort_dir == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc(), Milestone.planned_end_date.asc())

        return query.all()

    def get_milestone(self, milestone_id: int) -> Milestone:
        """Get a milestone by ID.

        Args:
            milestone_id: ID of the milestone

        Returns:
            The milestone

        Raises:
            MilestoneNotFoundError: If milestone does not exist
        """
        milestone = (
            self.db.query(Milestone)
            .filter(
                Milestone.id == milestone_id,
                Milestone.is_deleted == False,
            )
            .first()
        )
        if not milestone:
            raise MilestoneNotFoundError(milestone_id)
        return milestone

    def get_milestone_with_tasks(
        self,
        milestone_id: int,
    ) -> Tuple[Milestone, List[Task]]:
        """Get a milestone with its associated tasks.

        Args:
            milestone_id: ID of the milestone

        Returns:
            Tuple of (milestone, tasks)

        Raises:
            MilestoneNotFoundError: If milestone does not exist
        """
        milestone = self.get_milestone(milestone_id)
        tasks = list(milestone.tasks) if milestone.tasks else []
        return milestone, tasks

    def calculate_progress(self, milestone_id: int) -> MilestoneProgress:
        """Calculate progress for a milestone based on its tasks.

        Args:
            milestone_id: ID of the milestone

        Returns:
            MilestoneProgress with task counts and completion percentage

        Raises:
            MilestoneNotFoundError: If milestone does not exist
        """
        milestone = self.get_milestone(milestone_id)

        tasks = milestone.tasks if milestone.tasks else []
        total_tasks = len(tasks)
        completed_tasks = sum(
            1 for t in tasks if t.status == TaskStatus.COMPLETED
        )

        if total_tasks > 0:
            percent_complete = Decimal(completed_tasks) / Decimal(total_tasks) * 100
        else:
            percent_complete = Decimal("0")

        return MilestoneProgress(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            percent_complete=percent_complete.quantize(Decimal("0.01")),
        )

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_milestone(self, data: MilestoneCreateData) -> Milestone:
        """Create a new milestone.

        Args:
            data: Milestone creation data

        Returns:
            The created milestone (not yet committed)

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        # Verify project exists
        project = (
            self.db.query(Project)
            .filter(Project.id == data.project_id, Project.is_deleted == False)
            .first()
        )
        if not project:
            raise ProjectNotFoundError(data.project_id)

        # Calculate idx if not provided
        idx = data.idx
        if idx is None:
            max_idx = (
                self.db.query(func.max(Milestone.idx))
                .filter(
                    Milestone.project_id == data.project_id,
                    Milestone.is_deleted == False,
                )
                .scalar()
                or 0
            )
            idx = max_idx + 1

        # Get creator ID from principal
        created_by_id = self.principal.id if self.principal else None

        milestone = Milestone(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            status=data.status,
            planned_start_date=data.planned_start_date,
            planned_end_date=data.planned_end_date,
            actual_start_date=data.actual_start_date,
            actual_end_date=data.actual_end_date,
            percent_complete=_decimal_or_default(data.percent_complete),
            idx=idx,
            company=data.company or project.company,
            created_by_id=created_by_id,
        )

        self.db.add(milestone)
        self.db.flush()

        # Log activity
        self.activity_service.log_created(
            entity_type="milestone",
            entity_id=milestone.id,
            entity_name=milestone.name,
            company=milestone.company,
        )

        return milestone

    def update_milestone(
        self,
        milestone_id: int,
        data: MilestoneUpdateData,
    ) -> Milestone:
        """Update a milestone.

        Args:
            milestone_id: ID of the milestone to update
            data: Milestone update data

        Returns:
            The updated milestone (not yet committed)

        Raises:
            MilestoneNotFoundError: If milestone does not exist
        """
        milestone = self.get_milestone(milestone_id)
        changed_fields = []

        if data.name is not None and data.name != milestone.name:
            milestone.name = data.name
            changed_fields.append("name")

        if data.description is not None and data.description != milestone.description:
            milestone.description = data.description
            changed_fields.append("description")

        if data.status is not None and data.status != milestone.status:
            old_status = milestone.status
            milestone.status = data.status
            changed_fields.append("status")

            # If completed, set actual_end_date if not set
            if data.status == MilestoneStatus.COMPLETED and not milestone.actual_end_date:
                milestone.actual_end_date = date.today()
                changed_fields.append("actual_end_date")

            # Log status change
            self.activity_service.log_status_change(
                entity_type="milestone",
                entity_id=milestone.id,
                old_status=old_status.value,
                new_status=data.status.value,
                company=milestone.company,
            )

            # If completed, log milestone completed on project
            if data.status == MilestoneStatus.COMPLETED:
                from .activity_types import ActivityCreateData

                self.activity_service.log_activity(
                    ActivityCreateData(
                        entity_type="project",
                        entity_id=milestone.project_id,
                        activity_type=ProjectActivityType.MILESTONE_COMPLETED,
                        description=f"Milestone '{milestone.name}' completed",
                        company=milestone.company,
                    )
                )

        if data.planned_start_date is not None:
            milestone.planned_start_date = data.planned_start_date
            changed_fields.append("planned_start_date")

        if data.planned_end_date is not None:
            milestone.planned_end_date = data.planned_end_date
            changed_fields.append("planned_end_date")

        if data.actual_start_date is not None:
            milestone.actual_start_date = data.actual_start_date
            changed_fields.append("actual_start_date")

        if data.actual_end_date is not None:
            milestone.actual_end_date = data.actual_end_date
            changed_fields.append("actual_end_date")

        if data.percent_complete is not None:
            milestone.percent_complete = _decimal_or_default(data.percent_complete)
            changed_fields.append("percent_complete")

        if data.idx is not None:
            milestone.idx = data.idx
            changed_fields.append("idx")

        # Log update if fields changed (excluding status which is logged separately)
        non_status_changes = [f for f in changed_fields if f != "status"]
        if non_status_changes:
            self.activity_service.log_updated(
                entity_type="milestone",
                entity_id=milestone.id,
                changed_fields=non_status_changes,
                company=milestone.company,
            )

        return milestone

    def delete_milestone(self, milestone_id: int) -> None:
        """Soft-delete a milestone.

        Args:
            milestone_id: ID of the milestone to delete

        Raises:
            MilestoneNotFoundError: If milestone does not exist
        """
        milestone = self.get_milestone(milestone_id)

        milestone.is_deleted = True
        milestone.deleted_at = datetime.now(timezone.utc)
        if self.principal:
            milestone.deleted_by_id = self.principal.id

    def transition_status(
        self,
        milestone_id: int,
        new_status: MilestoneStatus,
    ) -> Milestone:
        """Transition milestone to a new status with validation.

        Args:
            milestone_id: ID of the milestone
            new_status: Target status

        Returns:
            The updated milestone

        Raises:
            MilestoneNotFoundError: If milestone does not exist
            MilestoneStatusError: If transition is not allowed
        """
        milestone = self.get_milestone(milestone_id)

        # Validate transition
        allowed = VALID_MILESTONE_TRANSITIONS.get(milestone.status, set())
        if new_status not in allowed:
            raise MilestoneStatusError(
                current_status=milestone.status.value,
                target_status=new_status.value,
            )

        return self.update_milestone(
            milestone_id,
            MilestoneUpdateData(status=new_status),
        )

    # -------------------------------------------------------------------------
    # Task Assignment Methods
    # -------------------------------------------------------------------------

    def assign_task(
        self,
        task_id: int,
        milestone_id: Optional[int],
    ) -> Task:
        """Assign or unassign a task to a milestone.

        Args:
            task_id: ID of the task
            milestone_id: ID of the milestone to assign, or None to unassign

        Returns:
            The updated task

        Raises:
            TaskNotFoundError: If task does not exist
            MilestoneNotFoundError: If milestone does not exist
            ValidationError: If task and milestone belong to different projects
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)

        if milestone_id is not None:
            milestone = self.get_milestone(milestone_id)

            # Verify task and milestone belong to same project
            if task.project_id != milestone.project_id:
                from app.services.errors import ValidationError

                raise ValidationError(
                    "Task and milestone must belong to the same project"
                )

        task.milestone_id = milestone_id

        return task

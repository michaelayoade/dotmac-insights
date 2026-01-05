"""Activity service for project audit trail.

This service handles:
- Logging activity events for projects, tasks, and milestones
- Querying activity feeds for entities
- Building project timelines
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, or_, false
from sqlalchemy.orm import Session

from app.models.project import Project, Milestone, ProjectActivity, ProjectActivityType
from app.models.task import Task
from app.services.types import PaginatedResult, PaginationParams

from .activity_types import ActivityFilters, ActivityCreateData
from .errors import InvalidEntityTypeError, ProjectNotFoundError

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ActivityService"]

VALID_ENTITY_TYPES = {"project", "task", "milestone"}


class ActivityService:
    """Service for managing project activity audit trail.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def list_entity_activities(
        self,
        entity_type: str,
        entity_id: int,
        filters: Optional[ActivityFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ProjectActivity]:
        """List activity feed for an entity.

        Args:
            entity_type: Type of entity ('project', 'task', 'milestone')
            entity_id: ID of the entity
            filters: Optional filters for the query
            pagination: Optional pagination parameters

        Returns:
            Paginated list of activities

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(entity_type, list(VALID_ENTITY_TYPES))

        if filters is None:
            filters = ActivityFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ProjectActivity).filter(
            ProjectActivity.entity_type == entity_type,
            ProjectActivity.entity_id == entity_id,
        )

        # Apply filters
        if filters.activity_type:
            query = query.filter(ProjectActivity.activity_type == filters.activity_type)
        if filters.actor_id:
            query = query.filter(ProjectActivity.actor_id == filters.actor_id)
        if filters.start_date:
            query = query.filter(ProjectActivity.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(ProjectActivity.created_at <= filters.end_date)

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(ProjectActivity, filters.sort_by, ProjectActivity.created_at)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        activities = query.offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(
            items=activities,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_project_timeline(
        self,
        project_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProjectActivity]:
        """Get combined activity timeline for a project including its tasks and milestones.

        Args:
            project_id: ID of the project
            limit: Maximum number of activities to return

        Returns:
            List of activities ordered by creation time (newest first)

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

        # Get task and milestone IDs for this project
        task_ids = [t.id for t in project.tasks]
        milestone_ids = [m.id for m in project.milestones if not m.is_deleted]

        # Build combined query for all activities
        task_clause = (
            and_(
                ProjectActivity.entity_type == "task",
                ProjectActivity.entity_id.in_(task_ids),
            )
            if task_ids
            else false()
        )
        milestone_clause = (
            and_(
                ProjectActivity.entity_type == "milestone",
                ProjectActivity.entity_id.in_(milestone_ids),
            )
            if milestone_ids
            else false()
        )

        query = self.db.query(ProjectActivity).filter(
            or_(
                and_(
                    ProjectActivity.entity_type == "project",
                    ProjectActivity.entity_id == project_id,
                ),
                task_clause,
                milestone_clause,
            )
        )

        activities = (
            query.order_by(ProjectActivity.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return activities

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def log_activity(self, data: ActivityCreateData) -> ProjectActivity:
        """Log an activity event.

        Args:
            data: Activity data to log

        Returns:
            The created activity record (not yet committed)

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
        """
        if data.entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(data.entity_type, list(VALID_ENTITY_TYPES))

        # Get actor info from principal if available
        actor_id = None
        actor_name = None
        actor_email = None
        if self.principal:
            actor_id = self.principal.id
            actor_name = getattr(self.principal, "name", None) or getattr(
                self.principal, "email", None
            )
            actor_email = getattr(self.principal, "email", None)

        activity = ProjectActivity(
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            activity_type=data.activity_type,
            description=data.description,
            from_value=data.from_value,
            to_value=data.to_value,
            changed_fields=data.changed_fields,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_email=actor_email,
            company=data.company,
        )
        self.db.add(activity)
        self.db.flush()

        return activity

    # -------------------------------------------------------------------------
    # Helper Methods for Status Changes
    # -------------------------------------------------------------------------

    def log_status_change(
        self,
        entity_type: str,
        entity_id: int,
        old_status: str,
        new_status: str,
        company: Optional[str] = None,
    ) -> ProjectActivity:
        """Log a status change activity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            old_status: Previous status value
            new_status: New status value
            company: Optional company code

        Returns:
            The created activity record
        """
        return self.log_activity(
            ActivityCreateData(
                entity_type=entity_type,
                entity_id=entity_id,
                activity_type=ProjectActivityType.STATUS_CHANGED,
                description=f"Status changed from '{old_status}' to '{new_status}'",
                from_value=old_status,
                to_value=new_status,
                changed_fields=["status"],
                company=company,
            )
        )

    def log_created(
        self,
        entity_type: str,
        entity_id: int,
        entity_name: str,
        company: Optional[str] = None,
    ) -> ProjectActivity:
        """Log an entity creation activity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            entity_name: Name of the entity for description
            company: Optional company code

        Returns:
            The created activity record
        """
        return self.log_activity(
            ActivityCreateData(
                entity_type=entity_type,
                entity_id=entity_id,
                activity_type=ProjectActivityType.CREATED,
                description=f"{entity_type.capitalize()} '{entity_name}' created",
                company=company,
            )
        )

    def log_updated(
        self,
        entity_type: str,
        entity_id: int,
        changed_fields: List[str],
        company: Optional[str] = None,
    ) -> ProjectActivity:
        """Log an entity update activity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            changed_fields: List of field names that were changed
            company: Optional company code

        Returns:
            The created activity record
        """
        fields_str = ", ".join(changed_fields[:5])
        if len(changed_fields) > 5:
            fields_str += f" and {len(changed_fields) - 5} more"

        return self.log_activity(
            ActivityCreateData(
                entity_type=entity_type,
                entity_id=entity_id,
                activity_type=ProjectActivityType.UPDATED,
                description=f"Updated: {fields_str}",
                changed_fields=changed_fields,
                company=company,
            )
        )

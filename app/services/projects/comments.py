"""Comment service for projects, tasks, and milestones.

This service handles:
- Creating, updating, and deleting comments
- Querying comments for entities
- Author authorization checks
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.models.project import (
    Project,
    Milestone,
    ProjectComment,
    ProjectActivityType,
)
from app.models.task import Task
from app.services.types import PaginatedResult, PaginationParams

from .activities import ActivityService
from .activity_types import ActivityCreateData
from .comment_types import CommentCreateData, CommentUpdateData
from .errors import (
    CommentNotFoundError,
    InvalidEntityTypeError,
    ProjectNotFoundError,
    TaskNotFoundError,
    MilestoneNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["CommentService"]

VALID_ENTITY_TYPES = {"project", "task", "milestone"}


class CommentService:
    """Service for managing project comments.

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

    def list_entity_comments(
        self,
        entity_type: str,
        entity_id: int,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ProjectComment]:
        """List comments for an entity.

        Args:
            entity_type: Type of entity ('project', 'task', 'milestone')
            entity_id: ID of the entity
            pagination: Optional pagination parameters

        Returns:
            Paginated list of comments

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(entity_type, list(VALID_ENTITY_TYPES))

        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ProjectComment).filter(
            ProjectComment.entity_type == entity_type,
            ProjectComment.entity_id == entity_id,
            ProjectComment.is_deleted == False,
        )

        total = query.count()
        comments = (
            query.order_by(ProjectComment.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
            .all()
        )

        return PaginatedResult(
            items=comments,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_comment(self, comment_id: int) -> ProjectComment:
        """Get a comment by ID.

        Args:
            comment_id: ID of the comment

        Returns:
            The comment

        Raises:
            CommentNotFoundError: If comment does not exist
        """
        comment = (
            self.db.query(ProjectComment)
            .filter(
                ProjectComment.id == comment_id,
                ProjectComment.is_deleted == False,
            )
            .first()
        )
        if not comment:
            raise CommentNotFoundError(comment_id)
        return comment

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_comment(self, data: CommentCreateData) -> ProjectComment:
        """Create a new comment.

        Args:
            data: Comment creation data

        Returns:
            The created comment (not yet committed)

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
            ProjectNotFoundError: If project does not exist
            TaskNotFoundError: If task does not exist
            MilestoneNotFoundError: If milestone does not exist
        """
        if data.entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(data.entity_type, list(VALID_ENTITY_TYPES))

        # Validate entity exists
        self._validate_entity_exists(data.entity_type, data.entity_id)

        # Get author info from principal
        author_id = self.principal.id if self.principal else None
        author_name = None
        author_email = None
        if self.principal:
            author_name = getattr(self.principal, "name", None) or getattr(
                self.principal, "email", None
            )
            author_email = getattr(self.principal, "email", None)

        if not author_id:
            from app.services.errors import ValidationError

            raise ValidationError("Cannot create comment without authenticated user")

        comment = ProjectComment(
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            content=data.content,
            author_id=author_id,
            author_name=author_name,
            author_email=author_email,
            company=data.company,
        )
        self.db.add(comment)
        self.db.flush()

        # Log activity
        self.activity_service.log_activity(
            ActivityCreateData(
                entity_type=data.entity_type,
                entity_id=data.entity_id,
                activity_type=ProjectActivityType.COMMENT_ADDED,
                description="Comment added",
                company=data.company,
            )
        )

        return comment

    def update_comment(
        self,
        comment_id: int,
        data: CommentUpdateData,
    ) -> ProjectComment:
        """Update an existing comment.

        Only the comment author can update the comment.

        Args:
            comment_id: ID of the comment to update
            data: Comment update data

        Returns:
            The updated comment (not yet committed)

        Raises:
            CommentNotFoundError: If comment does not exist
            ForbiddenError: If user is not the author
        """
        comment = self.get_comment(comment_id)

        # Check author authorization
        if self.principal and comment.author_id != self.principal.id:
            from app.services.errors import ForbiddenError

            raise ForbiddenError("Only the comment author can edit this comment")

        comment.content = data.content
        comment.is_edited = True
        comment.edited_at = datetime.now(timezone.utc)

        return comment

    def delete_comment(self, comment_id: int) -> None:
        """Soft delete a comment.

        Only the comment author can delete the comment.

        Args:
            comment_id: ID of the comment to delete

        Raises:
            CommentNotFoundError: If comment does not exist
            ForbiddenError: If user is not the author
        """
        comment = self.get_comment(comment_id)

        # Check author authorization
        if self.principal and comment.author_id != self.principal.id:
            from app.services.errors import ForbiddenError

            raise ForbiddenError("Only the comment author can delete this comment")

        comment.is_deleted = True
        comment.deleted_at = datetime.now(timezone.utc)
        if self.principal:
            comment.deleted_by_id = self.principal.id

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def _validate_entity_exists(self, entity_type: str, entity_id: int) -> None:
        """Validate that the referenced entity exists.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Raises:
            ProjectNotFoundError: If project does not exist
            TaskNotFoundError: If task does not exist
            MilestoneNotFoundError: If milestone does not exist
        """
        if entity_type == "project":
            exists = (
                self.db.query(Project)
                .filter(Project.id == entity_id, Project.is_deleted == False)
                .first()
            )
            if not exists:
                raise ProjectNotFoundError(entity_id)

        elif entity_type == "task":
            exists = self.db.query(Task).filter(Task.id == entity_id).first()
            if not exists:
                raise TaskNotFoundError(entity_id)

        elif entity_type == "milestone":
            exists = (
                self.db.query(Milestone)
                .filter(Milestone.id == entity_id, Milestone.is_deleted == False)
                .first()
            )
            if not exists:
                raise MilestoneNotFoundError(entity_id)

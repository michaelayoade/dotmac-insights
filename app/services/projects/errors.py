"""Projects domain errors."""
from app.services.errors import ServiceError, ValidationError, NotFoundError


class ProjectError(ServiceError):
    """Base error for project operations."""

    pass


class ProjectNotFoundError(NotFoundError):
    """Raised when a project is not found."""

    def __init__(self, project_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Project not found: {project_id}" if project_id else "Project not found"
        super().__init__(message)
        self.project_id = project_id


class TaskNotFoundError(NotFoundError):
    """Raised when a task is not found."""

    def __init__(self, task_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Task not found: {task_id}" if task_id else "Task not found"
        super().__init__(message)
        self.task_id = task_id


class MilestoneNotFoundError(NotFoundError):
    """Raised when a milestone is not found."""

    def __init__(self, milestone_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Milestone not found: {milestone_id}" if milestone_id else "Milestone not found"
        super().__init__(message)
        self.milestone_id = milestone_id


class CommentNotFoundError(NotFoundError):
    """Raised when a comment is not found."""

    def __init__(self, comment_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Comment not found: {comment_id}" if comment_id else "Comment not found"
        super().__init__(message)
        self.comment_id = comment_id


class AttachmentNotFoundError(NotFoundError):
    """Raised when an attachment is not found."""

    def __init__(self, attachment_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Attachment not found: {attachment_id}" if attachment_id else "Attachment not found"
        super().__init__(message)
        self.attachment_id = attachment_id


class TemplateNotFoundError(NotFoundError):
    """Raised when a project template is not found."""

    def __init__(self, template_id: int | None = None, message: str | None = None) -> None:
        if message is None:
            message = f"Project template not found: {template_id}" if template_id else "Project template not found"
        super().__init__(message)
        self.template_id = template_id


class ProjectStatusTransitionError(ValidationError):
    """Raised when a project status transition is invalid."""

    def __init__(
        self,
        current_status: str,
        target_status: str,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Cannot transition project from '{current_status}' to '{target_status}'"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status


class TaskDependencyError(ValidationError):
    """Raised when task dependencies are invalid (circular, blocked)."""

    def __init__(
        self,
        task_id: int | None = None,
        dependent_task_id: int | None = None,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Invalid task dependency: task {task_id} cannot depend on {dependent_task_id}"
        super().__init__(message)
        self.task_id = task_id
        self.dependent_task_id = dependent_task_id


class MilestoneStatusError(ValidationError):
    """Raised when milestone status transition is invalid."""

    def __init__(
        self,
        current_status: str,
        target_status: str,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Cannot transition milestone from '{current_status}' to '{target_status}'"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status


class AttachmentError(ValidationError):
    """Raised when attachment operations fail."""

    pass


class InvalidEntityTypeError(ValidationError):
    """Raised when an invalid entity type is provided."""

    def __init__(self, entity_type: str, allowed_types: list[str] | None = None) -> None:
        allowed = allowed_types or ["project", "task", "milestone"]
        message = f"Invalid entity type '{entity_type}'. Allowed types: {', '.join(allowed)}"
        super().__init__(message)
        self.entity_type = entity_type
        self.allowed_types = allowed

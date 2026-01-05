"""Template service for project templates.

This service handles:
- CRUD operations for project templates
- Task and milestone template management
- Creating projects from templates
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.project import (
    Project,
    ProjectStatus,
    Milestone,
    MilestoneStatus,
    ProjectTemplate,
    TaskTemplate,
    MilestoneTemplate,
    ProjectActivityType,
)
from app.models.task import Task, TaskStatus, TaskPriority
from app.services.types import PaginatedResult, PaginationParams

from .activities import ActivityService
from .activity_types import ActivityCreateData
from .errors import (
    TemplateNotFoundError,
    ValidationError,
)
from .template_types import (
    TaskTemplateData,
    MilestoneTemplateData,
    TemplateFilters,
    TemplateCreateData,
    TemplateUpdateData,
    CreateFromTemplateData,
    TemplateExpansionResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ProjectTemplateService"]


def _validate_task_priority(priority: Optional[str]) -> Optional[str]:
    """Validate task template priority values."""
    if priority is None:
        return None
    try:
        TaskPriority(priority)
    except ValueError:
        raise ValidationError(f"Invalid task template priority: {priority}")
    return priority


class ProjectTemplateService:
    """Service for managing project templates.

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

    def list_templates(
        self,
        filters: Optional[TemplateFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ProjectTemplate]:
        """List project templates with filtering and pagination.

        Args:
            filters: Optional filters for active_only, project_type, etc.
            pagination: Optional pagination parameters

        Returns:
            Paginated list of templates
        """
        if filters is None:
            filters = TemplateFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(ProjectTemplate)

        # Apply filters
        if filters.is_active is not None:
            query = query.filter(ProjectTemplate.is_active == filters.is_active)
        elif filters.active_only:
            query = query.filter(ProjectTemplate.is_active == True)

        if filters.project_type:
            query = query.filter(ProjectTemplate.project_type == filters.project_type)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(ProjectTemplate.name.ilike(search_term))

        total = query.count()
        templates = (
            query.order_by(ProjectTemplate.name)
            .offset(pagination.offset)
            .limit(pagination.limit)
            .all()
        )

        return PaginatedResult(
            items=templates,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_template(self, template_id: int) -> ProjectTemplate:
        """Get a project template by ID.

        Args:
            template_id: ID of the template

        Returns:
            The project template

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = (
            self.db.query(ProjectTemplate)
            .filter(ProjectTemplate.id == template_id)
            .first()
        )
        if not template:
            raise TemplateNotFoundError(template_id)
        return template

    def get_active_template(self, template_id: int) -> ProjectTemplate:
        """Get an active project template by ID.

        Args:
            template_id: ID of the template

        Returns:
            The project template (must be active)

        Raises:
            TemplateNotFoundError: If template does not exist or is inactive
        """
        template = (
            self.db.query(ProjectTemplate)
            .filter(
                ProjectTemplate.id == template_id,
                ProjectTemplate.is_active == True,
            )
            .first()
        )
        if not template:
            raise TemplateNotFoundError(template_id, "Template not found or inactive")
        return template

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_template(self, data: TemplateCreateData) -> ProjectTemplate:
        """Create a new project template.

        Args:
            data: Template creation data

        Returns:
            The created template (not yet committed)
        """
        created_by_id = self.principal.id if self.principal else None

        template = ProjectTemplate(
            name=data.name,
            description=data.description,
            project_type=data.project_type,
            default_priority=data.default_priority,
            estimated_duration_days=data.estimated_duration_days,
            default_notes=data.default_notes,
            is_active=data.is_active if data.is_active is not None else True,
            created_by_id=created_by_id,
        )
        self.db.add(template)
        self.db.flush()

        # Add task templates
        if data.task_templates:
            for idx, tt in enumerate(data.task_templates):
                task_template = TaskTemplate(
                    project_template_id=template.id,
                    subject=tt.subject,
                    description=tt.description,
                    priority=_validate_task_priority(tt.priority),
                    start_day_offset=tt.start_day_offset,
                    duration_days=tt.duration_days,
                    default_assigned_role=tt.default_assigned_role,
                    is_group=tt.is_group,
                    idx=tt.idx if tt.idx is not None else idx,
                )
                self.db.add(task_template)

        # Add milestone templates
        if data.milestone_templates:
            for idx, mt in enumerate(data.milestone_templates):
                milestone_template = MilestoneTemplate(
                    project_template_id=template.id,
                    name=mt.name,
                    description=mt.description,
                    start_day_offset=mt.start_day_offset,
                    end_day_offset=mt.end_day_offset,
                    idx=mt.idx if mt.idx is not None else idx,
                )
                self.db.add(milestone_template)

        self.db.flush()
        return template

    def update_template(
        self,
        template_id: int,
        data: TemplateUpdateData,
    ) -> ProjectTemplate:
        """Update a project template.

        Args:
            template_id: ID of the template to update
            data: Template update data

        Returns:
            The updated template (not yet committed)

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = self.get_template(template_id)

        # Update fields
        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.project_type is not None:
            template.project_type = data.project_type
        if data.default_priority is not None:
            template.default_priority = data.default_priority
        if data.estimated_duration_days is not None:
            template.estimated_duration_days = data.estimated_duration_days
        if data.default_notes is not None:
            template.default_notes = data.default_notes
        if data.is_active is not None:
            template.is_active = data.is_active

        # Replace task templates if provided
        if data.task_templates is not None:
            # Clear existing task templates
            for tt in list(template.task_templates):
                self.db.delete(tt)
            self.db.flush()

            # Add new task templates
            for idx, tt in enumerate(data.task_templates):
                task_template = TaskTemplate(
                    project_template_id=template.id,
                    subject=tt.subject,
                    description=tt.description,
                    priority=_validate_task_priority(tt.priority),
                    start_day_offset=tt.start_day_offset,
                    duration_days=tt.duration_days,
                    default_assigned_role=tt.default_assigned_role,
                    is_group=tt.is_group,
                    idx=tt.idx if tt.idx is not None else idx,
                )
                self.db.add(task_template)

        # Replace milestone templates if provided
        if data.milestone_templates is not None:
            # Clear existing milestone templates
            for mt in list(template.milestone_templates):
                self.db.delete(mt)
            self.db.flush()

            # Add new milestone templates
            for idx, mt in enumerate(data.milestone_templates):
                milestone_template = MilestoneTemplate(
                    project_template_id=template.id,
                    name=mt.name,
                    description=mt.description,
                    start_day_offset=mt.start_day_offset,
                    end_day_offset=mt.end_day_offset,
                    idx=mt.idx if mt.idx is not None else idx,
                )
                self.db.add(milestone_template)

        self.db.flush()
        return template

    def delete_template(self, template_id: int) -> None:
        """Delete a project template.

        This is a hard delete that also deletes associated task and milestone templates.

        Args:
            template_id: ID of the template to delete

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = self.get_template(template_id)
        self.db.delete(template)

    def deactivate_template(self, template_id: int) -> ProjectTemplate:
        """Deactivate a project template (soft delete alternative).

        Args:
            template_id: ID of the template to deactivate

        Returns:
            The deactivated template

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = self.get_template(template_id)
        template.is_active = False
        return template

    # -------------------------------------------------------------------------
    # Project Creation from Template
    # -------------------------------------------------------------------------

    def create_project_from_template(
        self,
        template_id: int,
        data: CreateFromTemplateData,
    ) -> TemplateExpansionResult:
        """Create a new project from a template.

        Args:
            template_id: ID of the template to use
            data: Project creation data

        Returns:
            TemplateExpansionResult with created project and counts

        Raises:
            TemplateNotFoundError: If template does not exist or is inactive
        """
        template = self.get_active_template(template_id)

        # Calculate dates
        start_date = data.expected_start_date or date.today()
        end_date = None
        if template.estimated_duration_days:
            end_date = start_date + timedelta(days=template.estimated_duration_days)

        # Get creator info from principal
        created_by_id = self.principal.id if self.principal else None

        # Create project
        project = Project(
            project_name=data.project_name,
            project_type=template.project_type,
            priority=template.default_priority,
            status=ProjectStatus.OPEN,
            expected_start_date=start_date,
            expected_end_date=end_date,
            notes=data.notes or template.default_notes,
            customer_account_id=data.customer_account_id,
            project_manager_id=data.project_manager_id,
            company=data.company,
        )
        self.db.add(project)
        self.db.flush()

        # Create milestones from template
        milestone_map: Dict[int, Milestone] = {}
        for mt in sorted(template.milestone_templates, key=lambda x: x.idx):
            milestone = Milestone(
                project_id=project.id,
                name=mt.name,
                description=mt.description,
                status=MilestoneStatus.PLANNED,
                planned_start_date=start_date + timedelta(days=mt.start_day_offset),
                planned_end_date=start_date + timedelta(days=mt.end_day_offset),
                idx=mt.idx,
                company=data.company,
                created_by_id=created_by_id,
            )
            self.db.add(milestone)
            self.db.flush()
            milestone_map[mt.id] = milestone

        # Create tasks from template
        tasks_created = 0
        for tt in sorted(template.task_templates, key=lambda x: x.idx):
            task_priority = TaskPriority.MEDIUM
            if tt.priority:
                try:
                    task_priority = TaskPriority(tt.priority)
                except ValueError:
                    task_priority = TaskPriority.MEDIUM

            # Map to milestone if applicable
            milestone_for_task = None
            if tt.milestone_template_id and tt.milestone_template_id in milestone_map:
                milestone_for_task = milestone_map[tt.milestone_template_id]

            task = Task(
                project_id=project.id,
                subject=tt.subject,
                description=tt.description,
                priority=task_priority,
                status=TaskStatus.OPEN,
                exp_start_date=start_date + timedelta(days=tt.start_day_offset),
                exp_end_date=start_date
                + timedelta(days=tt.start_day_offset + tt.duration_days),
                is_group=tt.is_group,
                milestone_id=milestone_for_task.id if milestone_for_task else None,
                company=data.company,
            )
            self.db.add(task)
            tasks_created += 1

        self.db.flush()

        # Log activity
        self.activity_service.log_activity(
            ActivityCreateData(
                entity_type="project",
                entity_id=project.id,
                activity_type=ProjectActivityType.CREATED,
                description=f"Project created from template: {template.name}",
                company=data.company,
            )
        )

        return TemplateExpansionResult(
            project=project,
            milestones_created=len(milestone_map),
            tasks_created=tasks_created,
            template_name=template.name,
        )

    # -------------------------------------------------------------------------
    # Template Helper Methods
    # -------------------------------------------------------------------------

    def add_task_template(
        self,
        template_id: int,
        data: TaskTemplateData,
    ) -> TaskTemplate:
        """Add a task template to a project template.

        Args:
            template_id: ID of the project template
            data: Task template data

        Returns:
            The created task template

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = self.get_template(template_id)

        # Calculate idx if not provided
        idx = data.idx
        if idx is None:
            max_idx = max((tt.idx for tt in template.task_templates), default=0)
            idx = max_idx + 1

        task_template = TaskTemplate(
            project_template_id=template.id,
            subject=data.subject,
            description=data.description,
            priority=_validate_task_priority(data.priority),
            start_day_offset=data.start_day_offset,
            duration_days=data.duration_days,
            default_assigned_role=data.default_assigned_role,
            is_group=data.is_group,
            idx=idx,
        )
        self.db.add(task_template)
        self.db.flush()
        return task_template

    def add_milestone_template(
        self,
        template_id: int,
        data: MilestoneTemplateData,
    ) -> MilestoneTemplate:
        """Add a milestone template to a project template.

        Args:
            template_id: ID of the project template
            data: Milestone template data

        Returns:
            The created milestone template

        Raises:
            TemplateNotFoundError: If template does not exist
        """
        template = self.get_template(template_id)

        # Calculate idx if not provided
        idx = data.idx
        if idx is None:
            max_idx = max((mt.idx for mt in template.milestone_templates), default=0)
            idx = max_idx + 1

        milestone_template = MilestoneTemplate(
            project_template_id=template.id,
            name=data.name,
            description=data.description,
            start_day_offset=data.start_day_offset,
            end_day_offset=data.end_day_offset,
            idx=idx,
        )
        self.db.add(milestone_template)
        self.db.flush()
        return milestone_template

    def remove_task_template(
        self,
        template_id: int,
        task_template_id: int,
    ) -> None:
        """Remove a task template from a project template.

        Args:
            template_id: ID of the project template
            task_template_id: ID of the task template to remove

        Raises:
            TemplateNotFoundError: If template does not exist
            ValidationError: If task template does not belong to template
        """
        template = self.get_template(template_id)

        task_template = (
            self.db.query(TaskTemplate)
            .filter(
                TaskTemplate.id == task_template_id,
                TaskTemplate.project_template_id == template.id,
            )
            .first()
        )
        if not task_template:
            raise ValidationError(
                f"Task template {task_template_id} not found in template {template_id}"
            )

        self.db.delete(task_template)

    def remove_milestone_template(
        self,
        template_id: int,
        milestone_template_id: int,
    ) -> None:
        """Remove a milestone template from a project template.

        Args:
            template_id: ID of the project template
            milestone_template_id: ID of the milestone template to remove

        Raises:
            TemplateNotFoundError: If template does not exist
            ValidationError: If milestone template does not belong to template
        """
        template = self.get_template(template_id)

        milestone_template = (
            self.db.query(MilestoneTemplate)
            .filter(
                MilestoneTemplate.id == milestone_template_id,
                MilestoneTemplate.project_template_id == template.id,
            )
            .first()
        )
        if not milestone_template:
            raise ValidationError(
                f"Milestone template {milestone_template_id} not found in template {template_id}"
            )

        self.db.delete(milestone_template)

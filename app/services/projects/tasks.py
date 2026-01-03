"""Task service for project tasks.

This service handles:
- CRUD operations for tasks
- Task dependencies management
- Employee name resolution
- Progress tracking
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectActivityType
from app.models.task import Task, TaskStatus, TaskPriority, TaskDependency
from app.models.employee import Employee
from app.services.types import PaginatedResult, PaginationParams

from .activities import ActivityService
from .activity_types import ActivityCreateData
from .errors import TaskNotFoundError, TaskDependencyError, ProjectNotFoundError
from .task_types import (
    TaskFilters,
    TaskDependencyData,
    TaskCreateData,
    TaskUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TaskService"]


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """Convert value to Decimal with default fallback."""
    return Decimal(str(val)) if val is not None else default


class TaskService:
    """Service for managing project tasks.

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

    def list_tasks(
        self,
        filters: Optional[TaskFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Task]:
        """List tasks with filters and pagination.

        Args:
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Paginated list of tasks
        """
        if filters is None:
            filters = TaskFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Task)

        # Apply filters
        if filters.status:
            query = query.filter(Task.status == filters.status)

        if filters.priority:
            query = query.filter(Task.priority == filters.priority)

        if filters.project_id:
            query = query.filter(Task.project_id == filters.project_id)

        if filters.milestone_id:
            query = query.filter(Task.milestone_id == filters.milestone_id)

        if filters.assigned_to_id:
            query = query.filter(Task.assigned_to_id == filters.assigned_to_id)

        if filters.assigned_to:
            query = query.filter(Task.assigned_to.ilike(f"%{filters.assigned_to}%"))

        if filters.task_type:
            query = query.filter(Task.task_type == filters.task_type)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Task.subject.ilike(search_term),
                    Task.erpnext_id.ilike(search_term),
                    Task.description.ilike(search_term),
                )
            )

        if filters.overdue_only:
            today = date.today()
            query = query.filter(
                Task.exp_end_date < today,
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )

        if filters.start_date:
            query = query.filter(Task.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(Task.created_at <= filters.end_date)

        if filters.is_group is not None:
            query = query.filter(Task.is_group == filters.is_group)

        if filters.is_template is not None:
            query = query.filter(Task.is_template == filters.is_template)

        if filters.parent_task_id is not None:
            query = query.filter(Task.parent_task_id == filters.parent_task_id)

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(Task, filters.sort_by, Task.created_at)
        if filters.sort_dir == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        tasks = query.offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(
            items=tasks,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_task(self, task_id: int) -> Task:
        """Get a task by ID.

        Args:
            task_id: ID of the task

        Returns:
            The task

        Raises:
            TaskNotFoundError: If task does not exist
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise TaskNotFoundError(task_id)
        return task

    def get_task_with_dependencies(
        self,
        task_id: int,
    ) -> Tuple[Task, List[TaskDependency], List[Task]]:
        """Get a task with its dependencies and sub-tasks.

        Args:
            task_id: ID of the task

        Returns:
            Tuple of (task, dependencies, sub_tasks)

        Raises:
            TaskNotFoundError: If task does not exist
        """
        task = self.get_task(task_id)
        dependencies = sorted(task.depends_on, key=lambda x: x.idx)
        sub_tasks = list(task.sub_tasks) if task.sub_tasks else []
        return task, dependencies, sub_tasks

    def get_sub_tasks(self, task_id: int) -> List[Task]:
        """Get sub-tasks of a task.

        Args:
            task_id: ID of the parent task

        Returns:
            List of sub-tasks
        """
        return (
            self.db.query(Task)
            .filter(Task.parent_task_id == task_id)
            .order_by(Task.created_at)
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_task(self, data: TaskCreateData) -> Task:
        """Create a new task.

        Args:
            data: Task creation data

        Returns:
            The created task (not yet committed)

        Raises:
            ProjectNotFoundError: If project_id is provided but project doesn't exist
        """
        # Validate project exists if provided
        if data.project_id:
            project = (
                self.db.query(Project)
                .filter(Project.id == data.project_id, Project.is_deleted == False)
                .first()
            )
            if not project:
                raise ProjectNotFoundError(data.project_id)

        # Resolve employee names if IDs provided
        assigned_to = data.assigned_to
        completed_by = data.completed_by

        if data.assigned_to_id and not assigned_to:
            assigned_to = self._resolve_employee_name(data.assigned_to_id)

        if data.completed_by_id and not completed_by:
            completed_by = self._resolve_employee_name(data.completed_by_id)

        task = Task(
            subject=data.subject,
            description=data.description,
            project_id=data.project_id,
            milestone_id=data.milestone_id,
            erpnext_project=data.erpnext_project,
            issue=data.issue,
            task_type=data.task_type,
            color=data.color,
            status=data.status,
            priority=data.priority,
            assigned_to=assigned_to,
            completed_by=completed_by,
            assigned_to_id=data.assigned_to_id,
            completed_by_id=data.completed_by_id,
            progress=_decimal_or_default(data.progress),
            expected_time=_decimal_or_default(data.expected_time),
            actual_time=_decimal_or_default(data.actual_time),
            exp_start_date=data.exp_start_date,
            exp_end_date=data.exp_end_date,
            act_start_date=data.act_start_date,
            act_end_date=data.act_end_date,
            completed_on=data.completed_on,
            review_date=data.review_date,
            closing_date=data.closing_date,
            parent_task=data.parent_task,
            parent_task_id=data.parent_task_id,
            is_group=data.is_group,
            is_template=data.is_template,
            company=data.company,
            department=data.department,
            total_costing_amount=_decimal_or_default(data.total_costing_amount),
            total_billing_amount=_decimal_or_default(data.total_billing_amount),
            total_expense_claim=_decimal_or_default(data.total_expense_claim),
            template_task=data.template_task,
            docstatus=data.docstatus,
        )

        self.db.add(task)
        self.db.flush()

        # Add dependencies if provided
        if data.depends_on:
            for idx, dep in enumerate(data.depends_on):
                self._add_dependency(task.id, dep, idx)

        # Log activity
        self.activity_service.log_created(
            entity_type="task",
            entity_id=task.id,
            entity_name=task.subject,
            company=task.company,
        )

        return task

    def update_task(self, task_id: int, data: TaskUpdateData) -> Task:
        """Update a task.

        Args:
            task_id: ID of the task to update
            data: Task update data

        Returns:
            The updated task (not yet committed)

        Raises:
            TaskNotFoundError: If task does not exist
        """
        task = self.get_task(task_id)
        changed_fields = []
        old_status = task.status

        # Update basic fields
        if data.subject is not None and data.subject != task.subject:
            task.subject = data.subject
            changed_fields.append("subject")

        if data.description is not None:
            task.description = data.description
            changed_fields.append("description")

        if data.project_id is not None:
            task.project_id = data.project_id
            changed_fields.append("project_id")

        if data.milestone_id is not None:
            task.milestone_id = data.milestone_id
            changed_fields.append("milestone_id")

        if data.erpnext_project is not None:
            task.erpnext_project = data.erpnext_project

        if data.issue is not None:
            task.issue = data.issue

        if data.task_type is not None:
            task.task_type = data.task_type
            changed_fields.append("task_type")

        if data.color is not None:
            task.color = data.color

        if data.status is not None and data.status != task.status:
            task.status = data.status
            changed_fields.append("status")

        if data.priority is not None and data.priority != task.priority:
            task.priority = data.priority
            changed_fields.append("priority")

        # Handle assignment
        if data.assigned_to is not None:
            task.assigned_to = data.assigned_to
            changed_fields.append("assigned_to")

        if data.assigned_to_id is not None:
            task.assigned_to_id = data.assigned_to_id
            if data.assigned_to is None:
                task.assigned_to = self._resolve_employee_name(data.assigned_to_id)
            changed_fields.append("assigned_to")

        if data.completed_by is not None:
            task.completed_by = data.completed_by

        if data.completed_by_id is not None:
            task.completed_by_id = data.completed_by_id
            if data.completed_by is None:
                task.completed_by = self._resolve_employee_name(data.completed_by_id)

        # Update progress
        if data.progress is not None:
            task.progress = _decimal_or_default(data.progress)
            changed_fields.append("progress")

        if data.expected_time is not None:
            task.expected_time = _decimal_or_default(data.expected_time)

        if data.actual_time is not None:
            task.actual_time = _decimal_or_default(data.actual_time)
            changed_fields.append("actual_time")

        # Update dates
        if data.exp_start_date is not None:
            task.exp_start_date = data.exp_start_date

        if data.exp_end_date is not None:
            task.exp_end_date = data.exp_end_date

        if data.act_start_date is not None:
            task.act_start_date = data.act_start_date

        if data.act_end_date is not None:
            task.act_end_date = data.act_end_date

        if data.completed_on is not None:
            task.completed_on = data.completed_on

        if data.review_date is not None:
            task.review_date = data.review_date

        if data.closing_date is not None:
            task.closing_date = data.closing_date

        # Update hierarchy
        if data.parent_task is not None:
            task.parent_task = data.parent_task

        if data.parent_task_id is not None:
            task.parent_task_id = data.parent_task_id

        if data.is_group is not None:
            task.is_group = data.is_group

        # Update organization
        if data.company is not None:
            task.company = data.company

        if data.department is not None:
            task.department = data.department

        # Update financials
        if data.total_costing_amount is not None:
            task.total_costing_amount = _decimal_or_default(data.total_costing_amount)

        if data.total_billing_amount is not None:
            task.total_billing_amount = _decimal_or_default(data.total_billing_amount)

        if data.total_expense_claim is not None:
            task.total_expense_claim = _decimal_or_default(data.total_expense_claim)

        if data.docstatus is not None:
            task.docstatus = data.docstatus

        # Replace dependencies if provided
        if data.depends_on is not None:
            self.replace_dependencies(task_id, data.depends_on)
            changed_fields.append("depends_on")

        # Log status change if changed
        if "status" in changed_fields and old_status != task.status:
            self.activity_service.log_status_change(
                entity_type="task",
                entity_id=task.id,
                old_status=old_status.value,
                new_status=task.status.value,
                company=task.company,
            )

            # If completed, log task completed on project
            if task.status == TaskStatus.COMPLETED and task.project_id:
                self.activity_service.log_activity(
                    ActivityCreateData(
                        entity_type="project",
                        entity_id=task.project_id,
                        activity_type=ProjectActivityType.TASK_COMPLETED,
                        description=f"Task '{task.subject}' completed",
                        company=task.company,
                    )
                )
        elif changed_fields:
            # Log other updates
            self.activity_service.log_updated(
                entity_type="task",
                entity_id=task.id,
                changed_fields=changed_fields,
                company=task.company,
            )

        return task

    def delete_task(self, task_id: int) -> None:
        """Delete a task and its dependencies.

        Args:
            task_id: ID of the task to delete

        Raises:
            TaskNotFoundError: If task does not exist
        """
        task = self.get_task(task_id)
        self.db.delete(task)

    # -------------------------------------------------------------------------
    # Status Transition Methods
    # -------------------------------------------------------------------------

    def complete_task(self, task_id: int) -> Task:
        """Mark a task as completed.

        Args:
            task_id: ID of the task

        Returns:
            The updated task
        """
        return self.update_task(
            task_id,
            TaskUpdateData(
                status=TaskStatus.COMPLETED,
                progress=Decimal("100"),
                completed_on=date.today(),
            ),
        )

    def reopen_task(self, task_id: int) -> Task:
        """Reopen a completed task.

        Args:
            task_id: ID of the task

        Returns:
            The updated task
        """
        return self.update_task(
            task_id,
            TaskUpdateData(status=TaskStatus.OPEN),
        )

    def update_progress(
        self,
        task_id: int,
        progress: Decimal,
        actual_time: Optional[Decimal] = None,
    ) -> Task:
        """Update task progress.

        Args:
            task_id: ID of the task
            progress: New progress value (0-100)
            actual_time: Optional actual time spent

        Returns:
            The updated task
        """
        data = TaskUpdateData(progress=progress)
        if actual_time is not None:
            data.actual_time = actual_time
        return self.update_task(task_id, data)

    # -------------------------------------------------------------------------
    # Dependency Methods
    # -------------------------------------------------------------------------

    def add_dependency(
        self,
        task_id: int,
        dependency: TaskDependencyData,
    ) -> TaskDependency:
        """Add a dependency to a task.

        Args:
            task_id: ID of the task
            dependency: Dependency data

        Returns:
            The created dependency

        Raises:
            TaskNotFoundError: If task does not exist
            TaskDependencyError: If circular dependency detected
        """
        task = self.get_task(task_id)

        # Validate no circular dependency
        if dependency.dependent_task_id:
            self._validate_no_circular_dependency(task_id, dependency.dependent_task_id)

        # Get max idx
        max_idx = max((d.idx for d in task.depends_on), default=-1)

        return self._add_dependency(task_id, dependency, max_idx + 1)

    def remove_dependency(self, task_id: int, dependency_id: int) -> None:
        """Remove a dependency from a task.

        Args:
            task_id: ID of the task
            dependency_id: ID of the dependency to remove

        Raises:
            TaskNotFoundError: If task does not exist
        """
        self.get_task(task_id)  # Verify task exists

        self.db.query(TaskDependency).filter(
            TaskDependency.id == dependency_id,
            TaskDependency.task_id == task_id,
        ).delete()

    def replace_dependencies(
        self,
        task_id: int,
        dependencies: List[TaskDependencyData],
    ) -> List[TaskDependency]:
        """Replace all dependencies for a task.

        Args:
            task_id: ID of the task
            dependencies: New list of dependencies

        Returns:
            List of created dependencies

        Raises:
            TaskNotFoundError: If task does not exist
        """
        self.get_task(task_id)  # Verify task exists

        # Delete existing dependencies
        self.db.query(TaskDependency).filter(
            TaskDependency.task_id == task_id
        ).delete(synchronize_session=False)

        # Add new dependencies
        created = []
        for idx, dep in enumerate(dependencies):
            created.append(self._add_dependency(task_id, dep, idx))

        return created

    def _add_dependency(
        self,
        task_id: int,
        dependency: TaskDependencyData,
        idx: int,
    ) -> TaskDependency:
        """Internal method to add a dependency."""
        dep = TaskDependency(
            task_id=task_id,
            dependent_task_id=dependency.dependent_task_id,
            dependent_task_erpnext=dependency.dependent_task_erpnext,
            subject=dependency.subject,
            project=dependency.project,
            idx=dependency.idx if dependency.idx else idx,
        )
        self.db.add(dep)
        self.db.flush()
        return dep

    def _validate_no_circular_dependency(
        self,
        task_id: int,
        dependent_task_id: int,
    ) -> None:
        """Validate that adding a dependency won't create a circular reference."""
        if task_id == dependent_task_id:
            raise TaskDependencyError(
                task_id=task_id,
                dependent_task_id=dependent_task_id,
                message="A task cannot depend on itself",
            )

        # Check if dependent_task depends on task_id (direct or indirect)
        visited = set()
        to_check = [dependent_task_id]

        while to_check:
            current_id = to_check.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == task_id:
                raise TaskDependencyError(
                    task_id=task_id,
                    dependent_task_id=dependent_task_id,
                    message="Circular dependency detected",
                )

            # Get dependencies of current task
            deps = (
                self.db.query(TaskDependency.dependent_task_id)
                .filter(
                    TaskDependency.task_id == current_id,
                    TaskDependency.dependent_task_id.isnot(None),
                )
                .all()
            )
            to_check.extend(d[0] for d in deps if d[0])

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _resolve_employee_name(self, employee_id: int) -> Optional[str]:
        """Resolve employee ID to name.

        Args:
            employee_id: ID of the employee

        Returns:
            Employee name or None if not found
        """
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        return employee.name if employee else None

    def _resolve_employee_id(self, employee_name: str) -> Optional[int]:
        """Resolve employee name to ID.

        Args:
            employee_name: Name of the employee

        Returns:
            Employee ID or None if not found
        """
        employee = (
            self.db.query(Employee)
            .filter(Employee.name.ilike(f"%{employee_name}%"))
            .first()
        )
        return employee.id if employee else None

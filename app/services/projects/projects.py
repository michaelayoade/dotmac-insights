"""Project service for project CRUD and team management.

This service handles:
- CRUD operations for projects
- Team member (ProjectUser) management
- Status transitions
- Notification emission for project events
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.project import (
    Project,
    ProjectStatus,
    ProjectPriority,
    ProjectUser,
    ProjectActivityType,
)
from app.models.task import Task, TaskStatus
from app.models.party import CustomerAccount, Party
from app.models.employee import Employee
from app.models.hr import ERPNextUser
from app.models.auth import User
from app.services.types import PaginatedResult, PaginationParams
from app.services.activity_logger import ActivityLogger

from .activities import ActivityService
from .activity_types import ActivityCreateData
from .errors import ProjectNotFoundError, ProjectStatusTransitionError
from .project_types import (
    ProjectFilters,
    ProjectUserData,
    ProjectCreateData,
    ProjectUpdateData,
    ProjectTaskStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ProjectService"]

# Valid status transitions
VALID_PROJECT_TRANSITIONS = {
    ProjectStatus.OPEN: {
        ProjectStatus.COMPLETED,
        ProjectStatus.CANCELLED,
        ProjectStatus.ON_HOLD,
    },
    ProjectStatus.ON_HOLD: {
        ProjectStatus.OPEN,
        ProjectStatus.CANCELLED,
    },
    ProjectStatus.COMPLETED: set(),  # Cannot transition from completed
    ProjectStatus.CANCELLED: set(),  # Cannot transition from cancelled
}


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """Convert value to Decimal with default fallback."""
    return Decimal(str(val)) if val is not None else default


class ProjectService:
    """Service for managing projects.

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

    def list_projects(
        self,
        filters: Optional[ProjectFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Project]:
        """List projects with filters and pagination.

        Args:
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Paginated list of projects
        """
        if filters is None:
            filters = ProjectFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Project).filter(Project.is_deleted == False)

        # Apply filters
        if filters.status:
            query = query.filter(Project.status == filters.status)

        if filters.priority:
            query = query.filter(Project.priority == filters.priority)

        if filters.customer_account_id:
            query = query.filter(Project.customer_account_id == filters.customer_account_id)

        if filters.project_type:
            query = query.filter(Project.project_type == filters.project_type)

        if filters.department:
            query = query.filter(Project.department.ilike(f"%{filters.department}%"))

        if filters.project_manager_id:
            query = query.filter(Project.project_manager_id == filters.project_manager_id)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Project.project_name.ilike(search_term),
                    Project.erpnext_id.ilike(search_term),
                )
            )

        if filters.overdue_only:
            query = query.filter(
                Project.expected_end_date < datetime.now(timezone.utc),
                Project.status == ProjectStatus.OPEN,
            )

        if filters.start_date:
            query = query.filter(Project.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(Project.created_at <= filters.end_date)

        if filters.is_active:
            query = query.filter(Project.is_active == filters.is_active)

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(Project, filters.sort_by, Project.created_at)
        if filters.sort_dir == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        projects = query.offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(
            items=projects,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_project(self, project_id: int) -> Project:
        """Get a project by ID.

        Args:
            project_id: ID of the project

        Returns:
            The project

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id, Project.is_deleted == False)
            .first()
        )
        if not project:
            raise ProjectNotFoundError(project_id)
        return project

    def get_project_task_stats(self, project_id: int) -> ProjectTaskStats:
        """Get task statistics for a project.

        Args:
            project_id: ID of the project

        Returns:
            Task statistics

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        project = self.get_project(project_id)
        tasks = project.tasks

        return ProjectTaskStats(
            total=len(tasks),
            completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            open=sum(
                1 for t in tasks if t.status in [TaskStatus.OPEN, TaskStatus.WORKING]
            ),
            overdue=sum(1 for t in tasks if t.is_overdue),
        )

    def get_customer_info(self, project: Project) -> Optional[dict]:
        """Get customer information for a project.

        Args:
            project: The project

        Returns:
            Customer info dict or None
        """
        if not project.customer_account_id:
            return None

        account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.id == project.customer_account_id)
            .first()
        )
        if not account or not account.party:
            return None

        return {
            "id": account.id,
            "party_id": account.party_id,
            "name": account.party.name,
            "email": account.party.primary_email,
        }

    def get_manager_info(self, project: Project) -> Optional[dict]:
        """Get project manager information.

        Args:
            project: The project

        Returns:
            Manager info dict or None
        """
        if not project.project_manager_id:
            return None

        emp = (
            self.db.query(Employee)
            .filter(Employee.id == project.project_manager_id)
            .first()
        )
        if not emp:
            return None

        return {
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
        }

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_project(self, data: ProjectCreateData) -> Project:
        """Create a new project.

        Args:
            data: Project creation data

        Returns:
            The created project (not yet committed)
        """
        project = Project(
            project_name=data.project_name,
            project_type=data.project_type,
            status=data.status,
            priority=data.priority,
            department=data.department,
            company=data.company,
            cost_center=data.cost_center,
            customer_account_id=data.customer_account_id,
            project_manager_id=data.project_manager_id,
            erpnext_customer=data.erpnext_customer,
            erpnext_sales_order=data.erpnext_sales_order,
            percent_complete=_decimal_or_default(data.percent_complete),
            percent_complete_method=data.percent_complete_method,
            is_active=data.is_active,
            actual_time=_decimal_or_default(data.actual_time),
            total_consumed_material_cost=_decimal_or_default(
                data.total_consumed_material_cost
            ),
            estimated_costing=_decimal_or_default(data.estimated_costing),
            total_costing_amount=_decimal_or_default(data.total_costing_amount),
            total_expense_claim=_decimal_or_default(data.total_expense_claim),
            total_purchase_cost=_decimal_or_default(data.total_purchase_cost),
            total_sales_amount=_decimal_or_default(data.total_sales_amount),
            total_billable_amount=_decimal_or_default(data.total_billable_amount),
            total_billed_amount=_decimal_or_default(data.total_billed_amount),
            gross_margin=_decimal_or_default(data.gross_margin),
            per_gross_margin=_decimal_or_default(data.per_gross_margin),
            collect_progress=data.collect_progress,
            frequency=data.frequency,
            message=data.message,
            notes=data.notes,
            expected_start_date=data.expected_start_date,
            expected_end_date=data.expected_end_date,
            actual_start_date=data.actual_start_date,
            actual_end_date=data.actual_end_date,
            from_time=data.from_time,
            to_time=data.to_time,
        )

        self.db.add(project)
        self.db.flush()

        # Add team members if provided
        if data.users:
            for idx, user_data in enumerate(data.users):
                self._add_team_member(project.id, user_data, idx)

        # Log activity
        self.activity_service.log_created(
            entity_type="project",
            entity_id=project.id,
            entity_name=project.project_name,
            company=project.company,
        )

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="projects.project.create",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="project",
            entity_id=str(project.id),
            summary=f"Created project {project.project_name}",
            metadata={"status": project.status},
        )
        return project

    def update_project(self, project_id: int, data: ProjectUpdateData) -> Project:
        """Update a project.

        Args:
            project_id: ID of the project to update
            data: Project update data

        Returns:
            The updated project (not yet committed)

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        project = self.get_project(project_id)
        changed_fields = []
        old_status = project.status

        # Update basic fields
        if data.project_name is not None and data.project_name != project.project_name:
            project.project_name = data.project_name
            changed_fields.append("project_name")

        if data.project_type is not None:
            project.project_type = data.project_type
            changed_fields.append("project_type")

        if data.status is not None and data.status != project.status:
            project.status = data.status
            changed_fields.append("status")

        if data.priority is not None and data.priority != project.priority:
            project.priority = data.priority
            changed_fields.append("priority")

        if data.department is not None:
            project.department = data.department
            changed_fields.append("department")

        if data.company is not None:
            project.company = data.company

        if data.cost_center is not None:
            project.cost_center = data.cost_center

        if data.customer_account_id is not None:
            project.customer_account_id = data.customer_account_id
            changed_fields.append("customer")

        if data.project_manager_id is not None:
            project.project_manager_id = data.project_manager_id
            changed_fields.append("project_manager")

        if data.erpnext_customer is not None:
            project.erpnext_customer = data.erpnext_customer

        if data.erpnext_sales_order is not None:
            project.erpnext_sales_order = data.erpnext_sales_order

        if data.percent_complete is not None:
            project.percent_complete = _decimal_or_default(data.percent_complete)
            changed_fields.append("percent_complete")

        if data.percent_complete_method is not None:
            project.percent_complete_method = data.percent_complete_method

        if data.is_active is not None:
            project.is_active = data.is_active

        # Update financials
        if data.actual_time is not None:
            project.actual_time = _decimal_or_default(data.actual_time)

        if data.total_consumed_material_cost is not None:
            project.total_consumed_material_cost = _decimal_or_default(
                data.total_consumed_material_cost
            )

        if data.estimated_costing is not None:
            project.estimated_costing = _decimal_or_default(data.estimated_costing)

        if data.total_costing_amount is not None:
            project.total_costing_amount = _decimal_or_default(data.total_costing_amount)

        if data.total_expense_claim is not None:
            project.total_expense_claim = _decimal_or_default(data.total_expense_claim)

        if data.total_purchase_cost is not None:
            project.total_purchase_cost = _decimal_or_default(data.total_purchase_cost)

        if data.total_sales_amount is not None:
            project.total_sales_amount = _decimal_or_default(data.total_sales_amount)

        if data.total_billable_amount is not None:
            project.total_billable_amount = _decimal_or_default(data.total_billable_amount)

        if data.total_billed_amount is not None:
            project.total_billed_amount = _decimal_or_default(data.total_billed_amount)

        if data.gross_margin is not None:
            project.gross_margin = _decimal_or_default(data.gross_margin)

        if data.per_gross_margin is not None:
            project.per_gross_margin = _decimal_or_default(data.per_gross_margin)

        if data.collect_progress is not None:
            project.collect_progress = data.collect_progress

        if data.frequency is not None:
            project.frequency = data.frequency

        if data.message is not None:
            project.message = data.message

        if data.notes is not None:
            project.notes = data.notes

        # Update dates
        if data.expected_start_date is not None:
            project.expected_start_date = data.expected_start_date

        if data.expected_end_date is not None:
            project.expected_end_date = data.expected_end_date

        if data.actual_start_date is not None:
            project.actual_start_date = data.actual_start_date

        if data.actual_end_date is not None:
            project.actual_end_date = data.actual_end_date

        if data.from_time is not None:
            project.from_time = data.from_time

        if data.to_time is not None:
            project.to_time = data.to_time

        # Replace team members if provided
        if data.users is not None:
            self.replace_team(project_id, data.users)
            changed_fields.append("users")

        # Log status change if changed
        if "status" in changed_fields and old_status != project.status:
            self.activity_service.log_status_change(
                entity_type="project",
                entity_id=project.id,
                old_status=old_status.value,
                new_status=project.status.value,
                company=project.company,
            )
        elif changed_fields:
            # Log other updates
            self.activity_service.log_updated(
                entity_type="project",
                entity_id=project.id,
                changed_fields=changed_fields,
                company=project.company,
            )

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="projects.project.update",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="project",
            entity_id=str(project.id),
            summary=f"Updated project {project.project_name}",
            metadata={"changed_fields": changed_fields, "status": project.status.value},
        )
        return project

    def delete_project(self, project_id: int) -> None:
        """Soft-delete a project.

        Args:
            project_id: ID of the project to delete

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        project = self.get_project(project_id)

        project.is_deleted = True
        project.deleted_at = datetime.now(timezone.utc)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="projects.project.delete",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="project",
            entity_id=str(project.id),
            summary=f"Deleted project {project.project_name}",
        )

    # -------------------------------------------------------------------------
    # Status Transition Methods
    # -------------------------------------------------------------------------

    def complete_project(self, project_id: int) -> Project:
        """Mark a project as completed.

        Args:
            project_id: ID of the project

        Returns:
            The updated project
        """
        return self._transition_status(project_id, ProjectStatus.COMPLETED)

    def cancel_project(
        self,
        project_id: int,
        reason: Optional[str] = None,
    ) -> Project:
        """Cancel a project.

        Args:
            project_id: ID of the project
            reason: Optional cancellation reason

        Returns:
            The updated project
        """
        project = self._transition_status(project_id, ProjectStatus.CANCELLED)
        if reason:
            project.notes = (project.notes or "") + f"\n\nCancellation reason: {reason}"
        return project

    def reopen_project(self, project_id: int) -> Project:
        """Reopen a project that is on hold.

        Args:
            project_id: ID of the project

        Returns:
            The updated project
        """
        return self._transition_status(project_id, ProjectStatus.OPEN)

    def put_on_hold(self, project_id: int) -> Project:
        """Put a project on hold.

        Args:
            project_id: ID of the project

        Returns:
            The updated project
        """
        return self._transition_status(project_id, ProjectStatus.ON_HOLD)

    def _transition_status(
        self,
        project_id: int,
        new_status: ProjectStatus,
    ) -> Project:
        """Internal method to transition project status.

        Args:
            project_id: ID of the project
            new_status: Target status

        Returns:
            The updated project

        Raises:
            ProjectNotFoundError: If project does not exist
            ProjectStatusTransitionError: If transition is not allowed
        """
        project = self.get_project(project_id)

        # Validate transition
        allowed = VALID_PROJECT_TRANSITIONS.get(project.status, set())
        if new_status not in allowed:
            raise ProjectStatusTransitionError(
                current_status=project.status.value,
                target_status=new_status.value,
            )

        return self.update_project(
            project_id,
            ProjectUpdateData(status=new_status),
        )

    # -------------------------------------------------------------------------
    # Team Management Methods
    # -------------------------------------------------------------------------

    def add_team_member(
        self,
        project_id: int,
        user: ProjectUserData,
    ) -> ProjectUser:
        """Add a team member to a project.

        Args:
            project_id: ID of the project
            user: Team member data

        Returns:
            The created ProjectUser

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        project = self.get_project(project_id)

        # Get max idx
        max_idx = max((u.idx or 0 for u in project.users), default=-1)

        return self._add_team_member(project_id, user, max_idx + 1)

    def remove_team_member(self, project_id: int, user_id: int) -> None:
        """Remove a team member from a project.

        Args:
            project_id: ID of the project
            user_id: ID of the ProjectUser to remove

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        self.get_project(project_id)  # Verify project exists

        self.db.query(ProjectUser).filter(
            ProjectUser.id == user_id,
            ProjectUser.project_id == project_id,
        ).delete()

    def replace_team(
        self,
        project_id: int,
        users: List[ProjectUserData],
    ) -> List[ProjectUser]:
        """Replace all team members for a project.

        Args:
            project_id: ID of the project
            users: New list of team members

        Returns:
            List of created ProjectUser records

        Raises:
            ProjectNotFoundError: If project does not exist
        """
        self.get_project(project_id)  # Verify project exists

        # Delete existing team members
        self.db.query(ProjectUser).filter(
            ProjectUser.project_id == project_id
        ).delete(synchronize_session=False)

        # Add new team members
        created = []
        for idx, user_data in enumerate(users):
            created.append(self._add_team_member(project_id, user_data, idx))

        return created

    def _add_team_member(
        self,
        project_id: int,
        user: ProjectUserData,
        idx: int,
    ) -> ProjectUser:
        """Internal method to add a team member."""
        party_id = None
        if user.email:
            email_norm = user.email.strip().lower()
            party = self.db.query(Party).filter(Party.primary_email == email_norm).first()
            if party:
                party_id = party.id
        if not party_id and user.user:
            erpnext_user = self.db.query(ERPNextUser).filter(
                or_(
                    ERPNextUser.erpnext_id == user.user,
                    ERPNextUser.email == user.user,
                )
            ).first()
            if erpnext_user:
                party_id = erpnext_user.party_id
                if not party_id and erpnext_user.employee_id:
                    employee = self.db.get(Employee, erpnext_user.employee_id)
                    if employee and employee.party_id:
                        party_id = employee.party_id

        project_user = ProjectUser(
            project_id=project_id,
            user=user.user,
            full_name=user.full_name,
            email=user.email,
            project_status=user.project_status,
            view_attachments=user.view_attachments,
            welcome_email_sent=user.welcome_email_sent,
            idx=user.idx if user.idx else idx,
            party_id=party_id,
        )
        self.db.add(project_user)
        self.db.flush()
        return project_user

    # -------------------------------------------------------------------------
    # Notification Methods
    # -------------------------------------------------------------------------

    def emit_project_created_notification(self, project: Project) -> None:
        """Emit notification for project creation.

        Args:
            project: The created project
        """
        try:
            from app.models.notification import NotificationEventType
            from app.services.notification_service import NotificationService

            notif_service = NotificationService(self.db)

            # Collect user IDs to notify
            user_ids = []
            if project.project_manager_id:
                user_ids.append(project.project_manager_id)

            for pu in project.users:
                if pu.email:
                    pu_user = (
                        self.db.query(User).filter(User.email == pu.email).first()
                    )
                    if pu_user and pu_user.id not in user_ids:
                        user_ids.append(pu_user.id)

            actor_name = None
            if self.principal:
                actor_name = getattr(self.principal, "name", None) or getattr(
                    self.principal, "email", None
                )

            notif_service.emit_event(
                event_type=NotificationEventType.PROJECT_CREATED,
                payload={
                    "project_id": project.id,
                    "project_name": project.project_name,
                    "created_by_name": actor_name,
                    "expected_end_date": (
                        str(project.expected_end_date)
                        if project.expected_end_date
                        else None
                    ),
                },
                entity_type="project",
                entity_id=project.id,
                user_ids=user_ids if user_ids else None,
                company=project.company,
            )
        except Exception:
            pass  # Don't fail if notification fails

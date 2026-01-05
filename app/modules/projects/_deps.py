"""
Shared dependencies for projects routes.

This module contains common imports, helpers, and permission dependencies
used across all projects route modules.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Models - Projects
from app.models.project import (
    Project, ProjectStatus, ProjectPriority, ProjectType,
    Milestone, MilestoneStatus,
)

# Models - Tasks
from app.models.task import Task, TaskStatus, TaskPriority

# Models - Related
from app.services.projects import (
    ActivityService,
    AttachmentService,
    CommentCreateData,
    CommentService,
    MilestoneFilters,
    MilestoneService,
    ProjectService,
    ProjectsLookupService,
    TaskFilters,
    TaskService,
)
from app.services.types import PaginationParams

# Permission dependencies
RequireProjectsRead = Depends(require_scope("projects:read"))
RequireProjectsWrite = Depends(require_scope("projects:write"))

# Template environment
templates = get_template_env()


# =============================================================================
# COMMON HELPER FUNCTIONS
# =============================================================================

def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string value from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    """Extract integer value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _form_date(form: Any, key: str) -> Optional[datetime]:
    """Extract date value from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile) or not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _form_decimal(form: Any, key: str, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Extract decimal value from form data."""
    from decimal import InvalidOperation
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return Decimal(value)
    except InvalidOperation:
        return default


# =============================================================================
# PROJECT ENUM OPTIONS
# =============================================================================

def get_status_options():
    """Get project status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ProjectStatus
    ]


def get_priority_options():
    """Get project priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in ProjectPriority
    ]


def get_type_options():
    """Get project type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in ProjectType
    ]


def get_task_status_options():
    """Get task status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in TaskStatus
    ]


def get_task_priority_options():
    """Get task priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in TaskPriority
    ]


def get_milestone_status_options():
    """Get milestone status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in MilestoneStatus
    ]


# =============================================================================
# DYNAMIC OPTIONS FROM DATABASE
# =============================================================================

def get_customer_options(db):
    """Get customer accounts for project assignment dropdown."""
    lookup = ProjectsLookupService(db)
    return lookup.list_customer_options()


def get_manager_options(db):
    """Get active employees for project manager dropdown."""
    lookup = ProjectsLookupService(db)
    return lookup.list_manager_options()


def get_project_options(db):
    """Get active projects for parent project or linking dropdown."""
    lookup = ProjectsLookupService(db)
    return lookup.list_project_options()


def get_milestone_options(db, project_id: int):
    """Get milestones for a specific project."""
    lookup = ProjectsLookupService(db)
    return lookup.list_milestone_options(project_id)


# =============================================================================
# ADDITIONAL MODELS FOR COMMENTS & ATTACHMENTS
# =============================================================================

from app.models.project import (
    ProjectComment,
    ProjectActivity,
)
from app.models.task import TaskDependency
from app.models.document_attachment import DocumentAttachment
from typing import Dict, List


# =============================================================================
# PROJECTS WEB SERVICE
# =============================================================================

class ProjectsWebService:
    """
    Service class for Projects UI operations.

    Encapsulates operations for Gantt, comments, and attachments.
    """

    def __init__(
        self,
        db,
        user_id: Optional[int] = None,
        principal: Optional[Any] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.principal = principal
        self._project_service: Optional[ProjectService] = None
        self._task_service: Optional[TaskService] = None
        self._milestone_service: Optional[MilestoneService] = None
        self._comment_service: Optional[CommentService] = None
        self._attachment_service: Optional[AttachmentService] = None
        self._activity_service: Optional[ActivityService] = None

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService(self.db, self.principal)
        return self._project_service

    @property
    def task_service(self) -> TaskService:
        if self._task_service is None:
            self._task_service = TaskService(self.db, self.principal)
        return self._task_service

    @property
    def milestone_service(self) -> MilestoneService:
        if self._milestone_service is None:
            self._milestone_service = MilestoneService(self.db, self.principal)
        return self._milestone_service

    @property
    def comment_service(self) -> CommentService:
        if self._comment_service is None:
            self._comment_service = CommentService(self.db, self.principal)
        return self._comment_service

    @property
    def attachment_service(self) -> AttachmentService:
        if self._attachment_service is None:
            self._attachment_service = AttachmentService(self.db, self.principal)
        return self._attachment_service

    @property
    def activity_service(self) -> ActivityService:
        if self._activity_service is None:
            self._activity_service = ActivityService(self.db, self.principal)
        return self._activity_service

    # =========================================================================
    # GANTT DATA
    # =========================================================================

    def get_gantt_data(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get all tasks with dependencies for Gantt chart visualization."""
        try:
            project = self.project_service.get_project(project_id)
        except Exception:
            return None

        if not project:
            return None

        # Get all tasks for this project
        tasks = self.task_service.list_tasks_with_dependencies(project_id)

        task_list = []
        min_date = None
        max_date = None

        for task in tasks:
            # Extract dependency IDs
            depends_on_ids = [
                dep.dependent_task_id
                for dep in task.depends_on
                if dep.dependent_task_id is not None
            ] if hasattr(task, 'depends_on') else []

            task_data = {
                "id": task.id,
                "subject": task.subject,
                "status": task.status.value if task.status else "open",
                "priority": task.priority.value if task.priority else "medium",
                "progress": float(task.progress) if task.progress else 0,
                "exp_start_date": task.exp_start_date.isoformat() if task.exp_start_date else None,
                "exp_end_date": task.exp_end_date.isoformat() if task.exp_end_date else None,
                "assigned_to": task.assigned_to,
                "parent_task_id": task.parent_task_id,
                "is_group": getattr(task, 'is_group', False),
                "depends_on": depends_on_ids,
            }
            task_list.append(task_data)

            # Track date range
            if task.exp_start_date:
                if min_date is None or task.exp_start_date < min_date:
                    min_date = task.exp_start_date
            if task.exp_end_date:
                if max_date is None or task.exp_end_date > max_date:
                    max_date = task.exp_end_date

        # Get milestones
        milestones = self.milestone_service.list_project_milestones(
            project_id,
            MilestoneFilters(),
        )

        milestone_list = [
            {
                "id": m.id,
                "name": m.name,
                "due_date": m.planned_end_date.isoformat() if m.planned_end_date else None,
                "status": m.status.value if m.status else "pending",
            }
            for m in milestones
        ]

        return {
            "project": {
                "id": project.id,
                "name": (
                    getattr(project, "project_name", None)
                    or getattr(project, "name", None)
                    or f"Project {project.id}"
                ),
                "start_date": (
                    project.start_date.isoformat()
                    if getattr(project, "start_date", None)
                    else (
                        project.expected_start_date.isoformat()
                        if getattr(project, "expected_start_date", None)
                        else None
                    )
                ),
                "end_date": (
                    project.end_date.isoformat()
                    if getattr(project, "end_date", None)
                    else (
                        project.expected_end_date.isoformat()
                        if getattr(project, "expected_end_date", None)
                        else None
                    )
                ),
            },
            "tasks": task_list,
            "milestones": milestone_list,
            "date_range": {
                "min_date": min_date.isoformat() if min_date else None,
                "max_date": max_date.isoformat() if max_date else None,
            },
        }

    # =========================================================================
    # COMMENTS
    # =========================================================================

    def list_comments(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List comments for an entity (project, task, or milestone)."""
        pagination = PaginationParams(offset=offset, limit=limit)
        result = self.comment_service.list_entity_comments(
            entity_type, entity_id, pagination
        )
        return {
            "items": result.items,
            "total": result.total,
            "limit": result.limit,
            "offset": result.offset,
        }

    def create_comment(
        self,
        entity_type: str,
        entity_id: int,
        content: str,
    ) -> ProjectComment:
        """Create a new comment."""
        comment = self.comment_service.create_comment(
            CommentCreateData(
                entity_type=entity_type,
                entity_id=entity_id,
                content=content,
            )
        )
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def delete_comment(self, comment_id: int) -> bool:
        """Soft delete a comment."""
        try:
            self.comment_service.delete_comment(comment_id)
            self.db.commit()
            return True
        except Exception:
            return False

    # =========================================================================
    # ATTACHMENTS
    # =========================================================================

    def list_attachments(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[DocumentAttachment]:
        """List attachments for an entity."""
        return self.attachment_service.list_entity_attachments(entity_type, entity_id)

    # =========================================================================
    # ACTIVITY LOG
    # =========================================================================

    def list_activity(
        self,
        project_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProjectActivity]:
        """List activity log for a project."""
        return self.activity_service.get_project_timeline(
            project_id, limit=limit, offset=offset
        )

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
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

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
from app.models.customer import Customer
from app.models.employee import Employee

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
    """Get customers for project assignment dropdown."""
    customers = db.query(Customer).filter(
        Customer.is_deleted == False
    ).order_by(Customer.name).limit(100).all()
    return [
        {"value": str(c.id), "label": c.name}
        for c in customers
    ]


def get_manager_options(db):
    """Get active employees for project manager dropdown."""
    employees = db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == "active"
    ).order_by(Employee.first_name).all()
    return [
        {"value": str(e.id), "label": f"{e.first_name} {e.last_name}".strip() or e.email}
        for e in employees
    ]


def get_project_options(db):
    """Get active projects for parent project or linking dropdown."""
    projects = db.query(Project).filter(
        Project.is_deleted == False,
        Project.status.notin_(["completed", "cancelled"])
    ).order_by(Project.name).limit(100).all()
    return [
        {"value": str(p.id), "label": p.name}
        for p in projects
    ]


def get_milestone_options(db, project_id: int):
    """Get milestones for a specific project."""
    milestones = db.query(Milestone).filter(
        Milestone.project_id == project_id,
        Milestone.is_deleted == False
    ).order_by(Milestone.planned_end_date).all()
    return [
        {"value": str(m.id), "label": m.name}
        for m in milestones
    ]


# =============================================================================
# ADDITIONAL MODELS FOR COMMENTS & ATTACHMENTS
# =============================================================================

from app.models.project import (
    ProjectComment,
    ProjectActivity,
    ProjectActivityType,
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

    def __init__(self, db, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # GANTT DATA
    # =========================================================================

    def get_gantt_data(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get all tasks with dependencies for Gantt chart visualization."""
        project = self.db.query(Project).filter(
            Project.id == project_id,
            Project.is_deleted == False
        ).first()

        if not project:
            return None

        # Get all tasks for this project
        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()

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
        milestones = self.db.query(Milestone).filter(
            Milestone.project_id == project_id,
            Milestone.is_deleted == False
        ).all()

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
                "name": project.name,
                "start_date": project.start_date.isoformat() if project.start_date else None,
                "end_date": project.end_date.isoformat() if project.end_date else None,
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
        query = self.db.query(ProjectComment).filter(
            ProjectComment.entity_type == entity_type,
            ProjectComment.entity_id == entity_id,
            ProjectComment.is_deleted == False,
        )

        total = query.count()
        comments = query.order_by(ProjectComment.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "items": comments,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def create_comment(
        self,
        entity_type: str,
        entity_id: int,
        content: str,
        author_name: str,
        author_email: str,
    ) -> ProjectComment:
        """Create a new comment."""
        comment = ProjectComment(
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            author_id=self.user_id,
            author_name=author_name,
            author_email=author_email,
            created_at=datetime.utcnow(),
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def delete_comment(self, comment_id: int) -> bool:
        """Soft delete a comment."""
        comment = self.db.query(ProjectComment).filter(
            ProjectComment.id == comment_id
        ).first()
        if not comment:
            return False

        comment.is_deleted = True
        self.db.commit()
        return True

    # =========================================================================
    # ATTACHMENTS
    # =========================================================================

    def list_attachments(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[DocumentAttachment]:
        """List attachments for an entity."""
        doctype = f"project_{entity_type}"
        attachments: list[DocumentAttachment] = []
        if entity_type in ("project", "task", "milestone"):
            attachments = self.db.query(DocumentAttachment).filter(
                DocumentAttachment.doctype == doctype,
                DocumentAttachment.document_id == entity_id,
            ).order_by(DocumentAttachment.uploaded_at.desc()).all()

        return attachments

    # =========================================================================
    # ACTIVITY LOG
    # =========================================================================

    def list_activity(
        self,
        project_id: int,
        limit: int = 50,
    ) -> List[ProjectActivity]:
        """List activity log for a project."""
        activities: list[ProjectActivity] = self.db.query(ProjectActivity).filter(
            ProjectActivity.entity_type == "project",
            ProjectActivity.entity_id == project_id,
        ).order_by(ProjectActivity.created_at.desc()).limit(limit).all()
        return activities

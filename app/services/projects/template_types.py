"""Type definitions for project template service.

These dataclasses define the contract for template operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from app.models.project import ProjectPriority

__all__ = [
    "TaskTemplateData",
    "MilestoneTemplateData",
    "TemplateCreateData",
    "TemplateUpdateData",
    "CreateFromTemplateData",
    "TemplateExpansionResult",
]


@dataclass
class TaskTemplateData:
    """Data for a task template within a project template."""

    subject: str
    description: Optional[str] = None
    priority: Optional[str] = None  # low, medium, high
    start_day_offset: int = 0
    duration_days: int = 1
    default_assigned_role: Optional[str] = None
    is_group: bool = False
    idx: int = 0
    parent_template_idx: Optional[int] = None  # Reference to parent task template by idx
    milestone_template_idx: Optional[int] = None  # Reference to milestone template by idx


@dataclass
class MilestoneTemplateData:
    """Data for a milestone template within a project template."""

    name: str
    description: Optional[str] = None
    start_day_offset: int = 0
    end_day_offset: int = 7
    idx: int = 0


@dataclass
class TemplateCreateData:
    """Data for creating a project template."""

    name: str
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: bool = True
    company: Optional[str] = None
    task_templates: Optional[List[TaskTemplateData]] = field(default=None)
    milestone_templates: Optional[List[MilestoneTemplateData]] = field(default=None)


@dataclass
class TemplateUpdateData:
    """Data for updating a project template (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: Optional[bool] = None
    # None = no change, empty list = clear all
    task_templates: Optional[List[TaskTemplateData]] = None
    milestone_templates: Optional[List[MilestoneTemplateData]] = None


@dataclass
class CreateFromTemplateData:
    """Data for creating a project from a template."""

    template_id: int
    project_name: str
    expected_start_date: Optional[date] = None
    customer_account_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    notes: Optional[str] = None
    company: Optional[str] = None


@dataclass
class TemplateExpansionResult:
    """Result of expanding a template into a project."""

    project_id: int
    project_name: str
    template_id: int
    milestones_created: int
    tasks_created: int

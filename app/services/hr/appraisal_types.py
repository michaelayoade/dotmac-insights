"""Type definitions for appraisal service.

These dataclasses define the contract for appraisal operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.models.hr_appraisal import AppraisalStatus

__all__ = [
    # Template
    "TemplateFilters",
    "TemplateCreateData",
    "TemplateUpdateData",
    "TemplateGoalData",
    # Appraisal
    "AppraisalFilters",
    "AppraisalCreateData",
    "AppraisalUpdateData",
    "AppraisalGoalData",
    "AppraisalScoreData",
    # Results
    "AppraisalMetrics",
    "EmployeeAppraisalSummary",
    "TeamAppraisalSummary",
]


# ==============================================================================
# Appraisal Template Types
# ==============================================================================


@dataclass
class TemplateGoalData:
    """Goal/KRA definition in a template."""

    kra: str
    per_weightage: Decimal = Decimal("0")
    idx: int = 0


@dataclass
class TemplateFilters:
    """Filters for listing appraisal templates."""

    search: Optional[str] = None  # Search name/description


@dataclass
class TemplateCreateData:
    """Data for creating an appraisal template."""

    template_name: str
    description: Optional[str] = None
    goals: List[TemplateGoalData] = field(default_factory=list)


@dataclass
class TemplateUpdateData:
    """Data for updating an appraisal template (all fields optional)."""

    template_name: Optional[str] = None
    description: Optional[str] = None
    goals: Optional[List[TemplateGoalData]] = None


# ==============================================================================
# Appraisal Types
# ==============================================================================


@dataclass
class AppraisalGoalData:
    """Individual goal data in an appraisal."""

    kra: str
    per_weightage: Decimal = Decimal("0")
    goal: Optional[str] = None
    score_earned: Decimal = Decimal("0")
    self_score: Decimal = Decimal("0")
    idx: int = 0


@dataclass
class AppraisalFilters:
    """Filters for listing appraisals."""

    employee_id: Optional[int] = None
    appraisal_template_id: Optional[int] = None
    status: Optional[AppraisalStatus] = None
    company: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None  # Search employee name


@dataclass
class AppraisalCreateData:
    """Data for creating an appraisal."""

    employee_id: int
    employee: str
    start_date: date
    end_date: date
    employee_name: Optional[str] = None
    appraisal_template_id: Optional[int] = None
    appraisal_template: Optional[str] = None
    company: Optional[str] = None
    feedback: Optional[str] = None
    reflections: Optional[str] = None
    goals: List[AppraisalGoalData] = field(default_factory=list)


@dataclass
class AppraisalUpdateData:
    """Data for updating an appraisal (all fields optional)."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    feedback: Optional[str] = None
    reflections: Optional[str] = None
    goals: Optional[List[AppraisalGoalData]] = None


@dataclass
class AppraisalScoreData:
    """Data for scoring an appraisal."""

    goals: List[AppraisalGoalData]
    feedback: Optional[str] = None


# ==============================================================================
# Result Types
# ==============================================================================


@dataclass
class AppraisalMetrics:
    """Appraisal metrics and statistics."""

    total_templates: int = 0
    total_appraisals: int = 0
    draft_count: int = 0
    submitted_count: int = 0
    completed_count: int = 0
    cancelled_count: int = 0
    average_score: Optional[Decimal] = None
    current_period_count: int = 0


@dataclass
class EmployeeAppraisalSummary:
    """Appraisal summary for an employee."""

    employee_id: int
    employee_name: str
    total_appraisals: int = 0
    completed_appraisals: int = 0
    average_score: Optional[Decimal] = None
    latest_score: Optional[Decimal] = None
    latest_appraisal_date: Optional[date] = None


@dataclass
class TeamAppraisalSummary:
    """Appraisal summary for a team/department."""

    department_id: Optional[int] = None
    department_name: Optional[str] = None
    total_employees: int = 0
    appraised_count: int = 0
    pending_count: int = 0
    average_score: Optional[Decimal] = None
    completion_rate: Optional[Decimal] = None

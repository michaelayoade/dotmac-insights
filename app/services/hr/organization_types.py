"""Type definitions for organization service.

These dataclasses define the contract for department, designation, and team operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

__all__ = [
    # Department types
    "DepartmentFilters",
    "DepartmentCreateData",
    "DepartmentUpdateData",
    "DepartmentNode",
    "DepartmentHeadcount",
    # Designation types
    "DesignationFilters",
    "DesignationCreateData",
    "DesignationUpdateData",
    "DesignationHeadcount",
    # HD Team types
    "HDTeamFilters",
    "HDTeamCreateData",
    "HDTeamUpdateData",
    "TeamMemberData",
]


# ==============================================================================
# Department Types
# ==============================================================================


@dataclass
class DepartmentFilters:
    """Filters for listing departments."""

    company: Optional[str] = None
    is_group: Optional[bool] = None
    parent_department: Optional[str] = None
    search: Optional[str] = None


@dataclass
class DepartmentCreateData:
    """Data for creating a department."""

    department_name: str
    parent_department: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False


@dataclass
class DepartmentUpdateData:
    """Data for updating a department (all fields optional)."""

    department_name: Optional[str] = None
    parent_department: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None


@dataclass
class DepartmentNode:
    """Node in department hierarchy tree."""

    id: int
    department_name: str
    parent_department: Optional[str]
    company: Optional[str]
    is_group: bool
    children: List["DepartmentNode"] = field(default_factory=list)


@dataclass
class DepartmentHeadcount:
    """Headcount information for a department."""

    department_id: int
    department_name: str
    total_employees: int
    active_employees: int
    on_leave: int
    terminated: int


# ==============================================================================
# Designation Types
# ==============================================================================


@dataclass
class DesignationHeadcount:
    """Headcount information for a designation."""

    designation_id: int
    designation_name: str
    total_employees: int
    active_employees: int
    on_leave: int
    terminated: int


@dataclass
class DesignationFilters:
    """Filters for listing designations."""

    search: Optional[str] = None


@dataclass
class DesignationCreateData:
    """Data for creating a designation."""

    designation_name: str
    description: Optional[str] = None


@dataclass
class DesignationUpdateData:
    """Data for updating a designation (all fields optional)."""

    designation_name: Optional[str] = None
    description: Optional[str] = None


# ==============================================================================
# HD Team Types
# ==============================================================================


@dataclass
class HDTeamFilters:
    """Filters for listing helpdesk teams."""

    search: Optional[str] = None
    assignment_rule: Optional[str] = None


@dataclass
class HDTeamCreateData:
    """Data for creating a helpdesk team."""

    team_name: str
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    ignore_restrictions: bool = False


@dataclass
class HDTeamUpdateData:
    """Data for updating a helpdesk team (all fields optional)."""

    team_name: Optional[str] = None
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    ignore_restrictions: Optional[bool] = None


@dataclass
class TeamMemberData:
    """Data for adding a team member."""

    user: str
    user_name: Optional[str] = None
    employee_id: Optional[int] = None

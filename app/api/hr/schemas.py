"""Pydantic schemas for HR module APIs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.employee import EmploymentStatus


# -------------------- Employee --------------------


class EmployeeCreateRequest(BaseModel):
    """Create a new employee record.

    Required fields: name. All other fields are optional.
    """

    name: str = Field(..., description="Full name of the employee", min_length=1, max_length=255)
    employee_number: Optional[str] = Field(None, description="Unique employee ID/number", max_length=50)
    email: Optional[str] = Field(None, description="Work email address", max_length=255)
    phone: Optional[str] = Field(None, description="Contact phone number", max_length=50)
    designation: Optional[str] = Field(None, description="Job title/designation name")
    department: Optional[str] = Field(None, description="Department name")
    reports_to: Optional[str] = Field(None, description="Manager's name or employee number")
    department_id: Optional[int] = Field(None, description="Department ID reference")
    designation_id: Optional[int] = Field(None, description="Designation ID reference")
    reports_to_id: Optional[int] = Field(None, description="Manager's employee ID")
    status: Optional[str] = Field(EmploymentStatus.ACTIVE.value, description="Employment status")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    date_of_joining: Optional[datetime] = Field(None, description="Employee start date")
    date_of_leaving: Optional[datetime] = Field(None, description="Employee end date (if applicable)")
    salary: Optional[Decimal] = Field(None, description="Monthly salary amount", ge=0)
    currency: Optional[str] = Field("NGN", description="Salary currency code", max_length=3)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "employee_number": "EMP001",
                "email": "john.doe@company.com",
                "designation": "Software Engineer",
                "department": "Engineering",
                "status": "active",
                "employment_type": "full_time",
                "salary": 500000,
                "currency": "NGN",
            }
        }
    )

    @field_validator("salary", mode="before")
    @classmethod
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


class EmployeeUpdateRequest(BaseModel):
    """Update an existing employee record.

    All fields are optional - only provided fields will be updated.
    """

    name: Optional[str] = Field(None, description="Full name of the employee", max_length=255)
    employee_number: Optional[str] = Field(None, description="Unique employee ID/number", max_length=50)
    email: Optional[str] = Field(None, description="Work email address", max_length=255)
    phone: Optional[str] = Field(None, description="Contact phone number", max_length=50)
    designation: Optional[str] = Field(None, description="Job title/designation name")
    department: Optional[str] = Field(None, description="Department name")
    reports_to: Optional[str] = Field(None, description="Manager's name or employee number")
    department_id: Optional[int] = Field(None, description="Department ID reference")
    designation_id: Optional[int] = Field(None, description="Designation ID reference")
    reports_to_id: Optional[int] = Field(None, description="Manager's employee ID")
    status: Optional[str] = Field(None, description="Employment status")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    date_of_joining: Optional[datetime] = Field(None, description="Employee start date")
    date_of_leaving: Optional[datetime] = Field(None, description="Employee end date (if applicable)")
    salary: Optional[Decimal] = Field(None, description="Monthly salary amount", ge=0)
    currency: Optional[str] = Field(None, description="Salary currency code", max_length=3)

    @field_validator("salary", mode="before")
    @classmethod
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


# -------------------- Department --------------------


class DepartmentCreateRequest(BaseModel):
    """Create a new department.

    Departments can be organized hierarchically using parent_department.
    """

    department_name: str = Field(..., description="Name of the department", min_length=1, max_length=255)
    parent_department: Optional[str] = Field(None, description="Parent department for hierarchy")
    company: Optional[str] = Field(None, description="Company this department belongs to")
    is_group: bool = Field(False, description="True if this is a group (parent) department")
    lft: Optional[int] = Field(None, description="Left value for nested set model")
    rgt: Optional[int] = Field(None, description="Right value for nested set model")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "department_name": "Engineering",
                "company": "DotMac Ltd",
                "is_group": True,
            }
        }
    )


class DepartmentUpdateRequest(BaseModel):
    """Update an existing department."""

    department_name: Optional[str] = Field(None, description="Name of the department", max_length=255)
    parent_department: Optional[str] = Field(None, description="Parent department for hierarchy")
    company: Optional[str] = Field(None, description="Company this department belongs to")
    is_group: Optional[bool] = Field(None, description="True if this is a group (parent) department")
    lft: Optional[int] = Field(None, description="Left value for nested set model")
    rgt: Optional[int] = Field(None, description="Right value for nested set model")


# -------------------- Designation --------------------


class DesignationCreateRequest(BaseModel):
    """Create a new job designation/title."""

    designation_name: str = Field(..., description="Job title/designation name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Description of the role and responsibilities")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "designation_name": "Senior Software Engineer",
                "description": "Leads technical projects and mentors junior developers",
            }
        }
    )


class DesignationUpdateRequest(BaseModel):
    """Update an existing designation."""

    designation_name: Optional[str] = Field(None, description="Job title/designation name", max_length=255)
    description: Optional[str] = Field(None, description="Description of the role and responsibilities")


# -------------------- ERPNext User --------------------


class ERPNextUserCreateRequest(BaseModel):
    """Create an ERPNext user record for system integration."""

    email: str = Field(..., description="User's email address (used as login)", max_length=255)
    full_name: Optional[str] = Field(None, description="Full display name", max_length=255)
    first_name: Optional[str] = Field(None, description="First name", max_length=100)
    last_name: Optional[str] = Field(None, description="Last name", max_length=100)
    enabled: bool = Field(True, description="Whether the user account is active")
    user_type: Optional[str] = Field(None, description="User type (System User, Website User, etc.)")
    employee_id: Optional[int] = Field(None, description="Linked employee record ID")


class ERPNextUserUpdateRequest(BaseModel):
    """Update an ERPNext user record."""

    email: Optional[str] = Field(None, description="User's email address", max_length=255)
    full_name: Optional[str] = Field(None, description="Full display name", max_length=255)
    first_name: Optional[str] = Field(None, description="First name", max_length=100)
    last_name: Optional[str] = Field(None, description="Last name", max_length=100)
    enabled: Optional[bool] = Field(None, description="Whether the user account is active")
    user_type: Optional[str] = Field(None, description="User type (System User, Website User, etc.)")
    employee_id: Optional[int] = Field(None, description="Linked employee record ID")


# -------------------- HD Team --------------------


class HDTeamCreateRequest(BaseModel):
    """Create a helpdesk/support team."""

    team_name: str = Field(..., description="Name of the support team", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Team description and responsibilities")
    assignment_rule: Optional[str] = Field(None, description="Ticket assignment rule (round_robin, load_balance, etc.)")
    ignore_restrictions: bool = Field(False, description="Bypass assignment restrictions")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team_name": "Technical Support",
                "description": "Handles technical issues and escalations",
                "assignment_rule": "round_robin",
            }
        }
    )


class HDTeamUpdateRequest(BaseModel):
    """Update a helpdesk team."""

    team_name: Optional[str] = Field(None, description="Name of the support team", max_length=255)
    description: Optional[str] = Field(None, description="Team description and responsibilities")
    assignment_rule: Optional[str] = Field(None, description="Ticket assignment rule")
    ignore_restrictions: Optional[bool] = Field(None, description="Bypass assignment restrictions")


# -------------------- HD Team Member --------------------


class HDTeamMemberCreateRequest(BaseModel):
    """Add a member to a helpdesk team."""

    team_id: int = Field(..., description="ID of the team to add member to")
    user: str = Field(..., description="User email or identifier", max_length=255)
    user_name: Optional[str] = Field(None, description="Display name of the user", max_length=255)
    employee_id: Optional[int] = Field(None, description="Linked employee record ID")


class HDTeamMemberUpdateRequest(BaseModel):
    """Update a team member record."""

    user: Optional[str] = Field(None, description="User email or identifier", max_length=255)
    user_name: Optional[str] = Field(None, description="Display name of the user", max_length=255)
    employee_id: Optional[int] = Field(None, description="Linked employee record ID")

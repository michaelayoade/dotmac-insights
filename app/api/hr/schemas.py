"""Pydantic schemas for HR module APIs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.employee import EmploymentStatus


# -------------------- Employee --------------------


class EmployeeCreateRequest(BaseModel):
    name: str
    employee_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    reports_to: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    status: Optional[str] = EmploymentStatus.ACTIVE.value
    employment_type: Optional[str] = None
    date_of_joining: Optional[datetime] = None
    date_of_leaving: Optional[datetime] = None
    salary: Optional[Decimal] = None
    currency: Optional[str] = "NGN"

    @field_validator("salary", mode="before")
    @classmethod
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


class EmployeeUpdateRequest(BaseModel):
    name: Optional[str] = None
    employee_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    reports_to: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    status: Optional[str] = None
    employment_type: Optional[str] = None
    date_of_joining: Optional[datetime] = None
    date_of_leaving: Optional[datetime] = None
    salary: Optional[Decimal] = None
    currency: Optional[str] = None

    @field_validator("salary", mode="before")
    @classmethod
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


# -------------------- Department --------------------


class DepartmentCreateRequest(BaseModel):
    department_name: str
    parent_department: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    lft: Optional[int] = None
    rgt: Optional[int] = None


class DepartmentUpdateRequest(BaseModel):
    department_name: Optional[str] = None
    parent_department: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


# -------------------- Designation --------------------


class DesignationCreateRequest(BaseModel):
    designation_name: str
    description: Optional[str] = None


class DesignationUpdateRequest(BaseModel):
    designation_name: Optional[str] = None
    description: Optional[str] = None


# -------------------- ERPNext User --------------------


class ERPNextUserCreateRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    enabled: bool = True
    user_type: Optional[str] = None
    employee_id: Optional[int] = None


class ERPNextUserUpdateRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    enabled: Optional[bool] = None
    user_type: Optional[str] = None
    employee_id: Optional[int] = None


# -------------------- HD Team --------------------


class HDTeamCreateRequest(BaseModel):
    team_name: str
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    ignore_restrictions: bool = False


class HDTeamUpdateRequest(BaseModel):
    team_name: Optional[str] = None
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    ignore_restrictions: Optional[bool] = None


# -------------------- HD Team Member --------------------


class HDTeamMemberCreateRequest(BaseModel):
    team_id: int
    user: str
    user_name: Optional[str] = None
    employee_id: Optional[int] = None


class HDTeamMemberUpdateRequest(BaseModel):
    user: Optional[str] = None
    user_name: Optional[str] = None
    employee_id: Optional[int] = None

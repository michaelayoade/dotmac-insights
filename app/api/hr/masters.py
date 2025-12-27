"""HR master data endpoints: employees, departments, designations, users, teams."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department, Designation, ERPNextUser, HDTeam, HDTeamMember

router = APIRouter()


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
    def _to_decimal(cls, value):
        return Decimal(str(value)) if value is not None else None


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


class DesignationCreateRequest(BaseModel):
    designation_name: str
    description: Optional[str] = None


class DesignationUpdateRequest(BaseModel):
    designation_name: Optional[str] = None
    description: Optional[str] = None


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


class HDTeamMemberCreateRequest(BaseModel):
    team_id: int
    user: str
    user_name: Optional[str] = None
    employee_id: Optional[int] = None


class HDTeamMemberUpdateRequest(BaseModel):
    user: Optional[str] = None
    user_name: Optional[str] = None
    employee_id: Optional[int] = None


@router.get("/employees", dependencies=[Depends(Require("hr:read"))])
def list_employees(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employees."""
    query = db.query(Employee)
    if not include_deleted:
        query = query.filter(Employee.is_deleted == False)
    if search:
        query = query.filter(Employee.name.ilike(f"%{search}%"))

    total = query.count()
    employees = query.order_by(Employee.name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "employees": [
            {
                "id": emp.id,
                "erpnext_id": emp.erpnext_id,
                "employee_number": emp.employee_number,
                "name": emp.name,
                "email": emp.email,
                "phone": emp.phone,
                "designation": emp.designation,
                "department": emp.department,
                "status": emp.status.value if emp.status else None,
                "employment_type": emp.employment_type,
                "date_of_joining": emp.date_of_joining.isoformat() if emp.date_of_joining else None,
                "date_of_leaving": emp.date_of_leaving.isoformat() if emp.date_of_leaving else None,
                "salary": float(emp.salary) if emp.salary is not None else None,
                "currency": emp.currency,
            }
            for emp in employees
        ],
    }


@router.get("/employees/{employee_id}", dependencies=[Depends(Require("hr:read"))])
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an employee by id."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {
        "id": employee.id,
        "erpnext_id": employee.erpnext_id,
        "employee_number": employee.employee_number,
        "name": employee.name,
        "email": employee.email,
        "phone": employee.phone,
        "designation": employee.designation,
        "department": employee.department,
        "status": employee.status.value if employee.status else None,
        "employment_type": employee.employment_type,
        "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
        "date_of_leaving": employee.date_of_leaving.isoformat() if employee.date_of_leaving else None,
        "salary": float(employee.salary) if employee.salary is not None else None,
        "currency": employee.currency,
    }


@router.post("/employees", dependencies=[Depends(Require("hr:write"))])
def create_employee(
    payload: EmployeeCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an employee locally."""
    employee = Employee(
        employee_number=payload.employee_number,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        designation=payload.designation,
        department=payload.department,
        reports_to=payload.reports_to,
        department_id=payload.department_id,
        designation_id=payload.designation_id,
        reports_to_id=payload.reports_to_id,
        status=EmploymentStatus(payload.status) if payload.status else EmploymentStatus.ACTIVE,
        employment_type=payload.employment_type,
        date_of_joining=payload.date_of_joining,
        date_of_leaving=payload.date_of_leaving,
        salary=payload.salary,
        currency=payload.currency or "NGN",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return {"id": employee.id}


@router.patch("/employees/{employee_id}", dependencies=[Depends(Require("hr:write"))])
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an employee locally."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"]:
        update_data["status"] = EmploymentStatus(update_data["status"])

    for key, value in update_data.items():
        setattr(employee, key, value)

    db.commit()
    db.refresh(employee)
    return {"id": employee.id}


@router.delete("/employees/{employee_id}", dependencies=[Depends(Require("hr:write"))])
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete an employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or employee.is_deleted:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee.is_deleted = True
    employee.deleted_at = datetime.utcnow()
    employee.deleted_by_id = principal.id
    db.commit()
    return {"status": "disabled", "employee_id": employee_id}


@router.get("/departments", dependencies=[Depends(Require("hr:read"))])
def list_departments(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List departments."""
    query = db.query(Department)
    if search:
        query = query.filter(Department.department_name.ilike(f"%{search}%"))

    total = query.count()
    departments = query.order_by(Department.department_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "departments": [
            {
                "id": dept.id,
                "erpnext_id": dept.erpnext_id,
                "department_name": dept.department_name,
                "parent_department": dept.parent_department,
                "company": dept.company,
                "is_group": dept.is_group,
                "lft": dept.lft,
                "rgt": dept.rgt,
            }
            for dept in departments
        ],
    }


@router.get("/departments/{department_id}", dependencies=[Depends(Require("hr:read"))])
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a department by id."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    return {
        "id": department.id,
        "erpnext_id": department.erpnext_id,
        "department_name": department.department_name,
        "parent_department": department.parent_department,
        "company": department.company,
        "is_group": department.is_group,
        "lft": department.lft,
        "rgt": department.rgt,
    }


@router.post("/departments", dependencies=[Depends(Require("hr:write"))])
def create_department(
    payload: DepartmentCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a department locally."""
    department = Department(
        department_name=payload.department_name,
        parent_department=payload.parent_department,
        company=payload.company,
        is_group=payload.is_group,
        lft=payload.lft,
        rgt=payload.rgt,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return {"id": department.id}


@router.patch("/departments/{department_id}", dependencies=[Depends(Require("hr:write"))])
def update_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a department locally."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(department, key, value)

    db.commit()
    db.refresh(department)
    return {"id": department.id}


@router.delete("/departments/{department_id}", dependencies=[Depends(Require("hr:write"))])
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a department."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    db.delete(department)
    db.commit()
    return {"status": "deleted", "department_id": department_id}


@router.get("/designations", dependencies=[Depends(Require("hr:read"))])
def list_designations(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List designations."""
    query = db.query(Designation)
    if search:
        query = query.filter(Designation.designation_name.ilike(f"%{search}%"))

    total = query.count()
    designations = query.order_by(Designation.designation_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "designations": [
            {
                "id": desig.id,
                "erpnext_id": desig.erpnext_id,
                "designation_name": desig.designation_name,
                "description": desig.description,
            }
            for desig in designations
        ],
    }


@router.get("/designations/{designation_id}", dependencies=[Depends(Require("hr:read"))])
def get_designation(
    designation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a designation by id."""
    designation = db.query(Designation).filter(Designation.id == designation_id).first()
    if not designation:
        raise HTTPException(status_code=404, detail="Designation not found")

    return {
        "id": designation.id,
        "erpnext_id": designation.erpnext_id,
        "designation_name": designation.designation_name,
        "description": designation.description,
    }


@router.post("/designations", dependencies=[Depends(Require("hr:write"))])
def create_designation(
    payload: DesignationCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a designation locally."""
    designation = Designation(
        designation_name=payload.designation_name,
        description=payload.description,
    )
    db.add(designation)
    db.commit()
    db.refresh(designation)
    return {"id": designation.id}


@router.patch("/designations/{designation_id}", dependencies=[Depends(Require("hr:write"))])
def update_designation(
    designation_id: int,
    payload: DesignationUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a designation locally."""
    designation = db.query(Designation).filter(Designation.id == designation_id).first()
    if not designation:
        raise HTTPException(status_code=404, detail="Designation not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(designation, key, value)

    db.commit()
    db.refresh(designation)
    return {"id": designation.id}


@router.delete("/designations/{designation_id}", dependencies=[Depends(Require("hr:write"))])
def delete_designation(
    designation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a designation."""
    designation = db.query(Designation).filter(Designation.id == designation_id).first()
    if not designation:
        raise HTTPException(status_code=404, detail="Designation not found")

    db.delete(designation)
    db.commit()
    return {"status": "deleted", "designation_id": designation_id}


@router.get("/erpnext-users", dependencies=[Depends(Require("hr:read"))])
def list_erpnext_users(
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List ERPNext users."""
    query = db.query(ERPNextUser)
    if not include_disabled:
        query = query.filter(ERPNextUser.enabled == True)
    if search:
        query = query.filter(ERPNextUser.email.ilike(f"%{search}%"))

    total = query.count()
    users = query.order_by(ERPNextUser.email).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "erpnext_users": [
            {
                "id": user.id,
                "erpnext_id": user.erpnext_id,
                "email": user.email,
                "full_name": user.full_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "enabled": user.enabled,
                "user_type": user.user_type,
                "employee_id": user.employee_id,
            }
            for user in users
        ],
    }


@router.get("/erpnext-users/{user_id}", dependencies=[Depends(Require("hr:read"))])
def get_erpnext_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an ERPNext user by id."""
    user = db.query(ERPNextUser).filter(ERPNextUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ERPNext user not found")

    return {
        "id": user.id,
        "erpnext_id": user.erpnext_id,
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "enabled": user.enabled,
        "user_type": user.user_type,
        "employee_id": user.employee_id,
    }


@router.post("/erpnext-users", dependencies=[Depends(Require("hr:write"))])
def create_erpnext_user(
    payload: ERPNextUserCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an ERPNext user locally."""
    user = ERPNextUser(
        email=payload.email,
        full_name=payload.full_name,
        first_name=payload.first_name,
        last_name=payload.last_name,
        enabled=payload.enabled,
        user_type=payload.user_type,
        employee_id=payload.employee_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id}


@router.patch("/erpnext-users/{user_id}", dependencies=[Depends(Require("hr:write"))])
def update_erpnext_user(
    user_id: int,
    payload: ERPNextUserUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an ERPNext user locally."""
    user = db.query(ERPNextUser).filter(ERPNextUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ERPNext user not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return {"id": user.id}


@router.delete("/erpnext-users/{user_id}", dependencies=[Depends(Require("hr:write"))])
def delete_erpnext_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable an ERPNext user."""
    user = db.query(ERPNextUser).filter(ERPNextUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ERPNext user not found")

    user.enabled = False
    db.commit()
    return {"status": "disabled", "erpnext_user_id": user_id}


@router.get("/hd-teams", dependencies=[Depends(Require("hr:read"))])
def list_hd_teams(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List HD teams."""
    query = db.query(HDTeam)
    if search:
        query = query.filter(HDTeam.team_name.ilike(f"%{search}%"))

    total = query.count()
    teams = query.order_by(HDTeam.team_name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "hd_teams": [
            {
                "id": team.id,
                "erpnext_id": team.erpnext_id,
                "team_name": team.team_name,
                "description": team.description,
                "assignment_rule": team.assignment_rule,
                "ignore_restrictions": team.ignore_restrictions,
            }
            for team in teams
        ],
    }


@router.get("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:read"))])
def get_hd_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an HD team by id."""
    team = db.query(HDTeam).filter(HDTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="HD team not found")

    return {
        "id": team.id,
        "erpnext_id": team.erpnext_id,
        "team_name": team.team_name,
        "description": team.description,
        "assignment_rule": team.assignment_rule,
        "ignore_restrictions": team.ignore_restrictions,
    }


@router.post("/hd-teams", dependencies=[Depends(Require("hr:write"))])
def create_hd_team(
    payload: HDTeamCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an HD team locally."""
    team = HDTeam(
        team_name=payload.team_name,
        description=payload.description,
        assignment_rule=payload.assignment_rule,
        ignore_restrictions=payload.ignore_restrictions,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"id": team.id}


@router.patch("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:write"))])
def update_hd_team(
    team_id: int,
    payload: HDTeamUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an HD team locally."""
    team = db.query(HDTeam).filter(HDTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="HD team not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(team, key, value)

    db.commit()
    db.refresh(team)
    return {"id": team.id}


@router.delete("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:write"))])
def delete_hd_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an HD team."""
    team = db.query(HDTeam).filter(HDTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="HD team not found")

    db.delete(team)
    db.commit()
    return {"status": "deleted", "hd_team_id": team_id}


@router.get("/hd-team-members", dependencies=[Depends(Require("hr:read"))])
def list_hd_team_members(
    team_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List HD team members."""
    query = db.query(HDTeamMember)
    if team_id:
        query = query.filter(HDTeamMember.team_id == team_id)

    total = query.count()
    members = query.order_by(HDTeamMember.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "hd_team_members": [
            {
                "id": member.id,
                "team_id": member.team_id,
                "user": member.user,
                "user_name": member.user_name,
                "employee_id": member.employee_id,
            }
            for member in members
        ],
    }


@router.get("/hd-team-members/{member_id}", dependencies=[Depends(Require("hr:read"))])
def get_hd_team_member(
    member_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an HD team member by id."""
    member = db.query(HDTeamMember).filter(HDTeamMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="HD team member not found")

    return {
        "id": member.id,
        "team_id": member.team_id,
        "user": member.user,
        "user_name": member.user_name,
        "employee_id": member.employee_id,
    }


@router.post("/hd-team-members", dependencies=[Depends(Require("hr:write"))])
def create_hd_team_member(
    payload: HDTeamMemberCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an HD team member locally."""
    member = HDTeamMember(
        team_id=payload.team_id,
        user=payload.user,
        user_name=payload.user_name,
        employee_id=payload.employee_id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id}


@router.patch("/hd-team-members/{member_id}", dependencies=[Depends(Require("hr:write"))])
def update_hd_team_member(
    member_id: int,
    payload: HDTeamMemberUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an HD team member locally."""
    member = db.query(HDTeamMember).filter(HDTeamMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="HD team member not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(member, key, value)

    db.commit()
    db.refresh(member)
    return {"id": member.id}


@router.delete("/hd-team-members/{member_id}", dependencies=[Depends(Require("hr:write"))])
def delete_hd_team_member(
    member_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an HD team member."""
    member = db.query(HDTeamMember).filter(HDTeamMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="HD team member not found")

    db.delete(member)
    db.commit()
    return {"status": "deleted", "hd_team_member_id": member_id}

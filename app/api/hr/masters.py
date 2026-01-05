"""HR master data endpoints: employees, departments, designations, users, teams.

Uses EmployeeService and OrganizationService for business logic.
ERPNextUser endpoints use direct DB as no business logic service exists for them.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.employee import EmploymentStatus
from app.models.hr import ERPNextUser
from app.services.hr.employees import EmployeeService
from app.services.hr.employee_types import (
    EmployeeFilters,
    EmployeeCreateData,
    EmployeeUpdateData,
)
from app.services.hr.organization import OrganizationService
from app.services.hr.organization_types import (
    DepartmentFilters,
    DepartmentCreateData,
    DepartmentUpdateData,
    DesignationFilters,
    DesignationCreateData,
    DesignationUpdateData,
    HDTeamFilters,
    HDTeamCreateData,
    HDTeamUpdateData,
    TeamMemberData,
)
from app.services.hr.errors import (
    EmployeeNotFoundError,
    EmployeeAlreadyExistsError,
    DepartmentNotFoundError,
    DesignationNotFoundError,
    HDTeamNotFoundError,
    ValidationError as HRValidationError,
)
from app.services.types import PaginationParams
from .schemas import (
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DesignationCreateRequest,
    DesignationUpdateRequest,
    ERPNextUserCreateRequest,
    ERPNextUserUpdateRequest,
    HDTeamCreateRequest,
    HDTeamUpdateRequest,
    HDTeamMemberCreateRequest,
    HDTeamMemberUpdateRequest,
)

router = APIRouter()


# =============================================================================
# EMPLOYEES
# =============================================================================

@router.get("/employees", dependencies=[Depends(Require("hr:read"))])
def list_employees(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List employees."""
    service = EmployeeService(db)

    filters = EmployeeFilters(
        search=search,
        include_deleted=include_deleted,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_employees(filters, pagination)

    return {
        "total": result.total,
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
            for emp in result.items
        ],
    }


@router.get("/employees/{employee_id}", dependencies=[Depends(Require("hr:read"))])
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an employee by id."""
    service = EmployeeService(db)

    try:
        employee = service.get_employee(employee_id)
    except EmployeeNotFoundError:
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create an employee locally."""
    service = EmployeeService(db, principal)

    try:
        data = EmployeeCreateData(
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
            salary=payload.salary,
            currency=payload.currency or "NGN",
        )
        employee = service.create_employee(data)
        db.commit()
    except EmployeeAlreadyExistsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": employee.id}


@router.patch("/employees/{employee_id}", dependencies=[Depends(Require("hr:write"))])
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an employee locally."""
    service = EmployeeService(db, principal)

    # Convert payload to update data
    update_dict = payload.model_dump(exclude_unset=True)
    status_val = None
    if "status" in update_dict and update_dict["status"]:
        status_val = EmploymentStatus(update_dict["status"])

    try:
        data = EmployeeUpdateData(
            name=update_dict.get("name"),
            email=update_dict.get("email"),
            phone=update_dict.get("phone"),
            employee_number=update_dict.get("employee_number"),
            designation=update_dict.get("designation"),
            department=update_dict.get("department"),
            reports_to=update_dict.get("reports_to"),
            department_id=update_dict.get("department_id"),
            designation_id=update_dict.get("designation_id"),
            reports_to_id=update_dict.get("reports_to_id"),
            status=status_val,
            employment_type=update_dict.get("employment_type"),
            date_of_joining=update_dict.get("date_of_joining"),
            date_of_leaving=update_dict.get("date_of_leaving"),
            salary=update_dict.get("salary"),
            currency=update_dict.get("currency"),
        )
        employee = service.update_employee(employee_id, data)
        db.commit()
    except EmployeeNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Employee not found")
    except (EmployeeAlreadyExistsError, HRValidationError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": employee.id}


@router.delete("/employees/{employee_id}", dependencies=[Depends(Require("hr:write"))])
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete an employee."""
    service = EmployeeService(db, principal)

    try:
        service.delete_employee(employee_id)
        db.commit()
    except EmployeeNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"status": "disabled", "employee_id": employee_id}


# =============================================================================
# ORG CHART
# =============================================================================

def _serialize_org_chart_node(node) -> Dict[str, Any]:
    """Recursively serialize an OrgChartNode to dict."""
    return {
        "employee_id": node.employee_id,
        "name": node.name,
        "designation": node.designation,
        "department": node.department,
        "email": node.email,
        "direct_reports": [
            _serialize_org_chart_node(child) for child in node.direct_reports
        ],
    }


@router.get("/org-chart", dependencies=[Depends(Require("hr:read"))])
def get_org_chart(
    depth: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the organization chart as a hierarchical tree.

    Returns all top-level employees (no manager) with their direct reports
    nested recursively up to the specified depth.
    """
    service = EmployeeService(db)
    nodes = service.get_org_chart(root_employee_id=None, depth=depth)

    return {
        "depth": depth,
        "nodes": [_serialize_org_chart_node(node) for node in nodes],
    }


@router.get("/org-chart/{employee_id}", dependencies=[Depends(Require("hr:read"))])
def get_org_chart_from_employee(
    employee_id: int,
    depth: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the organization chart rooted at a specific employee.

    Returns the specified employee with their direct reports nested
    recursively up to the specified depth.
    """
    service = EmployeeService(db)

    # Verify employee exists
    try:
        service.get_employee(employee_id)
    except EmployeeNotFoundError:
        raise HTTPException(status_code=404, detail="Employee not found")

    nodes = service.get_org_chart(root_employee_id=employee_id, depth=depth)

    return {
        "root_employee_id": employee_id,
        "depth": depth,
        "nodes": [_serialize_org_chart_node(node) for node in nodes],
    }


# =============================================================================
# DEPARTMENTS
# =============================================================================

@router.get("/departments", dependencies=[Depends(Require("hr:read"))])
def list_departments(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List departments."""
    service = OrganizationService(db)

    filters = DepartmentFilters(search=search)
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_departments(filters, pagination)

    return {
        "total": result.total,
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
            for dept in result.items
        ],
    }


@router.get("/departments/{department_id}", dependencies=[Depends(Require("hr:read"))])
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a department by id."""
    service = OrganizationService(db)

    try:
        department = service.get_department(department_id)
    except DepartmentNotFoundError:
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a department locally."""
    service = OrganizationService(db, principal)

    try:
        data = DepartmentCreateData(
            department_name=payload.department_name,
            parent_department=payload.parent_department,
            company=payload.company,
            is_group=payload.is_group,
        )
        department = service.create_department(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": department.id}


@router.patch("/departments/{department_id}", dependencies=[Depends(Require("hr:write"))])
def update_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a department locally."""
    service = OrganizationService(db, principal)

    try:
        data = DepartmentUpdateData(
            department_name=payload.department_name,
            parent_department=payload.parent_department,
            company=payload.company,
            is_group=payload.is_group,
        )
        department = service.update_department(department_id, data)
        db.commit()
    except DepartmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Department not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": department.id}


@router.delete("/departments/{department_id}", dependencies=[Depends(Require("hr:write"))])
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a department."""
    service = OrganizationService(db, principal)

    try:
        service.delete_department(department_id)
        db.commit()
    except DepartmentNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Department not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "deleted", "department_id": department_id}


# =============================================================================
# DEPARTMENT TREE
# =============================================================================

def _serialize_department_node(node) -> Dict[str, Any]:
    """Recursively serialize a DepartmentNode to dict."""
    return {
        "id": node.id,
        "department_name": node.department_name,
        "parent_department": node.parent_department,
        "company": node.company,
        "is_group": node.is_group,
        "children": [
            _serialize_department_node(child) for child in node.children
        ],
    }


@router.get("/department-tree", dependencies=[Depends(Require("hr:read"))])
def get_department_tree(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the department hierarchy as a tree.

    Returns all root departments (no parent) with their child departments
    nested recursively.
    """
    service = OrganizationService(db)
    nodes = service.get_department_tree(company=company)

    return {
        "company": company,
        "nodes": [_serialize_department_node(node) for node in nodes],
    }


# =============================================================================
# DESIGNATIONS
# =============================================================================

@router.get("/designations", dependencies=[Depends(Require("hr:read"))])
def list_designations(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List designations."""
    service = OrganizationService(db)

    filters = DesignationFilters(search=search)
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_designations(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "designations": [
            {
                "id": desig.id,
                "erpnext_id": desig.erpnext_id,
                "designation_name": desig.designation_name,
                "description": desig.description,
            }
            for desig in result.items
        ],
    }


@router.get("/designations/{designation_id}", dependencies=[Depends(Require("hr:read"))])
def get_designation(
    designation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a designation by id."""
    service = OrganizationService(db)

    try:
        designation = service.get_designation(designation_id)
    except DesignationNotFoundError:
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a designation locally."""
    service = OrganizationService(db, principal)

    try:
        data = DesignationCreateData(
            designation_name=payload.designation_name,
            description=payload.description,
        )
        designation = service.create_designation(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": designation.id}


@router.patch("/designations/{designation_id}", dependencies=[Depends(Require("hr:write"))])
def update_designation(
    designation_id: int,
    payload: DesignationUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a designation locally."""
    service = OrganizationService(db, principal)

    try:
        data = DesignationUpdateData(
            designation_name=payload.designation_name,
            description=payload.description,
        )
        designation = service.update_designation(designation_id, data)
        db.commit()
    except DesignationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Designation not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": designation.id}


@router.delete("/designations/{designation_id}", dependencies=[Depends(Require("hr:write"))])
def delete_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a designation."""
    service = OrganizationService(db, principal)

    try:
        service.delete_designation(designation_id)
        db.commit()
    except DesignationNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Designation not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "deleted", "designation_id": designation_id}


# =============================================================================
# ERPNEXT USERS (No service layer - direct DB operations)
# =============================================================================

@router.get("/erpnext-users", dependencies=[Depends(Require("hr:read"))])
def list_erpnext_users(
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
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


# =============================================================================
# HD TEAMS
# =============================================================================

@router.get("/hd-teams", dependencies=[Depends(Require("hr:read"))])
def list_hd_teams(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List HD teams."""
    service = OrganizationService(db)

    filters = HDTeamFilters(search=search)
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_hd_teams(filters, pagination)

    return {
        "total": result.total,
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
            for team in result.items
        ],
    }


@router.get("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:read"))])
def get_hd_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an HD team by id."""
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
    except HDTeamNotFoundError:
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create an HD team locally."""
    service = OrganizationService(db, principal)

    try:
        data = HDTeamCreateData(
            team_name=payload.team_name,
            description=payload.description,
            assignment_rule=payload.assignment_rule,
            ignore_restrictions=payload.ignore_restrictions,
        )
        team = service.create_hd_team(data)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": team.id}


@router.patch("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:write"))])
def update_hd_team(
    team_id: int,
    payload: HDTeamUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update an HD team locally."""
    service = OrganizationService(db, principal)

    try:
        data = HDTeamUpdateData(
            team_name=payload.team_name,
            description=payload.description,
            assignment_rule=payload.assignment_rule,
            ignore_restrictions=payload.ignore_restrictions,
        )
        team = service.update_hd_team(team_id, data)
        db.commit()
    except HDTeamNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="HD team not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": team.id}


@router.delete("/hd-teams/{team_id}", dependencies=[Depends(Require("hr:write"))])
def delete_hd_team(
    team_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an HD team."""
    service = OrganizationService(db, principal)

    try:
        service.delete_hd_team(team_id)
        db.commit()
    except HDTeamNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="HD team not found")

    return {"status": "deleted", "hd_team_id": team_id}


# =============================================================================
# HD TEAM MEMBERS
# =============================================================================

@router.get("/hd-team-members", dependencies=[Depends(Require("hr:read"))])
def list_hd_team_members(
    team_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List HD team members."""
    service = OrganizationService(db)

    if team_id:
        try:
            members = service.get_team_members(team_id)
        except HDTeamNotFoundError:
            raise HTTPException(status_code=404, detail="HD team not found")

        # Apply pagination manually
        total = len(members)
        members = members[offset:offset + limit]
    else:
        # When no team_id, use direct query for all members
        from app.models.hr import HDTeamMember
        query = db.query(HDTeamMember)
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
    from app.models.hr import HDTeamMember
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create an HD team member locally."""
    service = OrganizationService(db, principal)

    try:
        data = TeamMemberData(
            user=payload.user,
            user_name=payload.user_name,
            employee_id=payload.employee_id,
        )
        member = service.add_team_member(payload.team_id, data)
        db.commit()
    except HDTeamNotFoundError:
        db.rollback()
        raise HTTPException(status_code=404, detail="HD team not found")
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": member.id}


@router.patch("/hd-team-members/{member_id}", dependencies=[Depends(Require("hr:write"))])
def update_hd_team_member(
    member_id: int,
    payload: HDTeamMemberUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an HD team member locally."""
    from app.models.hr import HDTeamMember
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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an HD team member."""
    from app.models.hr import HDTeamMember

    # Get member to find team_id
    member = db.query(HDTeamMember).filter(HDTeamMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="HD team member not found")

    service = OrganizationService(db, principal)

    try:
        service.remove_team_member(member.team_id, member_id)
        db.commit()
    except HRValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "deleted", "hd_team_member_id": member_id}

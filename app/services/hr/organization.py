"""Organization service - business logic for departments, designations, and teams.

This service encapsulates organization structure business logic:
- Department CRUD and hierarchy
- Designation CRUD
- HD Team CRUD and membership

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.hr import Department, Designation, HDTeam, HDTeamMember
from app.models.employee import Employee, EmploymentStatus
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams

from .errors import (
    DepartmentNotFoundError,
    DesignationNotFoundError,
    HDTeamNotFoundError,
    CircularDepartmentError,
    ValidationError,
)
from .organization_types import (
    DepartmentCreateData,
    DepartmentFilters,
    DepartmentHeadcount,
    DepartmentNode,
    DepartmentUpdateData,
    DesignationCreateData,
    DesignationFilters,
    DesignationHeadcount,
    DesignationUpdateData,
    HDTeamCreateData,
    HDTeamFilters,
    HDTeamUpdateData,
    TeamMemberData,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.hr_settings import HRSettings

__all__ = ["OrganizationService"]


class OrganizationService:
    """Service for organization structure business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        self._settings_cache: dict[str, "HRSettings"] = {}

    def _get_settings(self, company: Optional[str] = None) -> "HRSettings":
        """Get HR settings, using cache for repeated access within same request."""
        cache_key = company or "__default__"
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]

        from .settings import HRSettingsService

        settings_service = HRSettingsService(self.db, self.principal)
        self._settings_cache[cache_key] = settings_service.get_settings(company)
        return self._settings_cache[cache_key]

    # =========================================================================
    # Department Methods
    # =========================================================================

    def list_departments(
        self,
        filters: Optional[DepartmentFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Department]:
        """List departments with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing departments and total count.
        """
        if filters is None:
            filters = DepartmentFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(Department)

        if filters.company:
            stmt = stmt.where(Department.company == filters.company)

        if filters.is_group is not None:
            stmt = stmt.where(Department.is_group == filters.is_group)

        if filters.parent_department:
            stmt = stmt.where(
                Department.parent_department == filters.parent_department
            )

        if filters.search:
            search_term = f"%{filters.search}%"
            stmt = stmt.where(Department.department_name.ilike(search_term))

        # Order by name
        stmt = stmt.order_by(Department.department_name.asc())

        return paginate(self.db, stmt, pagination)

    def get_department(self, department_id: int) -> Department:
        """Get a department by ID.

        Args:
            department_id: The department ID.

        Returns:
            The Department object.

        Raises:
            DepartmentNotFoundError: If department not found.
        """
        department = self.db.get(Department, department_id)

        if not department:
            raise DepartmentNotFoundError(department_id)

        return department

    def get_department_by_name(self, name: str) -> Optional[Department]:
        """Get a department by name.

        Args:
            name: The department name.

        Returns:
            The Department object or None if not found.
        """
        return self.db.scalar(
            select(Department).where(Department.department_name == name)
        )

    def create_department(self, data: DepartmentCreateData) -> Department:
        """Create a new department.

        Args:
            data: Department creation data.

        Returns:
            The created Department (not yet committed).

        Raises:
            ValidationError: If department name already exists.
        """
        # Check for duplicate name
        existing = self.get_department_by_name(data.department_name)
        if existing:
            raise ValidationError(
                f"Department with name '{data.department_name}' already exists"
            )

        department = Department(
            department_name=data.department_name,
            parent_department=data.parent_department,
            company=data.company,
            is_group=data.is_group,
        )

        self.db.add(department)
        self.db.flush()

        return department

    def update_department(
        self, department_id: int, data: DepartmentUpdateData
    ) -> Department:
        """Update an existing department.

        Args:
            department_id: The department ID.
            data: Fields to update.

        Returns:
            The updated Department (not yet committed).

        Raises:
            DepartmentNotFoundError: If department not found.
            ValidationError: If department name already exists.
            CircularDepartmentError: If update would create a cycle.
        """
        department = self.get_department(department_id)

        if data.department_name is not None:
            # Check for duplicate name (excluding self)
            existing = self.get_department_by_name(data.department_name)
            if existing and existing.id != department_id:
                raise ValidationError(
                    f"Department with name '{data.department_name}' already exists"
                )
            department.department_name = data.department_name

        if data.parent_department is not None:
            # Check for circular reference
            if data.parent_department == department.department_name:
                raise CircularDepartmentError()
            department.parent_department = data.parent_department

        if data.company is not None:
            department.company = data.company

        if data.is_group is not None:
            department.is_group = data.is_group

        department.updated_at = datetime.now(timezone.utc)

        return department

    def delete_department(self, department_id: int) -> None:
        """Delete a department.

        Args:
            department_id: The department ID.

        Raises:
            DepartmentNotFoundError: If department not found.
            ValidationError: If department has employees assigned.
        """
        department = self.get_department(department_id)

        # Check if any employees are in this department
        employee_count = self.db.scalar(
            select(func.count(Employee.id)).where(Employee.department_id == department_id)
        )
        if employee_count and employee_count > 0:
            raise ValidationError(
                f"Cannot delete department with {employee_count} employees assigned"
            )

        self.db.delete(department)

    def get_department_tree(
        self, company: Optional[str] = None
    ) -> List[DepartmentNode]:
        """Get the department hierarchy as a tree.

        Args:
            company: Optional company filter.

        Returns:
            List of root DepartmentNode objects with nested children.
        """
        stmt = select(Department)
        if company:
            stmt = stmt.where(Department.company == company)

        departments = self.db.scalars(stmt).all()

        # Build lookup dict
        dept_dict = {d.department_name: d for d in departments}
        nodes: dict[str, DepartmentNode] = {}

        # Create nodes
        for dept in departments:
            nodes[dept.department_name] = DepartmentNode(
                id=dept.id,
                department_name=dept.department_name,
                parent_department=dept.parent_department,
                company=dept.company,
                is_group=dept.is_group,
                children=[],
            )

        # Build tree
        roots: List[DepartmentNode] = []
        for node in nodes.values():
            if node.parent_department and node.parent_department in nodes:
                nodes[node.parent_department].children.append(node)
            else:
                roots.append(node)

        return roots

    def get_department_headcount(self, department_id: int) -> DepartmentHeadcount:
        """Get employee headcount for a department.

        Args:
            department_id: The department ID.

        Returns:
            DepartmentHeadcount with employee counts.

        Raises:
            DepartmentNotFoundError: If department not found.
        """
        department = self.get_department(department_id)

        # Get counts by status
        stmt = (
            select(Employee.status, func.count(Employee.id))
            .where(Employee.department_id == department_id, Employee.is_deleted == False)
            .group_by(Employee.status)
        )
        counts = self.db.execute(stmt).all()

        status_counts = {status: count for status, count in counts}
        total = sum(status_counts.values())

        return DepartmentHeadcount(
            department_id=department_id,
            department_name=department.department_name,
            total_employees=total,
            active_employees=status_counts.get(EmploymentStatus.ACTIVE, 0),
            on_leave=status_counts.get(EmploymentStatus.ON_LEAVE, 0),
            terminated=status_counts.get(EmploymentStatus.TERMINATED, 0),
        )

    def get_designation_headcount(self, designation_id: int) -> DesignationHeadcount:
        """Get employee headcount for a designation.

        Args:
            designation_id: The designation ID.

        Returns:
            DesignationHeadcount with employee counts.

        Raises:
            DesignationNotFoundError: If designation not found.
        """
        designation = self.get_designation(designation_id)

        stmt = (
            select(Employee.status, func.count(Employee.id))
            .where(Employee.designation_id == designation_id, Employee.is_deleted == False)
            .group_by(Employee.status)
        )
        counts = self.db.execute(stmt).all()

        status_counts = {status: count for status, count in counts}
        total = sum(status_counts.values())

        return DesignationHeadcount(
            designation_id=designation_id,
            designation_name=designation.designation_name,
            total_employees=total,
            active_employees=status_counts.get(EmploymentStatus.ACTIVE, 0),
            on_leave=status_counts.get(EmploymentStatus.ON_LEAVE, 0),
            terminated=status_counts.get(EmploymentStatus.TERMINATED, 0),
        )

    # =========================================================================
    # Designation Methods
    # =========================================================================

    def list_designations(
        self,
        filters: Optional[DesignationFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Designation]:
        """List designations with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing designations and total count.
        """
        if filters is None:
            filters = DesignationFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(Designation)

        if filters.search:
            search_term = f"%{filters.search}%"
            stmt = stmt.where(
                or_(
                    Designation.designation_name.ilike(search_term),
                    Designation.description.ilike(search_term),
                )
            )

        # Order by name
        stmt = stmt.order_by(Designation.designation_name.asc())

        return paginate(self.db, stmt, pagination)

    def get_designation(self, designation_id: int) -> Designation:
        """Get a designation by ID.

        Args:
            designation_id: The designation ID.

        Returns:
            The Designation object.

        Raises:
            DesignationNotFoundError: If designation not found.
        """
        designation = self.db.get(Designation, designation_id)

        if not designation:
            raise DesignationNotFoundError(designation_id)

        return designation

    def get_designation_by_name(self, name: str) -> Optional[Designation]:
        """Get a designation by name.

        Args:
            name: The designation name.

        Returns:
            The Designation object or None if not found.
        """
        return self.db.scalar(
            select(Designation).where(Designation.designation_name == name)
        )

    def create_designation(self, data: DesignationCreateData) -> Designation:
        """Create a new designation.

        Args:
            data: Designation creation data.

        Returns:
            The created Designation (not yet committed).

        Raises:
            ValidationError: If designation name already exists.
        """
        # Check for duplicate name
        existing = self.get_designation_by_name(data.designation_name)
        if existing:
            raise ValidationError(
                f"Designation with name '{data.designation_name}' already exists"
            )

        designation = Designation(
            designation_name=data.designation_name,
            description=data.description,
        )

        self.db.add(designation)
        self.db.flush()

        return designation

    def update_designation(
        self, designation_id: int, data: DesignationUpdateData
    ) -> Designation:
        """Update an existing designation.

        Args:
            designation_id: The designation ID.
            data: Fields to update.

        Returns:
            The updated Designation (not yet committed).

        Raises:
            DesignationNotFoundError: If designation not found.
            ValidationError: If designation name already exists.
        """
        designation = self.get_designation(designation_id)

        if data.designation_name is not None:
            # Check for duplicate name (excluding self)
            existing = self.get_designation_by_name(data.designation_name)
            if existing and existing.id != designation_id:
                raise ValidationError(
                    f"Designation with name '{data.designation_name}' already exists"
                )
            designation.designation_name = data.designation_name

        if data.description is not None:
            designation.description = data.description

        designation.updated_at = datetime.now(timezone.utc)

        return designation

    def delete_designation(self, designation_id: int) -> None:
        """Delete a designation.

        Args:
            designation_id: The designation ID.

        Raises:
            DesignationNotFoundError: If designation not found.
            ValidationError: If designation has employees assigned.
        """
        designation = self.get_designation(designation_id)

        # Check if any employees have this designation
        employee_count = self.db.scalar(
            select(func.count(Employee.id)).where(Employee.designation_id == designation_id)
        )
        if employee_count and employee_count > 0:
            raise ValidationError(
                f"Cannot delete designation with {employee_count} employees assigned"
            )

        self.db.delete(designation)

    # =========================================================================
    # HD Team Methods
    # =========================================================================

    def list_hd_teams(
        self,
        filters: Optional[HDTeamFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[HDTeam]:
        """List helpdesk teams with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing teams and total count.
        """
        if filters is None:
            filters = HDTeamFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(HDTeam)

        if filters.search:
            search_term = f"%{filters.search}%"
            stmt = stmt.where(
                or_(
                    HDTeam.team_name.ilike(search_term),
                    HDTeam.description.ilike(search_term),
                )
            )

        if filters.assignment_rule:
            stmt = stmt.where(HDTeam.assignment_rule == filters.assignment_rule)

        # Order by name
        stmt = stmt.order_by(HDTeam.team_name.asc())

        return paginate(self.db, stmt, pagination)

    def get_hd_team(self, team_id: int) -> HDTeam:
        """Get a helpdesk team by ID.

        Args:
            team_id: The team ID.

        Returns:
            The HDTeam object.

        Raises:
            HDTeamNotFoundError: If team not found.
        """
        team = self.db.get(HDTeam, team_id)

        if not team:
            raise HDTeamNotFoundError(team_id)

        return team

    def create_hd_team(self, data: HDTeamCreateData) -> HDTeam:
        """Create a new helpdesk team.

        Args:
            data: Team creation data.

        Returns:
            The created HDTeam (not yet committed).
        """
        team = HDTeam(
            team_name=data.team_name,
            description=data.description,
            assignment_rule=data.assignment_rule,
            ignore_restrictions=data.ignore_restrictions,
        )

        self.db.add(team)
        self.db.flush()

        return team

    def update_hd_team(self, team_id: int, data: HDTeamUpdateData) -> HDTeam:
        """Update an existing helpdesk team.

        Args:
            team_id: The team ID.
            data: Fields to update.

        Returns:
            The updated HDTeam (not yet committed).

        Raises:
            HDTeamNotFoundError: If team not found.
        """
        team = self.get_hd_team(team_id)

        if data.team_name is not None:
            team.team_name = data.team_name

        if data.description is not None:
            team.description = data.description

        if data.assignment_rule is not None:
            team.assignment_rule = data.assignment_rule

        if data.ignore_restrictions is not None:
            team.ignore_restrictions = data.ignore_restrictions

        team.updated_at = datetime.now(timezone.utc)

        return team

    def delete_hd_team(self, team_id: int) -> None:
        """Delete a helpdesk team.

        Args:
            team_id: The team ID.

        Raises:
            HDTeamNotFoundError: If team not found.
        """
        team = self.get_hd_team(team_id)
        self.db.delete(team)

    def add_team_member(self, team_id: int, data: TeamMemberData) -> HDTeamMember:
        """Add a member to a helpdesk team.

        Args:
            team_id: The team ID.
            data: Team member data.

        Returns:
            The created HDTeamMember (not yet committed).

        Raises:
            HDTeamNotFoundError: If team not found.
            ValidationError: If member already exists in team.
        """
        team = self.get_hd_team(team_id)

        # Check if member already exists
        existing = self.db.scalar(
            select(HDTeamMember).where(
                HDTeamMember.team_id == team_id, HDTeamMember.user == data.user
            )
        )
        if existing:
            raise ValidationError(f"User '{data.user}' is already a member of this team")

        member = HDTeamMember(
            team_id=team_id,
            user=data.user,
            user_name=data.user_name,
            employee_id=data.employee_id,
        )

        self.db.add(member)
        self.db.flush()

        return member

    def remove_team_member(self, team_id: int, member_id: int) -> None:
        """Remove a member from a helpdesk team.

        Args:
            team_id: The team ID.
            member_id: The team member ID.

        Raises:
            HDTeamNotFoundError: If team not found.
            ValidationError: If member not found.
        """
        # Verify team exists
        self.get_hd_team(team_id)

        member = self.db.scalar(
            select(HDTeamMember).where(
                HDTeamMember.id == member_id, HDTeamMember.team_id == team_id
            )
        )

        if not member:
            raise ValidationError(f"Team member {member_id} not found in team {team_id}")

        self.db.delete(member)

    def get_team_members(self, team_id: int) -> List[HDTeamMember]:
        """Get all members of a helpdesk team.

        Args:
            team_id: The team ID.

        Returns:
            List of HDTeamMember objects.

        Raises:
            HDTeamNotFoundError: If team not found.
        """
        # Verify team exists
        self.get_hd_team(team_id)

        stmt = (
            select(HDTeamMember)
            .where(HDTeamMember.team_id == team_id)
            .order_by(HDTeamMember.user_name.asc())
        )
        return list(self.db.scalars(stmt).all())

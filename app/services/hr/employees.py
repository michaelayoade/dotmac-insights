"""Employee service - business logic for employee management.

This service encapsulates employee-related business logic:
- Employee CRUD operations
- Org chart / reporting hierarchy
- Status management (activate, terminate, etc.)
- Bulk operations

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department, Designation
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams

from .errors import (
    EmployeeAlreadyExistsError,
    EmployeeNotFoundError,
    EmployeeStatusError,
    InvalidManagerError,
    ValidationError,
)
from .employee_types import (
    BulkResult,
    BulkUpdateData,
    EmployeeCreateData,
    EmployeeFilters,
    EmployeeSummary,
    EmployeeUpdateData,
    OrgChartNode,
    TerminationData,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.hr_settings import HRSettings
    from app.models.party import Party

__all__ = ["EmployeeService"]


class EmployeeService:
    """Service for employee business logic.

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
    # Validation Helpers
    # =========================================================================

    def _validate_manager(
        self, employee_id: int, manager_id: int, visited: Optional[set] = None
    ) -> bool:
        """Check if setting manager_id would create a circular reference.

        Args:
            employee_id: The employee being modified.
            manager_id: The proposed manager ID.
            visited: Set of already visited employee IDs.

        Returns:
            True if the manager assignment is valid, False if it creates a cycle.
        """
        if visited is None:
            visited = set()

        # Can't report to self
        if employee_id == manager_id:
            return False

        # Check if manager reports to employee (directly or transitively)
        manager = self.db.scalar(select(Employee).where(Employee.id == manager_id))
        if not manager:
            return True  # Manager doesn't exist, will fail separately

        visited.add(manager_id)

        if manager.reports_to_id is None:
            return True

        if manager.reports_to_id == employee_id:
            return False

        if manager.reports_to_id in visited:
            return False

        return self._validate_manager(employee_id, manager.reports_to_id, visited)

    # =========================================================================
    # Queries
    # =========================================================================

    def list_employees(
        self,
        filters: Optional[EmployeeFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Employee]:
        """List employees with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing employees and total count.
        """
        if filters is None:
            filters = EmployeeFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(Employee)

        # Handle soft delete
        if not filters.include_deleted:
            stmt = stmt.where(Employee.is_deleted == False)

        if filters.status:
            stmt = stmt.where(Employee.status == filters.status)

        if filters.department_id:
            stmt = stmt.where(Employee.department_id == filters.department_id)

        if filters.designation_id:
            stmt = stmt.where(Employee.designation_id == filters.designation_id)

        if filters.reports_to_id:
            stmt = stmt.where(Employee.reports_to_id == filters.reports_to_id)

        if filters.employment_type:
            stmt = stmt.where(Employee.employment_type == filters.employment_type)

        if filters.search:
            search_term = f"%{filters.search}%"
            stmt = stmt.where(
                or_(
                    Employee.name.ilike(search_term),
                    Employee.email.ilike(search_term),
                    Employee.employee_number.ilike(search_term),
                )
            )

        if filters.date_of_joining_from:
            stmt = stmt.where(Employee.date_of_joining >= filters.date_of_joining_from)

        if filters.date_of_joining_to:
            stmt = stmt.where(Employee.date_of_joining <= filters.date_of_joining_to)

        # Default ordering by name
        stmt = stmt.order_by(Employee.name.asc())

        return paginate(self.db, stmt, pagination)

    def get_employee(self, employee_id: int, include_deleted: bool = False) -> Employee:
        """Get an employee by ID.

        Args:
            employee_id: The employee ID.
            include_deleted: Whether to include soft-deleted employees.

        Returns:
            The Employee object.

        Raises:
            EmployeeNotFoundError: If employee not found.
        """
        stmt = select(Employee).where(Employee.id == employee_id)

        if not include_deleted:
            stmt = stmt.where(Employee.is_deleted == False)

        employee = self.db.scalar(stmt)

        if not employee:
            raise EmployeeNotFoundError(employee_id)

        return employee

    def get_employee_by_number(self, employee_number: str) -> Optional[Employee]:
        """Get an employee by employee number.

        Args:
            employee_number: The employee number.

        Returns:
            The Employee object or None if not found.
        """
        return self.db.scalar(
            select(Employee).where(
                Employee.employee_number == employee_number,
                Employee.is_deleted == False,
            )
        )

    def get_employee_by_email(self, email: str) -> Optional[Employee]:
        """Get an employee by email.

        Args:
            email: The employee email.

        Returns:
            The Employee object or None if not found.
        """
        return self.db.scalar(
            select(Employee).where(Employee.email == email, Employee.is_deleted == False)
        )

    def search_employees(self, query: str, limit: int = 20) -> List[EmployeeSummary]:
        """Search employees for autocomplete.

        Args:
            query: Search query (name, email, or employee number).
            limit: Maximum number of results.

        Returns:
            List of EmployeeSummary objects.
        """
        search_term = f"%{query}%"

        stmt = (
            select(Employee)
            .where(
                Employee.is_deleted == False,
                or_(
                    Employee.name.ilike(search_term),
                    Employee.email.ilike(search_term),
                    Employee.employee_number.ilike(search_term),
                ),
            )
            .order_by(Employee.name.asc())
            .limit(limit)
        )
        employees = self.db.scalars(stmt).all()

        return [
            EmployeeSummary(
                id=emp.id,
                name=emp.name,
                email=emp.email,
                employee_number=emp.employee_number,
                department=emp.department,
                designation=emp.designation,
                status=emp.status,
            )
            for emp in employees
        ]

    def get_direct_reports(self, manager_id: int) -> List[Employee]:
        """Get all direct reports of a manager.

        Args:
            manager_id: The manager's employee ID.

        Returns:
            List of Employee objects who report to this manager.
        """
        stmt = (
            select(Employee)
            .where(
                Employee.reports_to_id == manager_id,
                Employee.is_deleted == False,
            )
            .order_by(Employee.name.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_org_chart(
        self, root_employee_id: Optional[int] = None, depth: int = 3
    ) -> List[OrgChartNode]:
        """Get organization chart as a tree.

        Args:
            root_employee_id: Start from this employee. If None, starts from
                             employees with no manager.
            depth: Maximum depth to traverse.

        Returns:
            List of OrgChartNode objects with nested direct_reports.
        """

        def build_node(employee: Employee, current_depth: int) -> OrgChartNode:
            node = OrgChartNode(
                employee_id=employee.id,
                name=employee.name,
                designation=employee.designation,
                department=employee.department,
                email=employee.email,
                direct_reports=[],
            )

            if current_depth < depth:
                reports = self.get_direct_reports(employee.id)
                for report in reports:
                    node.direct_reports.append(build_node(report, current_depth + 1))

            return node

        if root_employee_id:
            root = self.get_employee(root_employee_id)
            return [build_node(root, 0)]

        # Get all employees with no manager (top of hierarchy)
        stmt = (
            select(Employee)
            .where(
                Employee.reports_to_id.is_(None),
                Employee.is_deleted == False,
            )
            .order_by(Employee.name.asc())
        )
        roots = self.db.scalars(stmt).all()

        return [build_node(emp, 0) for emp in roots]

    # =========================================================================
    # CRUD
    # =========================================================================

    def create_employee(self, data: EmployeeCreateData) -> Employee:
        """Create a new employee.

        Args:
            data: Employee creation data.

        Returns:
            The created Employee (not yet committed).

        Raises:
            EmployeeAlreadyExistsError: If employee number or email already exists.
            ValidationError: If validation fails.
        """
        # Check for duplicate employee number
        if data.employee_number:
            existing = self.get_employee_by_number(data.employee_number)
            if existing:
                raise EmployeeAlreadyExistsError(
                    data.employee_number,
                    f"Employee with number '{data.employee_number}' already exists",
                )

        # Check for duplicate email
        if data.email:
            existing = self.get_employee_by_email(data.email)
            if existing:
                raise EmployeeAlreadyExistsError(
                    data.email,
                    f"Employee with email '{data.email}' already exists",
                )

        # Validate manager doesn't create cycle (not possible for new employee, but check anyway)
        if data.reports_to_id:
            manager = self.db.scalar(select(Employee).where(Employee.id == data.reports_to_id))
            if not manager:
                raise ValidationError(f"Manager with ID {data.reports_to_id} not found")

        # Resolve department/designation text from IDs if provided
        department_text = data.department
        designation_text = data.designation

        if data.department_id and not department_text:
            dept = self.db.get(Department, data.department_id)
            if dept:
                department_text = dept.department_name

        if data.designation_id and not designation_text:
            desig = self.db.get(Designation, data.designation_id)
            if desig:
                designation_text = desig.designation_name

        employee = Employee(
            name=data.name,
            email=data.email,
            phone=data.phone,
            employee_number=data.employee_number,
            department_id=data.department_id,
            designation_id=data.designation_id,
            reports_to_id=data.reports_to_id,
            department=department_text,
            designation=designation_text,
            reports_to=data.reports_to,
            employment_type=data.employment_type,
            date_of_joining=data.date_of_joining,
            salary=data.salary,
            currency=data.currency,
            status=data.status,
        )

        self.db.add(employee)
        self.db.flush()

        return employee

    def update_employee(self, employee_id: int, data: EmployeeUpdateData) -> Employee:
        """Update an existing employee.

        Args:
            employee_id: The employee ID.
            data: Fields to update.

        Returns:
            The updated Employee (not yet committed).

        Raises:
            EmployeeNotFoundError: If employee not found.
            EmployeeAlreadyExistsError: If employee number or email conflicts.
            InvalidManagerError: If manager assignment creates cycle.
        """
        employee = self.get_employee(employee_id)

        # Check for duplicate employee number
        if data.employee_number is not None and data.employee_number != employee.employee_number:
            existing = self.get_employee_by_number(data.employee_number)
            if existing and existing.id != employee_id:
                raise EmployeeAlreadyExistsError(
                    data.employee_number,
                    f"Employee with number '{data.employee_number}' already exists",
                )
            employee.employee_number = data.employee_number

        # Check for duplicate email
        if data.email is not None and data.email != employee.email:
            existing = self.get_employee_by_email(data.email)
            if existing and existing.id != employee_id:
                raise EmployeeAlreadyExistsError(
                    data.email,
                    f"Employee with email '{data.email}' already exists",
                )
            employee.email = data.email

        # Validate manager doesn't create cycle
        if data.reports_to_id is not None and data.reports_to_id != employee.reports_to_id:
            if data.reports_to_id and not self._validate_manager(employee_id, data.reports_to_id):
                raise InvalidManagerError()
            employee.reports_to_id = data.reports_to_id

        # Update simple fields
        if data.name is not None:
            employee.name = data.name
        if data.phone is not None:
            employee.phone = data.phone
        if data.department_id is not None:
            employee.department_id = data.department_id
        if data.designation_id is not None:
            employee.designation_id = data.designation_id
        if data.department is not None:
            employee.department = data.department
        if data.designation is not None:
            employee.designation = data.designation
        if data.reports_to is not None:
            employee.reports_to = data.reports_to
        if data.employment_type is not None:
            employee.employment_type = data.employment_type
        if data.date_of_joining is not None:
            employee.date_of_joining = data.date_of_joining
        if data.date_of_leaving is not None:
            employee.date_of_leaving = data.date_of_leaving
        if data.salary is not None:
            employee.salary = data.salary
        if data.currency is not None:
            employee.currency = data.currency
        if data.status is not None:
            employee.status = data.status

        employee.updated_at = datetime.now(timezone.utc)

        return employee

    def delete_employee(self, employee_id: int) -> None:
        """Soft delete an employee.

        Args:
            employee_id: The employee ID.

        Raises:
            EmployeeNotFoundError: If employee not found.
        """
        employee = self.get_employee(employee_id)

        employee.is_deleted = True
        employee.deleted_at = datetime.now(timezone.utc)
        employee.deleted_by_id = self.principal.id if self.principal else None
        employee.updated_at = datetime.now(timezone.utc)

    # =========================================================================
    # Status Management
    # =========================================================================

    def activate_employee(self, employee_id: int) -> Employee:
        """Activate an employee.

        Args:
            employee_id: The employee ID.

        Returns:
            The updated Employee.

        Raises:
            EmployeeNotFoundError: If employee not found.
        """
        employee = self.get_employee(employee_id)
        employee.status = EmploymentStatus.ACTIVE
        employee.updated_at = datetime.now(timezone.utc)
        return employee

    def deactivate_employee(
        self, employee_id: int, reason: Optional[str] = None
    ) -> Employee:
        """Deactivate an employee.

        Args:
            employee_id: The employee ID.
            reason: Optional reason for deactivation.

        Returns:
            The updated Employee.

        Raises:
            EmployeeNotFoundError: If employee not found.
        """
        employee = self.get_employee(employee_id)
        employee.status = EmploymentStatus.INACTIVE
        employee.updated_at = datetime.now(timezone.utc)
        return employee

    def terminate_employee(
        self, employee_id: int, data: TerminationData
    ) -> Employee:
        """Terminate an employee.

        Args:
            employee_id: The employee ID.
            data: Termination data.

        Returns:
            The updated Employee.

        Raises:
            EmployeeNotFoundError: If employee not found.
            EmployeeStatusError: If employee is already terminated.
        """
        employee = self.get_employee(employee_id)

        if employee.status == EmploymentStatus.TERMINATED:
            raise EmployeeStatusError(
                employee.status.value,
                "Employee is already terminated",
            )

        employee.status = EmploymentStatus.TERMINATED
        employee.date_of_leaving = data.date_of_leaving
        employee.updated_at = datetime.now(timezone.utc)

        return employee

    def set_on_leave(self, employee_id: int) -> Employee:
        """Set employee status to on leave.

        Args:
            employee_id: The employee ID.

        Returns:
            The updated Employee.

        Raises:
            EmployeeNotFoundError: If employee not found.
            EmployeeStatusError: If employee is terminated.
        """
        employee = self.get_employee(employee_id)

        if employee.status == EmploymentStatus.TERMINATED:
            raise EmployeeStatusError(
                employee.status.value,
                "Cannot set terminated employee on leave",
            )

        employee.status = EmploymentStatus.ON_LEAVE
        employee.updated_at = datetime.now(timezone.utc)

        return employee

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def bulk_update(self, data: BulkUpdateData) -> BulkResult:
        """Bulk update multiple employees.

        Args:
            data: Bulk update data containing IDs and fields to update.

        Returns:
            BulkResult with count of updated employees and any failures.
        """
        if not data.ids:
            return BulkResult()

        result = BulkResult()
        now = datetime.now(timezone.utc)

        # Build update dict from non-None fields
        updates: dict = {}
        if data.department_id is not None:
            updates["department_id"] = data.department_id
        if data.designation_id is not None:
            updates["designation_id"] = data.designation_id
        if data.status is not None:
            updates["status"] = data.status
        if data.reports_to_id is not None:
            updates["reports_to_id"] = data.reports_to_id

        if not updates:
            return result

        # Add audit fields
        updates["updated_at"] = now

        # Perform bulk update using modern statement
        from sqlalchemy import update
        stmt = (
            update(Employee)
            .where(Employee.id.in_(data.ids), Employee.is_deleted == False)
            .values(**updates)
        )
        result_proxy = self.db.execute(stmt)
        result.updated_count = result_proxy.rowcount

        return result

    def bulk_update_department(
        self, employee_ids: List[int], department_id: int
    ) -> BulkResult:
        """Bulk update department for multiple employees.

        Args:
            employee_ids: List of employee IDs.
            department_id: The new department ID.

        Returns:
            BulkResult with count of updated employees.
        """
        return self.bulk_update(
            BulkUpdateData(ids=employee_ids, department_id=department_id)
        )

    def bulk_update_designation(
        self, employee_ids: List[int], designation_id: int
    ) -> BulkResult:
        """Bulk update designation for multiple employees.

        Args:
            employee_ids: List of employee IDs.
            designation_id: The new designation ID.

        Returns:
            BulkResult with count of updated employees.
        """
        return self.bulk_update(
            BulkUpdateData(ids=employee_ids, designation_id=designation_id)
        )

    def bulk_delete(self, ids: List[int]) -> BulkResult:
        """Bulk soft-delete multiple employees.

        Args:
            ids: List of employee IDs to delete.

        Returns:
            BulkResult with count of deleted employees.
        """
        if not ids:
            return BulkResult()

        result = BulkResult()
        now = datetime.now(timezone.utc)
        user_id = self.principal.id if self.principal else None

        # Perform bulk soft delete using modern statement
        from sqlalchemy import update
        stmt = (
            update(Employee)
            .where(Employee.id.in_(ids), Employee.is_deleted == False)
            .values(
                is_deleted=True,
                deleted_at=now,
                deleted_by_id=user_id,
                updated_at=now,
            )
        )
        result_proxy = self.db.execute(stmt)
        result.deleted_count = result_proxy.rowcount

        return result

    # =========================================================================
    # Party Integration
    # =========================================================================

    def link_to_party(self, employee_id: int, party_id: int) -> Employee:
        """Link an employee to an existing party.

        Args:
            employee_id: The employee ID to link.
            party_id: The party ID to link to.

        Returns:
            The updated Employee object.

        Raises:
            EmployeeNotFoundError: If employee not found.
            ValidationError: If party not found.
        """
        from app.models.party import Party

        employee = self.get_employee(employee_id)

        # Verify party exists
        party = self.db.get(Party, party_id)
        if not party:
            raise ValidationError(f"Party {party_id} not found")

        employee.party_id = party_id
        employee.updated_at = datetime.now(timezone.utc)

        return employee

    def create_party_for_employee(self, employee_id: int) -> "Party":
        """Create a party record for an employee and link them.

        Creates a new Party with type="person" and links it to the employee.
        Also creates an "employee" role for the party.

        Args:
            employee_id: The employee ID to create party for.

        Returns:
            The created Party object.

        Raises:
            EmployeeNotFoundError: If employee not found.
            ValidationError: If employee already has a party linked.
        """
        from app.models.party import Party, PartyRole

        employee = self.get_employee(employee_id)

        if employee.party_id is not None:
            raise ValidationError(
                f"Employee {employee_id} already linked to party {employee.party_id}"
            )

        # Create party from employee data
        party = Party(
            type="person",
            status="active",
            name=employee.name,
            primary_email=employee.email,
            primary_phone=employee.phone,
        )
        self.db.add(party)
        self.db.flush()  # Get party.id

        # Create employee role
        role = PartyRole(
            party_id=party.id,
            role="employee",
            status="active",
        )
        self.db.add(role)

        # Link employee to party
        employee.party_id = party.id
        employee.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        return party

    def get_or_create_party(self, employee_id: int) -> "Party":
        """Get the party linked to an employee, or create one.

        Args:
            employee_id: The employee ID.

        Returns:
            The linked or newly created Party object.

        Raises:
            EmployeeNotFoundError: If employee not found.
        """
        from app.models.party import Party

        employee = self.get_employee(employee_id)

        if employee.party_id is not None:
            party = self.db.get(Party, employee.party_id)
            if party:
                return party

        # Party doesn't exist, create one
        return self.create_party_for_employee(employee_id)

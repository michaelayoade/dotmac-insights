"""Leave service - business logic for leave management.

This service encapsulates leave-related business logic:
- Leave types and policies
- Leave allocations
- Leave applications with workflow
- Balance calculations

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.hr_leave import (
    Holiday,
    HolidayList,
    LeaveAllocation,
    LeaveAllocationStatus,
    LeaveApplication,
    LeaveApplicationStatus,
    LeavePolicy,
    LeavePolicyDetail,
    LeaveType,
)
from app.models.employee import Employee
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams

from .errors import (
    InsufficientLeaveBalanceError,
    LeaveAllocationNotFoundError,
    LeaveApplicationNotFoundError,
    LeaveOverlapError,
    LeaveStatusTransitionError,
    LeaveTypeNotFoundError,
    LeavePolicyViolationError,
    ValidationError,
)
from .leave_types import (
    AllocationCreateData,
    AllocationFilters,
    AllocationUpdateData,
    ApplicationCreateData,
    ApplicationFilters,
    ApplicationUpdateData,
    BulkAllocationData,
    BulkAllocationResult,
    BulkApprovalResult,
    HolidayData,
    HolidayListCreateData,
    HolidayListUpdateData,
    LeaveBalanceInfo,
    LeavePolicyCreateData,
    LeavePolicyDetailData,
    LeavePolicyUpdateData,
    LeaveTypeCreateData,
    LeaveTypeUpdateData,
    OverlapInfo,
    ValidationResult,
)
if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.hr_settings import HRSettings

__all__ = ["LeaveService"]


class LeaveService:
    """Service for leave management business logic.

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
        """Get HR settings, using cache for repeated access within same request.

        Args:
            company: Company code for settings lookup.

        Returns:
            HRSettings model with current settings or defaults.
        """
        cache_key = company or "__default__"
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]

        # Import here to avoid circular dependency
        from .settings import HRSettingsService

        settings_service = HRSettingsService(self.db, self.principal)
        self._settings_cache[cache_key] = settings_service.get_settings(company)
        return self._settings_cache[cache_key]

    # =========================================================================
    # Leave Types
    # =========================================================================

    def list_leave_types(
        self, include_inactive: bool = False
    ) -> List[LeaveType]:
        """List all leave types.

        Args:
            include_inactive: Include inactive leave types.

        Returns:
            List of LeaveType objects.
        """
        stmt = select(LeaveType)
        if not include_inactive:
            stmt = stmt.where(LeaveType.is_active == True)
        stmt = stmt.order_by(LeaveType.leave_type_name.asc())
        return list(self.db.scalars(stmt).all())

    def get_leave_type(self, leave_type_id: int) -> LeaveType:
        """Get a leave type by ID.

        Args:
            leave_type_id: The leave type ID.

        Returns:
            The LeaveType object.

        Raises:
            LeaveTypeNotFoundError: If leave type not found.
        """
        leave_type = self.db.get(LeaveType, leave_type_id)
        if not leave_type:
            raise LeaveTypeNotFoundError(leave_type_id)
        return leave_type

    def get_leave_type_by_name(self, name: str) -> Optional[LeaveType]:
        """Get a leave type by name."""
        return self.db.scalar(
            select(LeaveType).where(LeaveType.leave_type_name == name)
        )

    def create_leave_type(self, data: LeaveTypeCreateData) -> LeaveType:
        """Create a new leave type.

        Args:
            data: Leave type creation data.

        Returns:
            The created LeaveType (not yet committed).
        """
        existing = self.get_leave_type_by_name(data.leave_type_name)
        if existing:
            raise ValidationError(
                f"Leave type '{data.leave_type_name}' already exists"
            )

        leave_type = LeaveType(
            leave_type_name=data.leave_type_name,
            is_active=data.is_active,
            max_leaves_allowed=data.max_leaves_allowed,
            max_continuous_days_allowed=data.max_continuous_days_allowed,
            is_carry_forward=data.is_carry_forward,
            is_lwp=data.is_lwp,
            is_optional_leave=data.is_optional_leave,
            is_compensatory=data.is_compensatory,
            allow_encashment=data.allow_encashment,
            include_holiday=data.include_holiday,
            is_earned_leave=data.is_earned_leave,
            earned_leave_frequency=data.earned_leave_frequency,
            rounding=data.rounding,
        )

        self.db.add(leave_type)
        self.db.flush()
        return leave_type

    def update_leave_type(
        self, leave_type_id: int, data: LeaveTypeUpdateData
    ) -> LeaveType:
        """Update an existing leave type.

        Args:
            leave_type_id: The leave type ID.
            data: Fields to update.

        Returns:
            The updated LeaveType (not yet committed).
        """
        leave_type = self.get_leave_type(leave_type_id)

        if data.leave_type_name is not None:
            existing = self.get_leave_type_by_name(data.leave_type_name)
            if existing and existing.id != leave_type_id:
                raise ValidationError(
                    f"Leave type '{data.leave_type_name}' already exists"
                )
            leave_type.leave_type_name = data.leave_type_name
        if data.is_active is not None:
            leave_type.is_active = data.is_active

        if data.max_leaves_allowed is not None:
            leave_type.max_leaves_allowed = data.max_leaves_allowed
        if data.max_continuous_days_allowed is not None:
            leave_type.max_continuous_days_allowed = data.max_continuous_days_allowed
        if data.is_carry_forward is not None:
            leave_type.is_carry_forward = data.is_carry_forward
        if data.is_lwp is not None:
            leave_type.is_lwp = data.is_lwp
        if data.is_optional_leave is not None:
            leave_type.is_optional_leave = data.is_optional_leave
        if data.is_compensatory is not None:
            leave_type.is_compensatory = data.is_compensatory
        if data.allow_encashment is not None:
            leave_type.allow_encashment = data.allow_encashment
        if data.include_holiday is not None:
            leave_type.include_holiday = data.include_holiday
        if data.is_earned_leave is not None:
            leave_type.is_earned_leave = data.is_earned_leave
        if data.earned_leave_frequency is not None:
            leave_type.earned_leave_frequency = data.earned_leave_frequency
        if data.rounding is not None:
            leave_type.rounding = data.rounding

        leave_type.updated_at = datetime.now(timezone.utc)
        return leave_type

    # =========================================================================
    # Leave Policies
    # =========================================================================

    def list_leave_policies(self) -> List[LeavePolicy]:
        """List all leave policies."""
        stmt = select(LeavePolicy).order_by(LeavePolicy.leave_policy_name.asc())
        return list(self.db.scalars(stmt).all())

    def get_leave_policy(self, policy_id: int) -> LeavePolicy:
        """Get a leave policy by ID."""
        policy = self.db.get(LeavePolicy, policy_id)
        if not policy:
            raise ValidationError(f"Leave policy {policy_id} not found")
        return policy

    def create_leave_policy(self, data: LeavePolicyCreateData) -> LeavePolicy:
        """Create a new leave policy with details."""
        policy = LeavePolicy(leave_policy_name=data.leave_policy_name)
        self.db.add(policy)
        self.db.flush()

        for idx, detail_data in enumerate(data.details):
            detail = LeavePolicyDetail(
                leave_policy_id=policy.id,
                leave_type=detail_data.leave_type,
                leave_type_id=detail_data.leave_type_id,
                annual_allocation=detail_data.annual_allocation,
                idx=idx,
            )
            self.db.add(detail)

        self.db.flush()
        return policy

    def update_leave_policy(
        self, policy_id: int, data: LeavePolicyUpdateData
    ) -> LeavePolicy:
        """Update an existing leave policy."""
        policy = self.get_leave_policy(policy_id)

        if data.leave_policy_name is not None:
            policy.leave_policy_name = data.leave_policy_name

        if data.details is not None:
            # Remove existing details using modern statement
            from sqlalchemy import delete
            self.db.execute(
                delete(LeavePolicyDetail).where(
                    LeavePolicyDetail.leave_policy_id == policy_id
                )
            )

            # Add new details
            for idx, detail_data in enumerate(data.details):
                detail = LeavePolicyDetail(
                    leave_policy_id=policy.id,
                    leave_type=detail_data.leave_type,
                    leave_type_id=detail_data.leave_type_id,
                    annual_allocation=detail_data.annual_allocation,
                    idx=idx,
                )
                self.db.add(detail)

        policy.updated_at = datetime.now(timezone.utc)
        return policy

    # =========================================================================
    # Leave Allocations
    # =========================================================================

    def list_allocations(
        self,
        filters: Optional[AllocationFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[LeaveAllocation]:
        """List leave allocations with filters and pagination."""
        if filters is None:
            filters = AllocationFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(LeaveAllocation)

        if filters.employee_id:
            stmt = stmt.where(LeaveAllocation.employee_id == filters.employee_id)
        if filters.leave_type_id:
            stmt = stmt.where(LeaveAllocation.leave_type_id == filters.leave_type_id)
        if filters.status:
            stmt = stmt.where(LeaveAllocation.status == filters.status)
        if filters.from_date:
            stmt = stmt.where(LeaveAllocation.from_date >= filters.from_date)
        if filters.to_date:
            stmt = stmt.where(LeaveAllocation.to_date <= filters.to_date)
        if filters.company:
            stmt = stmt.where(LeaveAllocation.company == filters.company)

        stmt = stmt.order_by(LeaveAllocation.from_date.desc())
        return paginate(self.db, stmt, pagination)

    def get_current_allocations(
        self,
        employee_id: int,
        as_of: Optional[date] = None,
    ) -> List[LeaveAllocation]:
        """Get leave allocations valid on a specific date.

        Returns allocations where from_date <= as_of AND to_date >= as_of.

        Args:
            employee_id: The employee ID.
            as_of: Date to check validity (defaults to today).

        Returns:
            List of LeaveAllocation objects valid on the given date.
        """
        check_date = as_of or date.today()

        stmt = (
            select(LeaveAllocation)
            .where(
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.from_date <= check_date,
                LeaveAllocation.to_date >= check_date,
            )
            .order_by(LeaveAllocation.leave_type_id)
        )

        return list(self.db.scalars(stmt).all())

    def get_allocation(self, allocation_id: int) -> LeaveAllocation:
        """Get a leave allocation by ID."""
        allocation = self.db.get(LeaveAllocation, allocation_id)
        if not allocation:
            raise LeaveAllocationNotFoundError(allocation_id)
        return allocation

    def create_allocation(self, data: AllocationCreateData) -> LeaveAllocation:
        """Create a new leave allocation."""
        total = data.new_leaves_allocated + data.carry_forwarded_leaves

        allocation = LeaveAllocation(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            leave_type_id=data.leave_type_id,
            leave_type=data.leave_type,
            from_date=data.from_date,
            to_date=data.to_date,
            new_leaves_allocated=data.new_leaves_allocated,
            total_leaves_allocated=total,
            unused_leaves=total,
            carry_forwarded_leaves=data.carry_forwarded_leaves,
            leave_policy=data.leave_policy,
            company=data.company,
            status=LeaveAllocationStatus.SUBMITTED,
            docstatus=1,
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(allocation)
        self.db.flush()
        return allocation

    def update_allocation(
        self, allocation_id: int, data: AllocationUpdateData
    ) -> LeaveAllocation:
        """Update an existing leave allocation."""
        allocation = self.get_allocation(allocation_id)

        if data.new_leaves_allocated is not None:
            allocation.new_leaves_allocated = data.new_leaves_allocated
            # Recalculate total
            allocation.total_leaves_allocated = (
                data.new_leaves_allocated +
                (allocation.carry_forwarded_leaves or Decimal("0"))
            )
        if data.carry_forwarded_leaves is not None:
            allocation.carry_forwarded_leaves = data.carry_forwarded_leaves
        if data.unused_leaves is not None:
            allocation.unused_leaves = data.unused_leaves
        if data.status is not None:
            allocation.status = data.status
            allocation.status_changed_by_id = self.principal.id if self.principal else None
            allocation.status_changed_at = datetime.now(timezone.utc)

        allocation.updated_by_id = self.principal.id if self.principal else None
        allocation.updated_at = datetime.now(timezone.utc)
        return allocation

    def bulk_allocate(self, data: BulkAllocationData) -> BulkAllocationResult:
        """Create leave allocations for multiple employees."""
        result = BulkAllocationResult()

        # Get employee info
        stmt = (
            select(Employee)
            .where(Employee.id.in_(data.employee_ids), Employee.is_deleted == False)
        )
        employees = self.db.scalars(stmt).all()
        emp_map = {e.id: e for e in employees}

        for emp_id in data.employee_ids:
            emp = emp_map.get(emp_id)
            if not emp:
                result.skipped_count += 1
                result.skipped_employees.append(emp_id)
                result.errors.append(f"Employee {emp_id} not found")
                continue

            # Check for existing allocation
            existing = self.db.scalar(
                select(LeaveAllocation).where(
                    LeaveAllocation.employee_id == emp_id,
                    LeaveAllocation.leave_type_id == data.leave_type_id,
                    LeaveAllocation.from_date == data.from_date,
                    LeaveAllocation.to_date == data.to_date,
                )
            )
            if existing:
                result.skipped_count += 1
                result.skipped_employees.append(emp_id)
                continue

            allocation = LeaveAllocation(
                employee_id=emp_id,
                employee=emp.erpnext_id or str(emp_id),
                employee_name=emp.name,
                leave_type_id=data.leave_type_id,
                leave_type=data.leave_type,
                from_date=data.from_date,
                to_date=data.to_date,
                new_leaves_allocated=data.new_leaves_allocated,
                total_leaves_allocated=data.new_leaves_allocated,
                unused_leaves=data.new_leaves_allocated,
                company=data.company,
                status=LeaveAllocationStatus.SUBMITTED,
                docstatus=1,
                created_by_id=self.principal.id if self.principal else None,
            )
            self.db.add(allocation)
            result.created_count += 1

        self.db.flush()
        return result

    # =========================================================================
    # Leave Applications
    # =========================================================================

    def list_applications(
        self,
        filters: Optional[ApplicationFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[LeaveApplication]:
        """List leave applications with filters and pagination."""
        if filters is None:
            filters = ApplicationFilters()
        if pagination is None:
            pagination = PaginationParams()

        stmt = select(LeaveApplication)

        if filters.employee_id:
            stmt = stmt.where(LeaveApplication.employee_id == filters.employee_id)
        if filters.leave_type_id:
            stmt = stmt.where(LeaveApplication.leave_type_id == filters.leave_type_id)
        if filters.status:
            stmt = stmt.where(LeaveApplication.status == filters.status)
        if filters.from_date:
            stmt = stmt.where(LeaveApplication.from_date >= filters.from_date)
        if filters.to_date:
            stmt = stmt.where(LeaveApplication.to_date <= filters.to_date)
        if filters.company:
            stmt = stmt.where(LeaveApplication.company == filters.company)
        if filters.search:
            search_term = f"%{filters.search}%"
            stmt = stmt.where(
                or_(
                    LeaveApplication.employee_name.ilike(search_term),
                    LeaveApplication.employee.ilike(search_term),
                )
            )

        stmt = stmt.order_by(LeaveApplication.created_at.desc())
        return paginate(self.db, stmt, pagination)

    def get_application(self, application_id: int) -> LeaveApplication:
        """Get a leave application by ID."""
        application = self.db.get(LeaveApplication, application_id)
        if not application:
            raise LeaveApplicationNotFoundError(application_id)
        return application

    def create_application(self, data: ApplicationCreateData) -> LeaveApplication:
        """Create a new leave application."""
        # Calculate total leave days if not provided
        total_days = data.total_leave_days
        if total_days is None:
            days = (data.to_date - data.from_date).days + 1
            total_days = Decimal(str(days))
            if data.half_day:
                total_days = total_days - Decimal("0.5")

        posting_date = data.posting_date or date.today()

        application = LeaveApplication(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            leave_type_id=data.leave_type_id,
            leave_type=data.leave_type,
            from_date=data.from_date,
            to_date=data.to_date,
            posting_date=posting_date,
            half_day=data.half_day,
            half_day_date=data.half_day_date,
            total_leave_days=total_days,
            description=data.description,
            leave_approver=data.leave_approver,
            leave_approver_name=data.leave_approver_name,
            company=data.company,
            status=LeaveApplicationStatus.OPEN,
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(application)
        self.db.flush()
        return application

    def update_application(
        self, application_id: int, data: ApplicationUpdateData
    ) -> LeaveApplication:
        """Update an existing leave application."""
        application = self.get_application(application_id)

        if data.from_date is not None:
            application.from_date = data.from_date
        if data.to_date is not None:
            application.to_date = data.to_date
        if data.half_day is not None:
            application.half_day = data.half_day
        if data.half_day_date is not None:
            application.half_day_date = data.half_day_date
        if data.total_leave_days is not None:
            application.total_leave_days = data.total_leave_days
        if data.description is not None:
            application.description = data.description
        if data.leave_approver is not None:
            application.leave_approver = data.leave_approver
        if data.leave_approver_name is not None:
            application.leave_approver_name = data.leave_approver_name

        application.updated_by_id = self.principal.id if self.principal else None
        application.updated_at = datetime.now(timezone.utc)
        return application

    def delete_application(self, application_id: int) -> None:
        """Delete a leave application (only if open)."""
        application = self.get_application(application_id)

        if application.status != LeaveApplicationStatus.OPEN:
            raise LeaveStatusTransitionError(
                application.status.value, "deleted",
            )

        self.db.delete(application)

    # =========================================================================
    # Workflow Actions
    # =========================================================================

    def approve_application(
        self, application_id: int, remarks: Optional[str] = None
    ) -> LeaveApplication:
        """Approve a leave application.

        Uses HR settings for:
        - allow_negative_leave_balance: Whether to allow approval with negative balance
        """
        application = self.get_application(application_id)

        if application.status != LeaveApplicationStatus.OPEN:
            raise LeaveStatusTransitionError(
                application.status.value, LeaveApplicationStatus.APPROVED.value
            )

        # Get settings for validation rules
        settings = self._get_settings(application.company)

        # Validate balance (unless negative balance is allowed)
        balance = self.get_employee_balance(
            application.employee_id,
            application.leave_type_id,
            application.from_date,
        )
        if balance.available < application.total_leave_days:
            if not settings.allow_negative_leave_balance:
                raise InsufficientLeaveBalanceError(
                    float(balance.available),
                    float(application.total_leave_days),
                    application.leave_type,
                )
            # If negative balance is allowed, proceed with approval

        application.status = LeaveApplicationStatus.APPROVED
        application.docstatus = 1
        application.status_changed_by_id = self.principal.id if self.principal else None
        application.status_changed_at = datetime.now(timezone.utc)
        application.updated_at = datetime.now(timezone.utc)

        # Update allocation unused_leaves
        self._deduct_from_allocation(application)

        return application

    def reject_application(
        self, application_id: int, reason: str
    ) -> LeaveApplication:
        """Reject a leave application."""
        application = self.get_application(application_id)

        if application.status != LeaveApplicationStatus.OPEN:
            raise LeaveStatusTransitionError(
                application.status.value, LeaveApplicationStatus.REJECTED.value
            )

        application.status = LeaveApplicationStatus.REJECTED
        application.status_changed_by_id = self.principal.id if self.principal else None
        application.status_changed_at = datetime.now(timezone.utc)
        application.updated_at = datetime.now(timezone.utc)

        return application

    def cancel_application(
        self, application_id: int, reason: Optional[str] = None
    ) -> LeaveApplication:
        """Cancel a leave application."""
        application = self.get_application(application_id)

        if application.status == LeaveApplicationStatus.CANCELLED:
            raise LeaveStatusTransitionError(
                application.status.value, LeaveApplicationStatus.CANCELLED.value
            )

        # If was approved, restore balance
        if application.status == LeaveApplicationStatus.APPROVED:
            self._restore_to_allocation(application)

        application.status = LeaveApplicationStatus.CANCELLED
        application.docstatus = 2
        application.status_changed_by_id = self.principal.id if self.principal else None
        application.status_changed_at = datetime.now(timezone.utc)
        application.updated_at = datetime.now(timezone.utc)

        return application

    def bulk_approve(self, application_ids: List[int]) -> BulkApprovalResult:
        """Bulk approve multiple leave applications."""
        result = BulkApprovalResult()

        for app_id in application_ids:
            try:
                self.approve_application(app_id)
                result.approved_count += 1
            except Exception as e:
                result.skipped.append({"id": app_id, "error": str(e)})

        return result

    def bulk_reject(
        self, application_ids: List[int], reason: str
    ) -> BulkApprovalResult:
        """Bulk reject multiple leave applications."""
        result = BulkApprovalResult()

        for app_id in application_ids:
            try:
                self.reject_application(app_id, reason)
                result.rejected_count += 1
            except Exception as e:
                result.skipped.append({"id": app_id, "error": str(e)})

        return result

    # =========================================================================
    # Balance & Validation
    # =========================================================================

    def get_employee_balance(
        self, employee_id: int, leave_type_id: int, as_of: date
    ) -> LeaveBalanceInfo:
        """Get employee leave balance for a specific leave type."""
        leave_type = self.get_leave_type(leave_type_id)

        # Get current allocation
        allocation = self.db.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.leave_type_id == leave_type_id,
                LeaveAllocation.from_date <= as_of,
                LeaveAllocation.to_date >= as_of,
                LeaveAllocation.status == LeaveAllocationStatus.SUBMITTED,
            )
        )

        total_allocated = Decimal("0")
        carry_forwarded = Decimal("0")
        unused = Decimal("0")

        if allocation:
            total_allocated = allocation.total_leaves_allocated or Decimal("0")
            carry_forwarded = allocation.carry_forwarded_leaves or Decimal("0")
            unused = allocation.unused_leaves or Decimal("0")

        # Get approved leaves used
        used = self.db.scalar(
            select(func.coalesce(func.sum(LeaveApplication.total_leave_days), 0)).where(
                LeaveApplication.employee_id == employee_id,
                LeaveApplication.leave_type_id == leave_type_id,
                LeaveApplication.status == LeaveApplicationStatus.APPROVED,
                LeaveApplication.from_date >= (allocation.from_date if allocation else as_of),
            )
        ) or Decimal("0")

        # Get pending approvals
        pending = self.db.scalar(
            select(func.coalesce(func.sum(LeaveApplication.total_leave_days), 0)).where(
                LeaveApplication.employee_id == employee_id,
                LeaveApplication.leave_type_id == leave_type_id,
                LeaveApplication.status == LeaveApplicationStatus.OPEN,
            )
        ) or Decimal("0")

        available = total_allocated - used

        return LeaveBalanceInfo(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_type_name=leave_type.leave_type_name,
            total_allocated=total_allocated,
            used=used,
            available=available,
            carry_forwarded=carry_forwarded,
            pending_approval=pending,
        )

    def get_employee_all_balances(
        self, employee_id: int, as_of: date
    ) -> List[LeaveBalanceInfo]:
        """Get all leave balances for an employee."""
        leave_types = self.list_leave_types()
        balances = []

        for lt in leave_types:
            balance = self.get_employee_balance(employee_id, lt.id, as_of)
            balances.append(balance)

        return balances

    def validate_application(
        self, data: ApplicationCreateData, company: Optional[str] = None
    ) -> ValidationResult:
        """Validate a leave application before creation.

        Uses HR settings for configurable validation rules:
        - allow_leave_overlap: Whether overlapping leave is permitted
        - allow_negative_leave_balance: Whether negative balance is allowed
        - min_leave_notice_days: Minimum days notice required
        """
        errors = []
        warnings = []

        # Get settings for validation rules
        settings = self._get_settings(company)

        # Check dates
        if data.to_date < data.from_date:
            errors.append("To date cannot be before from date")

        # Check minimum notice period
        if settings.min_leave_notice_days > 0:
            notice_days = (data.from_date - date.today()).days
            if notice_days < settings.min_leave_notice_days:
                errors.append(
                    f"Leave application requires at least {settings.min_leave_notice_days} "
                    f"days notice. You provided {notice_days} days."
                )

        # Check for overlapping applications (if not allowed by settings)
        if not settings.allow_leave_overlap:
            overlap = self.check_overlap(
                data.employee_id, data.from_date, data.to_date
            )
            if overlap:
                errors.append(
                    f"Overlaps with existing application ({overlap.from_date} to {overlap.to_date})"
                )

        # Check balance
        balance = self.get_employee_balance(
            data.employee_id, data.leave_type_id, data.from_date
        )
        days = (data.to_date - data.from_date).days + 1
        if data.half_day:
            days -= 0.5

        requested_days = Decimal(str(days))
        if requested_days > balance.available:
            if settings.allow_negative_leave_balance:
                # Allow but warn
                warnings.append(
                    f"This will result in negative balance. "
                    f"Available: {balance.available}, Requested: {days}"
                )
            else:
                errors.append(
                    f"Insufficient balance. Available: {balance.available}, Requested: {days}"
                )

        # Check leave type constraints
        leave_type = self.get_leave_type(data.leave_type_id)
        if leave_type.max_continuous_days_allowed:
            if days > leave_type.max_continuous_days_allowed:
                errors.append(
                    f"Exceeds maximum continuous days ({leave_type.max_continuous_days_allowed})"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def check_overlap(
        self,
        employee_id: int,
        from_date: date,
        to_date: date,
        exclude_id: Optional[int] = None,
    ) -> Optional[OverlapInfo]:
        """Check for overlapping leave applications."""
        stmt = select(LeaveApplication).where(
            LeaveApplication.employee_id == employee_id,
            LeaveApplication.status.in_([
                LeaveApplicationStatus.OPEN,
                LeaveApplicationStatus.APPROVED,
            ]),
            # Overlapping dates check
            and_(
                LeaveApplication.from_date <= to_date,
                LeaveApplication.to_date >= from_date,
            ),
        )

        if exclude_id:
            stmt = stmt.where(LeaveApplication.id != exclude_id)

        overlap = self.db.scalar(stmt)

        if overlap:
            return OverlapInfo(
                id=overlap.id,
                from_date=overlap.from_date,
                to_date=overlap.to_date,
                leave_type=overlap.leave_type,
                status=overlap.status.value,
            )

        return None

    # =========================================================================
    # Holiday Lists
    # =========================================================================

    def list_holiday_lists(self, year: Optional[int] = None) -> List[HolidayList]:
        """List holiday lists, optionally filtered by year."""
        stmt = select(HolidayList)

        if year:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            stmt = stmt.where(
                HolidayList.from_date <= end,
                HolidayList.to_date >= start,
            )

        stmt = stmt.order_by(HolidayList.holiday_list_name.asc())
        return list(self.db.scalars(stmt).all())

    def get_holiday_list(self, list_id: int) -> HolidayList:
        """Get a holiday list by ID."""
        holiday_list = self.db.get(HolidayList, list_id)
        if not holiday_list:
            raise ValidationError(f"Holiday list {list_id} not found")
        return holiday_list

    def create_holiday_list(self, data: HolidayListCreateData) -> HolidayList:
        """Create a new holiday list."""
        # Validate date range
        if data.from_date and data.to_date:
            if data.from_date > data.to_date:
                raise ValidationError("From date must be before or equal to to date")

        holiday_list = HolidayList(
            holiday_list_name=data.holiday_list_name,
            from_date=data.from_date,
            to_date=data.to_date,
            company=data.company,
            weekly_off=data.weekly_off,
        )
        self.db.add(holiday_list)
        self.db.flush()
        return holiday_list

    def add_holiday(self, list_id: int, data: HolidayData) -> Holiday:
        """Add a holiday to a holiday list."""
        holiday_list = self.get_holiday_list(list_id)

        # Get next idx
        max_idx = self.db.scalar(
            select(func.max(Holiday.idx)).where(Holiday.holiday_list_id == list_id)
        ) or 0

        holiday = Holiday(
            holiday_list_id=list_id,
            holiday_date=data.holiday_date,
            description=data.description,
            weekly_off=data.weekly_off,
            idx=max_idx + 1,
        )
        self.db.add(holiday)

        # Update total count
        holiday_list.total_holidays = (holiday_list.total_holidays or 0) + 1
        self.db.flush()

        return holiday

    def remove_holiday(self, list_id: int, holiday_id: int) -> None:
        """Remove a holiday from a holiday list."""
        holiday_list = self.get_holiday_list(list_id)

        holiday = self.db.scalar(
            select(Holiday).where(Holiday.id == holiday_id, Holiday.holiday_list_id == list_id)
        )
        if not holiday:
            raise ValidationError(f"Holiday {holiday_id} not found in list {list_id}")

        self.db.delete(holiday)
        holiday_list.total_holidays = max(0, (holiday_list.total_holidays or 1) - 1)

    def is_holiday(self, holiday_list_id: int, check_date: date) -> bool:
        """Check if a date is a holiday."""
        holiday = self.db.scalar(
            select(Holiday).where(
                Holiday.holiday_list_id == holiday_list_id,
                Holiday.holiday_date == check_date,
            )
        )
        return holiday is not None

    def update_holiday_list(
        self, list_id: int, data: "HolidayListUpdateData"
    ) -> HolidayList:
        """Update a holiday list."""
        from app.services.hr.leave_types import HolidayListUpdateData

        holiday_list = self.get_holiday_list(list_id)

        # Check for duplicate name (excluding self)
        if data.holiday_list_name is not None:
            existing = self.db.scalar(
                select(HolidayList).where(
                    HolidayList.holiday_list_name == data.holiday_list_name,
                    HolidayList.id != list_id,
                )
            )
            if existing:
                raise ValidationError(
                    f"Holiday list with name '{data.holiday_list_name}' already exists"
                )
            holiday_list.holiday_list_name = data.holiday_list_name

        if data.from_date is not None:
            holiday_list.from_date = data.from_date
        if data.to_date is not None:
            holiday_list.to_date = data.to_date

        # Validate date range
        if holiday_list.from_date and holiday_list.to_date:
            if holiday_list.from_date > holiday_list.to_date:
                raise ValidationError("From date must be before or equal to to date")

        if data.company is not None:
            holiday_list.company = data.company
        if data.weekly_off is not None:
            holiday_list.weekly_off = data.weekly_off

        self.db.flush()
        return holiday_list

    def delete_holiday_list(self, list_id: int) -> None:
        """Delete a holiday list and its holidays."""
        holiday_list = self.get_holiday_list(list_id)

        # Delete associated holidays
        self.db.execute(
            Holiday.__table__.delete().where(Holiday.holiday_list_id == list_id)
        )

        self.db.delete(holiday_list)
        self.db.flush()

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _deduct_from_allocation(self, application: LeaveApplication) -> None:
        """Deduct leave days from allocation."""
        allocation = self.db.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.employee_id == application.employee_id,
                LeaveAllocation.leave_type_id == application.leave_type_id,
                LeaveAllocation.from_date <= application.from_date,
                LeaveAllocation.to_date >= application.to_date,
                LeaveAllocation.status == LeaveAllocationStatus.SUBMITTED,
            )
        )

        if allocation:
            allocation.unused_leaves = (
                (allocation.unused_leaves or Decimal("0")) -
                (application.total_leave_days or Decimal("0"))
            )

    def _restore_to_allocation(self, application: LeaveApplication) -> None:
        """Restore leave days to allocation (on cancellation)."""
        allocation = self.db.scalar(
            select(LeaveAllocation).where(
                LeaveAllocation.employee_id == application.employee_id,
                LeaveAllocation.leave_type_id == application.leave_type_id,
                LeaveAllocation.from_date <= application.from_date,
                LeaveAllocation.to_date >= application.to_date,
                LeaveAllocation.status == LeaveAllocationStatus.SUBMITTED,
            )
        )

        if allocation:
            allocation.unused_leaves = (
                (allocation.unused_leaves or Decimal("0")) +
                (application.total_leave_days or Decimal("0"))
            )

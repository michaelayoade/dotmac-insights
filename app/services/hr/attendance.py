"""Attendance service for HR module.

Handles shift types, shift assignments, attendance records,
check-in/check-out, and attendance requests.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.utils.datetime_utils import utc_now
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Set

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.hr_attendance import (
    Attendance,
    AttendanceRequest,
    AttendanceRequestStatus,
    AttendanceStatus,
    ShiftAssignment,
    ShiftType,
)
from app.models.employee import Employee
from app.services.base import apply_sort, paginate, safe_filter, scoped_query
from app.services.hr.attendance_types import (
    AttendanceCreateData,
    AttendanceFilters,
    AttendanceRequestCreateData,
    AttendanceRequestFilters,
    AttendanceSummary,
    AttendanceUpdateData,
    BulkResult,
    BulkShiftAssignmentData,
    CheckInData,
    CheckOutData,
    DepartmentAttendanceSummary,
    LateArrivalRecord,
    ShiftAssignmentCreateData,
    ShiftAssignmentFilters,
    ShiftAssignmentUpdateData,
    ShiftTypeCreateData,
    ShiftTypeUpdateData,
    WorkingHoursSummary,
)
from app.services.hr.errors import (
    AttendanceNotFoundError,
    AttendanceRequestNotFoundError,
    AttendanceRequestStatusError,
    CheckInError,
    CheckOutError,
    DuplicateAttendanceError,
    ShiftAssignmentError,
    ShiftAssignmentNotFoundError,
    ShiftTypeNotFoundError,
    ValidationError,
)
from app.services.types import PaginatedResult, PaginationParams, SortParams

if TYPE_CHECKING:
    from app.models.hr_settings import HRSettings
    from app.web.context import Principal

__all__ = ["AttendanceService"]


class AttendanceService:
    """Service for attendance management operations.

    Uses HR settings for configurable behavior:
    - late_entry_grace_minutes: Default grace period for late arrivals
    - early_exit_grace_minutes: Default grace period for early exits
    - half_day_hours_threshold: Hours threshold for half-day status
    - full_day_hours_threshold: Standard working hours per day
    - allow_backdated_attendance: Whether backdated entries are allowed
    - backdated_attendance_days: How far back attendance can be recorded
    - geolocation_required: Whether check-in requires location
    """

    def __init__(
        self, db: Session, principal: Optional["Principal"] = None
    ) -> None:
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

    # ==========================================================================
    # Shift Types
    # ==========================================================================

    def list_shift_types(
        self,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[ShiftType]:
        """List all shift types with pagination."""
        query = select(ShiftType)

        if sort:
            query = apply_sort(query, ShiftType, sort)
        else:
            query = query.order_by(ShiftType.shift_type_name)

        return paginate(self.db, query, pagination)

    def get_shift_type(self, shift_type_id: int) -> ShiftType:
        """Get a shift type by ID."""
        shift_type = self.db.get(ShiftType, shift_type_id)
        if not shift_type:
            raise ShiftTypeNotFoundError(shift_type_id)
        return shift_type

    def get_shift_type_by_name(self, name: str) -> Optional[ShiftType]:
        """Get a shift type by name."""
        return self.db.scalar(
            select(ShiftType).where(ShiftType.shift_type_name == name)
        )

    def create_shift_type(self, data: ShiftTypeCreateData) -> ShiftType:
        """Create a new shift type."""
        shift_type = ShiftType(
            shift_type_name=data.shift_type_name,
            start_time=data.start_time,
            end_time=data.end_time,
            working_hours_threshold_for_half_day=data.working_hours_threshold_for_half_day,
            working_hours_threshold_for_absent=data.working_hours_threshold_for_absent,
            determine_check_in_and_check_out=data.determine_check_in_and_check_out,
            begin_check_in_before_shift_start_time=data.begin_check_in_before_shift_start_time,
            allow_check_out_after_shift_end_time=data.allow_check_out_after_shift_end_time,
            enable_auto_attendance=data.enable_auto_attendance,
            enable_entry_grace_period=data.enable_entry_grace_period,
            late_entry_grace_period=data.late_entry_grace_period,
            enable_exit_grace_period=data.enable_exit_grace_period,
            early_exit_grace_period=data.early_exit_grace_period,
            holiday_list=data.holiday_list,
        )
        self.db.add(shift_type)
        self.db.flush()
        return shift_type

    def update_shift_type(
        self, shift_type_id: int, data: ShiftTypeUpdateData
    ) -> ShiftType:
        """Update a shift type."""
        shift_type = self.get_shift_type(shift_type_id)

        if data.shift_type_name is not None:
            shift_type.shift_type_name = data.shift_type_name
        if data.start_time is not None:
            shift_type.start_time = data.start_time
        if data.end_time is not None:
            shift_type.end_time = data.end_time
        if data.working_hours_threshold_for_half_day is not None:
            shift_type.working_hours_threshold_for_half_day = (
                data.working_hours_threshold_for_half_day
            )
        if data.working_hours_threshold_for_absent is not None:
            shift_type.working_hours_threshold_for_absent = (
                data.working_hours_threshold_for_absent
            )
        if data.determine_check_in_and_check_out is not None:
            shift_type.determine_check_in_and_check_out = (
                data.determine_check_in_and_check_out
            )
        if data.begin_check_in_before_shift_start_time is not None:
            shift_type.begin_check_in_before_shift_start_time = (
                data.begin_check_in_before_shift_start_time
            )
        if data.allow_check_out_after_shift_end_time is not None:
            shift_type.allow_check_out_after_shift_end_time = (
                data.allow_check_out_after_shift_end_time
            )
        if data.enable_auto_attendance is not None:
            shift_type.enable_auto_attendance = data.enable_auto_attendance
        if data.enable_entry_grace_period is not None:
            shift_type.enable_entry_grace_period = data.enable_entry_grace_period
        if data.late_entry_grace_period is not None:
            shift_type.late_entry_grace_period = data.late_entry_grace_period
        if data.enable_exit_grace_period is not None:
            shift_type.enable_exit_grace_period = data.enable_exit_grace_period
        if data.early_exit_grace_period is not None:
            shift_type.early_exit_grace_period = data.early_exit_grace_period
        if data.holiday_list is not None:
            shift_type.holiday_list = data.holiday_list

        self.db.flush()
        return shift_type

    def delete_shift_type(self, shift_type_id: int) -> None:
        """Delete a shift type."""
        shift_type = self.get_shift_type(shift_type_id)
        self.db.delete(shift_type)
        self.db.flush()

    # ==========================================================================
    # Shift Assignments
    # ==========================================================================

    def list_shift_assignments(
        self,
        filters: Optional[ShiftAssignmentFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[ShiftAssignment]:
        """List shift assignments with filters."""
        query = select(ShiftAssignment)

        if filters:
            if filters.employee_id is not None:
                query = query.where(ShiftAssignment.employee_id == filters.employee_id)
            if filters.shift_type_id is not None:
                query = query.where(
                    ShiftAssignment.shift_type_id == filters.shift_type_id
                )
            if filters.start_date is not None:
                query = query.where(ShiftAssignment.start_date >= filters.start_date)
            if filters.end_date is not None:
                query = query.where(
                    or_(
                        ShiftAssignment.end_date.is_(None),
                        ShiftAssignment.end_date <= filters.end_date,
                    )
                )
            if filters.company is not None:
                query = query.where(ShiftAssignment.company == filters.company)

        if sort:
            query = apply_sort(query, ShiftAssignment, sort)
        else:
            query = query.order_by(ShiftAssignment.start_date.desc())

        return paginate(self.db, query, pagination)

    def get_shift_assignment(self, assignment_id: int) -> ShiftAssignment:
        """Get a shift assignment by ID."""
        assignment = self.db.get(ShiftAssignment, assignment_id)
        if not assignment:
            raise ShiftAssignmentNotFoundError(assignment_id)
        return assignment

    def get_employee_current_shift(
        self, employee_id: int, on_date: Optional[date] = None
    ) -> Optional[ShiftAssignment]:
        """Get the current shift assignment for an employee."""
        check_date = on_date or date.today()

        return self.db.scalar(
            select(ShiftAssignment)
            .where(
                and_(
                    ShiftAssignment.employee_id == employee_id,
                    ShiftAssignment.start_date <= check_date,
                    or_(
                        ShiftAssignment.end_date.is_(None),
                        ShiftAssignment.end_date >= check_date,
                    ),
                )
            )
            .order_by(ShiftAssignment.start_date.desc())
            .limit(1)
        )

    def create_shift_assignment(
        self, data: ShiftAssignmentCreateData
    ) -> ShiftAssignment:
        """Create a new shift assignment."""
        # Check for overlapping assignments
        overlap = self._check_shift_overlap(
            data.employee_id, data.start_date, data.end_date
        )
        if overlap:
            raise ShiftAssignmentError(
                f"Overlapping shift assignment exists from {overlap.start_date}"
            )

        assignment = ShiftAssignment(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            shift_type_id=data.shift_type_id,
            shift_type=data.shift_type,
            start_date=data.start_date,
            end_date=data.end_date,
            company=data.company,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def update_shift_assignment(
        self, assignment_id: int, data: ShiftAssignmentUpdateData
    ) -> ShiftAssignment:
        """Update a shift assignment."""
        assignment = self.get_shift_assignment(assignment_id)

        # Check for overlaps if dates are changing
        if data.start_date is not None or data.end_date is not None:
            new_start = data.start_date or assignment.start_date
            new_end = data.end_date if data.end_date is not None else assignment.end_date
            overlap = self._check_shift_overlap(
                assignment.employee_id, new_start, new_end, exclude_id=assignment_id
            )
            if overlap:
                raise ShiftAssignmentError(
                    f"Overlapping shift assignment exists from {overlap.start_date}"
                )

        if data.shift_type_id is not None:
            assignment.shift_type_id = data.shift_type_id
        if data.shift_type is not None:
            assignment.shift_type = data.shift_type
        if data.start_date is not None:
            assignment.start_date = data.start_date
        if data.end_date is not None:
            assignment.end_date = data.end_date

        self.db.flush()
        return assignment

    def delete_shift_assignment(self, assignment_id: int) -> None:
        """Delete a shift assignment."""
        assignment = self.get_shift_assignment(assignment_id)
        self.db.delete(assignment)
        self.db.flush()

    def bulk_assign_shifts(self, data: BulkShiftAssignmentData) -> BulkResult:
        """Assign a shift to multiple employees."""
        result = BulkResult()

        for employee_id in data.employee_ids:
            try:
                # Get employee info
                employee = self.db.get(Employee, employee_id)
                if not employee:
                    result.failed_ids.append(employee_id)
                    result.errors.append(f"Employee {employee_id} not found")
                    continue

                # Check for overlap
                overlap = self._check_shift_overlap(
                    employee_id, data.start_date, data.end_date
                )
                if overlap:
                    result.skipped_count += 1
                    continue

                assignment = ShiftAssignment(
                    employee_id=employee_id,
                    employee=employee.erpnext_id or str(employee_id),
                    employee_name=employee.name,
                    shift_type_id=data.shift_type_id,
                    shift_type=data.shift_type,
                    start_date=data.start_date,
                    end_date=data.end_date,
                    company=data.company,
                )
                self.db.add(assignment)
                result.created_count += 1

            except Exception as e:
                result.failed_ids.append(employee_id)
                result.errors.append(str(e))

        self.db.flush()
        return result

    def _check_shift_overlap(
        self,
        employee_id: int,
        start_date: date,
        end_date: Optional[date],
        exclude_id: Optional[int] = None,
    ) -> Optional[ShiftAssignment]:
        """Check for overlapping shift assignments."""
        query = select(ShiftAssignment).where(
            ShiftAssignment.employee_id == employee_id
        )

        if exclude_id:
            query = query.where(ShiftAssignment.id != exclude_id)

        # Check overlap logic
        if end_date:
            # New assignment has an end date
            query = query.where(
                and_(
                    ShiftAssignment.start_date <= end_date,
                    or_(
                        ShiftAssignment.end_date.is_(None),
                        ShiftAssignment.end_date >= start_date,
                    ),
                )
            )
        else:
            # New assignment is open-ended
            query = query.where(
                or_(
                    ShiftAssignment.end_date.is_(None),
                    ShiftAssignment.end_date >= start_date,
                )
            )

        return self.db.scalar(query.limit(1))

    # ==========================================================================
    # Attendance Records
    # ==========================================================================

    def list_attendances(
        self,
        filters: Optional[AttendanceFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[Attendance]:
        """List attendance records with filters."""
        query = select(Attendance)

        if filters:
            if filters.employee_id is not None:
                query = query.where(Attendance.employee_id == filters.employee_id)
            if filters.department_id is not None:
                query = query.join(Employee).where(
                    Employee.department_id == filters.department_id
                )
            if filters.status is not None:
                query = query.where(Attendance.status == filters.status)
            if filters.from_date is not None:
                query = query.where(Attendance.attendance_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(Attendance.attendance_date <= filters.to_date)
            if filters.late_entry is not None:
                query = query.where(Attendance.late_entry == filters.late_entry)
            if filters.early_exit is not None:
                query = query.where(Attendance.early_exit == filters.early_exit)
            if filters.company is not None:
                query = query.where(Attendance.company == filters.company)

        if sort:
            query = apply_sort(query, Attendance, sort)
        else:
            query = query.order_by(Attendance.attendance_date.desc())

        return paginate(self.db, query, pagination)

    def get_attendance(self, attendance_id: int) -> Attendance:
        """Get an attendance record by ID."""
        attendance = self.db.get(Attendance, attendance_id)
        if not attendance:
            raise AttendanceNotFoundError(attendance_id)
        return attendance

    def get_attendance_by_employee_date(
        self, employee_id: int, attendance_date: date
    ) -> Optional[Attendance]:
        """Get attendance for a specific employee and date."""
        return self.db.scalar(
            select(Attendance).where(
                and_(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date == attendance_date,
                )
            )
        )

    def create_attendance(self, data: AttendanceCreateData) -> Attendance:
        """Create a new attendance record."""
        # Check for duplicate
        existing = self.get_attendance_by_employee_date(
            data.employee_id, data.attendance_date
        )
        if existing:
            raise DuplicateAttendanceError(data.employee_id, data.attendance_date)

        attendance = Attendance(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            attendance_date=data.attendance_date,
            status=data.status,
            shift=data.shift,
            in_time=data.in_time,
            out_time=data.out_time,
            working_hours=data.working_hours,
            leave_type=data.leave_type,
            leave_application=data.leave_application,
            late_entry=data.late_entry,
            early_exit=data.early_exit,
            company=data.company,
        )

        if self.principal and self.principal.user_id:
            attendance.created_by_id = self.principal.user_id

        self.db.add(attendance)
        self.db.flush()
        return attendance

    def update_attendance(
        self, attendance_id: int, data: AttendanceUpdateData
    ) -> Attendance:
        """Update an attendance record."""
        attendance = self.get_attendance(attendance_id)

        if data.status is not None:
            attendance.status = data.status
            attendance.status_changed_at = utc_now()
            if self.principal and self.principal.user_id:
                attendance.status_changed_by_id = self.principal.user_id
        if data.shift is not None:
            attendance.shift = data.shift
        if data.in_time is not None:
            attendance.in_time = data.in_time
        if data.out_time is not None:
            attendance.out_time = data.out_time
        if data.working_hours is not None:
            attendance.working_hours = data.working_hours
        if data.late_entry is not None:
            attendance.late_entry = data.late_entry
        if data.early_exit is not None:
            attendance.early_exit = data.early_exit
        if data.leave_type is not None:
            attendance.leave_type = data.leave_type
        if data.leave_application is not None:
            attendance.leave_application = data.leave_application

        if self.principal and self.principal.user_id:
            attendance.updated_by_id = self.principal.user_id

        self.db.flush()
        return attendance

    def delete_attendance(self, attendance_id: int) -> None:
        """Delete an attendance record."""
        attendance = self.get_attendance(attendance_id)

        if self.principal and self.principal.user_id:
            attendance.deleted_by_id = self.principal.user_id

        self.db.delete(attendance)
        self.db.flush()

    # ==========================================================================
    # Check-in / Check-out
    # ==========================================================================

    def check_in(self, employee_id: int, data: CheckInData) -> Attendance:
        """Record employee check-in.

        Uses HR settings for:
        - late_entry_grace_minutes: Default grace period if shift doesn't define one
        - allow_backdated_attendance: Whether backdated check-in is allowed
        - backdated_attendance_days: How far back check-in can be recorded
        - geolocation_required: Whether location is mandatory
        """
        check_date = data.attendance_date or date.today()
        check_time = data.in_time or utc_now()

        # Get employee info first (need company for settings)
        employee = self.db.get(Employee, employee_id)
        if not employee:
            raise CheckInError(f"Employee {employee_id} not found")

        # Get settings for validation
        settings = self._get_settings(employee.company)

        # Validate backdated attendance
        if check_date < date.today():
            if not settings.allow_backdated_attendance:
                raise ValidationError("Backdated attendance is not allowed")
            days_back = (date.today() - check_date).days
            if days_back > settings.backdated_attendance_days:
                raise ValidationError(
                    f"Cannot record attendance more than {settings.backdated_attendance_days} days in the past"
                )

        # Validate geolocation if required
        if settings.geolocation_required:
            if not data.latitude or not data.longitude:
                raise ValidationError("Geolocation is required for check-in")

        # Check if already checked in
        existing = self.get_attendance_by_employee_date(employee_id, check_date)
        if existing and existing.in_time:
            raise CheckInError(f"Already checked in at {existing.in_time}")

        # Get current shift
        shift_assignment = self.get_employee_current_shift(employee_id, check_date)
        shift_type = None
        late_entry = False

        if shift_assignment and shift_assignment.shift_type_id:
            shift_type = self.db.get(ShiftType, shift_assignment.shift_type_id)
            if shift_type and shift_type.start_time:
                # Check for late entry - use shift grace period or fall back to settings
                shift_start = datetime.combine(check_date, shift_type.start_time)
                if shift_type.enable_entry_grace_period:
                    grace_minutes = shift_type.late_entry_grace_period or 0
                else:
                    # Fall back to HR settings default
                    grace_minutes = settings.late_entry_grace_minutes
                late_threshold = shift_start + timedelta(minutes=grace_minutes)
                if check_time > late_threshold:
                    late_entry = True

        if existing:
            # Update existing record with check-in
            existing.in_time = check_time
            existing.late_entry = late_entry
            if data.latitude:
                existing.check_in_latitude = data.latitude
            if data.longitude:
                existing.check_in_longitude = data.longitude
            if data.device_info:
                existing.device_info = data.device_info
            if self.principal and self.principal.user_id:
                existing.updated_by_id = self.principal.user_id
            self.db.flush()
            return existing

        # Create new attendance record
        attendance = Attendance(
            employee_id=employee_id,
            employee=employee.erpnext_id or str(employee_id),
            employee_name=employee.name,
            attendance_date=check_date,
            status=AttendanceStatus.PRESENT,
            shift=shift_type.shift_type_name if shift_type else None,
            in_time=check_time,
            late_entry=late_entry,
            check_in_latitude=data.latitude,
            check_in_longitude=data.longitude,
            device_info=data.device_info,
            company=employee.company,
        )

        if self.principal and self.principal.user_id:
            attendance.created_by_id = self.principal.user_id

        self.db.add(attendance)
        self.db.flush()
        return attendance

    def check_out(self, employee_id: int, data: CheckOutData) -> Attendance:
        """Record employee check-out.

        Uses HR settings for:
        - early_exit_grace_minutes: Default grace period if shift doesn't define one
        - geolocation_required: Whether location is mandatory
        """
        check_date = data.attendance_date or date.today()
        check_time = data.out_time or utc_now()

        # Must have checked in first
        attendance = self.get_attendance_by_employee_date(employee_id, check_date)
        if not attendance:
            raise CheckOutError("No check-in record found for today")
        if not attendance.in_time:
            raise CheckOutError("Must check in before checking out")
        if attendance.out_time:
            raise CheckOutError(f"Already checked out at {attendance.out_time}")

        # Get settings for validation
        settings = self._get_settings(attendance.company)

        # Validate geolocation if required
        if settings.geolocation_required:
            if not data.latitude or not data.longitude:
                raise ValidationError("Geolocation is required for check-out")

        # Calculate working hours
        working_hours = Decimal("0")
        if attendance.in_time:
            delta = check_time - attendance.in_time
            working_hours = Decimal(str(delta.total_seconds() / 3600))

        # Check for early exit - use shift grace period or fall back to settings
        early_exit = False
        if attendance.shift:
            shift_type = self.get_shift_type_by_name(attendance.shift)
            if shift_type and shift_type.end_time:
                shift_end = datetime.combine(check_date, shift_type.end_time)
                if shift_type.enable_exit_grace_period:
                    grace_minutes = shift_type.early_exit_grace_period or 0
                else:
                    # Fall back to HR settings default
                    grace_minutes = settings.early_exit_grace_minutes
                early_threshold = shift_end - timedelta(minutes=grace_minutes)
                if check_time < early_threshold:
                    early_exit = True

        attendance.out_time = check_time
        attendance.working_hours = working_hours.quantize(Decimal("0.01"))
        attendance.early_exit = early_exit
        if data.latitude:
            attendance.check_out_latitude = data.latitude
        if data.longitude:
            attendance.check_out_longitude = data.longitude
        if data.device_info:
            attendance.device_info = data.device_info

        if self.principal and self.principal.user_id:
            attendance.updated_by_id = self.principal.user_id

        self.db.flush()
        return attendance

    # ==========================================================================
    # Attendance Requests
    # ==========================================================================

    def list_attendance_requests(
        self,
        filters: Optional[AttendanceRequestFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[AttendanceRequest]:
        """List attendance requests with filters."""
        query = select(AttendanceRequest)

        if filters:
            if filters.employee_id is not None:
                query = query.where(
                    AttendanceRequest.employee_id == filters.employee_id
                )
            if filters.status is not None:
                query = query.where(AttendanceRequest.status == filters.status)
            if filters.from_date is not None:
                query = query.where(AttendanceRequest.from_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(AttendanceRequest.to_date <= filters.to_date)
            if filters.company is not None:
                query = query.where(AttendanceRequest.company == filters.company)

        if sort:
            query = apply_sort(query, AttendanceRequest, sort)
        else:
            query = query.order_by(AttendanceRequest.created_at.desc())

        return paginate(self.db, query, pagination)

    def get_attendance_request(self, request_id: int) -> AttendanceRequest:
        """Get an attendance request by ID."""
        request = self.db.get(AttendanceRequest, request_id)
        if not request:
            raise AttendanceRequestNotFoundError(request_id)
        return request

    def create_attendance_request(
        self, data: AttendanceRequestCreateData
    ) -> AttendanceRequest:
        """Create a new attendance request."""
        request = AttendanceRequest(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            from_date=data.from_date,
            to_date=data.to_date,
            reason=data.reason,
            explanation=data.explanation,
            half_day=data.half_day,
            half_day_date=data.half_day_date,
            status=AttendanceRequestStatus.PENDING,
            company=data.company,
        )

        if self.principal and self.principal.user_id:
            request.created_by_id = self.principal.user_id

        self.db.add(request)
        self.db.flush()
        return request

    def approve_attendance_request(
        self, request_id: int, remarks: Optional[str] = None
    ) -> AttendanceRequest:
        """Approve an attendance request."""
        request = self.get_attendance_request(request_id)

        if request.status != AttendanceRequestStatus.PENDING:
            raise AttendanceRequestStatusError(
                request_id,
                str(request.status.value),
                str(AttendanceRequestStatus.APPROVED.value),
            )

        request.status = AttendanceRequestStatus.APPROVED
        request.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            request.status_changed_by_id = self.principal.user_id
            request.updated_by_id = self.principal.user_id

        self.db.flush()

        # Create/update attendance records for the requested period
        self._process_approved_request(request)

        return request

    def reject_attendance_request(
        self, request_id: int, reason: Optional[str] = None
    ) -> AttendanceRequest:
        """Reject an attendance request."""
        request = self.get_attendance_request(request_id)

        if request.status != AttendanceRequestStatus.PENDING:
            raise AttendanceRequestStatusError(
                request_id,
                str(request.status.value),
                str(AttendanceRequestStatus.REJECTED.value),
            )

        request.status = AttendanceRequestStatus.REJECTED
        request.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            request.status_changed_by_id = self.principal.user_id
            request.updated_by_id = self.principal.user_id

        self.db.flush()
        return request

    def _process_approved_request(self, request: AttendanceRequest) -> None:
        """Process an approved attendance request by creating/updating records."""
        current_date = request.from_date
        employee = self.db.get(Employee, request.employee_id)

        while current_date <= request.to_date:
            existing = self.get_attendance_by_employee_date(
                request.employee_id, current_date
            )

            status = AttendanceStatus.PRESENT
            if request.half_day and current_date == request.half_day_date:
                status = AttendanceStatus.HALF_DAY

            if existing:
                existing.status = status
                existing.status_changed_at = utc_now()
                if self.principal and self.principal.user_id:
                    existing.status_changed_by_id = self.principal.user_id
                    existing.updated_by_id = self.principal.user_id
            else:
                attendance = Attendance(
                    employee_id=request.employee_id,
                    employee=request.employee,
                    employee_name=request.employee_name,
                    attendance_date=current_date,
                    status=status,
                    company=request.company,
                )
                if self.principal and self.principal.user_id:
                    attendance.created_by_id = self.principal.user_id
                self.db.add(attendance)

            current_date += timedelta(days=1)

        self.db.flush()

    # ==========================================================================
    # Reports & Summaries
    # ==========================================================================

    def get_employee_monthly_summary(
        self, employee_id: int, month: int, year: int
    ) -> AttendanceSummary:
        """Get monthly attendance summary for an employee."""
        from calendar import monthrange

        employee = self.db.get(Employee, employee_id)
        if not employee:
            raise AttendanceNotFoundError(message=f"Employee {employee_id} not found")

        # Calculate date range
        _, last_day = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # Query attendance records
        records = self.db.scalars(
            select(Attendance).where(
                and_(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date >= start_date,
                    Attendance.attendance_date <= end_date,
                )
            )
        ).all()

        # Calculate summary
        present_days = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_days = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        half_days = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
        leave_days = sum(1 for r in records if r.status == AttendanceStatus.ON_LEAVE)
        wfh_days = sum(
            1 for r in records if r.status == AttendanceStatus.WORK_FROM_HOME
        )
        late_entries = sum(1 for r in records if r.late_entry)
        early_exits = sum(1 for r in records if r.early_exit)
        total_hours = sum(
            (r.working_hours or Decimal("0")) for r in records
        )

        return AttendanceSummary(
            employee_id=employee_id,
            employee_name=employee.name,
            month=month,
            year=year,
            total_days=len(records),
            present_days=present_days,
            absent_days=absent_days,
            half_days=half_days,
            leave_days=leave_days,
            work_from_home_days=wfh_days,
            late_entries=late_entries,
            early_exits=early_exits,
            total_working_hours=total_hours,
        )

    def get_department_daily_summary(
        self, department_id: int, attendance_date: date
    ) -> DepartmentAttendanceSummary:
        """Get daily attendance summary for a department."""
        from app.models.hr import Department

        department = self.db.get(Department, department_id)
        if not department:
            raise AttendanceNotFoundError(
                message=f"Department {department_id} not found"
            )

        # Get all employees in department
        total_employees = self.db.scalar(
            select(func.count(Employee.id)).where(
                Employee.department_id == department_id
            )
        ) or 0

        # Get attendance records for the day
        records = self.db.scalars(
            select(Attendance)
            .join(Employee)
            .where(
                and_(
                    Employee.department_id == department_id,
                    Attendance.attendance_date == attendance_date,
                )
            )
        ).all()

        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        on_leave = sum(1 for r in records if r.status == AttendanceStatus.ON_LEAVE)
        half_day = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
        wfh = sum(1 for r in records if r.status == AttendanceStatus.WORK_FROM_HOME)

        # Calculate attendance rate
        attendance_rate = Decimal("0")
        if total_employees > 0:
            attended = present + half_day * Decimal("0.5") + wfh
            attendance_rate = (attended / total_employees * 100).quantize(
                Decimal("0.01")
            )

        return DepartmentAttendanceSummary(
            department_id=department_id,
            department_name=department.department_name,
            attendance_date=attendance_date,
            total_employees=total_employees,
            present=present,
            absent=absent,
            on_leave=on_leave,
            half_day=half_day,
            work_from_home=wfh,
            attendance_rate=attendance_rate,
        )

    def get_working_hours_summary(
        self, employee_id: int, from_date: date, to_date: date
    ) -> WorkingHoursSummary:
        """Get working hours summary for an employee over a period.

        Uses HR settings for:
        - standard_work_hours_per_day: Standard hours for overtime calculation
        """
        employee = self.db.get(Employee, employee_id)
        if not employee:
            raise AttendanceNotFoundError(message=f"Employee {employee_id} not found")

        # Get settings for standard hours
        settings = self._get_settings(employee.company)

        records = self.db.scalars(
            select(Attendance).where(
                and_(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date >= from_date,
                    Attendance.attendance_date <= to_date,
                )
            )
        ).all()

        total_days = len(records)
        total_hours = sum((r.working_hours or Decimal("0")) for r in records)
        avg_hours = (
            (total_hours / total_days).quantize(Decimal("0.01"))
            if total_days > 0
            else Decimal("0")
        )

        # Calculate overtime using standard hours from settings
        standard_hours = settings.standard_work_hours_per_day * total_days
        overtime = max(total_hours - standard_hours, Decimal("0"))

        return WorkingHoursSummary(
            employee_id=employee_id,
            employee_name=employee.name,
            from_date=from_date,
            to_date=to_date,
            total_days=total_days,
            total_hours=total_hours,
            average_hours_per_day=avg_hours,
            overtime_hours=overtime,
        )

    def get_late_arrivals(
        self,
        from_date: date,
        to_date: date,
        department_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[LateArrivalRecord]:
        """Get late arrival records for a period."""
        query = (
            select(Attendance)
            .where(
                and_(
                    Attendance.late_entry == True,
                    Attendance.attendance_date >= from_date,
                    Attendance.attendance_date <= to_date,
                )
            )
            .order_by(Attendance.attendance_date.desc())
            .limit(limit)
        )

        if department_id:
            query = query.join(Employee).where(
                Employee.department_id == department_id
            )

        records = self.db.scalars(query).all()
        result = []

        for record in records:
            # Get shift info for late calculation
            shift_start = None
            minutes_late = 0
            department = None

            if record.shift:
                shift_type = self.get_shift_type_by_name(record.shift)
                if shift_type:
                    shift_start = shift_type.start_time

            if shift_start and record.in_time:
                shift_start_dt = datetime.combine(
                    record.attendance_date, shift_start
                )
                if record.in_time > shift_start_dt:
                    delta = record.in_time - shift_start_dt
                    minutes_late = int(delta.total_seconds() / 60)

            if record.employee_id:
                employee = self.db.get(Employee, record.employee_id)
                if employee and employee.department:
                    department = employee.department

            result.append(
                LateArrivalRecord(
                    employee_id=record.employee_id or 0,
                    employee_name=record.employee_name or record.employee,
                    attendance_date=record.attendance_date,
                    shift_start=shift_start,
                    actual_in_time=record.in_time,
                    minutes_late=minutes_late,
                    department=department,
                )
            )

        return result

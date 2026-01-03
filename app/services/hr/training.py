"""Training service implementation.

Handles training programs, events, registrations, and results.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.hr_training import (
    TrainingEvent,
    TrainingEventEmployee,
    TrainingEventStatus,
    TrainingProgram,
    TrainingResult,
    TrainingResultStatus,
)
from app.services.base import PaginatedResult, Pagination, SortParam, paginate
from app.services.hr.errors import (
    TrainingEventNotFoundError,
    TrainingEventStatusError,
    TrainingProgramNotFoundError,
    TrainingResultNotFoundError,
    ValidationError,
)
from app.services.hr.training_types import (
    BulkRegistrationData,
    BulkRegistrationResult,
    EmployeeTrainingHistory,
    EventEmployeeData,
    TrainingEventCreateData,
    TrainingEventFilters,
    TrainingEventUpdateData,
    TrainingMetrics,
    TrainingProgramCreateData,
    TrainingProgramFilters,
    TrainingProgramUpdateData,
    TrainingResultCreateData,
    TrainingResultFilters,
    TrainingResultUpdateData,
)
if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.hr_settings import HRSettings
    from app.web.auth import Principal

__all__ = ["TrainingService"]


# Valid status transitions for training events
EVENT_STATUS_TRANSITIONS = {
    TrainingEventStatus.SCHEDULED: {
        TrainingEventStatus.COMPLETED,
        TrainingEventStatus.CANCELLED,
    },
    TrainingEventStatus.COMPLETED: set(),  # Terminal state
    TrainingEventStatus.CANCELLED: set(),  # Terminal state
}


class TrainingService:
    """Service for managing training programs, events, and results.

    Uses HR settings for configurable behavior:
    - mandatory_training_hours_yearly: Required training hours per year
    - require_training_approval: Whether training requires approval
    - training_completion_threshold_percent: Passing threshold for training
    """

    def __init__(
        self,
        db: "Session",
        principal: Optional["Principal"] = None,
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

    # =========================================================================
    # Training Programs
    # =========================================================================

    def list_programs(
        self,
        filters: Optional[TrainingProgramFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[TrainingProgram]:
        """List training programs with optional filters."""
        query = select(TrainingProgram)

        if filters:
            conditions = []

            if filters.search:
                search_term = f"%{filters.search}%"
                conditions.append(
                    or_(
                        TrainingProgram.training_program_name.ilike(search_term),
                        TrainingProgram.description.ilike(search_term),
                    )
                )

            if filters.trainer_name:
                conditions.append(
                    TrainingProgram.trainer_name.ilike(f"%{filters.trainer_name}%")
                )

            if filters.supplier:
                conditions.append(
                    TrainingProgram.supplier.ilike(f"%{filters.supplier}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by name
        if sort:
            col = getattr(TrainingProgram, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(TrainingProgram.training_program_name)

        return paginate(self.db, query, pagination)

    def get_program(self, program_id: int) -> TrainingProgram:
        """Get a training program by ID."""
        program = self.db.get(TrainingProgram, program_id)
        if not program:
            raise TrainingProgramNotFoundError(program_id)
        return program

    def create_program(self, data: TrainingProgramCreateData) -> TrainingProgram:
        """Create a new training program."""
        program = TrainingProgram(
            training_program_name=data.training_program_name,
            description=data.description,
            trainer_name=data.trainer_name,
            trainer_email=data.trainer_email,
            supplier=data.supplier,
        )

        self.db.add(program)
        self.db.flush()
        return program

    def update_program(
        self,
        program_id: int,
        data: TrainingProgramUpdateData,
    ) -> TrainingProgram:
        """Update a training program."""
        program = self.get_program(program_id)

        if data.training_program_name is not None:
            program.training_program_name = data.training_program_name
        if data.description is not None:
            program.description = data.description
        if data.trainer_name is not None:
            program.trainer_name = data.trainer_name
        if data.trainer_email is not None:
            program.trainer_email = data.trainer_email
        if data.supplier is not None:
            program.supplier = data.supplier

        self.db.flush()
        return program

    def delete_program(self, program_id: int) -> None:
        """Delete a training program."""
        program = self.get_program(program_id)

        # Check if program has events
        event_count = self.db.scalar(
            select(func.count(TrainingEvent.id)).where(
                TrainingEvent.training_program_id == program_id
            )
        )
        if event_count and event_count > 0:
            raise ValidationError(
                f"Cannot delete program with {event_count} associated events"
            )

        self.db.delete(program)
        self.db.flush()

    # =========================================================================
    # Training Events
    # =========================================================================

    def list_events(
        self,
        filters: Optional[TrainingEventFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[TrainingEvent]:
        """List training events with optional filters."""
        query = select(TrainingEvent).options(
            joinedload(TrainingEvent.training_program_rel),
            joinedload(TrainingEvent.employees),
        )

        if filters:
            conditions = []

            if filters.training_program_id is not None:
                conditions.append(
                    TrainingEvent.training_program_id == filters.training_program_id
                )

            if filters.status is not None:
                conditions.append(TrainingEvent.status == filters.status)

            if filters.type is not None:
                conditions.append(TrainingEvent.type == filters.type)

            if filters.level is not None:
                conditions.append(TrainingEvent.level == filters.level)

            if filters.company is not None:
                conditions.append(TrainingEvent.company == filters.company)

            if filters.from_date is not None:
                conditions.append(TrainingEvent.start_time >= filters.from_date)

            if filters.to_date is not None:
                conditions.append(TrainingEvent.end_time <= filters.to_date)

            if filters.search:
                search_term = f"%{filters.search}%"
                conditions.append(
                    or_(
                        TrainingEvent.event_name.ilike(search_term),
                        TrainingEvent.course.ilike(search_term),
                        TrainingEvent.trainer_name.ilike(search_term),
                    )
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by start time descending
        if sort:
            col = getattr(TrainingEvent, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(TrainingEvent.start_time.desc())

        return paginate(self.db, query, pagination)

    def get_event(self, event_id: int) -> TrainingEvent:
        """Get a training event by ID with related data."""
        event = self.db.scalar(
            select(TrainingEvent)
            .options(
                joinedload(TrainingEvent.training_program_rel),
                joinedload(TrainingEvent.employees),
            )
            .where(TrainingEvent.id == event_id)
        )
        if not event:
            raise TrainingEventNotFoundError(event_id)
        return event

    def create_event(self, data: TrainingEventCreateData) -> TrainingEvent:
        """Create a new training event."""
        # Validate training program if specified
        if data.training_program_id:
            self.get_program(data.training_program_id)

        event = TrainingEvent(
            event_name=data.event_name,
            training_program_id=data.training_program_id,
            training_program=data.training_program,
            type=data.type,
            level=data.level,
            company=data.company,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location,
            trainer_name=data.trainer_name,
            trainer_email=data.trainer_email,
            course=data.course,
            introduction=data.introduction,
            status=TrainingEventStatus.SCHEDULED,
        )

        self.db.add(event)
        self.db.flush()

        # Add employees if provided
        if data.employees:
            for idx, emp_data in enumerate(data.employees):
                emp = TrainingEventEmployee(
                    parent_id=event.id,
                    employee_id=emp_data.employee_id,
                    employee=emp_data.employee,
                    employee_name=emp_data.employee_name,
                    department=emp_data.department,
                    status=emp_data.status,
                    idx=idx,
                )
                self.db.add(emp)

        self.db.flush()
        return event

    def update_event(
        self,
        event_id: int,
        data: TrainingEventUpdateData,
    ) -> TrainingEvent:
        """Update a training event."""
        event = self.get_event(event_id)

        # Validate status transition if changing status
        if data.status is not None and data.status != event.status:
            self._validate_event_status_transition(event, data.status)

        if data.event_name is not None:
            event.event_name = data.event_name
        if data.training_program_id is not None:
            self.get_program(data.training_program_id)
            event.training_program_id = data.training_program_id
        if data.training_program is not None:
            event.training_program = data.training_program
        if data.type is not None:
            event.type = data.type
        if data.level is not None:
            event.level = data.level
        if data.start_time is not None:
            event.start_time = data.start_time
        if data.end_time is not None:
            event.end_time = data.end_time
        if data.location is not None:
            event.location = data.location
        if data.trainer_name is not None:
            event.trainer_name = data.trainer_name
        if data.trainer_email is not None:
            event.trainer_email = data.trainer_email
        if data.course is not None:
            event.course = data.course
        if data.introduction is not None:
            event.introduction = data.introduction
        if data.status is not None:
            event.status = data.status

        # Update employees if provided
        if data.employees is not None:
            # Remove existing employees
            self.db.execute(
                TrainingEventEmployee.__table__.delete().where(
                    TrainingEventEmployee.parent_id == event_id
                )
            )
            # Add new employees
            for idx, emp_data in enumerate(data.employees):
                emp = TrainingEventEmployee(
                    parent_id=event_id,
                    employee_id=emp_data.employee_id,
                    employee=emp_data.employee,
                    employee_name=emp_data.employee_name,
                    department=emp_data.department,
                    status=emp_data.status,
                    idx=idx,
                )
                self.db.add(emp)

        self.db.flush()
        return event

    def delete_event(self, event_id: int) -> None:
        """Delete a training event."""
        event = self.get_event(event_id)
        self.db.delete(event)
        self.db.flush()

    def _validate_event_status_transition(
        self,
        event: TrainingEvent,
        target_status: TrainingEventStatus,
    ) -> None:
        """Validate that a status transition is allowed."""
        current = event.status
        allowed = EVENT_STATUS_TRANSITIONS.get(current, set())

        if target_status not in allowed:
            raise TrainingEventStatusError(
                event.id,
                current.value if current else "None",
                target_status.value,
            )

    def complete_event(self, event_id: int) -> TrainingEvent:
        """Mark a training event as completed."""
        event = self.get_event(event_id)
        self._validate_event_status_transition(event, TrainingEventStatus.COMPLETED)
        event.status = TrainingEventStatus.COMPLETED
        self.db.flush()
        return event

    def cancel_event(self, event_id: int) -> TrainingEvent:
        """Cancel a training event."""
        event = self.get_event(event_id)
        self._validate_event_status_transition(event, TrainingEventStatus.CANCELLED)
        event.status = TrainingEventStatus.CANCELLED
        self.db.flush()
        return event

    def register_employee(
        self,
        event_id: int,
        data: EventEmployeeData,
    ) -> TrainingEventEmployee:
        """Register an employee for a training event."""
        event = self.get_event(event_id)

        # Check if already registered
        existing = self.db.scalar(
            select(TrainingEventEmployee).where(
                and_(
                    TrainingEventEmployee.parent_id == event_id,
                    TrainingEventEmployee.employee_id == data.employee_id,
                )
            )
        )
        if existing:
            raise ValidationError(
                f"Employee {data.employee_id} already registered for this event"
            )

        # Get next idx
        max_idx = self.db.scalar(
            select(func.max(TrainingEventEmployee.idx)).where(
                TrainingEventEmployee.parent_id == event_id
            )
        )
        next_idx = (max_idx or 0) + 1

        emp = TrainingEventEmployee(
            parent_id=event_id,
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            department=data.department,
            status=data.status,
            idx=next_idx,
        )
        self.db.add(emp)
        self.db.flush()
        return emp

    def bulk_register(self, data: BulkRegistrationData) -> BulkRegistrationResult:
        """Bulk register employees for a training event."""
        event = self.get_event(data.training_event_id)
        result = BulkRegistrationResult()

        # Get existing registrations
        existing_ids = set(
            self.db.scalars(
                select(TrainingEventEmployee.employee_id).where(
                    TrainingEventEmployee.parent_id == data.training_event_id
                )
            ).all()
        )

        # Get next idx
        max_idx = self.db.scalar(
            select(func.max(TrainingEventEmployee.idx)).where(
                TrainingEventEmployee.parent_id == data.training_event_id
            )
        )
        next_idx = (max_idx or 0) + 1

        for emp_id in data.employee_ids:
            if emp_id in existing_ids:
                result.skipped_count += 1
                result.skipped_employees.append(emp_id)
                continue

            try:
                emp = TrainingEventEmployee(
                    parent_id=data.training_event_id,
                    employee_id=emp_id,
                    employee=f"EMP-{emp_id}",  # Will be resolved by caller
                    status=data.status,
                    idx=next_idx,
                )
                self.db.add(emp)
                result.registered_count += 1
                next_idx += 1
            except Exception as e:
                result.errors.append(f"Employee {emp_id}: {str(e)}")

        self.db.flush()
        return result

    def unregister_employee(self, event_id: int, employee_id: int) -> None:
        """Remove an employee from a training event."""
        registration = self.db.scalar(
            select(TrainingEventEmployee).where(
                and_(
                    TrainingEventEmployee.parent_id == event_id,
                    TrainingEventEmployee.employee_id == employee_id,
                )
            )
        )
        if not registration:
            raise ValidationError(
                f"Employee {employee_id} not registered for event {event_id}"
            )

        self.db.delete(registration)
        self.db.flush()

    def update_employee_status(
        self,
        event_id: int,
        employee_id: int,
        status: str,
    ) -> TrainingEventEmployee:
        """Update an employee's registration status."""
        registration = self.db.scalar(
            select(TrainingEventEmployee).where(
                and_(
                    TrainingEventEmployee.parent_id == event_id,
                    TrainingEventEmployee.employee_id == employee_id,
                )
            )
        )
        if not registration:
            raise ValidationError(
                f"Employee {employee_id} not registered for event {event_id}"
            )

        registration.status = status
        self.db.flush()
        return registration

    # =========================================================================
    # Training Results
    # =========================================================================

    def list_results(
        self,
        filters: Optional[TrainingResultFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[TrainingResult]:
        """List training results with optional filters."""
        query = select(TrainingResult).options(
            joinedload(TrainingResult.training_event_rel),
        )

        if filters:
            conditions = []

            if filters.training_event_id is not None:
                conditions.append(
                    TrainingResult.training_event_id == filters.training_event_id
                )

            if filters.employee_id is not None:
                conditions.append(TrainingResult.employee_id == filters.employee_id)

            if filters.result is not None:
                conditions.append(TrainingResult.result == filters.result)

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by creation date descending
        if sort:
            col = getattr(TrainingResult, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(TrainingResult.creation.desc())

        return paginate(self.db, query, pagination)

    def get_result(self, result_id: int) -> TrainingResult:
        """Get a training result by ID."""
        result = self.db.scalar(
            select(TrainingResult)
            .options(joinedload(TrainingResult.training_event_rel))
            .where(TrainingResult.id == result_id)
        )
        if not result:
            raise TrainingResultNotFoundError(result_id)
        return result

    def create_result(self, data: TrainingResultCreateData) -> TrainingResult:
        """Create a training result for an employee."""
        # Validate event exists
        self.get_event(data.training_event_id)

        # Check for duplicate result
        existing = self.db.scalar(
            select(TrainingResult).where(
                and_(
                    TrainingResult.training_event_id == data.training_event_id,
                    TrainingResult.employee_id == data.employee_id,
                )
            )
        )
        if existing:
            raise ValidationError(
                f"Result already exists for employee {data.employee_id} "
                f"in event {data.training_event_id}"
            )

        result = TrainingResult(
            training_event_id=data.training_event_id,
            training_event=data.training_event,
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            hours=data.hours,
            grade=data.grade,
            result=data.result,
            comments=data.comments,
        )

        self.db.add(result)
        self.db.flush()
        return result

    def update_result(
        self,
        result_id: int,
        data: TrainingResultUpdateData,
    ) -> TrainingResult:
        """Update a training result."""
        result = self.get_result(result_id)

        if data.hours is not None:
            result.hours = data.hours
        if data.grade is not None:
            result.grade = data.grade
        if data.result is not None:
            result.result = data.result
        if data.comments is not None:
            result.comments = data.comments

        self.db.flush()
        return result

    def delete_result(self, result_id: int) -> None:
        """Delete a training result."""
        result = self.get_result(result_id)
        self.db.delete(result)
        self.db.flush()

    def bulk_create_results(
        self,
        event_id: int,
        default_result: TrainingResultStatus = TrainingResultStatus.PENDING,
    ) -> List[TrainingResult]:
        """Create results for all registered employees in an event."""
        event = self.get_event(event_id)
        results = []

        # Get existing result employee IDs
        existing_ids = set(
            self.db.scalars(
                select(TrainingResult.employee_id).where(
                    TrainingResult.training_event_id == event_id
                )
            ).all()
        )

        for emp in event.employees:
            if emp.employee_id in existing_ids:
                continue

            result = TrainingResult(
                training_event_id=event_id,
                training_event=event.event_name,
                employee_id=emp.employee_id,
                employee=emp.employee,
                employee_name=emp.employee_name,
                hours=Decimal("0"),
                result=default_result,
            )
            self.db.add(result)
            results.append(result)

        self.db.flush()
        return results

    # =========================================================================
    # Metrics & Reporting
    # =========================================================================

    def get_metrics(self, company: Optional[str] = None) -> TrainingMetrics:
        """Get training metrics and statistics."""
        metrics = TrainingMetrics()

        # Base condition
        company_condition = TrainingEvent.company == company if company else True

        # Total programs
        metrics.total_programs = (
            self.db.scalar(select(func.count(TrainingProgram.id))) or 0
        )

        # Event counts by status
        metrics.total_events = (
            self.db.scalar(
                select(func.count(TrainingEvent.id)).where(company_condition)
            )
            or 0
        )

        metrics.scheduled_events = (
            self.db.scalar(
                select(func.count(TrainingEvent.id)).where(
                    and_(
                        company_condition,
                        TrainingEvent.status == TrainingEventStatus.SCHEDULED,
                    )
                )
            )
            or 0
        )

        metrics.completed_events = (
            self.db.scalar(
                select(func.count(TrainingEvent.id)).where(
                    and_(
                        company_condition,
                        TrainingEvent.status == TrainingEventStatus.COMPLETED,
                    )
                )
            )
            or 0
        )

        metrics.cancelled_events = (
            self.db.scalar(
                select(func.count(TrainingEvent.id)).where(
                    and_(
                        company_condition,
                        TrainingEvent.status == TrainingEventStatus.CANCELLED,
                    )
                )
            )
            or 0
        )

        # Total participants (unique employees registered)
        metrics.total_participants = (
            self.db.scalar(
                select(func.count(func.distinct(TrainingEventEmployee.employee_id)))
            )
            or 0
        )

        # Participants this month
        today = date.today()
        month_start = today.replace(day=1)
        metrics.participants_this_month = (
            self.db.scalar(
                select(
                    func.count(func.distinct(TrainingEventEmployee.employee_id))
                ).where(
                    TrainingEventEmployee.parent_id.in_(
                        select(TrainingEvent.id).where(
                            and_(
                                company_condition,
                                TrainingEvent.start_time >= month_start,
                            )
                        )
                    )
                )
            )
            or 0
        )

        # Total training hours
        total_hours = self.db.scalar(select(func.sum(TrainingResult.hours)))
        metrics.total_training_hours = total_hours or Decimal("0")

        # Pass rate
        total_results = self.db.scalar(
            select(func.count(TrainingResult.id)).where(
                TrainingResult.result.in_([
                    TrainingResultStatus.PASSED,
                    TrainingResultStatus.FAILED,
                ])
            )
        )
        if total_results and total_results > 0:
            passed = self.db.scalar(
                select(func.count(TrainingResult.id)).where(
                    TrainingResult.result == TrainingResultStatus.PASSED
                )
            )
            metrics.pass_rate = (
                Decimal(str(passed or 0)) / Decimal(str(total_results)) * 100
            )

        return metrics

    def get_employee_history(self, employee_id: int) -> EmployeeTrainingHistory:
        """Get training history for an employee."""
        # Get employee name from first result
        first_result = self.db.scalar(
            select(TrainingResult).where(TrainingResult.employee_id == employee_id)
        )

        history = EmployeeTrainingHistory(
            employee_id=employee_id,
            employee_name=first_result.employee_name if first_result else "",
        )

        # Count registrations
        history.total_trainings = (
            self.db.scalar(
                select(func.count(TrainingEventEmployee.id)).where(
                    TrainingEventEmployee.employee_id == employee_id
                )
            )
            or 0
        )

        # Count results by status
        results = self.db.execute(
            select(
                TrainingResult.result,
                func.count(TrainingResult.id),
            )
            .where(TrainingResult.employee_id == employee_id)
            .group_by(TrainingResult.result)
        ).all()

        for result_status, count in results:
            if result_status == TrainingResultStatus.PASSED:
                history.passed = count
                history.completed += count
            elif result_status == TrainingResultStatus.FAILED:
                history.failed = count
                history.completed += count
            elif result_status == TrainingResultStatus.PENDING:
                history.pending = count

        # Total hours
        total_hours = self.db.scalar(
            select(func.sum(TrainingResult.hours)).where(
                TrainingResult.employee_id == employee_id
            )
        )
        history.total_hours = total_hours or Decimal("0")

        return history

    def get_upcoming_events(
        self,
        company: Optional[str] = None,
        limit: int = 10,
    ) -> Sequence[TrainingEvent]:
        """Get upcoming scheduled training events."""
        query = (
            select(TrainingEvent)
            .options(joinedload(TrainingEvent.training_program_rel))
            .where(
                and_(
                    TrainingEvent.status == TrainingEventStatus.SCHEDULED,
                    TrainingEvent.start_time >= datetime.now(),
                )
            )
            .order_by(TrainingEvent.start_time.asc())
            .limit(limit)
        )

        if company:
            query = query.where(TrainingEvent.company == company)

        return self.db.scalars(query).unique().all()

    def get_events_for_employee(
        self,
        employee_id: int,
        include_completed: bool = False,
    ) -> Sequence[TrainingEvent]:
        """Get training events for an employee."""
        event_ids = self.db.scalars(
            select(TrainingEventEmployee.parent_id).where(
                TrainingEventEmployee.employee_id == employee_id
            )
        ).all()

        if not event_ids:
            return []

        query = (
            select(TrainingEvent)
            .options(joinedload(TrainingEvent.training_program_rel))
            .where(TrainingEvent.id.in_(event_ids))
            .order_by(TrainingEvent.start_time.desc())
        )

        if not include_completed:
            query = query.where(TrainingEvent.status == TrainingEventStatus.SCHEDULED)

        return self.db.scalars(query).unique().all()

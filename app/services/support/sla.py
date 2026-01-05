"""SLA service - business logic for SLA management.

This service handles SLA-related operations:
- Business calendar management (schedules, holidays)
- SLA policy management (conditions, targets)
- Due date calculation with business hours
- Breach detection and tracking

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.omni import OmniConversation
from app.models.support_sla import (
    BusinessCalendar,
    BusinessCalendarHoliday,
    SLABreachLog,
    SLAPolicy,
    SLATarget,
)
from app.models.ticket import Ticket, TicketPriority

from .errors import SLAConfigError
from .types import (
    BusinessCalendarCreate,
    BusinessCalendarUpdate,
    HolidayCreate,
    SLABreachFilters,
    SLABreachInfo,
    SLABreachSummary,
    SLADueDates,
    SLAPolicyCreate,
    SLAPolicyUpdate,
    SLATargetCreate,
    SLATargetUpdate,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["SLAService"]


# Default SLA targets (in hours)
DEFAULT_SLA_TARGETS = {
    "critical": {"first_response": 1, "resolution": 4},
    "urgent": {"first_response": 2, "resolution": 8},
    "high": {"first_response": 4, "resolution": 24},
    "medium": {"first_response": 8, "resolution": 48},
    "low": {"first_response": 24, "resolution": 72},
}


class SLAService:
    """Service for SLA calculations.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        self.sla_targets = DEFAULT_SLA_TARGETS

    # -------------------------------------------------------------------------
    # Due Date Calculation
    # -------------------------------------------------------------------------

    def calculate_due_dates(
        self,
        priority: str,
        created_at: Optional[datetime] = None,
    ) -> SLADueDates:
        """Calculate SLA due dates based on priority.

        Args:
            priority: Priority level (critical, urgent, high, medium, low).
            created_at: When the entity was created (defaults to now).

        Returns:
            SLADueDates with calculated due dates.

        Raises:
            SLAConfigError: If priority is not recognized.
        """
        priority_lower = priority.lower()
        targets = self.sla_targets.get(priority_lower)

        if not targets:
            # Use medium as default
            targets = self.sla_targets.get("medium", {"first_response": 8, "resolution": 48})

        start = created_at or datetime.now(timezone.utc)

        first_response_hours = targets.get("first_response", 8)
        resolution_hours = targets.get("resolution", 48)

        return SLADueDates(
            first_response_due=start + timedelta(hours=first_response_hours),
            resolution_due=start + timedelta(hours=resolution_hours),
            next_response_due=None,  # Calculated on demand
        )

    def calculate_ticket_due_dates(self, ticket: Ticket) -> SLADueDates:
        """Calculate SLA due dates for a ticket.

        Args:
            ticket: The ticket to calculate for.

        Returns:
            SLADueDates with calculated due dates.
        """
        priority = ticket.priority.value if ticket.priority else "medium"
        return self.calculate_due_dates(priority, ticket.created_at)

    def calculate_conversation_due_dates(
        self,
        conversation: OmniConversation,
    ) -> SLADueDates:
        """Calculate SLA due dates for a conversation.

        Args:
            conversation: The conversation to calculate for.

        Returns:
            SLADueDates with calculated due dates.
        """
        priority = conversation.priority or "medium"
        return self.calculate_due_dates(priority, conversation.created_at)

    # -------------------------------------------------------------------------
    # Time Remaining
    # -------------------------------------------------------------------------

    def get_remaining_time(
        self,
        due_at: Optional[datetime],
        now: Optional[datetime] = None,
    ) -> Optional[timedelta]:
        """Get remaining time until a due date.

        Args:
            due_at: The due date.
            now: Current time (defaults to now).

        Returns:
            Time remaining (negative if overdue), or None if no due date.
        """
        if not due_at:
            return None

        now = now or datetime.now(timezone.utc)

        # Ensure both are timezone-aware
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        return due_at - now

    def get_ticket_first_response_remaining(
        self,
        ticket: Ticket,
    ) -> Optional[timedelta]:
        """Get remaining time for ticket first response SLA."""
        if ticket.first_responded_at:
            return None  # Already responded

        due_dates = self.calculate_ticket_due_dates(ticket)
        return self.get_remaining_time(due_dates.first_response_due)

    def get_ticket_resolution_remaining(
        self,
        ticket: Ticket,
    ) -> Optional[timedelta]:
        """Get remaining time for ticket resolution SLA."""
        if ticket.resolution_date:
            return None  # Already resolved

        due_dates = self.calculate_ticket_due_dates(ticket)
        return self.get_remaining_time(due_dates.resolution_due)

    # -------------------------------------------------------------------------
    # Breach Detection
    # -------------------------------------------------------------------------

    def is_breached(
        self,
        due_at: Optional[datetime],
        completed_at: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if an SLA target is breached.

        Args:
            due_at: The due date.
            completed_at: When the target was completed (if any).
            now: Current time (defaults to now).

        Returns:
            True if breached, False otherwise.
        """
        if not due_at:
            return False

        # If completed, check against completion time
        check_time = completed_at or now or datetime.now(timezone.utc)

        # Ensure both are timezone-aware
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=timezone.utc)

        return check_time > due_at

    def check_ticket_breach(
        self,
        ticket: Ticket,
        target: str = "first_response",
    ) -> SLABreachInfo:
        """Check SLA breach status for a ticket.

        Args:
            ticket: The ticket to check.
            target: Which target to check (first_response, resolution).

        Returns:
            SLABreachInfo with breach details.
        """
        due_dates = self.calculate_ticket_due_dates(ticket)
        now = datetime.now(timezone.utc)

        if target == "first_response":
            due_at = due_dates.first_response_due
            completed_at = ticket.first_responded_at
        elif target == "resolution":
            due_at = due_dates.resolution_due
            completed_at = ticket.resolution_date
        else:
            return SLABreachInfo(breached=False)

        breached = self.is_breached(due_at, completed_at, now)

        if not breached:
            return SLABreachInfo(breached=False)

        # Calculate overdue time
        check_time = completed_at or now
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=timezone.utc)

        overdue = check_time - due_at if due_at else timedelta()
        overdue_minutes = int(overdue.total_seconds() / 60)

        return SLABreachInfo(
            breached=True,
            breach_type=target,
            breached_at=due_at,
            overdue_by_minutes=overdue_minutes,
        )

    def check_conversation_breach(
        self,
        conversation: OmniConversation,
        target: str = "first_response",
    ) -> SLABreachInfo:
        """Check SLA breach status for a conversation.

        Args:
            conversation: The conversation to check.
            target: Which target to check (first_response, resolution).

        Returns:
            SLABreachInfo with breach details.
        """
        due_dates = self.calculate_conversation_due_dates(conversation)
        now = datetime.now(timezone.utc)

        if target == "first_response":
            due_at = due_dates.first_response_due
            completed_at = conversation.first_response_at
        elif target == "resolution":
            due_at = due_dates.resolution_due
            completed_at = conversation.resolved_at
        else:
            return SLABreachInfo(breached=False)

        breached = self.is_breached(due_at, completed_at, now)

        if not breached:
            return SLABreachInfo(breached=False)

        # Calculate overdue time
        check_time = completed_at or now
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=timezone.utc)

        overdue = check_time - due_at if due_at else timedelta()
        overdue_minutes = int(overdue.total_seconds() / 60)

        return SLABreachInfo(
            breached=True,
            breach_type=target,
            breached_at=due_at,
            overdue_by_minutes=overdue_minutes,
        )

    # -------------------------------------------------------------------------
    # Business Hours (Simplified)
    # -------------------------------------------------------------------------

    def calculate_business_hours(
        self,
        start: datetime,
        end: datetime,
        hours_per_day: int = 8,
        working_days: tuple = (0, 1, 2, 3, 4),  # Mon-Fri
    ) -> timedelta:
        """Calculate business hours between two dates (simplified).

        This is a simplified implementation that counts working days.
        A production implementation would use a business calendar.

        Args:
            start: Start datetime.
            end: End datetime.
            hours_per_day: Working hours per day.
            working_days: Tuple of weekday numbers (0=Monday).

        Returns:
            Total business hours as timedelta.
        """
        if end <= start:
            return timedelta()

        # Ensure timezone-aware
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        # Count working days
        working_day_count = 0
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            if current.weekday() in working_days:
                working_day_count += 1
            current += timedelta(days=1)

        # Rough calculation
        total_hours = working_day_count * hours_per_day
        return timedelta(hours=total_hours)

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def set_sla_targets(
        self,
        priority: str,
        first_response_hours: int,
        resolution_hours: int,
    ) -> None:
        """Set SLA targets for a priority level.

        Args:
            priority: Priority level.
            first_response_hours: First response target in hours.
            resolution_hours: Resolution target in hours.
        """
        self.sla_targets[priority.lower()] = {
            "first_response": first_response_hours,
            "resolution": resolution_hours,
        }

    def get_sla_targets(self, priority: str) -> dict:
        """Get SLA targets for a priority level.

        Args:
            priority: Priority level.

        Returns:
            Dict with first_response and resolution targets.
        """
        return self.sla_targets.get(
            priority.lower(),
            self.sla_targets.get("medium", {}),
        )

    # =========================================================================
    # Business Calendar Management (Database-backed)
    # =========================================================================

    def list_calendars(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[BusinessCalendar], int]:
        """List business calendars.

        Args:
            is_active: Filter by active status.
            skip: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (calendars list, total count).
        """
        query = self.db.query(BusinessCalendar)

        if is_active is not None:
            query = query.filter(BusinessCalendar.is_active == is_active)

        total = query.count()
        calendars = query.order_by(BusinessCalendar.name).offset(skip).limit(limit).all()

        return calendars, total

    def get_calendar_usage(self, calendar_ids: Optional[List[int]] = None) -> Dict[int, int]:
        """Get SLA policy counts per calendar.

        Args:
            calendar_ids: Optional list of calendar IDs to filter.

        Returns:
            Dict mapping calendar_id to policy count.
        """
        query = self.db.query(
            SLAPolicy.calendar_id,
            func.count(SLAPolicy.id),
        ).filter(SLAPolicy.calendar_id.isnot(None))

        if calendar_ids:
            query = query.filter(SLAPolicy.calendar_id.in_(calendar_ids))

        rows = query.group_by(SLAPolicy.calendar_id).all()
        return {calendar_id: count for calendar_id, count in rows}

    def get_calendar(self, calendar_id: int) -> Optional[BusinessCalendar]:
        """Get a business calendar by ID."""
        return self.db.query(BusinessCalendar).filter(
            BusinessCalendar.id == calendar_id
        ).first()

    def get_default_calendar(self) -> Optional[BusinessCalendar]:
        """Get the default business calendar."""
        return self.db.query(BusinessCalendar).filter(
            BusinessCalendar.is_default == True,
            BusinessCalendar.is_active == True,
        ).first()

    def create_calendar(self, data: BusinessCalendarCreate) -> BusinessCalendar:
        """Create a new business calendar."""
        if data.is_default:
            self.db.query(BusinessCalendar).filter(
                BusinessCalendar.is_default == True
            ).update({"is_default": False})

        calendar = BusinessCalendar(
            name=data.name,
            description=data.description,
            calendar_type=data.calendar_type,
            timezone=data.timezone,
            schedule=data.schedule,
            is_default=data.is_default,
            is_active=True,
            created_by_id=self.principal.user_id if self.principal else None,
        )
        self.db.add(calendar)
        self.db.flush()
        return calendar

    def update_calendar(
        self, calendar_id: int, data: BusinessCalendarUpdate
    ) -> Optional[BusinessCalendar]:
        """Update a business calendar."""
        calendar = self.get_calendar(calendar_id)
        if not calendar:
            return None

        if data.is_default is True:
            self.db.query(BusinessCalendar).filter(
                BusinessCalendar.is_default == True,
                BusinessCalendar.id != calendar_id,
            ).update({"is_default": False})

        if data.name is not None:
            calendar.name = data.name
        if data.description is not None:
            calendar.description = data.description
        if data.calendar_type is not None:
            calendar.calendar_type = data.calendar_type
        if data.timezone is not None:
            calendar.timezone = data.timezone
        if data.schedule is not None:
            calendar.schedule = data.schedule
        if data.is_default is not None:
            calendar.is_default = data.is_default
        if data.is_active is not None:
            calendar.is_active = data.is_active

        calendar.updated_by_id = self.principal.user_id if self.principal else None
        self.db.flush()
        return calendar

    def delete_calendar(self, calendar_id: int) -> bool:
        """Delete a business calendar."""
        calendar = self.get_calendar(calendar_id)
        if not calendar:
            return False

        self.db.delete(calendar)
        self.db.flush()
        return True

    # =========================================================================
    # Holiday Management
    # =========================================================================

    def list_holidays(
        self,
        calendar_id: int,
        year: Optional[int] = None,
    ) -> List[BusinessCalendarHoliday]:
        """List holidays for a calendar."""
        query = self.db.query(BusinessCalendarHoliday).filter(
            BusinessCalendarHoliday.calendar_id == calendar_id
        )

        if year:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            query = query.filter(
                (
                    (BusinessCalendarHoliday.holiday_date >= start)
                    & (BusinessCalendarHoliday.holiday_date <= end)
                )
                | (BusinessCalendarHoliday.is_recurring == True)
            )

        return query.order_by(BusinessCalendarHoliday.holiday_date).all()

    def add_holiday(
        self, calendar_id: int, data: HolidayCreate
    ) -> Optional[BusinessCalendarHoliday]:
        """Add a holiday to a calendar."""
        calendar = self.get_calendar(calendar_id)
        if not calendar:
            return None

        holiday = BusinessCalendarHoliday(
            calendar_id=calendar_id,
            name=data.name,
            holiday_date=data.holiday_date.date() if isinstance(data.holiday_date, datetime) else data.holiday_date,
            is_recurring=data.is_recurring,
        )
        self.db.add(holiday)
        self.db.flush()
        return holiday

    def remove_holiday(self, calendar_id: int, holiday_id: int) -> bool:
        """Remove a holiday from a calendar."""
        holiday = self.db.query(BusinessCalendarHoliday).filter(
            BusinessCalendarHoliday.id == holiday_id,
            BusinessCalendarHoliday.calendar_id == calendar_id,
        ).first()

        if not holiday:
            return False

        self.db.delete(holiday)
        self.db.flush()
        return True

    # =========================================================================
    # SLA Policy Management
    # =========================================================================

    def list_policies(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[SLAPolicy], int]:
        """List SLA policies."""
        query = self.db.query(SLAPolicy)

        if is_active is not None:
            query = query.filter(SLAPolicy.is_active == is_active)

        total = query.count()
        policies = (
            query.order_by(SLAPolicy.priority.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return policies, total

    def get_policy(self, policy_id: int) -> Optional[SLAPolicy]:
        """Get an SLA policy by ID."""
        return self.db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()

    def get_default_policy(self) -> Optional[SLAPolicy]:
        """Get the default SLA policy."""
        return self.db.query(SLAPolicy).filter(
            SLAPolicy.is_default == True,
            SLAPolicy.is_active == True,
        ).first()

    def create_policy(self, data: SLAPolicyCreate) -> SLAPolicy:
        """Create a new SLA policy."""
        if data.is_default:
            self.db.query(SLAPolicy).filter(
                SLAPolicy.is_default == True
            ).update({"is_default": False})

        policy = SLAPolicy(
            name=data.name,
            description=data.description,
            calendar_id=data.calendar_id,
            conditions=data.conditions,
            is_default=data.is_default,
            priority=data.priority,
            is_active=True,
            created_by_id=self.principal.user_id if self.principal else None,
        )
        self.db.add(policy)
        self.db.flush()
        return policy

    def update_policy(
        self, policy_id: int, data: SLAPolicyUpdate
    ) -> Optional[SLAPolicy]:
        """Update an SLA policy."""
        policy = self.get_policy(policy_id)
        if not policy:
            return None

        if data.is_default is True:
            self.db.query(SLAPolicy).filter(
                SLAPolicy.is_default == True,
                SLAPolicy.id != policy_id,
            ).update({"is_default": False})

        if data.name is not None:
            policy.name = data.name
        if data.description is not None:
            policy.description = data.description
        if data.calendar_id is not None:
            policy.calendar_id = data.calendar_id
        if data.conditions is not None:
            policy.conditions = data.conditions
        if data.is_default is not None:
            policy.is_default = data.is_default
        if data.priority is not None:
            policy.priority = data.priority
        if data.is_active is not None:
            policy.is_active = data.is_active

        policy.updated_by_id = self.principal.user_id if self.principal else None
        self.db.flush()
        return policy

    def delete_policy(self, policy_id: int) -> bool:
        """Delete an SLA policy."""
        policy = self.get_policy(policy_id)
        if not policy:
            return False

        self.db.delete(policy)
        self.db.flush()
        return True

    # =========================================================================
    # SLA Target Management
    # =========================================================================

    def list_targets(self, policy_id: int) -> List[SLATarget]:
        """List targets for a policy."""
        return self.db.query(SLATarget).filter(
            SLATarget.policy_id == policy_id
        ).order_by(SLATarget.target_type, SLATarget.priority).all()

    def list_targets_for_policies(self, policy_ids: List[int]) -> Dict[int, List[SLATarget]]:
        """List targets for multiple policies in a single query.

        Args:
            policy_ids: Policy IDs to fetch targets for.

        Returns:
            Dict mapping policy_id to list of targets.
        """
        if not policy_ids:
            return {}

        targets = (
            self.db.query(SLATarget)
            .filter(SLATarget.policy_id.in_(policy_ids))
            .order_by(SLATarget.policy_id, SLATarget.priority)
            .all()
        )

        target_map: Dict[int, List[SLATarget]] = {}
        for target in targets:
            target_map.setdefault(target.policy_id, []).append(target)
        return target_map

    def get_target(self, target_id: int) -> Optional[SLATarget]:
        """Get an SLA target by ID."""
        return self.db.query(SLATarget).filter(SLATarget.id == target_id).first()

    def add_target(self, policy_id: int, data: SLATargetCreate) -> Optional[SLATarget]:
        """Add a target to a policy."""
        policy = self.get_policy(policy_id)
        if not policy:
            return None

        target = SLATarget(
            policy_id=policy_id,
            target_type=data.target_type,
            priority=data.priority,
            target_hours=Decimal(str(data.target_hours)),
            warning_threshold_pct=data.warning_threshold_pct,
        )
        self.db.add(target)
        self.db.flush()
        return target

    def update_target(
        self, target_id: int, data: SLATargetUpdate
    ) -> Optional[SLATarget]:
        """Update an SLA target."""
        target = self.get_target(target_id)
        if not target:
            return None

        if data.target_type is not None:
            target.target_type = data.target_type
        if data.priority is not None:
            target.priority = data.priority
        if data.target_hours is not None:
            target.target_hours = Decimal(str(data.target_hours))
        if data.warning_threshold_pct is not None:
            target.warning_threshold_pct = data.warning_threshold_pct

        self.db.flush()
        return target

    def remove_target(self, policy_id: int, target_id: int) -> bool:
        """Remove a target from a policy."""
        target = self.db.query(SLATarget).filter(
            SLATarget.id == target_id,
            SLATarget.policy_id == policy_id,
        ).first()

        if not target:
            return False

        self.db.delete(target)
        self.db.flush()
        return True

    # =========================================================================
    # Policy Matching
    # =========================================================================

    def match_policy_for_ticket(self, ticket: Ticket) -> Optional[SLAPolicy]:
        """Find the matching SLA policy for a ticket."""
        policies, _ = self.list_policies(is_active=True)

        for policy in policies:
            if policy.is_default:
                continue

            if self._evaluate_policy_conditions(policy, ticket):
                return policy

        return self.get_default_policy()

    def _evaluate_policy_conditions(self, policy: SLAPolicy, ticket: Ticket) -> bool:
        """Evaluate if a policy's conditions match a ticket."""
        conditions = policy.conditions or []
        if not conditions:
            return True

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "equals")
            value = condition.get("value")

            actual = getattr(ticket, field, None)
            if hasattr(actual, "value"):
                actual = actual.value

            if operator == "equals":
                if actual != value:
                    return False
            elif operator == "not_equals":
                if actual == value:
                    return False
            elif operator == "in":
                if actual not in (value if isinstance(value, list) else [value]):
                    return False
            elif operator == "not_in":
                if actual in (value if isinstance(value, list) else [value]):
                    return False
            elif operator == "is_empty":
                if actual:
                    return False
            elif operator == "is_not_empty":
                if not actual:
                    return False

        return True

    # =========================================================================
    # Advanced Due Date Calculation (Policy-based)
    # =========================================================================

    def calculate_policy_deadlines(
        self,
        ticket: Ticket,
        policy: Optional[SLAPolicy] = None,
        from_time: Optional[datetime] = None,
    ) -> SLADueDates:
        """Calculate SLA deadlines for a ticket using a policy."""
        if not policy:
            policy = self.match_policy_for_ticket(ticket)

        if not policy:
            return SLADueDates()

        targets = self.list_targets(policy.id)
        if not targets:
            return SLADueDates()

        start_time = from_time or ticket.created_at
        ticket_priority = ticket.priority.value if ticket.priority else None

        first_response_target = self._find_applicable_target(
            targets, "first_response", ticket_priority
        )
        resolution_target = self._find_applicable_target(
            targets, "resolution", ticket_priority
        )
        next_response_target = self._find_applicable_target(
            targets, "next_response", ticket_priority
        )

        calendar = policy.calendar

        first_response_due = None
        resolution_due = None
        next_response_due = None

        if first_response_target:
            first_response_due = self._add_business_hours(
                start_time,
                float(first_response_target.target_hours),
                calendar,
            )

        if resolution_target:
            resolution_due = self._add_business_hours(
                start_time,
                float(resolution_target.target_hours),
                calendar,
            )

        if next_response_target:
            next_response_due = self._add_business_hours(
                start_time,
                float(next_response_target.target_hours),
                calendar,
            )

        return SLADueDates(
            first_response_due=first_response_due,
            resolution_due=resolution_due,
            next_response_due=next_response_due,
        )

    def _find_applicable_target(
        self,
        targets: List[SLATarget],
        target_type: str,
        ticket_priority: Optional[str],
    ) -> Optional[SLATarget]:
        """Find the applicable target for a ticket priority."""
        for target in targets:
            if target.target_type == target_type and target.priority == ticket_priority:
                return target

        for target in targets:
            if target.target_type == target_type and target.priority is None:
                return target

        return None

    def _add_business_hours(
        self,
        start: datetime,
        hours: float,
        calendar: Optional[BusinessCalendar],
    ) -> datetime:
        """Add business hours to a datetime."""
        if not calendar or calendar.calendar_type == "24x7":
            return start + timedelta(hours=hours)

        schedule = calendar.schedule or {}
        holidays = {h.holiday_date for h in calendar.holidays}

        current = start
        remaining_minutes = hours * 60

        while remaining_minutes > 0:
            day_name = current.strftime("%a").lower()
            day_schedule = schedule.get(day_name)

            if current.date() in holidays:
                current = current + timedelta(days=1)
                current = current.replace(hour=0, minute=0, second=0, microsecond=0)
                continue

            if not day_schedule:
                current = current + timedelta(days=1)
                current = current.replace(hour=0, minute=0, second=0, microsecond=0)
                continue

            try:
                start_str = day_schedule.get("start", "09:00")
                end_str = day_schedule.get("end", "17:00")
                work_start_hour, work_start_min = map(int, start_str.split(":"))
                work_end_hour, work_end_min = map(int, end_str.split(":"))
            except (ValueError, AttributeError):
                current = current + timedelta(days=1)
                continue

            work_start = current.replace(
                hour=work_start_hour, minute=work_start_min, second=0, microsecond=0
            )
            work_end = current.replace(
                hour=work_end_hour, minute=work_end_min, second=0, microsecond=0
            )

            if current < work_start:
                current = work_start

            if current >= work_end:
                current = current + timedelta(days=1)
                current = current.replace(hour=0, minute=0, second=0, microsecond=0)
                continue

            available_minutes = (work_end - current).total_seconds() / 60

            if remaining_minutes <= available_minutes:
                current = current + timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
            else:
                remaining_minutes -= available_minutes
                current = current + timedelta(days=1)
                current = current.replace(hour=0, minute=0, second=0, microsecond=0)

        return current

    # =========================================================================
    # SLA Breach Management
    # =========================================================================

    def list_breaches(
        self,
        filters: Optional[SLABreachFilters] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[SLABreachLog], int]:
        """List SLA breaches with optional filters."""
        query = self.db.query(SLABreachLog)

        if filters:
            if filters.ticket_id:
                query = query.filter(SLABreachLog.ticket_id == filters.ticket_id)
            if filters.policy_id:
                query = query.filter(SLABreachLog.policy_id == filters.policy_id)
            if filters.target_type:
                query = query.filter(SLABreachLog.target_type == filters.target_type)
            if filters.start_date:
                query = query.filter(SLABreachLog.breached_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(SLABreachLog.breached_at <= filters.end_date)

        total = query.count()
        breaches = (
            query.order_by(SLABreachLog.breached_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return breaches, total

    def get_breach_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SLABreachSummary:
        """Get summary statistics for SLA breaches."""
        query = self.db.query(SLABreachLog)

        if start_date:
            query = query.filter(SLABreachLog.breached_at >= start_date)
        if end_date:
            query = query.filter(SLABreachLog.breached_at <= end_date)

        total_breaches = query.count()

        by_type_rows = (
            self.db.query(SLABreachLog.target_type, func.count(SLABreachLog.id))
            .group_by(SLABreachLog.target_type)
        )
        if start_date:
            by_type_rows = by_type_rows.filter(SLABreachLog.breached_at >= start_date)
        if end_date:
            by_type_rows = by_type_rows.filter(SLABreachLog.breached_at <= end_date)
        by_target_type = {t: c for t, c in by_type_rows.all()}

        by_policy_rows = (
            self.db.query(SLAPolicy.name, func.count(SLABreachLog.id))
            .join(SLAPolicy, SLABreachLog.policy_id == SLAPolicy.id)
            .group_by(SLAPolicy.name)
        )
        if start_date:
            by_policy_rows = by_policy_rows.filter(
                SLABreachLog.breached_at >= start_date
            )
        if end_date:
            by_policy_rows = by_policy_rows.filter(SLABreachLog.breached_at <= end_date)
        by_policy = {n: c for n, c in by_policy_rows.all()}

        avg_overdue_query = self.db.query(
            func.avg(SLABreachLog.actual_hours - SLABreachLog.target_hours)
        )
        if start_date:
            avg_overdue_query = avg_overdue_query.filter(
                SLABreachLog.breached_at >= start_date
            )
        if end_date:
            avg_overdue_query = avg_overdue_query.filter(
                SLABreachLog.breached_at <= end_date
            )
        avg_overdue = avg_overdue_query.scalar() or Decimal("0")

        return SLABreachSummary(
            total_breaches=total_breaches,
            by_target_type=by_target_type,
            by_policy=by_policy,
            avg_overdue_hours=float(avg_overdue),
        )

    def record_breach(
        self,
        ticket: Ticket,
        policy: SLAPolicy,
        target_type: str,
        target_hours: Decimal,
        actual_hours: Decimal,
    ) -> SLABreachLog:
        """Record an SLA breach."""
        log = SLABreachLog(
            ticket_id=ticket.id,
            policy_id=policy.id,
            target_type=target_type,
            target_hours=target_hours,
            actual_hours=actual_hours,
            breached_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.flush()
        return log

    def check_and_record_breaches(self, ticket: Ticket) -> List[SLABreachLog]:
        """Check for SLA breaches on a ticket and record them."""
        breaches = []
        now = datetime.now(timezone.utc)

        # Check first response breach
        if (
            ticket.response_by
            and not ticket.first_responded_at
            and ticket.response_by < now
        ):
            policy = self.match_policy_for_ticket(ticket)
            if policy:
                existing = self.db.query(SLABreachLog).filter(
                    SLABreachLog.ticket_id == ticket.id,
                    SLABreachLog.target_type == "first_response",
                ).first()

                if not existing:
                    hours_since_creation = (
                        now - ticket.created_at
                    ).total_seconds() / 3600
                    target_hours = (
                        ticket.response_by - ticket.created_at
                    ).total_seconds() / 3600

                    breach = self.record_breach(
                        ticket=ticket,
                        policy=policy,
                        target_type="first_response",
                        target_hours=Decimal(str(target_hours)),
                        actual_hours=Decimal(str(hours_since_creation)),
                    )
                    breaches.append(breach)

        # Check resolution breach
        if ticket.resolution_by and ticket.resolution_by < now:
            is_resolved = ticket.status and ticket.status.value in [
                "resolved",
                "closed",
            ]
            if not is_resolved:
                policy = self.match_policy_for_ticket(ticket)
                if policy:
                    existing = self.db.query(SLABreachLog).filter(
                        SLABreachLog.ticket_id == ticket.id,
                        SLABreachLog.target_type == "resolution",
                    ).first()

                    if not existing:
                        hours_since_creation = (
                            now - ticket.created_at
                        ).total_seconds() / 3600
                        target_hours = (
                            ticket.resolution_by - ticket.created_at
                        ).total_seconds() / 3600

                        breach = self.record_breach(
                            ticket=ticket,
                            policy=policy,
                            target_type="resolution",
                            target_hours=Decimal(str(target_hours)),
                            actual_hours=Decimal(str(hours_since_creation)),
                        )
                        breaches.append(breach)

        return breaches

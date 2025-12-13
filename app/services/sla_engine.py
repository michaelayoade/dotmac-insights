"""SLA calculation and monitoring service.

Handles SLA policy matching, target time calculations with business hours,
and breach detection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date, time
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.support_sla import (
    SLAPolicy,
    SLATarget,
    SLABreachLog,
    BusinessCalendar,
    BusinessCalendarHoliday,
    SLATargetType,
    BusinessHourType,
)
from app.models.ticket import Ticket, TicketPriority

logger = structlog.get_logger()


class SLAEngine:
    """Service for SLA calculations and breach monitoring."""

    def __init__(self, db: Session):
        self.db = db
        self._calendar_cache: Dict[int, BusinessCalendar] = {}
        self._holiday_cache: Dict[int, List[date]] = {}

    def get_applicable_policy(self, ticket: Ticket) -> Optional[SLAPolicy]:
        """Find the SLA policy that applies to a ticket.

        Policies are evaluated in priority order (lower number = higher priority).
        The first policy whose conditions match the ticket is returned.

        Args:
            ticket: The ticket to match

        Returns:
            Matching SLA policy or None if no policy matches
        """
        policies = self.db.query(SLAPolicy).filter(
            SLAPolicy.is_active == True
        ).order_by(SLAPolicy.priority).all()

        for policy in policies:
            if self._matches_policy_conditions(policy, ticket):
                logger.debug(
                    "sla_policy_matched",
                    ticket_id=ticket.id,
                    policy_id=policy.id,
                    policy_name=policy.name,
                )
                return policy

        # Return default policy if exists
        default = self.db.query(SLAPolicy).filter(
            SLAPolicy.is_default == True,
            SLAPolicy.is_active == True
        ).first()

        if default:
            logger.debug(
                "sla_default_policy_used",
                ticket_id=ticket.id,
                policy_id=default.id,
            )
        return default

    def _matches_policy_conditions(self, policy: SLAPolicy, ticket: Ticket) -> bool:
        """Check if a ticket matches a policy's conditions."""
        if not policy.conditions:
            return False  # Empty conditions = only applies if explicitly default

        for condition in policy.conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "")
            value = condition.get("value")

            ticket_value = getattr(ticket, field, None)
            if hasattr(ticket_value, "value"):
                ticket_value = ticket_value.value

            if not self._evaluate_condition(ticket_value, operator, value):
                return False

        return True

    def _evaluate_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        """Evaluate a single condition."""
        if operator == "equals":
            return str(actual) == str(expected)
        elif operator == "not_equals":
            return str(actual) != str(expected)
        elif operator == "contains":
            return expected in str(actual or "")
        elif operator == "not_contains":
            return expected not in str(actual or "")
        elif operator == "in_list":
            val_list = expected if isinstance(expected, list) else [expected]
            return str(actual) in val_list
        elif operator == "not_in_list":
            val_list = expected if isinstance(expected, list) else [expected]
            return str(actual) not in val_list
        elif operator == "is_empty":
            return actual is None or actual == ""
        elif operator == "is_not_empty":
            return actual is not None and actual != ""
        elif operator == "greater_than":
            try:
                return float(actual) > float(expected)
            except (TypeError, ValueError):
                return False
        elif operator == "less_than":
            try:
                return float(actual) < float(expected)
            except (TypeError, ValueError):
                return False
        return False

    def get_target_for_ticket(
        self,
        policy: SLAPolicy,
        ticket: Ticket,
        target_type: SLATargetType,
    ) -> Optional[SLATarget]:
        """Get the specific SLA target for a ticket's priority.

        Args:
            policy: The SLA policy
            ticket: The ticket
            target_type: Type of target (first_response, resolution, etc.)

        Returns:
            Matching SLA target or None
        """
        priority_value = ticket.priority.value if ticket.priority else None

        # First try to find priority-specific target
        for target in policy.targets:
            if target.target_type != target_type.value:
                continue
            if target.priority == priority_value:
                return target

        # Fall back to target without priority restriction
        for target in policy.targets:
            if target.target_type != target_type.value:
                continue
            if target.priority is None:
                return target

        return None

    def calculate_target_time(
        self,
        start_time: datetime,
        target_hours: Decimal,
        calendar: Optional[BusinessCalendar] = None,
    ) -> datetime:
        """Calculate the target deadline considering business hours.

        Args:
            start_time: When the SLA clock starts
            target_hours: Number of business hours allowed
            calendar: Business calendar to use (None = 24x7)

        Returns:
            Deadline datetime
        """
        if not calendar or calendar.calendar_type == BusinessHourType.TWENTY_FOUR_SEVEN.value:
            # 24x7 - simple addition
            return start_time + timedelta(hours=float(target_hours))

        # Calculate with business hours
        return self._add_business_hours(start_time, float(target_hours), calendar)

    def _add_business_hours(
        self,
        start_time: datetime,
        hours: float,
        calendar: BusinessCalendar,
    ) -> datetime:
        """Add business hours to a datetime, accounting for schedule and holidays."""
        # Cache holidays for this calendar
        if calendar.id not in self._holiday_cache:
            holidays = self.db.query(BusinessCalendarHoliday).filter(
                BusinessCalendarHoliday.calendar_id == calendar.id
            ).all()
            self._holiday_cache[calendar.id] = [h.holiday_date for h in holidays]

        holidays = self._holiday_cache[calendar.id]
        schedule = calendar.schedule or {}
        day_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        remaining_hours = hours
        current = start_time

        # Maximum iterations to prevent infinite loop
        max_days = int(hours / 0.1) + 365

        for _ in range(max_days):
            if remaining_hours <= 0:
                break

            current_date = current.date()

            # Check if holiday
            if current_date in holidays:
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            # Check recurring holidays
            for holiday in holidays:
                h = self.db.query(BusinessCalendarHoliday).filter(
                    BusinessCalendarHoliday.holiday_date == holiday,
                    BusinessCalendarHoliday.calendar_id == calendar.id
                ).first()
                if h and h.is_recurring:
                    if (current_date.month == holiday.month and
                        current_date.day == holiday.day):
                        current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                        continue

            # Get schedule for this day
            day_name = day_map[current.weekday()]
            day_schedule = schedule.get(day_name)

            if not day_schedule:
                # Non-business day
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            # Parse business hours
            try:
                start_str = day_schedule.get("start", "09:00")
                end_str = day_schedule.get("end", "17:00")
                day_start = datetime.strptime(start_str, "%H:%M").time()
                day_end = datetime.strptime(end_str, "%H:%M").time()
            except (ValueError, AttributeError):
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            # Calculate available hours today
            work_start = datetime.combine(current_date, day_start)
            work_end = datetime.combine(current_date, day_end)

            # If we're before business hours, move to start
            if current < work_start:
                current = work_start

            # If we're after business hours, move to next day
            if current >= work_end:
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            # Calculate hours remaining today
            hours_today = (work_end - current).total_seconds() / 3600

            if hours_today >= remaining_hours:
                # We can complete within today
                return current + timedelta(hours=remaining_hours)
            else:
                # Use all remaining hours today and continue tomorrow
                remaining_hours -= hours_today
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))

        # Fallback if we exceed max iterations
        logger.warning(
            "sla_business_hours_calculation_exceeded_max",
            start_time=start_time.isoformat(),
            hours=hours,
        )
        return start_time + timedelta(hours=hours)

    def calculate_elapsed_business_hours(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar: Optional[BusinessCalendar] = None,
    ) -> float:
        """Calculate elapsed business hours between two times.

        Args:
            start_time: Start datetime
            end_time: End datetime
            calendar: Business calendar to use (None = 24x7)

        Returns:
            Number of business hours elapsed
        """
        if not calendar or calendar.calendar_type == BusinessHourType.TWENTY_FOUR_SEVEN.value:
            return (end_time - start_time).total_seconds() / 3600

        # Calculate with business hours
        return self._count_business_hours(start_time, end_time, calendar)

    def _count_business_hours(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar: BusinessCalendar,
    ) -> float:
        """Count business hours between two datetimes."""
        if calendar.id not in self._holiday_cache:
            holidays = self.db.query(BusinessCalendarHoliday).filter(
                BusinessCalendarHoliday.calendar_id == calendar.id
            ).all()
            self._holiday_cache[calendar.id] = [h.holiday_date for h in holidays]

        holidays = self._holiday_cache[calendar.id]
        schedule = calendar.schedule or {}
        day_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        total_hours = 0.0
        current = start_time

        while current < end_time:
            current_date = current.date()

            # Check if holiday
            if current_date in holidays:
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            # Get schedule for this day
            day_name = day_map[current.weekday()]
            day_schedule = schedule.get(day_name)

            if not day_schedule:
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            try:
                start_str = day_schedule.get("start", "09:00")
                end_str = day_schedule.get("end", "17:00")
                day_start = datetime.strptime(start_str, "%H:%M").time()
                day_end = datetime.strptime(end_str, "%H:%M").time()
            except (ValueError, AttributeError):
                current = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                continue

            work_start = datetime.combine(current_date, day_start)
            work_end = datetime.combine(current_date, day_end)

            # Clamp to business hours
            effective_start = max(current, work_start)
            effective_end = min(end_time, work_end)

            if effective_start < effective_end:
                total_hours += (effective_end - effective_start).total_seconds() / 3600

            current = datetime.combine(current_date + timedelta(days=1), time(0, 0))

        return total_hours

    def update_ticket_sla(self, ticket: Ticket) -> Dict[str, Any]:
        """Calculate and update SLA fields on a ticket.

        Sets response_by and resolution_by based on applicable policy.

        Args:
            ticket: Ticket to update

        Returns:
            Dict with SLA info applied
        """
        policy = self.get_applicable_policy(ticket)
        if not policy:
            return {"policy_applied": False, "message": "No applicable SLA policy"}

        calendar = policy.calendar
        start_time = ticket.opening_date or ticket.created_at or datetime.utcnow()

        updates = {
            "policy_id": policy.id,
            "policy_name": policy.name,
            "targets_set": [],
        }

        # Set first response target
        first_response_target = self.get_target_for_ticket(
            policy, ticket, SLATargetType.FIRST_RESPONSE
        )
        if first_response_target:
            response_by = self.calculate_target_time(
                start_time,
                first_response_target.target_hours,
                calendar,
            )
            ticket.response_by = response_by
            updates["targets_set"].append({
                "type": "first_response",
                "target_hours": float(first_response_target.target_hours),
                "deadline": response_by.isoformat(),
            })

        # Set resolution target
        resolution_target = self.get_target_for_ticket(
            policy, ticket, SLATargetType.RESOLUTION
        )
        if resolution_target:
            resolution_by = self.calculate_target_time(
                start_time,
                resolution_target.target_hours,
                calendar,
            )
            ticket.resolution_by = resolution_by
            updates["targets_set"].append({
                "type": "resolution",
                "target_hours": float(resolution_target.target_hours),
                "deadline": resolution_by.isoformat(),
            })

        ticket.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            "sla_applied_to_ticket",
            ticket_id=ticket.id,
            policy_id=policy.id,
            targets=len(updates["targets_set"]),
        )

        return updates

    def check_sla_status(self, ticket: Ticket) -> Dict[str, Any]:
        """Check current SLA status for a ticket.

        Returns:
            Dict with status for each SLA target (time remaining, breached, etc.)
        """
        now = datetime.utcnow()
        policy = self.get_applicable_policy(ticket)
        calendar = policy.calendar if policy else None

        status = {
            "ticket_id": ticket.id,
            "policy_id": policy.id if policy else None,
            "first_response": None,
            "resolution": None,
        }

        # First response status
        if ticket.response_by:
            if ticket.first_response_at:
                # Already responded
                elapsed = self.calculate_elapsed_business_hours(
                    ticket.opening_date or ticket.created_at,
                    ticket.first_response_at,
                    calendar,
                )
                status["first_response"] = {
                    "status": "completed",
                    "responded_at": ticket.first_response_at.isoformat(),
                    "deadline": ticket.response_by.isoformat(),
                    "elapsed_hours": round(elapsed, 2),
                    "breached": ticket.first_response_at > ticket.response_by,
                }
            else:
                # Not yet responded
                time_remaining = (ticket.response_by - now).total_seconds() / 3600
                status["first_response"] = {
                    "status": "pending",
                    "deadline": ticket.response_by.isoformat(),
                    "hours_remaining": round(time_remaining, 2),
                    "breached": time_remaining < 0,
                    "warning": 0 < time_remaining < 1,  # Warning if less than 1 hour
                }

        # Resolution status
        if ticket.resolution_by:
            if ticket.resolution_date:
                # Already resolved
                elapsed = self.calculate_elapsed_business_hours(
                    ticket.opening_date or ticket.created_at,
                    ticket.resolution_date,
                    calendar,
                )
                status["resolution"] = {
                    "status": "completed",
                    "resolved_at": ticket.resolution_date.isoformat(),
                    "deadline": ticket.resolution_by.isoformat(),
                    "elapsed_hours": round(elapsed, 2),
                    "breached": ticket.resolution_date > ticket.resolution_by,
                }
            else:
                # Not yet resolved
                time_remaining = (ticket.resolution_by - now).total_seconds() / 3600
                status["resolution"] = {
                    "status": "pending",
                    "deadline": ticket.resolution_by.isoformat(),
                    "hours_remaining": round(time_remaining, 2),
                    "breached": time_remaining < 0,
                    "warning": 0 < time_remaining < 2,  # Warning if less than 2 hours
                }

        return status

    def find_sla_warnings(self, threshold_minutes: int = 60) -> List[Ticket]:
        """Find tickets approaching SLA breach.

        Args:
            threshold_minutes: Minutes before deadline to warn

        Returns:
            List of tickets needing attention
        """
        now = datetime.utcnow()
        warning_threshold = now + timedelta(minutes=threshold_minutes)

        # Find tickets with approaching first response deadline
        response_warnings = self.db.query(Ticket).filter(
            Ticket.first_response_at.is_(None),
            Ticket.response_by.isnot(None),
            Ticket.response_by > now,
            Ticket.response_by <= warning_threshold,
        ).all()

        # Find tickets with approaching resolution deadline
        resolution_warnings = self.db.query(Ticket).filter(
            Ticket.resolution_date.is_(None),
            Ticket.resolution_by.isnot(None),
            Ticket.resolution_by > now,
            Ticket.resolution_by <= warning_threshold,
        ).all()

        # Combine and deduplicate
        warning_ids = set()
        warnings = []
        for ticket in response_warnings + resolution_warnings:
            if ticket.id not in warning_ids:
                warning_ids.add(ticket.id)
                warnings.append(ticket)

        return warnings

    def find_sla_breaches(self) -> List[Tuple[Ticket, str]]:
        """Find tickets that have breached their SLA.

        Returns:
            List of (ticket, breach_type) tuples
        """
        now = datetime.utcnow()
        breaches = []

        # First response breaches
        response_breaches = self.db.query(Ticket).filter(
            Ticket.first_response_at.is_(None),
            Ticket.response_by.isnot(None),
            Ticket.response_by < now,
        ).all()

        for ticket in response_breaches:
            breaches.append((ticket, "first_response"))

        # Resolution breaches
        resolution_breaches = self.db.query(Ticket).filter(
            Ticket.resolution_date.is_(None),
            Ticket.resolution_by.isnot(None),
            Ticket.resolution_by < now,
        ).all()

        for ticket in resolution_breaches:
            breaches.append((ticket, "resolution"))

        return breaches

    def log_breach(
        self,
        ticket: Ticket,
        target_type: str,
        target_hours: Decimal,
        actual_hours: Decimal,
    ) -> SLABreachLog:
        """Log an SLA breach.

        Args:
            ticket: The breached ticket
            target_type: Type of breach (first_response, resolution)
            target_hours: Target hours allowed
            actual_hours: Actual hours taken

        Returns:
            Created breach log entry
        """
        policy = self.get_applicable_policy(ticket)

        breach = SLABreachLog(
            ticket_id=ticket.id,
            policy_id=policy.id if policy else None,
            target_type=target_type,
            target_hours=target_hours,
            actual_hours=actual_hours,
            breached_at=datetime.utcnow(),
        )
        self.db.add(breach)
        self.db.commit()

        logger.warning(
            "sla_breach_logged",
            ticket_id=ticket.id,
            target_type=target_type,
            target_hours=float(target_hours),
            actual_hours=float(actual_hours),
        )

        return breach

    def process_sla_checks(self) -> Dict[str, Any]:
        """Process all SLA checks (for scheduled task).

        Returns:
            Summary of warnings and breaches found
        """
        results = {
            "warnings_found": 0,
            "breaches_found": 0,
            "breaches_logged": 0,
        }

        # Check warnings
        warnings = self.find_sla_warnings()
        results["warnings_found"] = len(warnings)

        # Check and log breaches
        breaches = self.find_sla_breaches()
        results["breaches_found"] = len(breaches)

        for ticket, breach_type in breaches:
            # Check if already logged
            existing = self.db.query(SLABreachLog).filter(
                SLABreachLog.ticket_id == ticket.id,
                SLABreachLog.target_type == breach_type,
            ).first()

            if not existing:
                policy = self.get_applicable_policy(ticket)
                if policy:
                    target = self.get_target_for_ticket(
                        policy, ticket,
                        SLATargetType.FIRST_RESPONSE if breach_type == "first_response"
                        else SLATargetType.RESOLUTION
                    )
                    if target:
                        start_time = ticket.opening_date or ticket.created_at
                        actual_hours = (datetime.utcnow() - start_time).total_seconds() / 3600
                        self.log_breach(
                            ticket,
                            breach_type,
                            target.target_hours,
                            Decimal(str(round(actual_hours, 2))),
                        )
                        results["breaches_logged"] += 1

        logger.info(
            "sla_check_completed",
            warnings=results["warnings_found"],
            breaches=results["breaches_found"],
            logged=results["breaches_logged"],
        )

        return results

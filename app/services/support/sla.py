"""SLA service - business logic for SLA management.

This service handles SLA-related calculations:
- Due date calculation
- Breach detection
- Business hours calculation

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketPriority
from app.models.omni import OmniConversation

from .types import SLABreachInfo, SLADueDates
from .errors import SLAConfigError

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

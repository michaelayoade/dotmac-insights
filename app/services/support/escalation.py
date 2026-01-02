"""Escalation service - business logic for escalation policies and execution.

This service handles escalation management:
- Policy CRUD operations
- Level management
- Ticket escalation execution
- Escalation history tracking

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.support_settings import (
    EscalationLevel,
    EscalationPolicy,
    EscalationTrigger,
)
from app.models.ticket import Ticket

from .types import (
    EscalationLevelCreate,
    EscalationLevelUpdate,
    EscalationPolicyCreate,
    EscalationPolicyUpdate,
    EscalationResult,
)
from .errors import (
    DuplicatePolicyError,
    EscalationLevelNotFoundError,
    EscalationPolicyNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["EscalationService"]


class EscalationService:
    """Service for escalation policy management and execution.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Policy Queries
    # -------------------------------------------------------------------------

    def list_policies(
        self,
        active_only: bool = True,
        company: Optional[str] = None,
    ) -> List[EscalationPolicy]:
        """List escalation policies.

        Args:
            active_only: Only return active policies.
            company: Filter by company.

        Returns:
            List of EscalationPolicy instances.
        """
        query = self.db.query(EscalationPolicy)

        if active_only:
            query = query.filter(EscalationPolicy.is_active == True)

        if company:
            query = query.filter(EscalationPolicy.company == company)

        return query.order_by(EscalationPolicy.priority.asc()).all()

    def get_policy(self, policy_id: int) -> EscalationPolicy:
        """Get a policy by ID.

        Args:
            policy_id: The policy ID.

        Returns:
            EscalationPolicy instance.

        Raises:
            EscalationPolicyNotFoundError: If not found.
        """
        policy = (
            self.db.query(EscalationPolicy)
            .filter(EscalationPolicy.id == policy_id)
            .first()
        )
        if not policy:
            raise EscalationPolicyNotFoundError(policy_id)
        return policy

    def get_policy_by_name(
        self,
        name: str,
        company: Optional[str] = None,
    ) -> Optional[EscalationPolicy]:
        """Get a policy by name.

        Args:
            name: The policy name.
            company: Optional company filter.

        Returns:
            EscalationPolicy instance or None.
        """
        query = self.db.query(EscalationPolicy).filter(
            EscalationPolicy.name == name,
        )
        if company:
            query = query.filter(EscalationPolicy.company == company)
        return query.first()

    def get_matching_policy(self, ticket: Ticket) -> Optional[EscalationPolicy]:
        """Find an escalation policy that matches a ticket.

        Args:
            ticket: The ticket to match.

        Returns:
            Matching EscalationPolicy or None.
        """
        policies = self.list_policies(active_only=True)

        for policy in policies:
            if self._matches_ticket(policy, ticket):
                return policy

        return None

    def _matches_ticket(
        self,
        policy: EscalationPolicy,
        ticket: Ticket,
    ) -> bool:
        """Check if a policy matches a ticket.

        Args:
            policy: The escalation policy.
            ticket: The ticket to check.

        Returns:
            True if policy matches ticket.
        """
        conditions = policy.conditions or []
        if not conditions:
            return True  # Empty conditions match all

        for condition in conditions:
            if not self._evaluate_condition(condition, ticket):
                return False

        return True

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        ticket: Ticket,
    ) -> bool:
        """Evaluate a single condition against a ticket."""
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        if not field:
            return True

        # Get actual value from ticket
        actual = getattr(ticket, field, None)
        if hasattr(actual, "value"):  # Handle enums
            actual = actual.value

        # Evaluate based on operator
        if operator == "equals":
            return actual == value
        elif operator == "not_equals":
            return actual != value
        elif operator == "in":
            return actual in (value if isinstance(value, list) else [value])
        elif operator == "not_in":
            return actual not in (value if isinstance(value, list) else [value])
        elif operator == "is_empty":
            return not actual
        elif operator == "is_not_empty":
            return bool(actual)

        return False

    # -------------------------------------------------------------------------
    # Policy Mutations
    # -------------------------------------------------------------------------

    def create_policy(
        self,
        data: EscalationPolicyCreate,
        company: Optional[str] = None,
    ) -> EscalationPolicy:
        """Create a new escalation policy.

        Args:
            data: Policy creation data.
            company: Optional company identifier.

        Returns:
            Created EscalationPolicy instance.

        Raises:
            DuplicatePolicyError: If name already exists.
        """
        existing = self.get_policy_by_name(data.name, company)
        if existing:
            raise DuplicatePolicyError(data.name)

        policy = EscalationPolicy(
            company=company,
            name=data.name,
            description=data.description,
            conditions=data.conditions if data.conditions else [],
            priority=data.priority,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        if self.principal:
            policy.created_by_id = getattr(self.principal, "id", None)

        self.db.add(policy)
        self.db.flush()
        return policy

    def update_policy(
        self,
        policy_id: int,
        data: EscalationPolicyUpdate,
    ) -> EscalationPolicy:
        """Update an escalation policy.

        Args:
            policy_id: The policy ID.
            data: Update data.

        Returns:
            Updated EscalationPolicy instance.

        Raises:
            EscalationPolicyNotFoundError: If not found.
            DuplicatePolicyError: If new name conflicts.
        """
        policy = self.get_policy(policy_id)

        if data.name is not None and data.name != policy.name:
            existing = self.get_policy_by_name(data.name, policy.company)
            if existing:
                raise DuplicatePolicyError(data.name)
            policy.name = data.name

        if data.description is not None:
            policy.description = data.description

        if data.conditions is not None:
            policy.conditions = data.conditions if data.conditions else []

        if data.priority is not None:
            policy.priority = data.priority

        if data.is_active is not None:
            policy.is_active = data.is_active

        policy.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return policy

    def delete_policy(self, policy_id: int) -> bool:
        """Delete an escalation policy.

        Args:
            policy_id: The policy ID.

        Returns:
            True if deleted.

        Raises:
            EscalationPolicyNotFoundError: If not found.
        """
        policy = self.get_policy(policy_id)
        self.db.delete(policy)
        self.db.flush()
        return True

    def activate_policy(self, policy_id: int) -> EscalationPolicy:
        """Activate a policy.

        Args:
            policy_id: The policy ID.

        Returns:
            Updated EscalationPolicy.
        """
        policy = self.get_policy(policy_id)
        policy.is_active = True
        policy.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return policy

    def deactivate_policy(self, policy_id: int) -> EscalationPolicy:
        """Deactivate a policy.

        Args:
            policy_id: The policy ID.

        Returns:
            Updated EscalationPolicy.
        """
        policy = self.get_policy(policy_id)
        policy.is_active = False
        policy.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return policy

    # -------------------------------------------------------------------------
    # Level Management
    # -------------------------------------------------------------------------

    def get_level(self, level_id: int) -> EscalationLevel:
        """Get an escalation level by ID.

        Args:
            level_id: The level ID.

        Returns:
            EscalationLevel instance.

        Raises:
            EscalationLevelNotFoundError: If not found.
        """
        level = (
            self.db.query(EscalationLevel)
            .filter(EscalationLevel.id == level_id)
            .first()
        )
        if not level:
            raise EscalationLevelNotFoundError(level_id)
        return level

    def get_policy_levels(self, policy_id: int) -> List[EscalationLevel]:
        """Get all levels for a policy.

        Args:
            policy_id: The policy ID.

        Returns:
            List of EscalationLevel instances ordered by level.
        """
        return (
            self.db.query(EscalationLevel)
            .filter(EscalationLevel.policy_id == policy_id)
            .order_by(EscalationLevel.level.asc())
            .all()
        )

    def add_level(
        self,
        policy_id: int,
        data: EscalationLevelCreate,
    ) -> EscalationLevel:
        """Add a level to a policy.

        Args:
            policy_id: The policy ID.
            data: Level creation data.

        Returns:
            Created EscalationLevel instance.
        """
        # Verify policy exists
        self.get_policy(policy_id)

        level = EscalationLevel(
            policy_id=policy_id,
            level=data.level,
            trigger=data.trigger,
            trigger_hours=data.trigger_hours,
            escalate_to_team_id=data.escalate_to_team_id,
            escalate_to_user_id=data.escalate_to_user_id,
            notify_current_assignee=data.notify_current_assignee,
            notify_team_lead=data.notify_team_lead,
            reassign_ticket=data.reassign_ticket,
            change_priority=data.change_priority,
            new_priority=data.new_priority,
            notification_template=data.notification_template,
        )
        self.db.add(level)
        self.db.flush()
        return level

    def update_level(
        self,
        level_id: int,
        data: EscalationLevelUpdate,
    ) -> EscalationLevel:
        """Update an escalation level.

        Args:
            level_id: The level ID.
            data: Update data.

        Returns:
            Updated EscalationLevel instance.
        """
        level = self.get_level(level_id)

        if data.trigger is not None:
            level.trigger = data.trigger

        if data.trigger_hours is not None:
            level.trigger_hours = data.trigger_hours

        if data.escalate_to_team_id is not None:
            level.escalate_to_team_id = data.escalate_to_team_id

        if data.escalate_to_user_id is not None:
            level.escalate_to_user_id = data.escalate_to_user_id

        if data.notify_current_assignee is not None:
            level.notify_current_assignee = data.notify_current_assignee

        if data.notify_team_lead is not None:
            level.notify_team_lead = data.notify_team_lead

        if data.reassign_ticket is not None:
            level.reassign_ticket = data.reassign_ticket

        if data.change_priority is not None:
            level.change_priority = data.change_priority

        if data.new_priority is not None:
            level.new_priority = data.new_priority

        if data.notification_template is not None:
            level.notification_template = data.notification_template

        self.db.flush()
        return level

    def remove_level(self, level_id: int) -> bool:
        """Remove an escalation level.

        Args:
            level_id: The level ID.

        Returns:
            True if removed.
        """
        level = self.get_level(level_id)
        self.db.delete(level)
        self.db.flush()
        return True

    def reorder_levels(self, policy_id: int, level_ids: List[int]) -> None:
        """Reorder levels within a policy.

        Args:
            policy_id: The policy ID.
            level_ids: List of level IDs in desired order.
        """
        for order, level_id in enumerate(level_ids, start=1):
            level = (
                self.db.query(EscalationLevel)
                .filter(
                    EscalationLevel.id == level_id,
                    EscalationLevel.policy_id == policy_id,
                )
                .first()
            )
            if level:
                level.level = order
        self.db.flush()

    # -------------------------------------------------------------------------
    # Escalation Execution
    # -------------------------------------------------------------------------

    def check_and_escalate(self, ticket: Ticket) -> Optional[EscalationResult]:
        """Check if a ticket should be escalated and execute if needed.

        Args:
            ticket: The ticket to check.

        Returns:
            EscalationResult if escalated, None otherwise.
        """
        # Find matching policy
        policy = self.get_matching_policy(ticket)
        if not policy:
            return None

        # Get levels for the policy
        levels = self.get_policy_levels(policy.id)
        if not levels:
            return None

        # Determine current escalation level
        current_level = getattr(ticket, "escalation_level", 0) or 0

        # Find the next level to escalate to
        for level in levels:
            if level.level <= current_level:
                continue  # Already escalated past this level

            # Check if trigger condition is met
            if self._should_escalate(ticket, level):
                return self._execute_escalation(ticket, policy, level)

        return None

    def _should_escalate(
        self,
        ticket: Ticket,
        level: EscalationLevel,
    ) -> bool:
        """Check if escalation trigger condition is met."""
        trigger = level.trigger
        trigger_hours = level.trigger_hours or 0

        if trigger == EscalationTrigger.SLA_BREACH.value:
            # Check if SLA is breached
            if hasattr(ticket, "sla_breached") and ticket.sla_breached:
                return True
            # Check response/resolution times
            if hasattr(ticket, "first_response_due_at") and ticket.first_response_due_at:
                if datetime.now(timezone.utc) > ticket.first_response_due_at:
                    return True
            if hasattr(ticket, "resolution_due_at") and ticket.resolution_due_at:
                if datetime.now(timezone.utc) > ticket.resolution_due_at:
                    return True

        elif trigger == EscalationTrigger.SLA_WARNING.value:
            # Check if approaching SLA threshold
            warning_threshold = 0.8  # 80% of time used
            if hasattr(ticket, "first_response_due_at") and ticket.first_response_due_at:
                if hasattr(ticket, "created_at"):
                    total_time = ticket.first_response_due_at - ticket.created_at
                    elapsed = datetime.now(timezone.utc) - ticket.created_at
                    if elapsed.total_seconds() > total_time.total_seconds() * warning_threshold:
                        return True

        elif trigger == EscalationTrigger.IDLE_TIME.value:
            # Check if ticket has been idle for trigger_hours
            last_activity = getattr(ticket, "updated_at", None) or getattr(ticket, "created_at", None)
            if last_activity:
                idle_threshold = timedelta(hours=trigger_hours)
                if datetime.now(timezone.utc) - last_activity > idle_threshold:
                    return True

        elif trigger == EscalationTrigger.REOPEN_COUNT.value:
            # Check if ticket has been reopened too many times
            reopen_count = getattr(ticket, "reopen_count", 0) or 0
            if reopen_count >= trigger_hours:  # Using trigger_hours as count threshold
                return True

        elif trigger == EscalationTrigger.CUSTOMER_ESCALATION.value:
            # Check if customer requested escalation
            if hasattr(ticket, "customer_escalated") and ticket.customer_escalated:
                return True

        return False

    def _execute_escalation(
        self,
        ticket: Ticket,
        policy: EscalationPolicy,
        level: EscalationLevel,
    ) -> EscalationResult:
        """Execute escalation actions for a level."""
        result = EscalationResult(
            escalated=True,
            policy_id=policy.id,
            level=level.level,
        )

        try:
            # Update ticket escalation level
            if hasattr(ticket, "escalation_level"):
                ticket.escalation_level = level.level
                result.actions_taken.append(f"Set escalation level to {level.level}")

            # Reassign ticket if configured
            if level.reassign_ticket:
                if level.escalate_to_user_id:
                    ticket.assignee_id = level.escalate_to_user_id
                    result.actions_taken.append(f"Reassigned to user {level.escalate_to_user_id}")
                elif level.escalate_to_team_id:
                    if hasattr(ticket, "team_id"):
                        ticket.team_id = level.escalate_to_team_id
                    result.actions_taken.append(f"Reassigned to team {level.escalate_to_team_id}")

            # Change priority if configured
            if level.change_priority and level.new_priority:
                if hasattr(ticket, "priority"):
                    ticket.priority = level.new_priority
                    result.actions_taken.append(f"Changed priority to {level.new_priority}")

            # Record escalation timestamp
            if hasattr(ticket, "escalated_at"):
                ticket.escalated_at = datetime.now(timezone.utc)

            # Note: Actual notifications would be sent by a notification service
            if level.notify_current_assignee:
                result.notifications_sent.append("current_assignee")
            if level.notify_team_lead:
                result.notifications_sent.append("team_lead")

            self.db.flush()

        except Exception as e:
            result.escalated = False
            result.error = str(e)

        return result

    def escalate_ticket(
        self,
        ticket_id: int,
        reason: str,
        to_level: Optional[int] = None,
    ) -> EscalationResult:
        """Manually escalate a ticket.

        Args:
            ticket_id: The ticket ID.
            reason: Reason for escalation.
            to_level: Target escalation level (optional).

        Returns:
            EscalationResult instance.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return EscalationResult(
                escalated=False,
                error=f"Ticket not found: {ticket_id}",
            )

        # Find matching policy
        policy = self.get_matching_policy(ticket)
        if not policy:
            return EscalationResult(
                escalated=False,
                error="No matching escalation policy found",
            )

        # Get levels
        levels = self.get_policy_levels(policy.id)
        if not levels:
            return EscalationResult(
                escalated=False,
                error="No escalation levels defined",
            )

        # Determine target level
        current_level = getattr(ticket, "escalation_level", 0) or 0
        if to_level is not None:
            target_level = to_level
        else:
            target_level = current_level + 1

        # Find the level definition
        level_def = None
        for lvl in levels:
            if lvl.level == target_level:
                level_def = lvl
                break

        if not level_def:
            # Use last level if target exceeds available levels
            level_def = levels[-1] if levels else None

        if not level_def:
            return EscalationResult(
                escalated=False,
                error="No valid escalation level found",
            )

        # Execute escalation
        result = self._execute_escalation(ticket, policy, level_def)
        result.actions_taken.append(f"Manual escalation: {reason}")

        return result

    # -------------------------------------------------------------------------
    # Scheduled Processing
    # -------------------------------------------------------------------------

    def process_pending_escalations(self) -> int:
        """Process all tickets for pending escalations.

        This should be called by a scheduler periodically.

        Returns:
            Number of tickets escalated.
        """
        # Get all open/pending tickets
        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.status.in_(["open", "pending", "in_progress"]))
            .all()
        )

        escalated_count = 0
        for ticket in tickets:
            result = self.check_and_escalate(ticket)
            if result and result.escalated:
                escalated_count += 1

        if escalated_count > 0:
            self.db.flush()

        return escalated_count

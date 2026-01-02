"""Routing service - business logic for auto-assignment and routing rules.

This service handles automatic routing:
- Rule matching against conversations/tickets
- Agent selection (round-robin, load-balanced)
- Auto-assignment

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.omni import InboxRoutingRule, OmniConversation
from app.models.ticket import Ticket
from app.models.agent import Agent, Team, TeamMember

from .types import (
    RoutingMatch,
    RoutingRuleCreate,
    RoutingRuleUpdate,
)
from .errors import (
    NoMatchingRuleError,
    RoutingRuleNotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["RoutingService"]


class RoutingService:
    """Service for routing and auto-assignment.

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
    # Auto-Assignment
    # -------------------------------------------------------------------------

    def auto_assign_ticket(self, ticket: Ticket) -> Optional[Agent]:
        """Automatically assign a ticket based on routing rules.

        Args:
            ticket: The ticket to assign.

        Returns:
            Assigned Agent, or None if no match.
        """
        # Find matching rule
        match = self.find_matching_rule_for_ticket(ticket)
        if not match:
            return None

        return self._execute_assignment(match)

    def auto_assign_conversation(
        self,
        conversation: OmniConversation,
    ) -> Optional[Agent]:
        """Automatically assign a conversation based on routing rules.

        Args:
            conversation: The conversation to assign.

        Returns:
            Assigned Agent, or None if no match.
        """
        # Find matching rule
        match = self.find_matching_rule_for_conversation(conversation)
        if not match:
            return None

        return self._execute_assignment(match)

    def _execute_assignment(self, match: RoutingMatch) -> Optional[Agent]:
        """Execute the assignment from a routing match."""
        if match.action_type == "assign_agent":
            if match.action_value:
                agent_id = int(match.action_value)
                agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
                if agent:
                    return agent

        elif match.action_type == "assign_team":
            if match.action_value:
                team_id = int(match.action_value)
                # Select agent from team
                strategy = match.action_config.get("strategy", "round_robin")
                if strategy == "round_robin":
                    return self.select_agent_round_robin(team_id)
                elif strategy == "load_balanced":
                    return self.select_agent_load_balanced(team_id)

        return None

    # -------------------------------------------------------------------------
    # Rule Matching
    # -------------------------------------------------------------------------

    def find_matching_rule_for_ticket(
        self,
        ticket: Ticket,
    ) -> Optional[RoutingMatch]:
        """Find a matching routing rule for a ticket.

        Args:
            ticket: The ticket to match.

        Returns:
            RoutingMatch if found, None otherwise.
        """
        rules = self._get_active_rules()

        for rule in rules:
            if self._matches_ticket(rule, ticket):
                # Increment match count
                rule.match_count = (rule.match_count or 0) + 1
                self.db.flush()

                return RoutingMatch(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    action_type=rule.action_type,
                    action_value=rule.action_value,
                    action_config=rule.action_config or {},
                )

        return None

    def find_matching_rule_for_conversation(
        self,
        conversation: OmniConversation,
    ) -> Optional[RoutingMatch]:
        """Find a matching routing rule for a conversation.

        Args:
            conversation: The conversation to match.

        Returns:
            RoutingMatch if found, None otherwise.
        """
        rules = self._get_active_rules()

        for rule in rules:
            if self._matches_conversation(rule, conversation):
                # Increment match count
                rule.match_count = (rule.match_count or 0) + 1
                self.db.flush()

                return RoutingMatch(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    action_type=rule.action_type,
                    action_value=rule.action_value,
                    action_config=rule.action_config or {},
                )

        return None

    def _get_active_rules(self) -> List[InboxRoutingRule]:
        """Get active routing rules ordered by priority."""
        return (
            self.db.query(InboxRoutingRule)
            .filter(InboxRoutingRule.is_active == True)
            .order_by(InboxRoutingRule.priority.desc())
            .all()
        )

    def _matches_ticket(
        self,
        rule: InboxRoutingRule,
        ticket: Ticket,
    ) -> bool:
        """Check if a rule matches a ticket."""
        conditions = rule.conditions or []
        if not conditions:
            return False

        for condition in conditions:
            if not self._evaluate_condition_ticket(condition, ticket):
                return False

        return True

    def _matches_conversation(
        self,
        rule: InboxRoutingRule,
        conversation: OmniConversation,
    ) -> bool:
        """Check if a rule matches a conversation."""
        conditions = rule.conditions or []
        if not conditions:
            return False

        for condition in conditions:
            if not self._evaluate_condition_conversation(condition, conversation):
                return False

        return True

    def _evaluate_condition_ticket(
        self,
        condition: Dict[str, Any],
        ticket: Ticket,
    ) -> bool:
        """Evaluate a single condition against a ticket."""
        cond_type = condition.get("type")
        cond_value = condition.get("value")

        if cond_type == "priority":
            return ticket.priority and ticket.priority.value == cond_value

        elif cond_type == "status":
            return ticket.status and ticket.status.value == cond_value

        elif cond_type == "category":
            return ticket.category == cond_value

        elif cond_type == "keyword":
            keywords = [k.strip().lower() for k in cond_value.split(",")]
            subject = (ticket.subject or "").lower()
            description = (ticket.description or "").lower()
            return any(k in subject or k in description for k in keywords)

        elif cond_type == "source":
            return ticket.source == cond_value

        return False

    def _evaluate_condition_conversation(
        self,
        condition: Dict[str, Any],
        conversation: OmniConversation,
    ) -> bool:
        """Evaluate a single condition against a conversation."""
        cond_type = condition.get("type")
        cond_value = condition.get("value")

        if cond_type == "channel":
            if conversation.channel:
                return conversation.channel.name == cond_value or conversation.channel.type == cond_value
            return False

        elif cond_type == "priority":
            return conversation.priority == cond_value

        elif cond_type == "status":
            return conversation.status == cond_value

        elif cond_type == "keyword":
            keywords = [k.strip().lower() for k in cond_value.split(",")]
            subject = (conversation.subject or "").lower()
            contact_name = (conversation.contact_name or "").lower()
            return any(k in subject or k in contact_name for k in keywords)

        elif cond_type == "tag":
            tags = conversation.tags or []
            return cond_value in tags

        elif cond_type == "email_domain":
            email = conversation.contact_email or ""
            domain = email.split("@")[-1] if "@" in email else ""
            return domain.lower() == cond_value.lower()

        return False

    # -------------------------------------------------------------------------
    # Agent Selection
    # -------------------------------------------------------------------------

    def select_agent_round_robin(self, team_id: int) -> Optional[Agent]:
        """Select an agent using round-robin within a team.

        Args:
            team_id: The team ID.

        Returns:
            Selected Agent, or None if no available agents.
        """
        # Get team members
        members = (
            self.db.query(TeamMember)
            .filter(TeamMember.team_id == team_id)
            .all()
        )

        if not members:
            return None

        agent_ids = [m.agent_id for m in members if m.agent_id]
        if not agent_ids:
            return None

        # Get agents with conversation counts
        agents_with_counts = (
            self.db.query(
                Agent,
                func.count(OmniConversation.id).label("conv_count"),
            )
            .outerjoin(
                OmniConversation,
                (OmniConversation.assigned_agent_id == Agent.id)
                & (OmniConversation.status.in_(["open", "pending"])),
            )
            .filter(Agent.id.in_(agent_ids), Agent.is_active == True)
            .group_by(Agent.id)
            .order_by(func.count(OmniConversation.id).asc())
            .first()
        )

        if agents_with_counts:
            return agents_with_counts[0]

        # Fallback: just get first active agent
        return (
            self.db.query(Agent)
            .filter(Agent.id.in_(agent_ids), Agent.is_active == True)
            .first()
        )

    def select_agent_load_balanced(self, team_id: int) -> Optional[Agent]:
        """Select an agent using load-balancing within a team.

        This considers the agent's current workload.

        Args:
            team_id: The team ID.

        Returns:
            Selected Agent, or None if no available agents.
        """
        # Same as round-robin for now, but could be enhanced
        # to consider capacity limits, skills, etc.
        return self.select_agent_round_robin(team_id)

    # -------------------------------------------------------------------------
    # Rule CRUD
    # -------------------------------------------------------------------------

    def list_rules(
        self,
        active_only: bool = False,
    ) -> List[InboxRoutingRule]:
        """List routing rules.

        Args:
            active_only: Only return active rules.

        Returns:
            List of InboxRoutingRule instances.
        """
        query = self.db.query(InboxRoutingRule)

        if active_only:
            query = query.filter(InboxRoutingRule.is_active == True)

        return query.order_by(InboxRoutingRule.priority.desc()).all()

    def get_rule(self, rule_id: int) -> InboxRoutingRule:
        """Get a routing rule by ID.

        Args:
            rule_id: The rule ID.

        Returns:
            InboxRoutingRule instance.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
        """
        rule = (
            self.db.query(InboxRoutingRule)
            .filter(InboxRoutingRule.id == rule_id)
            .first()
        )
        if not rule:
            raise RoutingRuleNotFoundError(rule_id)
        return rule

    def create_rule(self, data: RoutingRuleCreate) -> InboxRoutingRule:
        """Create a new routing rule.

        Args:
            data: Rule creation data.

        Returns:
            Created InboxRoutingRule instance.

        Raises:
            ValidationError: If rule name already exists.
        """
        # Check for duplicate name
        existing = (
            self.db.query(InboxRoutingRule)
            .filter(InboxRoutingRule.name == data.name)
            .first()
        )
        if existing:
            raise ValidationError(f"Rule with name '{data.name}' already exists")

        rule = InboxRoutingRule(
            name=data.name,
            description=data.description,
            conditions=data.conditions,
            action_type=data.action_type,
            action_value=data.action_value,
            action_config=data.action_config if data.action_config else None,
            priority=data.priority,
            is_active=data.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def update_rule(
        self,
        rule_id: int,
        data: RoutingRuleUpdate,
    ) -> InboxRoutingRule:
        """Update a routing rule.

        Args:
            rule_id: The rule ID.
            data: Update data.

        Returns:
            Updated InboxRoutingRule instance.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
            ValidationError: If new name conflicts.
        """
        rule = self.get_rule(rule_id)

        if data.name is not None and data.name != rule.name:
            existing = (
                self.db.query(InboxRoutingRule)
                .filter(InboxRoutingRule.name == data.name, InboxRoutingRule.id != rule_id)
                .first()
            )
            if existing:
                raise ValidationError(f"Rule with name '{data.name}' already exists")
            rule.name = data.name

        if data.description is not None:
            rule.description = data.description

        if data.conditions is not None:
            rule.conditions = data.conditions

        if data.action_type is not None:
            rule.action_type = data.action_type

        if data.action_value is not None:
            rule.action_value = data.action_value

        if data.action_config is not None:
            rule.action_config = data.action_config if data.action_config else None

        if data.priority is not None:
            rule.priority = data.priority

        if data.is_active is not None:
            rule.is_active = data.is_active

        rule.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a routing rule.

        Args:
            rule_id: The rule ID.

        Returns:
            True if deleted.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
        """
        rule = self.get_rule(rule_id)
        self.db.delete(rule)
        self.db.flush()
        return True

    def activate_rule(self, rule_id: int) -> InboxRoutingRule:
        """Activate a routing rule.

        Args:
            rule_id: The rule ID.

        Returns:
            Updated InboxRoutingRule instance.
        """
        rule = self.get_rule(rule_id)
        rule.is_active = True
        rule.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return rule

    def deactivate_rule(self, rule_id: int) -> InboxRoutingRule:
        """Deactivate a routing rule.

        Args:
            rule_id: The rule ID.

        Returns:
            Updated InboxRoutingRule instance.
        """
        rule = self.get_rule(rule_id)
        rule.is_active = False
        rule.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return rule

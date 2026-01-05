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
from app.models.ticket import Ticket, TicketStatus
from app.models.agent import Team, TeamMember
from app.models.party import Party, PartyRole
from app.models.support_sla import RoutingRule, RoutingRoundRobinState, RoutingStrategy
from app.models.unified_ticket import UnifiedTicket, TicketStatus as UnifiedTicketStatus

from .types import (
    RoutingMatch,
    RoutingRuleCreate,
    RoutingRuleUpdate,
    TicketRoutingRuleCreate,
    TicketRoutingRuleUpdate,
    AgentWorkload,
    QueueHealth,
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

    def auto_assign_ticket(self, ticket: Ticket) -> Optional[Party]:
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
    ) -> Optional[Party]:
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

    def _execute_assignment(self, match: RoutingMatch) -> Optional[Party]:
        """Execute the assignment from a routing match."""
        if match.action_type == "assign_agent":
            if match.action_value:
                agent_id = int(match.action_value)
                agent = (
                    self.db.query(Party)
                    .join(PartyRole, Party.id == PartyRole.party_id)
                    .filter(Party.id == agent_id, PartyRole.role == "support_agent")
                    .first()
                )
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

    def select_agent_round_robin(self, team_id: int) -> Optional[Party]:
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

        agent_ids = [m.party_id for m in members if m.party_id]
        if not agent_ids:
            return None

        # Get agents with conversation counts
        agents_with_counts = (
            self.db.query(
                Party,
                func.count(OmniConversation.id).label("conv_count"),
            )
            .outerjoin(
                OmniConversation,
                (OmniConversation.assigned_party_id == Party.id)
                & (OmniConversation.status.in_(["open", "pending"])),
            )
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                Party.id.in_(agent_ids),
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
            )
            .group_by(Party.id)
            .order_by(func.count(OmniConversation.id).asc())
            .first()
        )

        if agents_with_counts:
            return agents_with_counts[0]

        # Fallback: just get first active agent
        return (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                Party.id.in_(agent_ids),
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
            )
            .first()
        )

    def select_agent_load_balanced(self, team_id: int) -> Optional[Party]:
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

    # -------------------------------------------------------------------------
    # Ticket Routing Rules (RoutingRule model from support_sla)
    # -------------------------------------------------------------------------

    def list_ticket_routing_rules(
        self,
        team_id: Optional[int] = None,
        active_only: bool = False,
    ) -> List[RoutingRule]:
        """List ticket routing rules.

        Args:
            team_id: Filter by team.
            active_only: Only return active rules.

        Returns:
            List of RoutingRule instances.
        """
        query = self.db.query(RoutingRule)

        if team_id:
            query = query.filter(RoutingRule.team_id == team_id)
        if active_only:
            query = query.filter(RoutingRule.is_active == True)

        return query.order_by(RoutingRule.priority, RoutingRule.name).all()

    def get_ticket_routing_rule(self, rule_id: int) -> RoutingRule:
        """Get a ticket routing rule by ID.

        Args:
            rule_id: The rule ID.

        Returns:
            RoutingRule instance.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
        """
        rule = (
            self.db.query(RoutingRule)
            .filter(RoutingRule.id == rule_id)
            .first()
        )
        if not rule:
            raise RoutingRuleNotFoundError(rule_id)
        return rule

    def create_ticket_routing_rule(
        self,
        data: TicketRoutingRuleCreate,
    ) -> RoutingRule:
        """Create a new ticket routing rule.

        Args:
            data: Rule creation data.

        Returns:
            Created RoutingRule instance.

        Raises:
            ValidationError: If team_id or fallback_team_id is invalid.
        """
        # Validate team_id if provided
        if data.team_id:
            team = self.db.query(Team).filter(Team.id == data.team_id).first()
            if not team:
                raise ValidationError(f"Invalid team_id: {data.team_id}")

        # Validate fallback_team_id if provided
        if data.fallback_team_id:
            fallback = self.db.query(Team).filter(Team.id == data.fallback_team_id).first()
            if not fallback:
                raise ValidationError(f"Invalid fallback_team_id: {data.fallback_team_id}")

        # Validate strategy
        valid_strategies = {s.value for s in RoutingStrategy}
        if data.strategy not in valid_strategies:
            raise ValidationError(f"Invalid strategy: {data.strategy}")

        rule = RoutingRule(
            name=data.name,
            description=data.description,
            team_id=data.team_id,
            strategy=data.strategy,
            conditions=data.conditions,
            priority=data.priority,
            is_active=data.is_active,
            fallback_team_id=data.fallback_team_id,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def update_ticket_routing_rule(
        self,
        rule_id: int,
        data: TicketRoutingRuleUpdate,
    ) -> RoutingRule:
        """Update a ticket routing rule.

        Args:
            rule_id: The rule ID.
            data: Update data.

        Returns:
            Updated RoutingRule instance.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
            ValidationError: If team_id or fallback_team_id is invalid.
        """
        rule = self.get_ticket_routing_rule(rule_id)

        if data.name is not None:
            rule.name = data.name
        if data.description is not None:
            rule.description = data.description
        if data.team_id is not None:
            if data.team_id:
                team = self.db.query(Team).filter(Team.id == data.team_id).first()
                if not team:
                    raise ValidationError(f"Invalid team_id: {data.team_id}")
            rule.team_id = data.team_id
        if data.strategy is not None:
            valid_strategies = {s.value for s in RoutingStrategy}
            if data.strategy not in valid_strategies:
                raise ValidationError(f"Invalid strategy: {data.strategy}")
            rule.strategy = data.strategy
        if data.conditions is not None:
            rule.conditions = data.conditions
        if data.priority is not None:
            rule.priority = data.priority
        if data.is_active is not None:
            rule.is_active = data.is_active
        if data.fallback_team_id is not None:
            if data.fallback_team_id:
                fallback = self.db.query(Team).filter(Team.id == data.fallback_team_id).first()
                if not fallback:
                    raise ValidationError(f"Invalid fallback_team_id: {data.fallback_team_id}")
            rule.fallback_team_id = data.fallback_team_id

        self.db.flush()
        return rule

    def delete_ticket_routing_rule(self, rule_id: int) -> bool:
        """Delete a ticket routing rule.

        Args:
            rule_id: The rule ID.

        Returns:
            True if deleted.

        Raises:
            RoutingRuleNotFoundError: If rule not found.
        """
        rule = self.get_ticket_routing_rule(rule_id)
        self.db.delete(rule)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Ticket Auto-Assignment
    # -------------------------------------------------------------------------

    def auto_assign_ticket_by_rules(self, ticket_id: int) -> Dict[str, Any]:
        """Auto-assign a ticket based on routing rules.

        Args:
            ticket_id: The ticket ID.

        Returns:
            Assignment result dict.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise ValidationError(f"Ticket not found: {ticket_id}")

        if ticket.assigned_to:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "Ticket is already assigned",
                "current_assignee": ticket.assigned_to,
            }

        # Find matching routing rule
        rules = self.list_ticket_routing_rules(active_only=True)

        matched_rule = None
        for rule in rules:
            if self._evaluate_ticket_conditions(rule.conditions, ticket):
                matched_rule = rule
                break

        if not matched_rule:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "No matching routing rule found",
            }

        if matched_rule.strategy == RoutingStrategy.MANUAL.value:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "Routing rule uses manual strategy",
                "rule_id": matched_rule.id,
                "rule_name": matched_rule.name,
            }

        # Get team members
        team_id = matched_rule.team_id
        if not team_id:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "Routing rule has no team configured",
                "rule_id": matched_rule.id,
            }

        agents = self._get_available_agents_for_team(team_id)

        # Try fallback team if no agents
        if not agents and matched_rule.fallback_team_id:
            agents = self._get_available_agents_for_team(matched_rule.fallback_team_id)
            team_id = matched_rule.fallback_team_id

        if not agents:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "No available agents in team",
                "rule_id": matched_rule.id,
            }

        # Select agent based on strategy
        selected_agent = self._select_agent_by_strategy(
            matched_rule.strategy, team_id, agents, ticket
        )

        if not selected_agent:
            return {
                "ticket_id": ticket.id,
                "assigned": False,
                "message": "Could not select an agent",
                "rule_id": matched_rule.id,
            }

        # Assign the ticket
        ticket.assigned_to = selected_agent.display_name or selected_agent.primary_email
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if team:
            ticket.resolution_team = team.name
        ticket.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return {
            "ticket_id": ticket.id,
            "assigned": True,
            "agent_id": selected_agent.id,
            "agent_name": selected_agent.display_name,
            "team_id": team_id,
            "rule_id": matched_rule.id,
            "rule_name": matched_rule.name,
            "strategy": matched_rule.strategy,
        }

    def _evaluate_ticket_conditions(
        self,
        conditions: Optional[List[Dict[str, Any]]],
        ticket: Ticket,
    ) -> bool:
        """Evaluate if ticket matches routing conditions."""
        if not conditions:
            return True  # No conditions = match all

        from enum import Enum as EnumType

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "")
            value = condition.get("value")

            ticket_value = getattr(ticket, field, None)
            if isinstance(ticket_value, EnumType):
                ticket_value = ticket_value.value

            if operator == "equals":
                if str(ticket_value) != str(value):
                    return False
            elif operator == "not_equals":
                if str(ticket_value) == str(value):
                    return False
            elif operator == "contains":
                if str(value) not in str(ticket_value or ""):
                    return False
            elif operator == "in_list":
                val_list = value if isinstance(value, list) else [value]
                if str(ticket_value) not in [str(v) for v in val_list]:
                    return False
            elif operator == "is_empty":
                if ticket_value is not None and ticket_value != "":
                    return False
            elif operator == "is_not_empty":
                if ticket_value is None or ticket_value == "":
                    return False

        return True

    def _get_available_agents_for_team(self, team_id: int) -> List[Party]:
        """Get active agents for a team."""
        members = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.is_active == True
        ).all()

        if not members:
            return []

        agent_ids = [m.party_id for m in members]
        return (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                Party.id.in_(agent_ids),
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
            )
            .all()
        )

    def _select_agent_by_strategy(
        self,
        strategy: str,
        team_id: int,
        agents: List[Party],
        ticket: Ticket,
    ) -> Optional[Party]:
        """Select agent based on routing strategy."""
        if strategy == RoutingStrategy.ROUND_ROBIN.value:
            return self._ticket_round_robin_select(team_id, agents)
        elif strategy == RoutingStrategy.LEAST_BUSY.value:
            return self._ticket_least_busy_select(agents)
        elif strategy == RoutingStrategy.SKILL_BASED.value:
            return self._ticket_skill_based_select(ticket, agents)
        elif strategy == RoutingStrategy.LOAD_BALANCED.value:
            return self._ticket_load_balanced_select(agents)
        else:
            return agents[0] if agents else None

    def _ticket_round_robin_select(
        self,
        team_id: int,
        agents: List[Party],
    ) -> Optional[Party]:
        """Select next agent in round-robin rotation."""
        state = self.db.query(RoutingRoundRobinState).filter(
            RoutingRoundRobinState.team_id == team_id
        ).first()

        agent_ids = [a.id for a in agents]

        if not state:
            selected = agents[0]
            state = RoutingRoundRobinState(team_id=team_id, last_party_id=selected.id)
            self.db.add(state)
            self.db.flush()
            return selected

        if state.last_party_id is None:
            next_idx = 0
        else:
            try:
                last_idx = agent_ids.index(state.last_party_id)
                next_idx = (last_idx + 1) % len(agents)
            except ValueError:
                next_idx = 0

        selected = agents[next_idx]
        state.last_party_id = selected.id
        self.db.flush()
        return selected

    def _ticket_least_busy_select(self, agents: List[Party]) -> Optional[Party]:
        """Select agent with fewest open tickets."""
        ticket_counts = {}
        for agent in agents:
            name = agent.display_name or agent.primary_email
            count = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
            ).scalar() or 0
            ticket_counts[agent.id] = count

        min_count = min(ticket_counts.values())
        for agent in agents:
            if ticket_counts[agent.id] == min_count:
                return agent

        return agents[0] if agents else None

    def _ticket_skill_based_select(
        self,
        ticket: Ticket,
        agents: List[Party],
    ) -> Optional[Party]:
        """Select agent based on skill matching."""
        ticket_type = ticket.ticket_type or ""
        issue_type = ticket.issue_type or ""

        best_match = None
        best_score = -1

        for agent in agents:
            score = 0
            skills = agent.agent_skills
            domains = agent.agent_domains

            if ticket_type.lower() in [k.lower() for k in skills.keys()]:
                score += 2
            if ticket_type.lower() in [k.lower() for k in domains.keys()]:
                score += 1
            if issue_type.lower() in [k.lower() for k in skills.keys()]:
                score += 2

            if score > best_score:
                best_score = score
                best_match = agent

        return best_match or (agents[0] if agents else None)

    def _ticket_load_balanced_select(self, agents: List[Party]) -> Optional[Party]:
        """Select agent based on capacity utilization."""
        best_agent = None
        lowest_utilization = float('inf')

        for agent in agents:
            capacity = agent.agent_capacity
            name = agent.display_name or agent.primary_email

            current_load = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
            ).scalar() or 0

            utilization = current_load / capacity if capacity > 0 else float('inf')

            if utilization < lowest_utilization:
                lowest_utilization = utilization
                best_agent = agent

        return best_agent

    # -------------------------------------------------------------------------
    # Workload & Metrics
    # -------------------------------------------------------------------------

    def get_agent_workloads(
        self,
        team_id: Optional[int] = None,
    ) -> List[AgentWorkload]:
        """Get workload for all agents.

        Args:
            team_id: Filter by team.

        Returns:
            List of AgentWorkload instances.
        """
        query = (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == "support_agent", PartyRole.status == "active")
        )

        if team_id:
            member_agent_ids = self.db.query(TeamMember.party_id).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True
            ).all()
            agent_ids = [m[0] for m in member_agent_ids]
            query = query.filter(Party.id.in_(agent_ids))

        agents = query.all()

        result = []
        for agent in agents:
            name = agent.display_name or agent.primary_email
            open_tickets = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
            ).scalar() or 0

            capacity = agent.agent_capacity
            utilization = (open_tickets / capacity * 100) if capacity > 0 else 0

            result.append(AgentWorkload(
                agent_id=agent.id,
                agent_name=name,
                open_tickets=open_tickets,
                capacity=capacity,
                utilization_pct=round(utilization, 1),
            ))

        return result

    def get_unified_agent_workloads(
        self,
        team_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get workload stats for agents based on UnifiedTicket assignments."""
        query = (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == "support_agent", PartyRole.status == "active")
        )

        if team_id:
            member_agent_ids = self.db.query(TeamMember.party_id).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True,
            ).all()
            agent_ids = [m[0] for m in member_agent_ids]
            query = query.filter(Party.id.in_(agent_ids))

        agents = query.all()

        open_statuses = [
            UnifiedTicketStatus.OPEN.value,
            UnifiedTicketStatus.IN_PROGRESS.value,
            UnifiedTicketStatus.WAITING.value,
            UnifiedTicketStatus.ON_HOLD.value,
            UnifiedTicketStatus.REOPENED.value,
        ]

        workloads: list[dict[str, Any]] = []
        for agent in agents:
            # agents are now Party objects with support_agent role
            capacity = agent.agent_capacity
            open_count = self.db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.assigned_to_party_id == agent.id,
                UnifiedTicket.status.in_(open_statuses),
            ).scalar() or 0

            utilization = round(open_count / capacity * 100, 1) if capacity > 0 else 0
            workloads.append({
                "id": agent.id,
                "name": agent.display_name,
                "email": agent.primary_email,
                "capacity": capacity,
                "load": open_count,
                "utilization": utilization,
                "available": max(0, capacity - open_count),
            })

        workloads.sort(key=lambda x: -float(x.get("utilization") or 0))
        return workloads

    def get_ticket_queue_health(self) -> Dict[str, Any]:
        """Get queue health metrics based on UnifiedTicket."""
        open_statuses = [
            UnifiedTicketStatus.OPEN.value,
            UnifiedTicketStatus.IN_PROGRESS.value,
            UnifiedTicketStatus.WAITING.value,
            UnifiedTicketStatus.ON_HOLD.value,
            UnifiedTicketStatus.REOPENED.value,
        ]

        unassigned = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.assigned_to_party_id.is_(None),
            UnifiedTicket.status.in_(open_statuses),
        ).scalar() or 0

        total_open = self.db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.in_(open_statuses),
        ).scalar() or 0

        # Get active support agents (Party with support_agent role)
        agents = (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(
                PartyRole.role == "support_agent",
                PartyRole.status == "active",
                PartyRole.until.is_(None),
            )
            .all()
        )
        total_capacity = sum(float(a.agent_capacity if hasattr(a, 'agent_capacity') else 10) for a in agents)

        total_load = 0.0
        for agent in agents:
            total_load += self.db.query(func.count(UnifiedTicket.id)).filter(
                UnifiedTicket.is_deleted == False,
                UnifiedTicket.assigned_to_party_id == agent.id,
                UnifiedTicket.status.in_(open_statuses),
            ).scalar() or 0

        utilization = round(total_load / total_capacity * 100, 1) if total_capacity > 0 else 0

        return {
            "unassigned": unassigned,
            "total_open": total_open,
            "total_agents": len(agents),
            "total_capacity": total_capacity,
            "total_load": total_load,
            "utilization": utilization,
        }

    def get_queue_health(self) -> QueueHealth:
        """Get queue health metrics.

        Returns:
            QueueHealth instance.
        """
        from datetime import timedelta

        # Total open tickets
        total_open = self.db.query(func.count(Ticket.id)).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
        ).scalar() or 0

        # By status
        status_counts = self.db.query(
            Ticket.status,
            func.count(Ticket.id)
        ).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
        ).group_by(Ticket.status).all()

        by_status = {
            str(s.value) if hasattr(s, 'value') else str(s): c
            for s, c in status_counts
        }

        # Average wait time (time since creation for unassigned tickets)
        now = datetime.now(timezone.utc)
        unassigned = self.db.query(Ticket).filter(
            Ticket.status == TicketStatus.OPEN,
            Ticket.assigned_to == None
        ).all()

        if unassigned:
            total_wait = sum(
                (now - t.created_at).total_seconds() / 60
                for t in unassigned if t.created_at
            )
            avg_wait = total_wait / len(unassigned)
        else:
            avg_wait = 0.0

        # Agent counts
        agents_active = (
            self.db.query(func.count(Party.id))
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == "support_agent", PartyRole.status == "active")
            .scalar()
            or 0
        )

        # Count agents at capacity
        agents_at_capacity = 0
        agents = (
            self.db.query(Party)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == "support_agent", PartyRole.status == "active")
            .all()
        )
        for agent in agents:
            name = agent.display_name or agent.primary_email
            capacity = agent.agent_capacity
            current = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED, TicketStatus.ON_HOLD])
            ).scalar() or 0
            if current >= capacity:
                agents_at_capacity += 1

        return QueueHealth(
            total_open=total_open,
            by_status=by_status,
            avg_wait_minutes=round(avg_wait, 1),
            agents_active=agents_active,
            agents_at_capacity=agents_at_capacity,
        )

    def rebalance_tickets(
        self,
        team_id: Optional[int] = None,
        max_per_agent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Rebalance tickets among agents.

        Args:
            team_id: Team to rebalance (optional).
            max_per_agent: Max tickets per agent.

        Returns:
            Rebalance result dict.
        """
        # Get workloads
        workloads = self.get_agent_workloads(team_id)

        if not workloads:
            return {"rebalanced": 0, "message": "No agents available"}

        # Find overloaded and underloaded agents
        max_cap = max_per_agent or 10
        overloaded = [w for w in workloads if w.open_tickets > max_cap]
        underloaded = [w for w in workloads if w.open_tickets < max_cap]

        if not overloaded or not underloaded:
            return {"rebalanced": 0, "message": "No rebalancing needed"}

        rebalanced = 0

        for over_agent in overloaded:
            excess = over_agent.open_tickets - max_cap

            # Get tickets to reassign
            tickets = self.db.query(Ticket).filter(
                Ticket.assigned_to == over_agent.agent_name,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
            ).order_by(Ticket.created_at.desc()).limit(excess).all()

            for ticket in tickets:
                # Find agent with capacity
                for under_agent in underloaded:
                    if under_agent.open_tickets < max_cap:
                        ticket.assigned_to = under_agent.agent_name
                        ticket.updated_at = datetime.now(timezone.utc)
                        under_agent.open_tickets += 1
                        rebalanced += 1
                        break

        self.db.flush()

        return {
            "rebalanced": rebalanced,
            "message": f"Rebalanced {rebalanced} tickets",
        }

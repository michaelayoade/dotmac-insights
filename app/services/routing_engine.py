"""Ticket routing and agent assignment service.

Handles automatic ticket assignment based on routing rules and strategies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.support_sla import RoutingRule, RoutingRoundRobinState, RoutingStrategy
from app.models.agent import Agent, Team, TeamMember
from app.models.ticket import Ticket, TicketStatus

logger = structlog.get_logger()


class RoutingEngine:
    """Service for automatic ticket routing and agent assignment."""

    def __init__(self, db: Session):
        self.db = db

    def auto_assign(self, ticket: Ticket) -> Dict[str, Any]:
        """Automatically assign a ticket to an agent.

        Finds the best matching routing rule and assigns an agent based on
        the rule's strategy.

        Args:
            ticket: Ticket to assign

        Returns:
            Dict with assignment results
        """
        if ticket.assigned_to:
            return {
                "assigned": False,
                "reason": "already_assigned",
                "current_assignee": ticket.assigned_to,
            }

        # Find matching routing rule
        rule = self.find_matching_rule(ticket)
        if not rule:
            logger.debug(
                "routing_no_rule_matched",
                ticket_id=ticket.id,
            )
            return {
                "assigned": False,
                "reason": "no_matching_rule",
            }

        if rule.strategy == RoutingStrategy.MANUAL.value:
            return {
                "assigned": False,
                "reason": "manual_strategy",
                "rule_id": rule.id,
                "rule_name": rule.name,
            }

        # Get available agents
        agents = self.get_available_agents(rule)
        if not agents:
            logger.warning(
                "routing_no_agents_available",
                ticket_id=ticket.id,
                rule_id=rule.id,
            )
            return {
                "assigned": False,
                "reason": "no_available_agents",
                "rule_id": rule.id,
            }

        # Select agent based on strategy
        selected = self.select_agent(ticket, agents, rule)
        if not selected:
            return {
                "assigned": False,
                "reason": "selection_failed",
                "rule_id": rule.id,
            }

        # Perform assignment
        ticket.assigned_to = selected.display_name or selected.email
        if rule.team_id:
            ticket.team_id = rule.team_id
        ticket.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            "ticket_auto_assigned",
            ticket_id=ticket.id,
            agent_id=selected.id,
            agent_name=selected.display_name,
            rule_id=rule.id,
            strategy=rule.strategy,
        )

        return {
            "assigned": True,
            "agent_id": selected.id,
            "agent_name": selected.display_name or selected.email,
            "team_id": rule.team_id,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "strategy": rule.strategy,
        }

    def find_matching_rule(self, ticket: Ticket) -> Optional[RoutingRule]:
        """Find the routing rule that matches a ticket.

        Rules are evaluated in priority order (lower = higher priority).

        Args:
            ticket: Ticket to match

        Returns:
            Matching routing rule or None
        """
        rules = self.db.query(RoutingRule).filter(
            RoutingRule.is_active == True
        ).order_by(RoutingRule.priority).all()

        for rule in rules:
            if self._evaluate_conditions(rule.conditions, ticket):
                logger.debug(
                    "routing_rule_matched",
                    ticket_id=ticket.id,
                    rule_id=rule.id,
                    rule_name=rule.name,
                )
                return rule

        return None

    def _evaluate_conditions(
        self,
        conditions: Optional[List[dict]],
        ticket: Ticket,
    ) -> bool:
        """Evaluate if ticket matches rule conditions."""
        if not conditions:
            return True  # No conditions = catch-all

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "")
            value = condition.get("value")

            ticket_value = getattr(ticket, field, None)
            if hasattr(ticket_value, "value"):
                ticket_value = ticket_value.value

            if not self._check_condition(ticket_value, operator, value):
                return False

        return True

    def _check_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        """Check a single condition."""
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
        elif operator == "starts_with":
            return str(actual or "").startswith(str(expected))
        elif operator == "ends_with":
            return str(actual or "").endswith(str(expected))
        return False

    def get_available_agents(self, rule: RoutingRule) -> List[Agent]:
        """Get list of available agents for a routing rule.

        Tries the rule's team first, then fallback team if configured.

        Args:
            rule: Routing rule

        Returns:
            List of available agents
        """
        team_id = rule.team_id

        if team_id:
            agents = self._get_team_agents(team_id)
            if agents:
                return agents

        # Try fallback team
        if rule.fallback_team_id:
            agents = self._get_team_agents(rule.fallback_team_id)
            if agents:
                return agents

        return []

    def _get_team_agents(self, team_id: int) -> List[Agent]:
        """Get active agents for a team."""
        members = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.is_active == True
        ).all()

        if not members:
            return []

        agent_ids = [m.agent_id for m in members]
        agents = self.db.query(Agent).filter(
            Agent.id.in_(agent_ids),
            Agent.is_active == True
        ).all()

        return agents

    def select_agent(
        self,
        ticket: Ticket,
        agents: List[Agent],
        rule: RoutingRule,
    ) -> Optional[Agent]:
        """Select the best agent based on routing strategy.

        Args:
            ticket: Ticket being assigned
            agents: Available agents
            rule: Routing rule with strategy

        Returns:
            Selected agent or None
        """
        strategy = rule.strategy

        if strategy == RoutingStrategy.ROUND_ROBIN.value:
            return self._round_robin(rule.team_id or 0, agents)
        elif strategy == RoutingStrategy.LEAST_BUSY.value:
            return self._least_busy(agents)
        elif strategy == RoutingStrategy.SKILL_BASED.value:
            return self._skill_based(ticket, agents)
        elif strategy == RoutingStrategy.LOAD_BALANCED.value:
            return self._load_balanced(agents)
        else:
            # Default to first available
            return agents[0] if agents else None

    def _round_robin(self, team_id: int, agents: List[Agent]) -> Optional[Agent]:
        """Round-robin agent selection."""
        if not agents:
            return None

        state = self.db.query(RoutingRoundRobinState).filter(
            RoutingRoundRobinState.team_id == team_id
        ).first()

        agent_ids = [a.id for a in agents]

        if not state:
            # First assignment
            selected = agents[0]
            state = RoutingRoundRobinState(
                team_id=team_id,
                last_agent_id=selected.id
            )
            self.db.add(state)
            self.db.commit()
            return selected

        # Find next agent in rotation
        try:
            last_idx = agent_ids.index(state.last_agent_id)
            next_idx = (last_idx + 1) % len(agents)
        except ValueError:
            next_idx = 0

        selected = agents[next_idx]
        state.last_agent_id = selected.id
        self.db.commit()

        return selected

    def _least_busy(self, agents: List[Agent]) -> Optional[Agent]:
        """Select agent with fewest open tickets."""
        if not agents:
            return None

        ticket_counts = {}
        for agent in agents:
            name = agent.display_name or agent.email
            count = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.PENDING
                ])
            ).scalar() or 0
            ticket_counts[agent.id] = count

        # Find minimum
        min_count = min(ticket_counts.values())
        for agent in agents:
            if ticket_counts[agent.id] == min_count:
                return agent

        return agents[0]

    def _skill_based(self, ticket: Ticket, agents: List[Agent]) -> Optional[Agent]:
        """Select agent based on skill matching."""
        if not agents:
            return None

        ticket_type = (ticket.ticket_type or "").lower()
        issue_type = (ticket.issue_type or "").lower()
        region = (ticket.region or "").lower()

        best_match = None
        best_score = -1

        for agent in agents:
            score = 0
            skills = agent.skills or {}
            domains = agent.domains or {}

            # Match ticket type
            if ticket_type:
                if ticket_type in [k.lower() for k in skills.keys()]:
                    score += 3
                if ticket_type in [k.lower() for k in domains.keys()]:
                    score += 2

            # Match issue type
            if issue_type:
                if issue_type in [k.lower() for k in skills.keys()]:
                    score += 2

            # Match region (if agent has region in domains)
            if region:
                if region in [k.lower() for k in domains.keys()]:
                    score += 1

            # Consider routing weight
            score += agent.routing_weight * 0.1

            if score > best_score:
                best_score = score
                best_match = agent

        return best_match or agents[0]

    def _load_balanced(self, agents: List[Agent]) -> Optional[Agent]:
        """Select agent based on capacity utilization."""
        if not agents:
            return None

        best_agent = None
        lowest_utilization = float('inf')

        for agent in agents:
            capacity = agent.capacity or 10
            name = agent.display_name or agent.email

            current_load = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.PENDING
                ])
            ).scalar() or 0

            utilization = current_load / capacity if capacity > 0 else float('inf')

            # Skip if at or over capacity
            if utilization >= 1.0:
                continue

            if utilization < lowest_utilization:
                lowest_utilization = utilization
                best_agent = agent

        return best_agent

    def get_workload_summary(self, team_id: Optional[int] = None) -> Dict[str, Any]:
        """Get workload summary for agents.

        Args:
            team_id: Optional team filter

        Returns:
            Summary of agent workloads
        """
        query = self.db.query(Agent).filter(Agent.is_active == True)

        if team_id:
            member_ids = self.db.query(TeamMember.agent_id).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True
            ).all()
            agent_ids = [m[0] for m in member_ids]
            query = query.filter(Agent.id.in_(agent_ids))

        agents = query.all()

        total_capacity = 0
        total_load = 0
        agent_data = []

        for agent in agents:
            capacity = agent.capacity or 10
            name = agent.display_name or agent.email

            load = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.PENDING
                ])
            ).scalar() or 0

            total_capacity += capacity
            total_load += load

            agent_data.append({
                "agent_id": agent.id,
                "agent_name": agent.display_name,
                "email": agent.email,
                "capacity": capacity,
                "current_load": load,
                "utilization_pct": round(load / capacity * 100, 1) if capacity > 0 else 0,
                "available": load < capacity,
            })

        return {
            "total_agents": len(agents),
            "total_capacity": total_capacity,
            "total_load": total_load,
            "overall_utilization_pct": round(total_load / total_capacity * 100, 1) if total_capacity > 0 else 0,
            "agents": sorted(agent_data, key=lambda x: x["utilization_pct"]),
        }

    def rebalance_workload(
        self,
        team_id: Optional[int] = None,
        max_per_agent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Rebalance tickets across agents.

        Moves tickets from overloaded agents to underloaded ones.

        Args:
            team_id: Optional team filter
            max_per_agent: Maximum tickets per agent

        Returns:
            Summary of rebalancing performed
        """
        # Get agents
        query = self.db.query(Agent).filter(Agent.is_active == True)

        if team_id:
            member_ids = self.db.query(TeamMember.agent_id).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True
            ).all()
            agent_ids = [m[0] for m in member_ids]
            query = query.filter(Agent.id.in_(agent_ids))

        agents = query.all()

        if len(agents) < 2:
            return {
                "rebalanced": 0,
                "message": "Need at least 2 agents to rebalance",
            }

        # Calculate current workloads
        workloads = {}
        for agent in agents:
            name = agent.display_name or agent.email
            capacity = agent.capacity or 10

            load = self.db.query(func.count(Ticket.id)).filter(
                Ticket.assigned_to == name,
                Ticket.status.in_([
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.PENDING
                ])
            ).scalar() or 0

            workloads[agent.id] = {
                "agent": agent,
                "name": name,
                "capacity": capacity,
                "load": load,
                "utilization": load / capacity if capacity > 0 else float('inf'),
            }

        # Calculate target utilization
        total_load = sum(w["load"] for w in workloads.values())
        total_capacity = sum(w["capacity"] for w in workloads.values())
        avg_utilization = total_load / total_capacity if total_capacity > 0 else 0

        rebalanced = 0
        moves = []

        # Find overloaded agents and move tickets
        for agent_id, data in sorted(
            workloads.items(),
            key=lambda x: -x[1]["utilization"]
        ):
            # Only rebalance if significantly overloaded
            if data["utilization"] <= avg_utilization + 0.15:
                continue

            # Calculate how many to move
            target_load = int(data["capacity"] * avg_utilization)
            tickets_to_move = data["load"] - max(target_load, 1)

            if tickets_to_move <= 0:
                continue

            # Get moveable tickets (only OPEN status, oldest first)
            tickets = self.db.query(Ticket).filter(
                Ticket.assigned_to == data["name"],
                Ticket.status == TicketStatus.OPEN
            ).order_by(Ticket.created_at).limit(tickets_to_move).all()

            for ticket in tickets:
                # Find best underloaded agent
                target_agent = None
                lowest_util = float('inf')

                for tid, tdata in workloads.items():
                    if tid == agent_id:
                        continue
                    if tdata["utilization"] >= avg_utilization:
                        continue
                    if max_per_agent and tdata["load"] >= max_per_agent:
                        continue
                    if tdata["load"] >= tdata["capacity"]:
                        continue

                    if tdata["utilization"] < lowest_util:
                        lowest_util = tdata["utilization"]
                        target_agent = tdata

                if target_agent:
                    # Move ticket
                    old_assignee = ticket.assigned_to
                    ticket.assigned_to = target_agent["name"]
                    ticket.updated_at = datetime.utcnow()

                    # Update workload tracking
                    target_agent["load"] += 1
                    target_agent["utilization"] = (
                        target_agent["load"] / target_agent["capacity"]
                        if target_agent["capacity"] > 0 else float('inf')
                    )
                    data["load"] -= 1
                    data["utilization"] = (
                        data["load"] / data["capacity"]
                        if data["capacity"] > 0 else 0
                    )

                    moves.append({
                        "ticket_id": ticket.id,
                        "from": old_assignee,
                        "to": target_agent["name"],
                    })
                    rebalanced += 1

        self.db.commit()

        logger.info(
            "workload_rebalanced",
            rebalanced=rebalanced,
            moves=moves,
        )

        return {
            "rebalanced": rebalanced,
            "moves": moves,
            "message": f"Rebalanced {rebalanced} tickets",
        }

    def find_unassigned_tickets(self, limit: int = 100) -> List[Ticket]:
        """Find unassigned open tickets.

        Args:
            limit: Maximum tickets to return

        Returns:
            List of unassigned tickets
        """
        return self.db.query(Ticket).filter(
            Ticket.assigned_to.is_(None),
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
        ).order_by(Ticket.created_at).limit(limit).all()

    def auto_assign_batch(self, limit: int = 50) -> Dict[str, Any]:
        """Auto-assign multiple unassigned tickets.

        Args:
            limit: Maximum tickets to process

        Returns:
            Summary of assignments made
        """
        tickets = self.find_unassigned_tickets(limit)

        results = {
            "processed": len(tickets),
            "assigned": 0,
            "failed": 0,
            "details": [],
        }

        for ticket in tickets:
            result = self.auto_assign(ticket)
            if result.get("assigned"):
                results["assigned"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "ticket_id": ticket.id,
                **result,
            })

        logger.info(
            "batch_auto_assign_completed",
            processed=results["processed"],
            assigned=results["assigned"],
            failed=results["failed"],
        )

        return results

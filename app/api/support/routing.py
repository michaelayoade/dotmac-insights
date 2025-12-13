"""Routing configuration and auto-assignment endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.support_sla import RoutingRule, RoutingRoundRobinState, RoutingStrategy
from app.models.agent import Agent, Team, TeamMember
from app.models.ticket import Ticket, TicketStatus
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RoutingRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    team_id: Optional[int] = None
    strategy: str = RoutingStrategy.ROUND_ROBIN.value
    conditions: Optional[List[dict]] = None
    priority: int = 100
    is_active: bool = True
    fallback_team_id: Optional[int] = None


class RoutingRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    strategy: Optional[str] = None
    conditions: Optional[List[dict]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    fallback_team_id: Optional[int] = None


class AutoAssignRequest(BaseModel):
    ticket_id: int


class RebalanceRequest(BaseModel):
    team_id: Optional[int] = None
    max_per_agent: Optional[int] = None


# =============================================================================
# REFERENCE DATA
# =============================================================================

@router.get("/strategies", dependencies=[Depends(Require("support:read"))])
def list_strategies() -> List[Dict[str, str]]:
    """List available routing strategies."""
    descriptions = {
        RoutingStrategy.ROUND_ROBIN: "Assign to agents in rotation",
        RoutingStrategy.LEAST_BUSY: "Assign to agent with fewest open tickets",
        RoutingStrategy.SKILL_BASED: "Match ticket type to agent skills",
        RoutingStrategy.LOAD_BALANCED: "Balance based on agent capacity percentage",
        RoutingStrategy.MANUAL: "No automatic assignment",
    }
    return [
        {
            "value": s.value,
            "label": s.value.replace("_", " ").title(),
            "description": descriptions.get(s, ""),
        }
        for s in RoutingStrategy
    ]


# =============================================================================
# ROUTING RULES
# =============================================================================

@router.get("/rules", dependencies=[Depends(Require("support:read"))])
def list_rules(
    team_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List routing rules."""
    query = db.query(RoutingRule)

    if team_id:
        query = query.filter(RoutingRule.team_id == team_id)
    if active_only:
        query = query.filter(RoutingRule.is_active == True)

    rules = query.order_by(RoutingRule.priority, RoutingRule.name).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "team_id": r.team_id,
            "team_name": r.team.name if r.team else None,
            "strategy": r.strategy,
            "conditions": r.conditions,
            "priority": r.priority,
            "is_active": r.is_active,
            "fallback_team_id": r.fallback_team_id,
            "fallback_team_name": r.fallback_team.name if r.fallback_team else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("/rules", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_rule(
    payload: RoutingRuleCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a routing rule."""
    # Validate strategy
    try:
        RoutingStrategy(payload.strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {payload.strategy}")

    # Validate team_id if provided
    if payload.team_id:
        team = db.query(Team).filter(Team.id == payload.team_id).first()
        if not team:
            raise HTTPException(status_code=400, detail="Invalid team_id")

    # Validate fallback_team_id if provided
    if payload.fallback_team_id:
        fallback = db.query(Team).filter(Team.id == payload.fallback_team_id).first()
        if not fallback:
            raise HTTPException(status_code=400, detail="Invalid fallback_team_id")

    rule = RoutingRule(
        name=payload.name,
        description=payload.description,
        team_id=payload.team_id,
        strategy=payload.strategy,
        conditions=payload.conditions,
        priority=payload.priority,
        is_active=payload.is_active,
        fallback_team_id=payload.fallback_team_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.get("/rules/{rule_id}", dependencies=[Depends(Require("support:read"))])
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get routing rule details."""
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "team_id": rule.team_id,
        "team_name": rule.team.name if rule.team else None,
        "strategy": rule.strategy,
        "conditions": rule.conditions,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "fallback_team_id": rule.fallback_team_id,
        "fallback_team_name": rule.fallback_team.name if rule.fallback_team else None,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.patch("/rules/{rule_id}", dependencies=[Depends(Require("support:write"))])
def update_rule(
    rule_id: int,
    payload: RoutingRuleUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a routing rule."""
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.team_id is not None:
        if payload.team_id:
            team = db.query(Team).filter(Team.id == payload.team_id).first()
            if not team:
                raise HTTPException(status_code=400, detail="Invalid team_id")
        rule.team_id = payload.team_id
    if payload.strategy is not None:
        try:
            RoutingStrategy(payload.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid strategy: {payload.strategy}")
        rule.strategy = payload.strategy
    if payload.conditions is not None:
        rule.conditions = payload.conditions
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.fallback_team_id is not None:
        if payload.fallback_team_id:
            fallback = db.query(Team).filter(Team.id == payload.fallback_team_id).first()
            if not fallback:
                raise HTTPException(status_code=400, detail="Invalid fallback_team_id")
        rule.fallback_team_id = payload.fallback_team_id

    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.delete("/rules/{rule_id}", dependencies=[Depends(Require("support:write"))])
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a routing rule."""
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# AUTO-ASSIGNMENT
# =============================================================================

@router.post("/auto-assign", dependencies=[Depends(Require("support:write"))])
def auto_assign(
    payload: AutoAssignRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger auto-assignment for a ticket.

    Finds the best matching routing rule and assigns an agent based on
    the rule's strategy.
    """
    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.assigned_to:
        return {
            "ticket_id": ticket.id,
            "assigned": False,
            "message": "Ticket is already assigned",
            "current_assignee": ticket.assigned_to,
        }

    # Find matching routing rule
    rules = db.query(RoutingRule).filter(
        RoutingRule.is_active == True
    ).order_by(RoutingRule.priority).all()

    matched_rule = None
    for rule in rules:
        if _evaluate_routing_conditions(rule.conditions, ticket):
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

    members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_active == True
    ).all()

    if not members:
        # Try fallback team
        if matched_rule.fallback_team_id:
            members = db.query(TeamMember).filter(
                TeamMember.team_id == matched_rule.fallback_team_id,
                TeamMember.is_active == True
            ).all()
            team_id = matched_rule.fallback_team_id

    if not members:
        return {
            "ticket_id": ticket.id,
            "assigned": False,
            "message": "No available agents in team",
            "rule_id": matched_rule.id,
        }

    # Get active agents
    agent_ids = [m.agent_id for m in members]
    agents = db.query(Agent).filter(
        Agent.id.in_(agent_ids),
        Agent.is_active == True
    ).all()

    if not agents:
        return {
            "ticket_id": ticket.id,
            "assigned": False,
            "message": "No active agents available",
            "rule_id": matched_rule.id,
        }

    # Select agent based on strategy
    selected_agent = None

    if matched_rule.strategy == RoutingStrategy.ROUND_ROBIN.value:
        selected_agent = _round_robin_select(db, team_id, agents)
    elif matched_rule.strategy == RoutingStrategy.LEAST_BUSY.value:
        selected_agent = _least_busy_select(db, agents)
    elif matched_rule.strategy == RoutingStrategy.SKILL_BASED.value:
        selected_agent = _skill_based_select(ticket, agents)
    elif matched_rule.strategy == RoutingStrategy.LOAD_BALANCED.value:
        selected_agent = _load_balanced_select(db, agents)
    else:
        # Default to first available
        selected_agent = agents[0]

    if not selected_agent:
        return {
            "ticket_id": ticket.id,
            "assigned": False,
            "message": "Could not select an agent",
            "rule_id": matched_rule.id,
        }

    # Assign the ticket
    ticket.assigned_to = selected_agent.display_name or selected_agent.email
    ticket.team_id = team_id
    ticket.updated_at = datetime.utcnow()
    db.commit()

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


def _evaluate_routing_conditions(conditions: Optional[List[dict]], ticket: Ticket) -> bool:
    """Evaluate if ticket matches routing conditions."""
    if not conditions:
        return True  # No conditions = match all

    for condition in conditions:
        field = condition.get("field", "")
        operator = condition.get("operator", "")
        value = condition.get("value")

        ticket_value = getattr(ticket, field, None)
        if hasattr(ticket_value, "value"):
            ticket_value = ticket_value.value

        if operator == "equals":
            if str(ticket_value) != str(value):
                return False
        elif operator == "not_equals":
            if str(ticket_value) == str(value):
                return False
        elif operator == "contains":
            if value not in str(ticket_value or ""):
                return False
        elif operator == "in_list":
            val_list = value if isinstance(value, list) else [value]
            if str(ticket_value) not in val_list:
                return False
        elif operator == "is_empty":
            if ticket_value is not None and ticket_value != "":
                return False
        elif operator == "is_not_empty":
            if ticket_value is None or ticket_value == "":
                return False

    return True


def _round_robin_select(db: Session, team_id: int, agents: List[Agent]) -> Optional[Agent]:
    """Select next agent in round-robin rotation."""
    state = db.query(RoutingRoundRobinState).filter(
        RoutingRoundRobinState.team_id == team_id
    ).first()

    agent_ids = [a.id for a in agents]

    if not state:
        # First assignment - create state
        selected = agents[0]
        state = RoutingRoundRobinState(team_id=team_id, last_agent_id=selected.id)
        db.add(state)
        db.commit()
        return selected

    # Find next agent after last assigned
    try:
        last_idx = agent_ids.index(state.last_agent_id)
        next_idx = (last_idx + 1) % len(agents)
    except ValueError:
        next_idx = 0

    selected = agents[next_idx]
    state.last_agent_id = selected.id
    db.commit()
    return selected


def _least_busy_select(db: Session, agents: List[Agent]) -> Optional[Agent]:
    """Select agent with fewest open tickets."""
    agent_ids = [a.id for a in agents]

    # Count open tickets per agent (by assigned_to name matching)
    agent_names = {a.id: a.display_name or a.email for a in agents}

    ticket_counts = {}
    for agent in agents:
        name = agent.display_name or agent.email
        count = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
        ).scalar() or 0
        ticket_counts[agent.id] = count

    # Select agent with minimum tickets
    min_count = min(ticket_counts.values())
    for agent in agents:
        if ticket_counts[agent.id] == min_count:
            return agent

    return agents[0]


def _skill_based_select(ticket: Ticket, agents: List[Agent]) -> Optional[Agent]:
    """Select agent based on skill matching."""
    ticket_type = ticket.ticket_type or ""
    issue_type = ticket.issue_type or ""

    best_match = None
    best_score = -1

    for agent in agents:
        score = 0
        skills = agent.skills or {}
        domains = agent.domains or {}

        # Check ticket type in skills/domains
        if ticket_type.lower() in [k.lower() for k in skills.keys()]:
            score += 2
        if ticket_type.lower() in [k.lower() for k in domains.keys()]:
            score += 1
        if issue_type.lower() in [k.lower() for k in skills.keys()]:
            score += 2

        if score > best_score:
            best_score = score
            best_match = agent

    return best_match or agents[0]


def _load_balanced_select(db: Session, agents: List[Agent]) -> Optional[Agent]:
    """Select agent based on capacity utilization."""
    best_agent = None
    lowest_utilization = float('inf')

    for agent in agents:
        capacity = agent.capacity or 10  # Default capacity
        name = agent.display_name or agent.email

        current_load = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
        ).scalar() or 0

        utilization = current_load / capacity if capacity > 0 else float('inf')

        if utilization < lowest_utilization:
            lowest_utilization = utilization
            best_agent = agent

    return best_agent


# =============================================================================
# WORKLOAD & QUEUE METRICS
# =============================================================================

@router.get("/agent-workload", dependencies=[Depends(Require("support:read"))])
def get_agent_workload(
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get current workload for all agents."""
    query = db.query(Agent).filter(Agent.is_active == True)

    if team_id:
        member_agent_ids = db.query(TeamMember.agent_id).filter(
            TeamMember.team_id == team_id,
            TeamMember.is_active == True
        ).all()
        agent_ids = [m[0] for m in member_agent_ids]
        query = query.filter(Agent.id.in_(agent_ids))

    agents = query.all()

    result = []
    for agent in agents:
        name = agent.display_name or agent.email
        capacity = agent.capacity or 10

        open_count = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
        ).scalar() or 0

        result.append({
            "agent_id": agent.id,
            "agent_name": agent.display_name,
            "email": agent.email,
            "capacity": capacity,
            "current_load": open_count,
            "utilization_pct": round(open_count / capacity * 100, 1) if capacity > 0 else 0,
            "available_slots": max(0, capacity - open_count),
            "routing_weight": agent.routing_weight,
        })

    return sorted(result, key=lambda x: x["utilization_pct"])


@router.get("/queue-health", dependencies=[Depends(Require("analytics:read"))])
@cached("routing-queue-health", ttl=CACHE_TTL["short"])
async def get_queue_health(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get overall queue health metrics."""
    # Unassigned tickets
    unassigned = db.query(func.count(Ticket.id)).filter(
        Ticket.assigned_to.is_(None),
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    ).scalar() or 0

    # Open tickets by status
    by_status = db.query(
        Ticket.status,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
    ).group_by(Ticket.status).all()

    # Average wait time (unassigned tickets)
    from sqlalchemy import cast, Numeric
    avg_wait = db.query(
        func.avg(
            func.extract('epoch', func.now() - Ticket.created_at) / 3600
        )
    ).filter(
        Ticket.assigned_to.is_(None),
        Ticket.status == TicketStatus.OPEN
    ).scalar()

    # Agent utilization summary
    agents = db.query(Agent).filter(Agent.is_active == True).all()
    total_capacity = sum(a.capacity or 10 for a in agents)
    total_load = 0
    for agent in agents:
        name = agent.display_name or agent.email
        load = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
        ).scalar() or 0
        total_load += load

    return {
        "unassigned_tickets": unassigned,
        "by_status": {
            row.status.value if hasattr(row.status, 'value') else row.status: row.count
            for row in by_status
        },
        "avg_wait_hours": round(float(avg_wait or 0), 2),
        "total_agents": len(agents),
        "total_capacity": total_capacity,
        "total_load": total_load,
        "overall_utilization_pct": round(total_load / total_capacity * 100, 1) if total_capacity > 0 else 0,
    }


@router.post("/rebalance", dependencies=[Depends(Require("support:write"))])
def rebalance_tickets(
    payload: RebalanceRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Rebalance ticket assignments across agents.

    Moves tickets from overloaded agents to underloaded ones.
    """
    # Get agents and their workloads
    query = db.query(Agent).filter(Agent.is_active == True)

    if payload.team_id:
        member_agent_ids = db.query(TeamMember.agent_id).filter(
            TeamMember.team_id == payload.team_id,
            TeamMember.is_active == True
        ).all()
        agent_ids = [m[0] for m in member_agent_ids]
        query = query.filter(Agent.id.in_(agent_ids))

    agents = query.all()
    if len(agents) < 2:
        return {"rebalanced": 0, "message": "Need at least 2 agents to rebalance"}

    # Calculate workloads
    workloads = {}
    for agent in agents:
        name = agent.display_name or agent.email
        capacity = agent.capacity or 10
        load = db.query(func.count(Ticket.id)).filter(
            Ticket.assigned_to == name,
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
        ).scalar() or 0
        workloads[agent.id] = {
            "agent": agent,
            "name": name,
            "capacity": capacity,
            "load": load,
            "utilization": load / capacity if capacity > 0 else float('inf'),
        }

    # Find overloaded and underloaded agents
    avg_utilization = sum(w["utilization"] for w in workloads.values()) / len(workloads)
    max_per_agent = payload.max_per_agent

    rebalanced = 0
    for agent_id, data in sorted(workloads.items(), key=lambda x: -x[1]["utilization"]):
        if data["utilization"] <= avg_utilization + 0.1:
            continue  # Not overloaded

        # Find tickets to move
        tickets_to_move = db.query(Ticket).filter(
            Ticket.assigned_to == data["name"],
            Ticket.status == TicketStatus.OPEN  # Only move open tickets
        ).order_by(Ticket.created_at.desc()).limit(
            max(1, data["load"] - int(data["capacity"] * avg_utilization))
        ).all()

        for ticket in tickets_to_move:
            # Find underloaded agent
            for target_id, target_data in sorted(workloads.items(), key=lambda x: x[1]["utilization"]):
                if target_id == agent_id:
                    continue
                if target_data["utilization"] >= avg_utilization:
                    continue
                if max_per_agent and target_data["load"] >= max_per_agent:
                    continue

                # Move ticket
                ticket.assigned_to = target_data["name"]
                ticket.updated_at = datetime.utcnow()
                target_data["load"] += 1
                target_data["utilization"] = target_data["load"] / target_data["capacity"]
                data["load"] -= 1
                data["utilization"] = data["load"] / data["capacity"] if data["capacity"] > 0 else 0
                rebalanced += 1
                break

    db.commit()

    return {
        "rebalanced": rebalanced,
        "message": f"Rebalanced {rebalanced} tickets across agents",
    }

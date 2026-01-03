"""Routing configuration and auto-assignment endpoints.

These routes are thin wrappers around RoutingService.
All business logic resides in the service layer.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.support_sla import RoutingStrategy
from app.auth import Require, get_current_user, Principal
from app.cache import cached, CACHE_TTL
from app.services.support import RoutingService
from app.services.support.types import TicketRoutingRuleCreate, TicketRoutingRuleUpdate
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

VALID_ROUTING_OPERATORS = {
    "equals", "not_equals", "contains", "in_list", "is_empty", "is_not_empty"
}


class RoutingCondition(BaseModel):
    """Validated routing rule condition."""
    field: str
    operator: str
    value: Optional[Any] = None

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        if v not in VALID_ROUTING_OPERATORS:
            raise ValueError(
                f"Invalid operator '{v}'. Must be one of: {sorted(VALID_ROUTING_OPERATORS)}"
            )
        return v


class RoutingRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    team_id: Optional[int] = None
    strategy: str = RoutingStrategy.ROUND_ROBIN.value
    conditions: Optional[List[RoutingCondition]] = None
    priority: int = 100
    is_active: bool = True
    fallback_team_id: Optional[int] = None

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid = {s.value for s in RoutingStrategy}
        if v not in valid:
            raise ValueError(f"Invalid strategy '{v}'. Must be one of: {sorted(valid)}")
        return v


class RoutingRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    strategy: Optional[str] = None
    conditions: Optional[List[RoutingCondition]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    fallback_team_id: Optional[int] = None

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = {s.value for s in RoutingStrategy}
        if v not in valid:
            raise ValueError(f"Invalid strategy '{v}'. Must be one of: {sorted(valid)}")
        return v


class AutoAssignRequest(BaseModel):
    ticket_id: int


class RebalanceRequest(BaseModel):
    team_id: Optional[int] = None
    max_per_agent: Optional[int] = None


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_routing_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
) -> RoutingService:
    """Provide RoutingService instance for dependency injection."""
    return RoutingService(db, principal)


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
    service: RoutingService = Depends(get_routing_service),
) -> List[Dict[str, Any]]:
    """List routing rules."""
    rules, _ = service.list_ticket_routing_rules(
        team_id=team_id,
        is_active=True if active_only else None,
    )

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
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Create a routing rule."""
    try:
        conditions_data = (
            [c.model_dump() for c in payload.conditions] if payload.conditions else None
        )

        rule = service.create_ticket_routing_rule(TicketRoutingRuleCreate(
            name=payload.name,
            description=payload.description,
            team_id=payload.team_id,
            strategy=payload.strategy,
            conditions=conditions_data,
            priority=payload.priority,
            is_active=payload.is_active,
            fallback_team_id=payload.fallback_team_id,
        ))
        db.commit()
        return {"id": rule.id, "name": rule.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules/{rule_id}", dependencies=[Depends(Require("support:read"))])
def get_rule(
    rule_id: int,
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Get routing rule details."""
    rule = service.get_ticket_routing_rule(rule_id)
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
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Update a routing rule."""
    try:
        conditions_data = None
        if payload.conditions is not None:
            conditions_data = [c.model_dump() for c in payload.conditions]

        rule = service.update_ticket_routing_rule(
            rule_id,
            TicketRoutingRuleUpdate(
                name=payload.name,
                description=payload.description,
                team_id=payload.team_id,
                strategy=payload.strategy,
                conditions=conditions_data,
                priority=payload.priority,
                is_active=payload.is_active,
                fallback_team_id=payload.fallback_team_id,
            ),
        )
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        db.commit()
        return {"id": rule.id, "name": rule.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/rules/{rule_id}", dependencies=[Depends(Require("support:write"))])
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    service: RoutingService = Depends(get_routing_service),
) -> Response:
    """Delete a routing rule."""
    if not service.delete_ticket_routing_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    db.commit()
    return Response(status_code=204)


# =============================================================================
# AUTO-ASSIGNMENT
# =============================================================================

@router.post("/auto-assign", dependencies=[Depends(Require("support:write"))])
def auto_assign(
    payload: AutoAssignRequest,
    db: Session = Depends(get_db),
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Trigger auto-assignment for a ticket.

    Finds the best matching routing rule and assigns an agent based on
    the rule's strategy.
    """
    try:
        result = service.auto_assign_ticket_by_rules(payload.ticket_id)
        if result.get("assigned"):
            db.commit()
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# WORKLOAD & QUEUE METRICS
# =============================================================================

@router.get("/agent-workload", dependencies=[Depends(Require("support:read"))])
def get_agent_workload(
    team_id: Optional[int] = None,
    service: RoutingService = Depends(get_routing_service),
) -> List[Dict[str, Any]]:
    """Get current workload for all agents."""
    workloads = service.get_agent_workloads(team_id=team_id)

    return [
        {
            "agent_id": w.agent_id,
            "agent_name": w.agent_name,
            "capacity": w.capacity,
            "current_load": w.open_tickets,
            "utilization_pct": w.utilization_pct,
            "available_slots": max(0, w.capacity - w.open_tickets),
        }
        for w in workloads
    ]


@router.get("/queue-health", dependencies=[Depends(Require("analytics:read"))])
@cached("routing-queue-health", ttl=CACHE_TTL["short"])
async def get_queue_health(
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Get overall queue health metrics."""
    health = service.get_queue_health()

    return {
        "unassigned_tickets": health.total_open,
        "by_status": health.by_status,
        "avg_wait_hours": round(health.avg_wait_minutes / 60, 2),
        "total_agents": health.agents_active,
        "agents_at_capacity": health.agents_at_capacity,
    }


@router.post("/rebalance", dependencies=[Depends(Require("support:write"))])
def rebalance_tickets(
    payload: RebalanceRequest,
    db: Session = Depends(get_db),
    service: RoutingService = Depends(get_routing_service),
) -> Dict[str, Any]:
    """Rebalance ticket assignments across agents.

    Moves tickets from overloaded agents to underloaded ones.
    """
    result = service.rebalance_tickets(
        team_id=payload.team_id,
        max_per_agent=payload.max_per_agent,
    )
    db.commit()

    return {
        "rebalanced": result.get("moved", 0),
        "message": f"Rebalanced {result.get('moved', 0)} tickets across agents",
    }

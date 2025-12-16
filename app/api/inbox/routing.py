"""Inbox Routing Rules API - Auto-assignment rules management."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require
from app.models.omni import InboxRoutingRule
from app.models.agent import Agent, Team

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class ConditionSchema(BaseModel):
    type: str  # channel, keyword, tag, priority, contact_company
    operator: str = "contains"  # contains, equals, starts_with
    value: str


class RoutingRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    conditions: List[ConditionSchema]
    action_type: str  # assign_agent, assign_team, add_tag, create_ticket, set_priority
    action_value: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    priority: int = 0
    is_active: bool = True


class RoutingRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[ConditionSchema]] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def serialize_routing_rule(rule: InboxRoutingRule) -> Dict[str, Any]:
    """Serialize a routing rule to JSON."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "conditions": rule.conditions or [],
        "action_type": rule.action_type,
        "action_value": rule.action_value,
        "action_config": rule.action_config,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "match_count": rule.match_count,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/routing-rules",
    dependencies=[Depends(Require("support:read"))],
)
async def list_routing_rules(
    is_active: Optional[bool] = None,
    action_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List routing rules."""
    query = db.query(InboxRoutingRule)

    if is_active is not None:
        query = query.filter(InboxRoutingRule.is_active == is_active)

    if action_type:
        query = query.filter(InboxRoutingRule.action_type == action_type)

    total = query.count()
    rules = query.order_by(InboxRoutingRule.priority.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_routing_rule(r) for r in rules],
    }


@router.get(
    "/routing-rules/{rule_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_routing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single routing rule."""
    rule = db.query(InboxRoutingRule).filter(InboxRoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    return serialize_routing_rule(rule)


@router.post(
    "/routing-rules",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_routing_rule(
    payload: RoutingRuleCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new routing rule."""
    # Validate action targets
    if payload.action_type == "assign_agent" and payload.action_value:
        agent = db.query(Agent).filter(Agent.id == int(payload.action_value)).first()
        if not agent:
            raise HTTPException(status_code=400, detail="Agent not found")

    if payload.action_type == "assign_team" and payload.action_value:
        team = db.query(Team).filter(Team.id == int(payload.action_value)).first()
        if not team:
            raise HTTPException(status_code=400, detail="Team not found")

    rule = InboxRoutingRule(
        name=payload.name,
        description=payload.description,
        conditions=[c.model_dump() for c in payload.conditions],
        action_type=payload.action_type,
        action_value=payload.action_value,
        action_config=payload.action_config,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return serialize_routing_rule(rule)


@router.patch(
    "/routing-rules/{rule_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_routing_rule(
    rule_id: int,
    payload: RoutingRuleUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a routing rule."""
    rule = db.query(InboxRoutingRule).filter(InboxRoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    if payload.name is not None:
        rule.name = payload.name

    if payload.description is not None:
        rule.description = payload.description

    if payload.conditions is not None:
        rule.conditions = [c.model_dump() for c in payload.conditions]

    if payload.action_type is not None:
        rule.action_type = payload.action_type

    if payload.action_value is not None:
        rule.action_value = payload.action_value

    if payload.action_config is not None:
        rule.action_config = payload.action_config

    if payload.priority is not None:
        rule.priority = payload.priority

    if payload.is_active is not None:
        rule.is_active = payload.is_active

    db.commit()
    db.refresh(rule)

    return serialize_routing_rule(rule)


@router.delete(
    "/routing-rules/{rule_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_routing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """Delete a routing rule."""
    rule = db.query(InboxRoutingRule).filter(InboxRoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    db.delete(rule)
    db.commit()

    return None


@router.post(
    "/routing-rules/{rule_id}/toggle",
    dependencies=[Depends(Require("support:write"))],
)
async def toggle_routing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Toggle a routing rule's active status."""
    rule = db.query(InboxRoutingRule).filter(InboxRoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)

    return serialize_routing_rule(rule)

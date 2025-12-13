"""Automation rules management endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.support_automation import (
    AutomationRule,
    AutomationLog,
    AutomationTrigger,
    AutomationActionType,
    ConditionOperator,
)
from app.models.ticket import Ticket
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AutomationRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: str
    conditions: Optional[List[dict]] = None
    actions: List[dict]
    is_active: bool = True
    priority: int = 100
    stop_processing: bool = False
    max_executions_per_hour: Optional[int] = None


class AutomationRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    conditions: Optional[List[dict]] = None
    actions: Optional[List[dict]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    stop_processing: Optional[bool] = None
    max_executions_per_hour: Optional[int] = None


class AutomationTestRequest(BaseModel):
    ticket_id: int


# =============================================================================
# REFERENCE DATA
# =============================================================================

@router.get("/reference/triggers", dependencies=[Depends(Require("support:automation:read"))])
def list_triggers() -> List[Dict[str, str]]:
    """List available automation triggers."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in AutomationTrigger
    ]


@router.get("/reference/action-types", dependencies=[Depends(Require("support:automation:read"))])
def list_action_types() -> List[Dict[str, str]]:
    """List available automation action types."""
    return [
        {"value": a.value, "label": a.value.replace("_", " ").title()}
        for a in AutomationActionType
    ]


@router.get("/reference/operators", dependencies=[Depends(Require("support:automation:read"))])
def list_operators() -> List[Dict[str, str]]:
    """List available condition operators."""
    return [
        {"value": o.value, "label": o.value.replace("_", " ").title()}
        for o in ConditionOperator
    ]


# =============================================================================
# AUTOMATION RULES
# =============================================================================

@router.get("/rules", dependencies=[Depends(Require("support:automation:read"))])
def list_rules(
    trigger: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List automation rules."""
    query = db.query(AutomationRule)

    if trigger:
        query = query.filter(AutomationRule.trigger == trigger)
    if active_only:
        query = query.filter(AutomationRule.is_active == True)

    rules = query.order_by(AutomationRule.priority, AutomationRule.name).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "trigger": r.trigger,
            "conditions": r.conditions,
            "actions": r.actions,
            "is_active": r.is_active,
            "priority": r.priority,
            "stop_processing": r.stop_processing,
            "execution_count": r.execution_count,
            "last_executed_at": r.last_executed_at.isoformat() if r.last_executed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("/rules", dependencies=[Depends(Require("support:automation:write"))], status_code=201)
def create_rule(
    payload: AutomationRuleCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an automation rule."""
    # Validate trigger
    try:
        AutomationTrigger(payload.trigger)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger: {payload.trigger}")

    # Validate actions
    if not payload.actions:
        raise HTTPException(status_code=400, detail="At least one action is required")

    for action in payload.actions:
        if "type" not in action:
            raise HTTPException(status_code=400, detail="Each action must have a 'type' field")
        try:
            AutomationActionType(action["type"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action type: {action['type']}")

    # Validate conditions if provided
    if payload.conditions:
        for condition in payload.conditions:
            if "field" not in condition or "operator" not in condition:
                raise HTTPException(
                    status_code=400,
                    detail="Each condition must have 'field' and 'operator' fields"
                )
            try:
                ConditionOperator(condition["operator"])
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid operator: {condition['operator']}")

    rule = AutomationRule(
        name=payload.name,
        description=payload.description,
        trigger=payload.trigger,
        conditions=payload.conditions,
        actions=payload.actions,
        is_active=payload.is_active,
        priority=payload.priority,
        stop_processing=payload.stop_processing,
        max_executions_per_hour=payload.max_executions_per_hour,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.get("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:read"))])
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get automation rule details."""
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Get recent logs
    recent_logs = db.query(AutomationLog).filter(
        AutomationLog.rule_id == rule_id
    ).order_by(AutomationLog.created_at.desc()).limit(10).all()

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "trigger": rule.trigger,
        "conditions": rule.conditions,
        "actions": rule.actions,
        "is_active": rule.is_active,
        "priority": rule.priority,
        "stop_processing": rule.stop_processing,
        "max_executions_per_hour": rule.max_executions_per_hour,
        "execution_count": rule.execution_count,
        "last_executed_at": rule.last_executed_at.isoformat() if rule.last_executed_at else None,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        "recent_logs": [
            {
                "id": log.id,
                "ticket_id": log.ticket_id,
                "trigger": log.trigger,
                "success": log.success,
                "error_message": log.error_message,
                "execution_time_ms": log.execution_time_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in recent_logs
        ],
    }


@router.patch("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:write"))])
def update_rule(
    rule_id: int,
    payload: AutomationRuleUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an automation rule."""
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.trigger is not None:
        try:
            AutomationTrigger(payload.trigger)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid trigger: {payload.trigger}")
        rule.trigger = payload.trigger
    if payload.conditions is not None:
        for condition in payload.conditions:
            if "field" not in condition or "operator" not in condition:
                raise HTTPException(
                    status_code=400,
                    detail="Each condition must have 'field' and 'operator' fields"
                )
        rule.conditions = payload.conditions
    if payload.actions is not None:
        if not payload.actions:
            raise HTTPException(status_code=400, detail="At least one action is required")
        for action in payload.actions:
            if "type" not in action:
                raise HTTPException(status_code=400, detail="Each action must have a 'type' field")
        rule.actions = payload.actions
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.stop_processing is not None:
        rule.stop_processing = payload.stop_processing
    if payload.max_executions_per_hour is not None:
        rule.max_executions_per_hour = payload.max_executions_per_hour

    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.delete("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:write"))])
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an automation rule."""
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return Response(status_code=204)


@router.post("/rules/{rule_id}/toggle", dependencies=[Depends(Require("support:automation:write"))])
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Toggle automation rule active status."""
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "is_active": rule.is_active}


@router.post("/rules/{rule_id}/test", dependencies=[Depends(Require("support:automation:write"))])
def test_rule(
    rule_id: int,
    payload: AutomationTestRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Test an automation rule against a ticket (dry run).

    Returns what would happen if the rule were executed, without actually
    performing any actions.
    """
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Evaluate conditions (simplified - full logic in automation_executor)
    conditions_result = []
    would_match = True

    if rule.conditions:
        for condition in rule.conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "")
            value = condition.get("value")

            # Get ticket field value
            ticket_value = getattr(ticket, field, None)
            if hasattr(ticket_value, "value"):
                ticket_value = ticket_value.value

            # Simple evaluation
            matched = False
            if operator == "equals":
                matched = str(ticket_value) == str(value)
            elif operator == "not_equals":
                matched = str(ticket_value) != str(value)
            elif operator == "contains":
                matched = value in str(ticket_value) if ticket_value else False
            elif operator == "is_empty":
                matched = ticket_value is None or ticket_value == ""
            elif operator == "is_not_empty":
                matched = ticket_value is not None and ticket_value != ""
            elif operator == "in_list":
                matched = str(ticket_value) in (value if isinstance(value, list) else [value])

            conditions_result.append({
                "field": field,
                "operator": operator,
                "expected_value": value,
                "actual_value": str(ticket_value) if ticket_value else None,
                "matched": matched,
            })

            if not matched:
                would_match = False

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "ticket_id": ticket.id,
        "would_trigger": would_match,
        "conditions_evaluated": conditions_result,
        "actions_would_execute": rule.actions if would_match else [],
        "note": "This is a dry run - no actions were executed",
    }


# =============================================================================
# AUTOMATION LOGS
# =============================================================================

@router.get("/logs", dependencies=[Depends(Require("support:automation:read"))])
def list_logs(
    rule_id: Optional[int] = None,
    ticket_id: Optional[int] = None,
    trigger: Optional[str] = None,
    success: Optional[bool] = None,
    days: int = Query(default=7, le=30),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List automation execution logs."""
    start_dt = datetime.utcnow() - __import__('datetime').timedelta(days=days)

    query = db.query(AutomationLog).filter(AutomationLog.created_at >= start_dt)

    if rule_id:
        query = query.filter(AutomationLog.rule_id == rule_id)
    if ticket_id:
        query = query.filter(AutomationLog.ticket_id == ticket_id)
    if trigger:
        query = query.filter(AutomationLog.trigger == trigger)
    if success is not None:
        query = query.filter(AutomationLog.success == success)

    total = query.count()
    logs = query.order_by(AutomationLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": log.id,
                "rule_id": log.rule_id,
                "rule_name": log.rule.name if log.rule else None,
                "ticket_id": log.ticket_id,
                "trigger": log.trigger,
                "conditions_matched": log.conditions_matched,
                "actions_executed": log.actions_executed,
                "success": log.success,
                "error_message": log.error_message,
                "execution_time_ms": log.execution_time_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@router.get("/logs/summary", dependencies=[Depends(Require("analytics:read"))])
@cached("automation-logs-summary", ttl=CACHE_TTL["medium"])
async def logs_summary(
    days: int = Query(default=7, le=30),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get automation execution summary statistics."""
    start_dt = datetime.utcnow() - __import__('datetime').timedelta(days=days)

    # Total executions
    total = db.query(func.count(AutomationLog.id)).filter(
        AutomationLog.created_at >= start_dt
    ).scalar() or 0

    success_count = db.query(func.count(AutomationLog.id)).filter(
        AutomationLog.created_at >= start_dt,
        AutomationLog.success == True
    ).scalar() or 0

    # By trigger
    by_trigger = db.query(
        AutomationLog.trigger,
        func.count(AutomationLog.id).label("count"),
        func.sum(func.cast(AutomationLog.success, __import__('sqlalchemy').Integer)).label("success_count"),
    ).filter(
        AutomationLog.created_at >= start_dt
    ).group_by(AutomationLog.trigger).all()

    # By rule
    by_rule = db.query(
        AutomationLog.rule_id,
        AutomationRule.name,
        func.count(AutomationLog.id).label("count"),
        func.avg(AutomationLog.execution_time_ms).label("avg_time_ms"),
    ).join(AutomationRule, AutomationLog.rule_id == AutomationRule.id).filter(
        AutomationLog.created_at >= start_dt
    ).group_by(AutomationLog.rule_id, AutomationRule.name).order_by(
        func.count(AutomationLog.id).desc()
    ).limit(10).all()

    return {
        "period_days": days,
        "total_executions": total,
        "successful_executions": success_count,
        "success_rate": round(success_count / total * 100, 1) if total > 0 else 0,
        "by_trigger": [
            {
                "trigger": row.trigger,
                "count": row.count,
                "success_count": row.success_count or 0,
            }
            for row in by_trigger
        ],
        "top_rules": [
            {
                "rule_id": row.rule_id,
                "rule_name": row.name,
                "execution_count": row.count,
                "avg_execution_time_ms": round(float(row.avg_time_ms or 0), 1),
            }
            for row in by_rule
        ],
    }

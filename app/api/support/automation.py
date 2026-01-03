"""Automation rules management endpoints.

These routes are thin wrappers around AutomationService.
All business logic resides in the service layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.support_automation import (
    AutomationTrigger,
    AutomationActionType,
    ConditionOperator,
)
from app.auth import Require, get_current_user, Principal
from app.cache import cached, CACHE_TTL
from app.services.support import AutomationService
from app.services.support.types import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationLogFilters,
)
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RuleCondition(BaseModel):
    """Validated automation rule condition."""
    field: str
    operator: str
    value: Optional[Any] = None

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid_operators = {op.value for op in ConditionOperator}
        if v not in valid_operators:
            raise ValueError(f"Invalid operator '{v}'. Must be one of: {sorted(valid_operators)}")
        return v


class RuleAction(BaseModel):
    """Validated automation rule action."""
    type: str
    params: Dict[str, Any] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {at.value for at in AutomationActionType}
        if v not in valid_types:
            raise ValueError(f"Invalid action type '{v}'. Must be one of: {sorted(valid_types)}")
        return v


class AutomationRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: str
    conditions: Optional[List[RuleCondition]] = None
    actions: List[RuleAction]
    is_active: bool = True
    priority: int = 100
    stop_processing: bool = False
    max_executions_per_hour: Optional[int] = None

    @field_validator("trigger")
    @classmethod
    def validate_trigger(cls, v: str) -> str:
        valid_triggers = {t.value for t in AutomationTrigger}
        if v not in valid_triggers:
            raise ValueError(f"Invalid trigger '{v}'. Must be one of: {sorted(valid_triggers)}")
        return v


class AutomationRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    conditions: Optional[List[RuleCondition]] = None
    actions: Optional[List[RuleAction]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    stop_processing: Optional[bool] = None
    max_executions_per_hour: Optional[int] = None

    @field_validator("trigger")
    @classmethod
    def validate_trigger(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_triggers = {t.value for t in AutomationTrigger}
        if v not in valid_triggers:
            raise ValueError(f"Invalid trigger '{v}'. Must be one of: {sorted(valid_triggers)}")
        return v


class AutomationTestRequest(BaseModel):
    ticket_id: int


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_automation_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
) -> AutomationService:
    """Provide AutomationService instance for dependency injection."""
    return AutomationService(db, principal)


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
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """List automation rules."""
    rules, total = service.list_db_rules(
        trigger=trigger,
        is_active=True if active_only else None,
        skip=offset,
        limit=limit,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
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
        ],
    }


@router.post("/rules", dependencies=[Depends(Require("support:automation:write"))], status_code=201)
def create_rule(
    payload: AutomationRuleCreateRequest,
    db: Session = Depends(get_db),
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Create an automation rule."""
    try:
        conditions_data = [c.model_dump() for c in payload.conditions] if payload.conditions else None
        actions_data = [a.model_dump() for a in payload.actions]

        rule = service.create_db_rule(AutomationRuleCreate(
            name=payload.name,
            description=payload.description,
            trigger=payload.trigger,
            conditions=conditions_data,
            actions=actions_data,
            is_active=payload.is_active,
            priority=payload.priority,
            stop_processing=payload.stop_processing,
            max_executions_per_hour=payload.max_executions_per_hour,
        ))
        db.commit()
        return {"id": rule.id, "name": rule.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:read"))])
def get_rule(
    rule_id: int,
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Get automation rule details."""
    rule = service.get_db_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Get recent logs
    logs, _ = service.list_logs(
        filters=AutomationLogFilters(rule_id=rule_id),
        limit=10,
    )

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
            for log in logs
        ],
    }


@router.patch("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:write"))])
def update_rule(
    rule_id: int,
    payload: AutomationRuleUpdateRequest,
    db: Session = Depends(get_db),
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Update an automation rule."""
    try:
        conditions_data = None
        if payload.conditions is not None:
            conditions_data = [c.model_dump() for c in payload.conditions]

        actions_data = None
        if payload.actions is not None:
            if not payload.actions:
                raise HTTPException(
                    status_code=400, detail="At least one action is required"
                )
            actions_data = [a.model_dump() for a in payload.actions]

        rule = service.update_db_rule(
            rule_id,
            AutomationRuleUpdate(
                name=payload.name,
                description=payload.description,
                trigger=payload.trigger,
                conditions=conditions_data,
                actions=actions_data,
                is_active=payload.is_active,
                priority=payload.priority,
                stop_processing=payload.stop_processing,
                max_executions_per_hour=payload.max_executions_per_hour,
            ),
        )
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        db.commit()
        return {"id": rule.id, "name": rule.name}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/rules/{rule_id}", dependencies=[Depends(Require("support:automation:write"))])
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    service: AutomationService = Depends(get_automation_service),
) -> Response:
    """Delete an automation rule."""
    if not service.delete_db_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    db.commit()
    return Response(status_code=204)


@router.post("/rules/{rule_id}/toggle", dependencies=[Depends(Require("support:automation:write"))])
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Toggle automation rule active status."""
    rule = service.toggle_db_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.commit()
    return {"id": rule.id, "is_active": rule.is_active}


@router.post("/rules/{rule_id}/test", dependencies=[Depends(Require("support:automation:write"))])
def test_rule(
    rule_id: int,
    payload: AutomationTestRequest,
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Test an automation rule against a ticket (dry run).

    Returns what would happen if the rule were executed, without actually
    performing any actions.
    """
    result = service.test_rule(rule_id, payload.ticket_id)

    if not result.get("success"):
        error = result.get("error", "Unknown error")
        if "not found" in error.lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error)

    return {
        "rule_id": result["rule"]["id"],
        "rule_name": result["rule"]["name"],
        "ticket_id": result["ticket"]["id"],
        "would_trigger": result["all_conditions_matched"],
        "conditions_evaluated": result["conditions_evaluated"],
        "actions_would_execute": result["actions_would_execute"],
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
    offset: int = Query(default=0, ge=0),
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """List automation execution logs."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    filters = AutomationLogFilters(
        rule_id=rule_id,
        ticket_id=ticket_id,
        trigger=trigger,
        success=success,
        start_date=start_dt,
    )

    logs, total = service.list_logs(filters=filters, skip=offset, limit=limit)

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
    service: AutomationService = Depends(get_automation_service),
) -> Dict[str, Any]:
    """Get automation execution summary statistics."""
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    summary = service.get_logs_summary(start_date=start_dt)

    success_rate = 0.0
    if summary.total_executions > 0:
        success_rate = round(summary.successful / summary.total_executions * 100, 1)

    return {
        "period_days": days,
        "total_executions": summary.total_executions,
        "successful_executions": summary.successful,
        "success_rate": success_rate,
        "by_trigger": [
            {"trigger": trigger, "count": count}
            for trigger, count in summary.by_trigger.items()
        ],
        "top_rules": [
            {"rule_name": name, "execution_count": count}
            for name, count in summary.by_rule.items()
        ],
    }

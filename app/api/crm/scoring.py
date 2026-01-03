"""
Lead Scoring API - Automated scoring rule management.

Manage lead scoring rules and calculate scores.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Any
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.utils.company_context import get_company_id
from app.services.crm.scoring import LeadScoringService
from app.services.crm.scoring_types import (
    ScoringRuleFilters,
    ScoringRuleCreateData,
    ScoringRuleUpdateData,
    ScoringCondition,
)

router = APIRouter(prefix="/scoring", tags=["crm-scoring"])


def get_scoring_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> LeadScoringService:
    """Create a LeadScoringService instance."""
    company_id = get_company_id(principal)
    return LeadScoringService(db, company_id, principal.user_id)


# ============= SCHEMAS =============
class ScoringConditionSchema(BaseModel):
    """A condition for scoring rules."""

    field: str
    operator: str  # equals, not_equals, contains, gt, lt, in, not_in, is_set, is_not_set
    value: Any


class ScoringRuleCreate(BaseModel):
    """Create a scoring rule."""

    name: str
    description: Optional[str] = None
    rule_type: str = "attribute"  # attribute, behavior, engagement
    category: Optional[str] = None  # demographic, firmographic, behavioral, engagement
    conditions: List[ScoringConditionSchema] = Field(default_factory=list)
    score_change: int = 0
    decay_enabled: bool = False
    decay_days: int = 30
    decay_amount: int = 0
    priority: int = 100
    is_active: bool = True


class ScoringRuleUpdate(BaseModel):
    """Update a scoring rule."""

    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    category: Optional[str] = None
    conditions: Optional[List[ScoringConditionSchema]] = None
    score_change: Optional[int] = None
    decay_enabled: Optional[bool] = None
    decay_days: Optional[int] = None
    decay_amount: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class ScoreLeadRequest(BaseModel):
    """Request to score a specific lead."""

    party_id: int


class BulkScoreRequest(BaseModel):
    """Request to score multiple leads."""

    party_ids: Optional[List[int]] = None  # None = score all leads


# ============= RULE ENDPOINTS =============
@router.get("/rules")
async def list_rules(
    search: Optional[str] = None,
    rule_type: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: LeadScoringService = Depends(get_scoring_service),
):
    """List scoring rules."""
    filters = ScoringRuleFilters(
        search=search,
        rule_type=rule_type,
        category=category,
        is_active=is_active,
    )
    rules, total = service.list_rules(filters, skip, limit)
    return {
        "items": [_serialize_rule(r) for r in rules],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/rules/summary")
async def get_rule_summary(
    service: LeadScoringService = Depends(get_scoring_service),
):
    """Get scoring rules summary."""
    summary = service.get_rule_summary()
    return {
        "total_rules": summary.total_rules,
        "active_rules": summary.active_rules,
        "rules_by_type": summary.rules_by_type,
        "rules_by_category": summary.rules_by_category,
        "avg_score_change": summary.avg_score_change,
        "top_scoring_rules": summary.top_scoring_rules,
    }


@router.post("/rules")
async def create_rule(
    data: ScoringRuleCreate,
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Create a scoring rule."""
    conditions = [
        ScoringCondition(
            field=c.field,
            operator=c.operator,
            value=c.value,
        )
        for c in data.conditions
    ]
    create_data = ScoringRuleCreateData(
        name=data.name,
        description=data.description,
        rule_type=data.rule_type,
        category=data.category,
        conditions=conditions,
        score_change=data.score_change,
        decay_enabled=data.decay_enabled,
        decay_days=data.decay_days,
        decay_amount=data.decay_amount,
        priority=data.priority,
        is_active=data.is_active,
    )
    rule = service.create_rule(create_data)
    db.commit()
    return _serialize_rule(rule)


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: int,
    service: LeadScoringService = Depends(get_scoring_service),
):
    """Get a scoring rule by ID."""
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _serialize_rule(rule)


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    data: ScoringRuleUpdate,
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Update a scoring rule."""
    conditions = None
    if data.conditions is not None:
        conditions = [
            ScoringCondition(
                field=c.field,
                operator=c.operator,
                value=c.value,
            )
            for c in data.conditions
        ]
    update_data = ScoringRuleUpdateData(
        name=data.name,
        description=data.description,
        rule_type=data.rule_type,
        category=data.category,
        conditions=conditions,
        score_change=data.score_change,
        decay_enabled=data.decay_enabled,
        decay_days=data.decay_days,
        decay_amount=data.decay_amount,
        priority=data.priority,
        is_active=data.is_active,
    )
    rule = service.update_rule(rule_id, update_data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.commit()
    return _serialize_rule(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Delete a scoring rule."""
    if not service.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    db.commit()
    return {"success": True}


# ============= SCORING ENDPOINTS =============
@router.post("/calculate")
async def score_lead(
    data: ScoreLeadRequest,
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Calculate score for a specific lead."""
    result = service.score_lead(data.party_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.commit()
    return {
        "party_id": result.party_id,
        "party_name": result.party_name,
        "previous_score": result.previous_score,
        "new_score": result.new_score,
        "score_change": result.score_change,
        "grade": result.grade,
        "qualified": result.qualified,
        "adjustments": [
            {
                "rule_id": a.rule_id,
                "rule_name": a.rule_name,
                "rule_type": a.rule_type,
                "score_change": a.score_change,
                "reason": a.reason,
            }
            for a in result.adjustments
        ],
        "calculated_at": result.calculated_at.isoformat(),
    }


@router.post("/calculate/bulk")
async def score_all_leads(
    data: BulkScoreRequest,
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Score all leads or specific leads."""
    if data.party_ids:
        scored = 0
        for party_id in data.party_ids:
            result = service.score_lead(party_id)
            if result:
                scored += 1
    else:
        scored = service.score_all_leads()
    db.commit()
    return {"scored": scored}


@router.post("/decay")
async def apply_decay(
    service: LeadScoringService = Depends(get_scoring_service),
    db: Session = Depends(get_db),
):
    """Apply score decay based on rules."""
    affected = service.apply_decay()
    db.commit()
    return {"affected": affected}


# ============= ANALYTICS ENDPOINTS =============
@router.get("/distribution")
async def get_score_distribution(
    service: LeadScoringService = Depends(get_scoring_service),
):
    """Get distribution of lead scores."""
    dist = service.get_score_distribution()
    return {
        "total_leads": dist.total_leads,
        "scored_leads": dist.scored_leads,
        "unscored_leads": dist.unscored_leads,
        "avg_score": dist.avg_score,
        "median_score": dist.median_score,
        "min_score": dist.min_score,
        "max_score": dist.max_score,
        "grade_a_count": dist.grade_a_count,
        "grade_b_count": dist.grade_b_count,
        "grade_c_count": dist.grade_c_count,
        "grade_d_count": dist.grade_d_count,
        "grade_f_count": dist.grade_f_count,
        "qualified_count": dist.qualified_count,
        "unqualified_count": dist.unqualified_count,
    }


@router.get("/history/{party_id}")
async def get_score_history(
    party_id: int,
    service: LeadScoringService = Depends(get_scoring_service),
):
    """Get score history for a lead."""
    history = service.get_score_history(party_id)
    if not history:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {
        "party_id": history.party_id,
        "party_name": history.party_name,
        "current_score": history.current_score,
        "current_grade": history.current_grade,
        "score_timeline": history.score_timeline,
        "total_positive_adjustments": history.total_positive_adjustments,
        "total_negative_adjustments": history.total_negative_adjustments,
        "net_change_30d": history.net_change_30d,
        "net_change_90d": history.net_change_90d,
        "rules_applied": history.rules_applied,
    }


# ============= SERIALIZERS =============
def _serialize_rule(rule) -> dict:
    """Serialize a scoring rule."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "category": rule.category,
        "conditions": rule.conditions,
        "score_change": rule.score_change,
        "decay_enabled": rule.decay_enabled,
        "decay_days": rule.decay_days,
        "decay_amount": rule.decay_amount,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }

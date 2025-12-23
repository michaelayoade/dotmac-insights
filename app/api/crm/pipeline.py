"""
Pipeline API - Stage management and pipeline views
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.crm import OpportunityStage, Opportunity, OpportunityStatus

router = APIRouter(prefix="/pipeline", tags=["crm-pipeline"])


# ============= SCHEMAS =============
class StageBase(BaseModel):
    name: str
    sequence: int = 0
    probability: int = 0
    is_won: bool = False
    is_lost: bool = False
    color: Optional[str] = None


class StageCreate(StageBase):
    pass


class StageUpdate(BaseModel):
    name: Optional[str] = None
    sequence: Optional[int] = None
    probability: Optional[int] = None
    is_won: Optional[bool] = None
    is_lost: Optional[bool] = None
    is_active: Optional[bool] = None
    color: Optional[str] = None


class StageResponse(BaseModel):
    id: int
    name: str
    sequence: int
    probability: int
    is_won: bool
    is_lost: bool
    is_active: bool
    color: Optional[str]
    opportunity_count: int = 0
    opportunity_value: float = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineViewResponse(BaseModel):
    stages: List[StageResponse]
    unassigned_count: int
    unassigned_value: float
    total_value: float
    weighted_value: float


class KanbanColumn(BaseModel):
    stage_id: int
    stage_name: str
    color: Optional[str]
    probability: int
    opportunities: List[dict]
    count: int
    value: float


class KanbanViewResponse(BaseModel):
    columns: List[KanbanColumn]
    total_opportunities: int
    total_value: float


# ============= ENDPOINTS =============
@router.get("/stages", response_model=List[StageResponse], dependencies=[Depends(Require("crm:read"))])
async def list_stages(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List all pipeline stages."""
    query = db.query(OpportunityStage)

    if not include_inactive:
        query = query.filter(OpportunityStage.is_active == True)

    stages = query.order_by(OpportunityStage.sequence).all()

    result = []
    for stage in stages:
        count = db.query(func.count(Opportunity.id)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        value = db.query(func.sum(Opportunity.deal_value)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0

        result.append(StageResponse(
            id=stage.id,
            name=stage.name,
            sequence=stage.sequence,
            probability=stage.probability,
            is_won=stage.is_won,
            is_lost=stage.is_lost,
            is_active=stage.is_active,
            color=stage.color,
            opportunity_count=count,
            opportunity_value=float(value),
            created_at=stage.created_at,
            updated_at=stage.updated_at,
        ))

    return result


@router.get("/view", response_model=PipelineViewResponse, dependencies=[Depends(Require("crm:read"))])
async def get_pipeline_view(db: Session = Depends(get_db)):
    """Get full pipeline view with stage stats."""
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.is_active == True
    ).order_by(OpportunityStage.sequence).all()

    stage_responses = []
    total_value = 0.0
    weighted_value = 0.0

    for stage in stages:
        count = db.query(func.count(Opportunity.id)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        value = db.query(func.sum(Opportunity.deal_value)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        weighted = db.query(func.sum(Opportunity.weighted_value)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0

        total_value += float(value)
        weighted_value += float(weighted)

        stage_responses.append(StageResponse(
            id=stage.id,
            name=stage.name,
            sequence=stage.sequence,
            probability=stage.probability,
            is_won=stage.is_won,
            is_lost=stage.is_lost,
            is_active=stage.is_active,
            color=stage.color,
            opportunity_count=count,
            opportunity_value=float(value),
            created_at=stage.created_at,
            updated_at=stage.updated_at,
        ))

    # Unassigned opportunities (no stage)
    unassigned_count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.stage_id.is_(None),
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0
    unassigned_value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.stage_id.is_(None),
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0

    return PipelineViewResponse(
        stages=stage_responses,
        unassigned_count=unassigned_count,
        unassigned_value=float(unassigned_value or 0),
        total_value=total_value + float(unassigned_value or 0),
        weighted_value=weighted_value,
    )


@router.get("/kanban", response_model=KanbanViewResponse, dependencies=[Depends(Require("crm:read"))])
async def get_kanban_view(
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get kanban board view of pipeline."""
    stages = db.query(OpportunityStage).filter(
        OpportunityStage.is_active == True
    ).order_by(OpportunityStage.sequence).all()

    columns = []
    total_count = 0
    total_value = 0.0

    for stage in stages:
        query = db.query(Opportunity).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        )

        if owner_id:
            query = query.filter(Opportunity.owner_id == owner_id)

        opportunities = query.order_by(Opportunity.expected_close_date.asc().nullslast()).all()

        opp_list = []
        stage_value = 0.0
        for opp in opportunities:
            opp_list.append({
                "id": opp.id,
                "name": opp.name,
                "customer_name": opp.customer.name if opp.customer else None,
                "deal_value": float(opp.deal_value),
                "probability": opp.probability,
                "expected_close_date": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
            })
            stage_value += float(opp.deal_value)

        columns.append(KanbanColumn(
            stage_id=stage.id,
            stage_name=stage.name,
            color=stage.color,
            probability=stage.probability,
            opportunities=opp_list,
            count=len(opp_list),
            value=stage_value,
        ))

        total_count += len(opp_list)
        total_value += stage_value

    return KanbanViewResponse(
        columns=columns,
        total_opportunities=total_count,
        total_value=total_value,
    )


@router.post("/stages", response_model=StageResponse, dependencies=[Depends(Require("crm:admin"))])
async def create_stage(payload: StageCreate, db: Session = Depends(get_db)):
    """Create a new pipeline stage."""
    # Check for duplicate name
    existing = db.query(OpportunityStage).filter(OpportunityStage.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Stage with this name already exists")

    stage = OpportunityStage(
        name=payload.name,
        sequence=payload.sequence,
        probability=payload.probability,
        is_won=payload.is_won,
        is_lost=payload.is_lost,
        color=payload.color,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)

    return StageResponse(
        id=stage.id,
        name=stage.name,
        sequence=stage.sequence,
        probability=stage.probability,
        is_won=stage.is_won,
        is_lost=stage.is_lost,
        is_active=stage.is_active,
        color=stage.color,
        opportunity_count=0,
        opportunity_value=0,
        created_at=stage.created_at,
        updated_at=stage.updated_at,
    )


@router.patch("/stages/{stage_id}", response_model=StageResponse, dependencies=[Depends(Require("crm:admin"))])
async def update_stage(stage_id: int, payload: StageUpdate, db: Session = Depends(get_db)):
    """Update a pipeline stage."""
    stage = db.query(OpportunityStage).filter(OpportunityStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Check for duplicate name if changing
    if "name" in update_data and update_data["name"] != stage.name:
        existing = db.query(OpportunityStage).filter(
            OpportunityStage.name == update_data["name"],
            OpportunityStage.id != stage_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Stage with this name already exists")

    for key, value in update_data.items():
        setattr(stage, key, value)

    db.commit()
    db.refresh(stage)

    count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.stage_id == stage.id,
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0
    value = db.query(func.sum(Opportunity.deal_value)).filter(
        Opportunity.stage_id == stage.id,
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0

    return StageResponse(
        id=stage.id,
        name=stage.name,
        sequence=stage.sequence,
        probability=stage.probability,
        is_won=stage.is_won,
        is_lost=stage.is_lost,
        is_active=stage.is_active,
        color=stage.color,
        opportunity_count=count,
        opportunity_value=float(value),
        created_at=stage.created_at,
        updated_at=stage.updated_at,
    )


@router.post("/stages/reorder", dependencies=[Depends(Require("crm:admin"))])
async def reorder_stages(stage_ids: List[int], db: Session = Depends(get_db)):
    """Reorder pipeline stages."""
    for i, stage_id in enumerate(stage_ids):
        stage = db.query(OpportunityStage).filter(OpportunityStage.id == stage_id).first()
        if stage:
            stage.sequence = i

    db.commit()

    return {"success": True, "message": "Stages reordered"}


@router.delete("/stages/{stage_id}", dependencies=[Depends(Require("crm:admin"))])
async def delete_stage(stage_id: int, db: Session = Depends(get_db)):
    """Deactivate a pipeline stage."""
    stage = db.query(OpportunityStage).filter(OpportunityStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    # Check if stage has opportunities
    count = db.query(func.count(Opportunity.id)).filter(
        Opportunity.stage_id == stage_id,
        Opportunity.status == OpportunityStatus.OPEN
    ).scalar() or 0

    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete stage with {count} active opportunities. Move them first."
        )

    stage.is_active = False
    db.commit()

    return {"success": True, "message": "Stage deactivated"}


@router.post("/seed-default-stages", dependencies=[Depends(Require("crm:admin"))])
async def seed_default_stages(db: Session = Depends(get_db)):
    """Seed default pipeline stages if none exist."""
    existing = db.query(func.count(OpportunityStage.id)).scalar() or 0
    if existing > 0:
        return {"success": False, "message": f"Stages already exist ({existing})"}

    default_stages = [
        {"name": "Qualification", "sequence": 0, "probability": 10, "color": "slate"},
        {"name": "Needs Analysis", "sequence": 1, "probability": 20, "color": "blue"},
        {"name": "Proposal", "sequence": 2, "probability": 40, "color": "amber"},
        {"name": "Negotiation", "sequence": 3, "probability": 60, "color": "orange"},
        {"name": "Closed Won", "sequence": 4, "probability": 100, "color": "emerald", "is_won": True},
        {"name": "Closed Lost", "sequence": 5, "probability": 0, "color": "red", "is_lost": True},
    ]

    for stage_data in default_stages:
        stage = OpportunityStage(**stage_data)
        db.add(stage)

    db.commit()

    return {"success": True, "message": f"Created {len(default_stages)} default stages"}

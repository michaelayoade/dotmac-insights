"""
Opportunities API - Deal pipeline management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.crm import Opportunity, OpportunityStatus, OpportunityStage

router = APIRouter(prefix="/opportunities", tags=["crm-opportunities"])


# ============= SCHEMAS =============
class OpportunityBase(BaseModel):
    name: str
    description: Optional[str] = None
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    stage_id: Optional[int] = None
    deal_value: float = 0
    probability: int = 0
    expected_close_date: Optional[date] = None
    owner_id: Optional[int] = None
    sales_person_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    stage_id: Optional[int] = None
    deal_value: Optional[float] = None
    probability: Optional[int] = None
    expected_close_date: Optional[date] = None
    owner_id: Optional[int] = None
    sales_person_id: Optional[int] = None
    source: Optional[str] = None
    campaign: Optional[str] = None


class StageInfo(BaseModel):
    id: int
    name: str
    probability: int
    color: Optional[str]

    class Config:
        from_attributes = True


class OpportunityResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    lead_id: Optional[int]
    customer_id: Optional[int]
    customer_name: Optional[str]
    stage_id: Optional[int]
    stage: Optional[StageInfo]
    status: str
    currency: str
    deal_value: float
    probability: int
    weighted_value: float
    expected_close_date: Optional[date]
    actual_close_date: Optional[date]
    owner_id: Optional[int]
    sales_person_id: Optional[int]
    source: Optional[str]
    campaign: Optional[str]
    lost_reason: Optional[str]
    competitor: Optional[str]
    quotation_id: Optional[int]
    sales_order_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OpportunityListResponse(BaseModel):
    items: List[OpportunityResponse]
    total: int
    page: int
    page_size: int


class PipelineSummaryResponse(BaseModel):
    total_opportunities: int
    total_value: float
    weighted_value: float
    won_count: int
    won_value: float
    lost_count: int
    by_stage: List[dict]
    avg_deal_size: float
    win_rate: float


# ============= ENDPOINTS =============
@router.get("", response_model=OpportunityListResponse, dependencies=[Depends(Require("crm:read"))])
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    stage_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """List opportunities with filtering and pagination."""
    query = db.query(Opportunity).options(joinedload(Opportunity.stage_rel), joinedload(Opportunity.customer))

    if search:
        search_term = f"%{search}%"
        query = query.filter(Opportunity.name.ilike(search_term))

    if status:
        try:
            status_enum = OpportunityStatus(status.lower())
            query = query.filter(Opportunity.status == status_enum)
        except ValueError:
            pass

    if stage_id:
        query = query.filter(Opportunity.stage_id == stage_id)

    if customer_id:
        query = query.filter(Opportunity.customer_id == customer_id)

    if owner_id:
        query = query.filter(Opportunity.owner_id == owner_id)

    if min_value is not None:
        query = query.filter(Opportunity.deal_value >= Decimal(str(min_value)))

    if max_value is not None:
        query = query.filter(Opportunity.deal_value <= Decimal(str(max_value)))

    total = query.count()
    opportunities = query.order_by(Opportunity.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return OpportunityListResponse(
        items=[_opp_to_response(o) for o in opportunities],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/pipeline", response_model=PipelineSummaryResponse, dependencies=[Depends(Require("crm:read"))])
async def get_pipeline_summary(db: Session = Depends(get_db)):
    """Get pipeline summary with stage breakdown."""
    # Overall stats
    total = db.query(func.count(Opportunity.id)).filter(Opportunity.status == OpportunityStatus.OPEN).scalar() or 0
    total_value = db.query(func.sum(Opportunity.deal_value)).filter(Opportunity.status == OpportunityStatus.OPEN).scalar() or 0
    weighted = db.query(func.sum(Opportunity.weighted_value)).filter(Opportunity.status == OpportunityStatus.OPEN).scalar() or 0

    won_count = db.query(func.count(Opportunity.id)).filter(Opportunity.status == OpportunityStatus.WON).scalar() or 0
    won_value = db.query(func.sum(Opportunity.deal_value)).filter(Opportunity.status == OpportunityStatus.WON).scalar() or 0
    lost_count = db.query(func.count(Opportunity.id)).filter(Opportunity.status == OpportunityStatus.LOST).scalar() or 0

    # By stage
    stages = db.query(OpportunityStage).filter(OpportunityStage.is_active == True).order_by(OpportunityStage.sequence).all()
    by_stage = []
    for stage in stages:
        count = db.query(func.count(Opportunity.id)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        value = db.query(func.sum(Opportunity.deal_value)).filter(
            Opportunity.stage_id == stage.id,
            Opportunity.status == OpportunityStatus.OPEN
        ).scalar() or 0
        by_stage.append({
            "stage_id": stage.id,
            "stage_name": stage.name,
            "color": stage.color,
            "probability": stage.probability,
            "count": count,
            "value": float(value),
        })

    # Metrics
    closed_total = won_count + lost_count
    win_rate = (won_count / closed_total * 100) if closed_total > 0 else 0
    avg_deal = float(total_value) / total if total > 0 else 0

    return PipelineSummaryResponse(
        total_opportunities=total,
        total_value=float(total_value),
        weighted_value=float(weighted),
        won_count=won_count,
        won_value=float(won_value),
        lost_count=lost_count,
        by_stage=by_stage,
        avg_deal_size=avg_deal,
        win_rate=win_rate,
    )


@router.get("/{opp_id}", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:read"))])
async def get_opportunity(opp_id: int, db: Session = Depends(get_db)):
    """Get a single opportunity by ID."""
    opp = db.query(Opportunity).options(
        joinedload(Opportunity.stage_rel),
        joinedload(Opportunity.customer)
    ).filter(Opportunity.id == opp_id).first()

    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return _opp_to_response(opp)


@router.post("", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:write"))])
async def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    """Create a new opportunity."""
    opp = Opportunity(
        name=payload.name,
        description=payload.description,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        stage_id=payload.stage_id,
        deal_value=Decimal(str(payload.deal_value)),
        probability=payload.probability,
        expected_close_date=payload.expected_close_date,
        owner_id=payload.owner_id,
        sales_person_id=payload.sales_person_id,
        source=payload.source,
        campaign=payload.campaign,
        status=OpportunityStatus.OPEN,
    )

    # If stage has probability and none set, use stage probability
    if payload.stage_id and not payload.probability:
        stage = db.query(OpportunityStage).filter(OpportunityStage.id == payload.stage_id).first()
        if stage:
            opp.probability = stage.probability

    opp.update_weighted_value()
    db.add(opp)
    db.commit()
    db.refresh(opp)

    return _opp_to_response(opp)


@router.patch("/{opp_id}", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:write"))])
async def update_opportunity(opp_id: int, payload: OpportunityUpdate, db: Session = Depends(get_db)):
    """Update an opportunity."""
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "deal_value" in update_data:
        update_data["deal_value"] = Decimal(str(update_data["deal_value"]))

    # If stage changes, optionally update probability
    if "stage_id" in update_data and "probability" not in update_data:
        stage = db.query(OpportunityStage).filter(OpportunityStage.id == update_data["stage_id"]).first()
        if stage:
            update_data["probability"] = stage.probability

    for key, value in update_data.items():
        setattr(opp, key, value)

    opp.update_weighted_value()
    db.commit()
    db.refresh(opp)

    return _opp_to_response(opp)


@router.post("/{opp_id}/move-stage", dependencies=[Depends(Require("crm:write"))])
async def move_stage(opp_id: int, stage_id: int, db: Session = Depends(get_db)):
    """Move opportunity to a different pipeline stage."""
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    stage = db.query(OpportunityStage).filter(OpportunityStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    opp.stage_id = stage_id
    opp.probability = stage.probability

    # If moving to won/lost stage, update status
    if stage.is_won:
        opp.status = OpportunityStatus.WON
        opp.actual_close_date = date.today()
    elif stage.is_lost:
        opp.status = OpportunityStatus.LOST
        opp.actual_close_date = date.today()

    opp.update_weighted_value()
    db.commit()

    return {"success": True, "message": f"Moved to stage: {stage.name}"}


@router.post("/{opp_id}/won", dependencies=[Depends(Require("crm:write"))])
async def mark_won(opp_id: int, db: Session = Depends(get_db)):
    """Mark opportunity as won."""
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opp.status = OpportunityStatus.WON
    opp.probability = 100
    opp.actual_close_date = date.today()
    opp.update_weighted_value()
    db.commit()

    return {"success": True, "message": "Opportunity marked as won"}


@router.post("/{opp_id}/lost", dependencies=[Depends(Require("crm:write"))])
async def mark_lost(opp_id: int, reason: Optional[str] = None, competitor: Optional[str] = None, db: Session = Depends(get_db)):
    """Mark opportunity as lost."""
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opp.status = OpportunityStatus.LOST
    opp.probability = 0
    opp.actual_close_date = date.today()
    opp.lost_reason = reason
    opp.competitor = competitor
    opp.update_weighted_value()
    db.commit()

    return {"success": True, "message": "Opportunity marked as lost"}


def _opp_to_response(opp: Opportunity) -> OpportunityResponse:
    """Convert Opportunity model to response."""
    stage_info = None
    if opp.stage_rel:
        stage_info = StageInfo(
            id=opp.stage_rel.id,
            name=opp.stage_rel.name,
            probability=opp.stage_rel.probability,
            color=opp.stage_rel.color,
        )

    customer_name = None
    if opp.customer:
        customer_name = opp.customer.name

    return OpportunityResponse(
        id=opp.id,
        name=opp.name,
        description=opp.description,
        lead_id=opp.lead_id,
        customer_id=opp.customer_id,
        customer_name=customer_name,
        stage_id=opp.stage_id,
        stage=stage_info,
        status=opp.status.value,
        currency=opp.currency,
        deal_value=float(opp.deal_value),
        probability=opp.probability,
        weighted_value=float(opp.weighted_value),
        expected_close_date=opp.expected_close_date,
        actual_close_date=opp.actual_close_date,
        owner_id=opp.owner_id,
        sales_person_id=opp.sales_person_id,
        source=opp.source,
        campaign=opp.campaign,
        lost_reason=opp.lost_reason,
        competitor=opp.competitor,
        quotation_id=opp.quotation_id,
        sales_order_id=opp.sales_order_id,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
    )

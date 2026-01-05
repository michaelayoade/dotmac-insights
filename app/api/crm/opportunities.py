"""
Opportunities API - Deal pipeline management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Principal, Require, get_current_principal
from app.models.crm import OpportunityStatus
from app.services.crm import OpportunityService
from app.services.crm.opportunity_types import (
    OpportunityFilters,
    OpportunityCreateData,
    OpportunityUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter(prefix="/opportunities", tags=["crm-opportunities"])


def get_opportunity_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> OpportunityService:
    """Create an OpportunityService instance for dependency injection."""
    return OpportunityService(db, principal)


# ============= SCHEMAS =============
class OpportunityBase(BaseModel):
    name: str
    description: Optional[str] = None
    party_id: int
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
    party_id: Optional[int] = None
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

    model_config = ConfigDict(from_attributes=True)


class OpportunityResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    party_id: Optional[int]
    party_name: Optional[str]
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
    created_at: date
    updated_at: date

    model_config = ConfigDict(from_attributes=True)


class OpportunityListResponse(BaseModel):
    items: List[OpportunityResponse]
    total: int
    page: int
    page_size: int


class StageSummaryResponse(BaseModel):
    stage_id: int
    stage_name: str
    color: Optional[str]
    probability: int
    count: int
    value: float


class PipelineSummaryResponse(BaseModel):
    total_opportunities: int
    total_value: float
    weighted_value: float
    won_count: int
    won_value: float
    lost_count: int
    by_stage: List[StageSummaryResponse]
    avg_deal_size: float
    win_rate: float


def _opp_to_response(opp) -> OpportunityResponse:
    """Convert Opportunity model to response."""
    stage_info = None
    if opp.stage_rel:
        stage_info = StageInfo(
            id=opp.stage_rel.id,
            name=opp.stage_rel.name,
            probability=opp.stage_rel.probability,
            color=opp.stage_rel.color,
        )

    party_name = None
    if opp.party:
        party_name = opp.party.name

    return OpportunityResponse(
        id=opp.id,
        name=opp.name,
        description=opp.description,
        party_id=opp.party_id,
        party_name=party_name,
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


# ============= ENDPOINTS =============
@router.get("", response_model=OpportunityListResponse, dependencies=[Depends(Require("crm:read"))])
def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    stage_id: Optional[int] = None,
    party_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """List opportunities with filtering and pagination."""
    filters = OpportunityFilters(
        search=search,
        status=status,
        stage_id=stage_id,
        party_id=party_id,
        owner_id=owner_id,
        min_value=Decimal(str(min_value)) if min_value is not None else None,
        max_value=Decimal(str(max_value)) if max_value is not None else None,
    )
    pagination = PaginationParams(
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    result = service.list_opportunities(filters, pagination)

    return OpportunityListResponse(
        items=[_opp_to_response(o) for o in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/pipeline", response_model=PipelineSummaryResponse, dependencies=[Depends(Require("crm:read"))])
def get_pipeline_summary(
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Get pipeline summary with stage breakdown."""
    summary = service.get_pipeline_summary()

    return PipelineSummaryResponse(
        total_opportunities=summary.total_opportunities,
        total_value=float(summary.total_value),
        weighted_value=float(summary.weighted_value),
        won_count=summary.won_count,
        won_value=float(summary.won_value),
        lost_count=summary.lost_count,
        by_stage=[
            StageSummaryResponse(
                stage_id=s.stage_id,
                stage_name=s.stage_name,
                color=s.color,
                probability=s.probability,
                count=s.count,
                value=float(s.value),
            )
            for s in summary.by_stage
        ],
        avg_deal_size=float(summary.avg_deal_size),
        win_rate=summary.win_rate,
    )


@router.get("/{opp_id}", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:read"))])
def get_opportunity(
    opp_id: int,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Get a single opportunity by ID."""
    try:
        opp = service.get_opportunity(opp_id)
        return _opp_to_response(opp)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:write"))])
def create_opportunity(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Create a new opportunity."""
    try:
        data = OpportunityCreateData(
            name=payload.name,
            description=payload.description,
            party_id=payload.party_id,
            stage_id=payload.stage_id,
            deal_value=Decimal(str(payload.deal_value)),
            probability=payload.probability,
            expected_close_date=payload.expected_close_date,
            owner_id=payload.owner_id,
            sales_person_id=payload.sales_person_id,
            source=payload.source,
            campaign=payload.campaign,
        )
        opp = service.create_opportunity(data)
        db.commit()
        db.refresh(opp)
        return _opp_to_response(opp)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch("/{opp_id}", response_model=OpportunityResponse, dependencies=[Depends(Require("crm:write"))])
def update_opportunity(
    opp_id: int,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Update an opportunity."""
    try:
        data = OpportunityUpdateData(
            name=payload.name,
            description=payload.description,
            party_id=payload.party_id,
            stage_id=payload.stage_id,
            deal_value=Decimal(str(payload.deal_value)) if payload.deal_value is not None else None,
            probability=payload.probability,
            expected_close_date=payload.expected_close_date,
            owner_id=payload.owner_id,
            sales_person_id=payload.sales_person_id,
            source=payload.source,
            campaign=payload.campaign,
        )
        opp = service.update_opportunity(opp_id, data)
        db.commit()
        db.refresh(opp)
        return _opp_to_response(opp)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("/{opp_id}/move-stage", dependencies=[Depends(Require("crm:write"))])
def move_stage(
    opp_id: int,
    stage_id: int,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Move opportunity to a different pipeline stage."""
    try:
        opp = service.move_to_stage(opp_id, stage_id)
        db.commit()
        stage_name = opp.stage_rel.name if opp.stage_rel else "Unknown"
        return {"success": True, "message": f"Moved to stage: {stage_name}"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("/{opp_id}/won", dependencies=[Depends(Require("crm:write"))])
def mark_won(
    opp_id: int,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Mark opportunity as won."""
    try:
        service.mark_won(opp_id)
        db.commit()
        return {"success": True, "message": "Opportunity marked as won"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post("/{opp_id}/lost", dependencies=[Depends(Require("crm:write"))])
def mark_lost(
    opp_id: int,
    reason: Optional[str] = None,
    competitor: Optional[str] = None,
    db: Session = Depends(get_db),
    service: OpportunityService = Depends(get_opportunity_service),
):
    """Mark opportunity as lost."""
    try:
        service.mark_lost(opp_id, reason=reason, competitor=competitor)
        db.commit()
        return {"success": True, "message": "Opportunity marked as lost"}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)

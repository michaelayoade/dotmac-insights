"""
Campaigns API - Marketing campaign management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.services.crm.campaigns import CampaignService
from app.services.crm.campaign_types import (
    CampaignFilters,
    CampaignCreateData,
    CampaignUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter(prefix="/campaigns", tags=["crm-campaigns"])


def get_campaign_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CampaignService:
    """Create a CampaignService instance for dependency injection."""
    return CampaignService(db, principal)


# ============= SCHEMAS =============
class CampaignCreate(BaseModel):
    """Create a new campaign."""

    name: str
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currency: str = "NGN"
    budget: Decimal = Decimal("0")


class CampaignUpdate(BaseModel):
    """Update a campaign."""

    name: Optional[str] = None
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    is_active: Optional[bool] = None


class CampaignResponse(BaseModel):
    """Campaign response."""

    id: int
    name: str
    description: Optional[str]
    campaign_type: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    currency: str
    budget: Decimal
    actual_cost: Decimal
    leads_generated: int
    opportunities_generated: int
    revenue_generated: Decimal
    is_active: bool
    created_at: date
    updated_at: date

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    """Paginated campaign list response."""

    items: List[CampaignResponse]
    total: int
    page: int
    page_size: int


class CampaignROIResponse(BaseModel):
    """Campaign ROI response."""

    campaign_id: int
    campaign_name: str
    budget: Decimal
    actual_cost: Decimal
    revenue_generated: Decimal
    roi_percentage: float
    cost_per_lead: Decimal
    cost_per_opportunity: Decimal


class CampaignPerformanceResponse(BaseModel):
    """Campaign performance response."""

    campaign_id: int
    campaign_name: str
    leads_generated: int
    opportunities_generated: int
    deals_won: int
    revenue_generated: Decimal
    conversion_rate: float
    win_rate: float


class CampaignSummaryResponse(BaseModel):
    """Campaign summary statistics."""

    total_campaigns: int
    active_campaigns: int
    total_budget: Decimal
    total_spent: Decimal
    total_leads: int
    total_opportunities: int
    total_revenue: Decimal
    overall_roi: float
    by_type: dict


class LeadByCampaignResponse(BaseModel):
    """Lead from a campaign."""

    party_id: int
    name: str
    email: Optional[str]
    qualification: Optional[str]
    created_at: date


class OpportunityByCampaignResponse(BaseModel):
    """Opportunity from a campaign."""

    id: int
    name: str
    party_name: Optional[str]
    deal_value: Decimal
    status: str
    created_at: date


def _campaign_to_response(campaign) -> CampaignResponse:
    """Convert Campaign model to response."""
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        currency=campaign.currency,
        budget=campaign.budget or Decimal("0"),
        actual_cost=campaign.actual_cost or Decimal("0"),
        leads_generated=campaign.leads_generated or 0,
        opportunities_generated=campaign.opportunities_generated or 0,
        revenue_generated=campaign.revenue_generated or Decimal("0"),
        is_active=campaign.is_active,
        created_at=campaign.created_at.date() if campaign.created_at else date.today(),
        updated_at=campaign.updated_at.date() if campaign.updated_at else date.today(),
    )


# ============= ENDPOINTS =============
@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    search: Optional[str] = None,
    campaign_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    end_date_from: Optional[date] = None,
    end_date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CampaignService = Depends(get_campaign_service),
):
    """List campaigns with optional filters and pagination."""
    filters = CampaignFilters(
        search=search,
        campaign_type=campaign_type,
        is_active=is_active,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        end_date_from=end_date_from,
        end_date_to=end_date_to,
    )
    pagination = PaginationParams(page=page, page_size=page_size)

    result = service.list_campaigns(filters, pagination)

    return CampaignListResponse(
        items=[_campaign_to_response(c) for c in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Create a new campaign."""
    try:
        create_data = CampaignCreateData(
            name=data.name,
            description=data.description,
            campaign_type=data.campaign_type,
            start_date=data.start_date,
            end_date=data.end_date,
            currency=data.currency,
            budget=data.budget,
        )
        campaign = service.create_campaign(create_data)
        db.commit()
        return _campaign_to_response(campaign)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=CampaignSummaryResponse)
async def get_campaign_summary(
    service: CampaignService = Depends(get_campaign_service),
):
    """Get campaign summary statistics."""
    summary = service.get_campaign_summary()
    return CampaignSummaryResponse(
        total_campaigns=summary.total_campaigns,
        active_campaigns=summary.active_campaigns,
        total_budget=summary.total_budget,
        total_spent=summary.total_spent,
        total_leads=summary.total_leads,
        total_opportunities=summary.total_opportunities,
        total_revenue=summary.total_revenue,
        overall_roi=summary.overall_roi,
        by_type=summary.by_type,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get a campaign by ID."""
    try:
        campaign = service.get_campaign(campaign_id)
        return _campaign_to_response(campaign)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Update a campaign."""
    try:
        update_data = CampaignUpdateData(
            name=data.name,
            description=data.description,
            campaign_type=data.campaign_type,
            start_date=data.start_date,
            end_date=data.end_date,
            budget=data.budget,
            actual_cost=data.actual_cost,
            is_active=data.is_active,
        )
        campaign = service.update_campaign(campaign_id, update_data)
        db.commit()
        return _campaign_to_response(campaign)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Delete a campaign."""
    try:
        service.delete_campaign(campaign_id)
        db.commit()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Activate a campaign."""
    try:
        campaign = service.activate_campaign(campaign_id)
        db.commit()
        return _campaign_to_response(campaign)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Pause a campaign."""
    try:
        campaign = service.pause_campaign(campaign_id)
        db.commit()
        return _campaign_to_response(campaign)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
    db: Session = Depends(get_db),
):
    """Mark a campaign as complete."""
    try:
        campaign = service.complete_campaign(campaign_id)
        db.commit()
        return _campaign_to_response(campaign)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/leads", response_model=List[LeadByCampaignResponse])
async def get_leads_by_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get leads attributed to a campaign."""
    try:
        leads = service.get_leads_by_campaign(campaign_id)
        return [
            LeadByCampaignResponse(
                party_id=lead.party_id,
                name=lead.name,
                email=lead.primary_email,
                qualification=lead.qualification,
                created_at=lead.created_at.date() if hasattr(lead.created_at, 'date') else lead.created_at,
            )
            for lead in leads
        ]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/opportunities", response_model=List[OpportunityByCampaignResponse])
async def get_opportunities_by_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get opportunities attributed to a campaign."""
    try:
        opportunities = service.get_opportunities_by_campaign(campaign_id)
        return [
            OpportunityByCampaignResponse(
                id=opp.id,
                name=opp.name,
                party_name=opp.party.name if opp.party else None,
                deal_value=opp.deal_value or Decimal("0"),
                status=opp.status.value if hasattr(opp.status, 'value') else str(opp.status),
                created_at=opp.created_at.date() if hasattr(opp.created_at, 'date') else opp.created_at,
            )
            for opp in opportunities
        ]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/roi", response_model=CampaignROIResponse)
async def get_campaign_roi(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get ROI analysis for a campaign."""
    try:
        roi = service.get_campaign_roi(campaign_id)
        return CampaignROIResponse(
            campaign_id=roi.campaign_id,
            campaign_name=roi.campaign_name,
            budget=roi.budget,
            actual_cost=roi.actual_cost,
            revenue_generated=roi.revenue_generated,
            roi_percentage=roi.roi_percentage,
            cost_per_lead=roi.cost_per_lead,
            cost_per_opportunity=roi.cost_per_opportunity,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get performance metrics for a campaign."""
    try:
        perf = service.get_campaign_performance(campaign_id)
        return CampaignPerformanceResponse(
            campaign_id=perf.campaign_id,
            campaign_name=perf.campaign_name,
            leads_generated=perf.leads_generated,
            opportunities_generated=perf.opportunities_generated,
            deals_won=perf.deals_won,
            revenue_generated=perf.revenue_generated,
            conversion_rate=perf.conversion_rate,
            win_rate=perf.win_rate,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

"""
Leads API - Party-based lead management

Leads are Party + PartyRole(role="lead") - NOT ERPNextLead.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.services.crm.leads import LeadService
from app.services.crm.lead_types import (
    LeadFilters,
    LeadCreateData,
    LeadUpdateData,
    LeadScoreUpdate,
    LeadConversionData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter(prefix="/leads", tags=["crm-leads"])


def get_lead_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> LeadService:
    """Create a LeadService instance for dependency injection."""
    return LeadService(db, principal)


# ============= SCHEMAS =============
class LeadCreate(BaseModel):
    """Create a new lead (Party + PartyRole)."""

    name: str
    type: str = "person"  # person or organization
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None
    owner_party_id: Optional[int] = None


class LeadUpdate(BaseModel):
    """Update a lead."""

    name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None
    owner_party_id: Optional[int] = None


class LeadScoreUpdateRequest(BaseModel):
    """Update lead score."""

    score: int
    reason: Optional[str] = None


class LeadQualifyRequest(BaseModel):
    """Qualify a lead."""

    qualification: str  # Hot, Warm, Cold, etc.


class LeadDisqualifyRequest(BaseModel):
    """Disqualify a lead."""

    reason: str


class LeadConvertToOpportunityRequest(BaseModel):
    """Convert lead to opportunity."""

    opportunity_name: Optional[str] = None
    deal_value: Optional[float] = None
    stage_id: Optional[int] = None
    expected_close_date: Optional[datetime] = None


class LeadConvertToCustomerRequest(BaseModel):
    """Convert lead to customer."""

    customer_tier: Optional[str] = None
    payment_terms: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead response with Party + PartyRole info."""

    party_id: int
    name: str
    type: str
    primary_email: Optional[str]
    primary_phone: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    notes: Optional[str]
    tags: List[dict]
    custom_fields: dict
    created_at: datetime
    role_id: int
    status: str
    source: Optional[str]
    source_campaign: Optional[str]
    qualification: Optional[str]
    lead_score: Optional[int]
    owner_party_id: Optional[int]
    role_since: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    """Paginated lead list response."""

    items: List[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadSummaryResponse(BaseModel):
    """Lead summary statistics."""

    total_leads: int
    active_leads: int
    qualified_leads: int
    unqualified_leads: int
    converted_leads: int
    avg_score: float
    by_source: dict
    by_qualification: dict


class LeadFunnelResponse(BaseModel):
    """Lead funnel breakdown."""

    new: int
    contacted: int
    qualified: int
    proposal: int
    converted: int
    lost: int


class BulkAssignRequest(BaseModel):
    """Bulk assign leads to owner."""

    lead_ids: List[int]
    owner_id: int


class BulkStatusRequest(BaseModel):
    """Bulk update lead status."""

    lead_ids: List[int]
    status: str


def _lead_to_response(lead) -> LeadResponse:
    """Convert Lead dataclass to response."""
    return LeadResponse(
        party_id=lead.party_id,
        name=lead.name,
        type=lead.type,
        primary_email=lead.primary_email,
        primary_phone=lead.primary_phone,
        first_name=lead.first_name,
        last_name=lead.last_name,
        notes=lead.notes,
        tags=lead.tags or [],
        custom_fields=lead.custom_fields or {},
        created_at=lead.created_at,
        role_id=lead.role_id,
        status=lead.status,
        source=lead.source,
        source_campaign=lead.source_campaign,
        qualification=lead.qualification,
        lead_score=lead.lead_score,
        owner_party_id=lead.owner_party_id,
        role_since=lead.role_since,
    )


# ============= ENDPOINTS =============
@router.get("", response_model=LeadListResponse)
async def list_leads(
    search: Optional[str] = None,
    status: Optional[str] = None,
    qualification: Optional[str] = None,
    source: Optional[str] = None,
    source_campaign: Optional[str] = None,
    owner_id: Optional[int] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: LeadService = Depends(get_lead_service),
):
    """List leads with optional filters and pagination."""
    filters = LeadFilters(
        search=search,
        status=status,
        qualification=qualification,
        source=source,
        source_campaign=source_campaign,
        owner_id=owner_id,
        min_score=min_score,
        max_score=max_score,
    )
    pagination = PaginationParams(page=page, page_size=page_size)

    result = service.list_leads(filters, pagination)

    return LeadListResponse(
        items=[_lead_to_response(lead) for lead in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(
    data: LeadCreate,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Create a new lead (Party + PartyRole)."""
    try:
        create_data = LeadCreateData(
            name=data.name,
            type=data.type,
            primary_email=data.primary_email,
            primary_phone=data.primary_phone,
            first_name=data.first_name,
            last_name=data.last_name,
            legal_name=data.legal_name,
            trading_name=data.trading_name,
            notes=data.notes,
            source=data.source,
            source_campaign=data.source_campaign,
            qualification=data.qualification,
            lead_score=data.lead_score,
            owner_party_id=data.owner_party_id,
        )
        lead = service.create_lead(create_data)
        db.commit()
        return _lead_to_response(lead)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=LeadSummaryResponse)
async def get_lead_summary(
    service: LeadService = Depends(get_lead_service),
):
    """Get lead summary statistics."""
    summary = service.get_lead_summary()
    return LeadSummaryResponse(
        total_leads=summary.total_leads,
        active_leads=summary.active_leads,
        qualified_leads=summary.qualified_leads,
        unqualified_leads=summary.unqualified_leads,
        converted_leads=summary.converted_leads,
        avg_score=summary.avg_score,
        by_source=summary.by_source,
        by_qualification=summary.by_qualification,
    )


@router.get("/funnel", response_model=LeadFunnelResponse)
async def get_lead_funnel(
    service: LeadService = Depends(get_lead_service),
):
    """Get lead funnel breakdown."""
    funnel = service.get_lead_funnel()
    return LeadFunnelResponse(
        new=funnel.new,
        contacted=funnel.contacted,
        qualified=funnel.qualified,
        proposal=funnel.proposal,
        converted=funnel.converted,
        lost=funnel.lost,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    service: LeadService = Depends(get_lead_service),
):
    """Get a lead by party ID."""
    try:
        lead = service.get_lead(lead_id)
        return _lead_to_response(lead)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    data: LeadUpdate,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Update a lead."""
    try:
        update_data = LeadUpdateData(
            name=data.name,
            primary_email=data.primary_email,
            primary_phone=data.primary_phone,
            first_name=data.first_name,
            last_name=data.last_name,
            notes=data.notes,
            status=data.status,
            source=data.source,
            source_campaign=data.source_campaign,
            qualification=data.qualification,
            lead_score=data.lead_score,
            owner_party_id=data.owner_party_id,
        )
        lead = service.update_lead(lead_id, update_data)
        db.commit()
        return _lead_to_response(lead)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: int,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Delete a lead (deactivates the lead role)."""
    try:
        service.delete_lead(lead_id)
        db.commit()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{lead_id}/score", response_model=LeadResponse)
async def update_lead_score(
    lead_id: int,
    data: LeadScoreUpdateRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Update lead score."""
    try:
        lead = service.update_score(lead_id, data.score, data.reason)
        db.commit()
        return _lead_to_response(lead)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{lead_id}/qualify", response_model=LeadResponse)
async def qualify_lead(
    lead_id: int,
    data: LeadQualifyRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Qualify a lead."""
    try:
        lead = service.qualify_lead(lead_id, data.qualification)
        db.commit()
        return _lead_to_response(lead)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{lead_id}/disqualify", response_model=LeadResponse)
async def disqualify_lead(
    lead_id: int,
    data: LeadDisqualifyRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Disqualify a lead."""
    try:
        lead = service.disqualify_lead(lead_id, data.reason)
        db.commit()
        return _lead_to_response(lead)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{lead_id}/convert/opportunity")
async def convert_to_opportunity(
    lead_id: int,
    data: LeadConvertToOpportunityRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Convert lead to opportunity."""
    try:
        conversion_data = LeadConversionData(
            opportunity_name=data.opportunity_name,
            deal_value=data.deal_value,
            stage_id=data.stage_id,
            expected_close_date=data.expected_close_date,
        )
        opportunity = service.convert_to_opportunity(lead_id, conversion_data)
        db.commit()
        return {"id": opportunity.id, "name": opportunity.name}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{lead_id}/convert/customer")
async def convert_to_customer(
    lead_id: int,
    data: LeadConvertToCustomerRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Convert lead to customer."""
    try:
        party = service.convert_to_customer(lead_id)
        db.commit()
        return {"id": party.id, "name": party.name}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk/assign")
async def bulk_assign_leads(
    data: BulkAssignRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Bulk assign leads to an owner."""
    try:
        count = service.bulk_assign(data.lead_ids, data.owner_id)
        db.commit()
        return {"assigned": count}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk/status")
async def bulk_update_status(
    data: BulkStatusRequest,
    service: LeadService = Depends(get_lead_service),
    db: Session = Depends(get_db),
):
    """Bulk update lead status."""
    try:
        count = service.bulk_update_status(data.lead_ids, data.status)
        db.commit()
        return {"updated": count}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Leads API - Lead management and conversion
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.sales import ERPNextLead, ERPNextLeadStatus
from app.models.customer import Customer, CustomerStatus, CustomerType
from app.models.crm import Opportunity, OpportunityStatus, Contact

router = APIRouter(prefix="/leads", tags=["crm-leads"])


# ============= SCHEMAS =============
class LeadBase(BaseModel):
    lead_name: str
    company_name: Optional[str] = None
    email_id: Optional[str] = None
    phone: Optional[str] = None
    mobile_no: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None
    lead_owner: Optional[str] = None
    territory: Optional[str] = None
    industry: Optional[str] = None
    market_segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    lead_name: Optional[str] = None
    company_name: Optional[str] = None
    email_id: Optional[str] = None
    phone: Optional[str] = None
    mobile_no: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None
    lead_owner: Optional[str] = None
    territory: Optional[str] = None
    industry: Optional[str] = None
    market_segment: Optional[str] = None
    status: Optional[str] = None
    qualification_status: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


class LeadResponse(LeadBase):
    id: int
    status: str
    qualification_status: Optional[str]
    converted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadConvertRequest(BaseModel):
    customer_name: Optional[str] = None
    customer_type: str = "business"
    create_opportunity: bool = False
    opportunity_name: Optional[str] = None
    deal_value: Optional[float] = None


class LeadSummaryResponse(BaseModel):
    total_leads: int
    new_leads: int
    qualified_leads: int
    converted_leads: int
    lost_leads: int
    by_status: dict
    by_source: dict


# ============= ENDPOINTS =============
@router.get("", response_model=LeadListResponse, dependencies=[Depends(Require("crm:read"))])
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    territory: Optional[str] = None,
    converted: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all leads with filtering and pagination."""
    query = db.query(ERPNextLead)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ERPNextLead.lead_name.ilike(search_term),
                ERPNextLead.company_name.ilike(search_term),
                ERPNextLead.email_id.ilike(search_term),
            )
        )

    if status:
        try:
            status_enum = ERPNextLeadStatus(status.lower())
            query = query.filter(ERPNextLead.status == status_enum)
        except ValueError:
            pass

    if source:
        query = query.filter(ERPNextLead.source == source)

    if territory:
        query = query.filter(ERPNextLead.territory == territory)

    if converted is not None:
        query = query.filter(ERPNextLead.converted == converted)

    total = query.count()
    leads = query.order_by(ERPNextLead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return LeadListResponse(
        items=[LeadResponse(
            id=l.id,
            lead_name=l.lead_name,
            company_name=l.company_name,
            email_id=l.email_id,
            phone=l.phone,
            mobile_no=l.mobile_no,
            website=l.website,
            source=l.source,
            lead_owner=l.lead_owner,
            territory=l.territory,
            industry=l.industry,
            market_segment=l.market_segment,
            city=l.city,
            state=l.state,
            country=l.country,
            notes=l.notes,
            status=l.status.value if l.status else "lead",
            qualification_status=l.qualification_status,
            converted=l.converted,
            created_at=l.created_at,
            updated_at=l.updated_at,
        ) for l in leads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=LeadSummaryResponse, dependencies=[Depends(Require("crm:read"))])
async def get_leads_summary(db: Session = Depends(get_db)):
    """Get lead summary statistics."""
    total = db.query(func.count(ERPNextLead.id)).scalar() or 0
    new_leads = db.query(func.count(ERPNextLead.id)).filter(ERPNextLead.status == ERPNextLeadStatus.LEAD).scalar() or 0
    qualified = db.query(func.count(ERPNextLead.id)).filter(ERPNextLead.status == ERPNextLeadStatus.OPPORTUNITY).scalar() or 0
    converted = db.query(func.count(ERPNextLead.id)).filter(ERPNextLead.converted == True).scalar() or 0
    lost = db.query(func.count(ERPNextLead.id)).filter(ERPNextLead.status == ERPNextLeadStatus.DO_NOT_CONTACT).scalar() or 0

    # By status
    status_counts = db.query(
        ERPNextLead.status,
        func.count(ERPNextLead.id)
    ).group_by(ERPNextLead.status).all()
    by_status = {s.value if s else "unknown": c for s, c in status_counts}

    # By source
    source_counts = db.query(
        ERPNextLead.source,
        func.count(ERPNextLead.id)
    ).filter(ERPNextLead.source.isnot(None)).group_by(ERPNextLead.source).all()
    by_source = {s or "Unknown": c for s, c in source_counts}

    return LeadSummaryResponse(
        total_leads=total,
        new_leads=new_leads,
        qualified_leads=qualified,
        converted_leads=converted,
        lost_leads=lost,
        by_status=by_status,
        by_source=by_source,
    )


@router.get("/{lead_id}", response_model=LeadResponse, dependencies=[Depends(Require("crm:read"))])
async def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Get a single lead by ID."""
    lead = db.query(ERPNextLead).filter(ERPNextLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return LeadResponse(
        id=lead.id,
        lead_name=lead.lead_name,
        company_name=lead.company_name,
        email_id=lead.email_id,
        phone=lead.phone,
        mobile_no=lead.mobile_no,
        website=lead.website,
        source=lead.source,
        lead_owner=lead.lead_owner,
        territory=lead.territory,
        industry=lead.industry,
        market_segment=lead.market_segment,
        city=lead.city,
        state=lead.state,
        country=lead.country,
        notes=lead.notes,
        status=lead.status.value if lead.status else "lead",
        qualification_status=lead.qualification_status,
        converted=lead.converted,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.post("", response_model=LeadResponse, dependencies=[Depends(Require("crm:write"))])
async def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    """Create a new lead."""
    lead = ERPNextLead(
        lead_name=payload.lead_name,
        company_name=payload.company_name,
        email_id=payload.email_id,
        phone=payload.phone,
        mobile_no=payload.mobile_no,
        website=payload.website,
        source=payload.source,
        lead_owner=payload.lead_owner,
        territory=payload.territory,
        industry=payload.industry,
        market_segment=payload.market_segment,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        notes=payload.notes,
        status=ERPNextLeadStatus.LEAD,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    return LeadResponse(
        id=lead.id,
        lead_name=lead.lead_name,
        company_name=lead.company_name,
        email_id=lead.email_id,
        phone=lead.phone,
        mobile_no=lead.mobile_no,
        website=lead.website,
        source=lead.source,
        lead_owner=lead.lead_owner,
        territory=lead.territory,
        industry=lead.industry,
        market_segment=lead.market_segment,
        city=lead.city,
        state=lead.state,
        country=lead.country,
        notes=lead.notes,
        status=lead.status.value,
        qualification_status=lead.qualification_status,
        converted=lead.converted,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.patch("/{lead_id}", response_model=LeadResponse, dependencies=[Depends(Require("crm:write"))])
async def update_lead(lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db)):
    """Update a lead."""
    lead = db.query(ERPNextLead).filter(ERPNextLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "status" in update_data:
        try:
            update_data["status"] = ERPNextLeadStatus(update_data["status"].lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    for key, value in update_data.items():
        setattr(lead, key, value)

    db.commit()
    db.refresh(lead)

    return LeadResponse(
        id=lead.id,
        lead_name=lead.lead_name,
        company_name=lead.company_name,
        email_id=lead.email_id,
        phone=lead.phone,
        mobile_no=lead.mobile_no,
        website=lead.website,
        source=lead.source,
        lead_owner=lead.lead_owner,
        territory=lead.territory,
        industry=lead.industry,
        market_segment=lead.market_segment,
        city=lead.city,
        state=lead.state,
        country=lead.country,
        notes=lead.notes,
        status=lead.status.value if lead.status else "lead",
        qualification_status=lead.qualification_status,
        converted=lead.converted,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.post("/{lead_id}/convert", dependencies=[Depends(Require("crm:write"))])
async def convert_lead(lead_id: int, payload: LeadConvertRequest, db: Session = Depends(get_db)):
    """Convert a lead to a customer (and optionally create an opportunity)."""
    lead = db.query(ERPNextLead).filter(ERPNextLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.converted:
        raise HTTPException(status_code=400, detail="Lead already converted")

    # Create customer
    customer_type = CustomerType.BUSINESS
    if payload.customer_type == "residential":
        customer_type = CustomerType.RESIDENTIAL
    elif payload.customer_type == "enterprise":
        customer_type = CustomerType.ENTERPRISE

    customer = Customer(
        name=payload.customer_name or lead.company_name or lead.lead_name,
        email=lead.email_id,
        phone=lead.phone or lead.mobile_no,
        city=lead.city,
        state=lead.state,
        country=lead.country or "Nigeria",
        customer_type=customer_type,
        status=CustomerStatus.ACTIVE,
        notes=lead.notes,
        conversion_date=datetime.utcnow(),
    )
    db.add(customer)
    db.flush()

    # Create primary contact
    contact = Contact(
        customer_id=customer.id,
        first_name=lead.lead_name.split()[0] if lead.lead_name else "Contact",
        last_name=" ".join(lead.lead_name.split()[1:]) if lead.lead_name and len(lead.lead_name.split()) > 1 else None,
        full_name=lead.lead_name,
        email=lead.email_id,
        phone=lead.phone,
        mobile=lead.mobile_no,
        is_primary=True,
    )
    db.add(contact)

    # Optionally create opportunity
    opportunity_id = None
    if payload.create_opportunity:
        opportunity = Opportunity(
            name=payload.opportunity_name or f"Opportunity from {lead.lead_name}",
            customer_id=customer.id,
            lead_id=lead.id,
            deal_value=Decimal(str(payload.deal_value or 0)),
            probability=20,
            source=lead.source,
            status=OpportunityStatus.OPEN,
        )
        opportunity.update_weighted_value()
        db.add(opportunity)
        db.flush()
        opportunity_id = opportunity.id

    # Mark lead as converted
    lead.converted = True
    lead.status = ERPNextLeadStatus.CONVERTED

    db.commit()

    return {
        "success": True,
        "customer_id": customer.id,
        "contact_id": contact.id,
        "opportunity_id": opportunity_id,
        "message": f"Lead converted to customer: {customer.name}",
    }


@router.post("/{lead_id}/qualify", dependencies=[Depends(Require("crm:write"))])
async def qualify_lead(lead_id: int, db: Session = Depends(get_db)):
    """Mark a lead as qualified (opportunity stage)."""
    lead = db.query(ERPNextLead).filter(ERPNextLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = ERPNextLeadStatus.OPPORTUNITY
    lead.qualification_status = "qualified"
    db.commit()

    return {"success": True, "message": "Lead qualified"}


@router.post("/{lead_id}/disqualify", dependencies=[Depends(Require("crm:write"))])
async def disqualify_lead(lead_id: int, reason: Optional[str] = None, db: Session = Depends(get_db)):
    """Mark a lead as disqualified."""
    lead = db.query(ERPNextLead).filter(ERPNextLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = ERPNextLeadStatus.DO_NOT_CONTACT
    lead.qualification_status = "disqualified"
    if reason:
        lead.notes = f"{lead.notes or ''}\n\nDisqualification reason: {reason}".strip()
    db.commit()

    return {"success": True, "message": "Lead disqualified"}

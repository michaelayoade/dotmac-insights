"""
CRM Contact CRUD Endpoints

Consolidated contact management for all contact types:
- Lead, Prospect, Customer, Churned, Person
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.contact import (
    Contact, ContactType, ContactCategory, ContactStatus,
    BillingType, LeadQualification
)
from app.auth import Require
from .schemas import (
    ContactCreate, ContactUpdate, ContactResponse,
    ContactSummary, ContactListResponse, PersonContactResponse,
    ContactTypeEnum, ContactCategoryEnum, ContactStatusEnum, LeadQualificationEnum,
    BillingTypeEnum
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _contact_to_summary(contact: Contact) -> ContactSummary:
    """Convert Contact to summary response."""
    return ContactSummary(
        id=contact.id,
        contact_type=ContactTypeEnum(contact.contact_type.value),
        category=ContactCategoryEnum(contact.category.value),
        status=ContactStatusEnum(contact.status.value),
        is_organization=contact.is_organization,
        is_primary_contact=contact.is_primary_contact,
        is_billing_contact=contact.is_billing_contact,
        is_decision_maker=contact.is_decision_maker,
        designation=contact.designation,
        department=contact.department,
        name=contact.name,
        company_name=contact.company_name,
        email=contact.email,
        phone=contact.phone,
        mobile=contact.mobile,
        website=contact.website,
        city=contact.city,
        state=contact.state,
        territory=contact.territory,
        owner_id=contact.owner_id,
        lead_qualification=LeadQualificationEnum(contact.lead_qualification.value) if contact.lead_qualification else None,
        lead_score=contact.lead_score,
        source=contact.source,
        mrr=contact.mrr,
        outstanding_balance=contact.outstanding_balance,
        last_contact_date=contact.last_contact_date,
        cancellation_date=contact.cancellation_date,
        churn_reason=contact.churn_reason,
        tags=contact.tags,
        created_at=contact.created_at,
    )


def _contact_to_response(contact: Contact) -> ContactResponse:
    """Convert Contact to full response."""
    return ContactResponse(
        id=contact.id,
        contact_type=ContactTypeEnum(contact.contact_type.value),
        category=ContactCategoryEnum(contact.category.value),
        status=ContactStatusEnum(contact.status.value),
        parent_id=contact.parent_id,
        is_organization=contact.is_organization,
        is_primary_contact=contact.is_primary_contact,
        is_billing_contact=contact.is_billing_contact,
        is_decision_maker=contact.is_decision_maker,
        designation=contact.designation,
        department=contact.department,
        name=contact.name,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company_name=contact.company_name,
        full_name=contact.full_name,
        email=contact.email,
        email_secondary=contact.email_secondary,
        billing_email=contact.billing_email,
        phone=contact.phone,
        phone_secondary=contact.phone_secondary,
        mobile=contact.mobile,
        website=contact.website,
        linkedin_url=contact.linkedin_url,
        address_line1=contact.address_line1,
        address_line2=contact.address_line2,
        city=contact.city,
        state=contact.state,
        postal_code=contact.postal_code,
        country=contact.country,
        latitude=contact.latitude,
        longitude=contact.longitude,
        erpnext_id=contact.erpnext_id,
        zoho_id=contact.zoho_id,
        account_number=contact.account_number,
        contract_number=contact.contract_number,
        billing_type=BillingTypeEnum(contact.billing_type.value) if contact.billing_type else None,
        mrr=contact.mrr,
        total_revenue=contact.total_revenue,
        outstanding_balance=contact.outstanding_balance,
        credit_limit=contact.credit_limit,
        deposit_balance=contact.deposit_balance,
        lead_qualification=LeadQualificationEnum(contact.lead_qualification.value) if contact.lead_qualification else None,
        lead_score=contact.lead_score,
        source=contact.source,
        source_campaign=contact.source_campaign,
        territory=contact.territory,
        owner_id=contact.owner_id,
        sales_person=contact.sales_person,
        account_manager=contact.account_manager,
        first_contact_date=contact.first_contact_date,
        last_contact_date=contact.last_contact_date,
        qualified_date=contact.qualified_date,
        conversion_date=contact.conversion_date,
        signup_date=contact.signup_date,
        activation_date=contact.activation_date,
        cancellation_date=contact.cancellation_date,
        churn_reason=contact.churn_reason,
        email_opt_in=contact.email_opt_in,
        sms_opt_in=contact.sms_opt_in,
        whatsapp_opt_in=contact.whatsapp_opt_in,
        phone_opt_in=contact.phone_opt_in,
        preferred_language=contact.preferred_language,
        preferred_channel=contact.preferred_channel,
        tags=contact.tags,
        custom_fields=contact.custom_fields,
        notes=contact.notes,
        total_conversations=contact.total_conversations,
        total_tickets=contact.total_tickets,
        total_orders=contact.total_orders,
        total_invoices=contact.total_invoices,
        nps_score=contact.nps_score,
        satisfaction_score=contact.satisfaction_score,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


# =============================================================================
# LIST ENDPOINTS
# =============================================================================

@router.get(
    "/",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("crm:read"))],
)
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    contact_type: Optional[ContactTypeEnum] = None,
    category: Optional[ContactCategoryEnum] = None,
    status: Optional[ContactStatusEnum] = None,
    qualification: Optional[LeadQualificationEnum] = None,
    owner_id: Optional[int] = None,
    territory: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    source: Optional[str] = None,
    is_organization: Optional[bool] = None,
    has_outstanding: Optional[bool] = None,
    tag: Optional[str] = None,
    quality_issue: Optional[str] = Query(None, description="Filter by quality issue: missing_email, missing_phone, missing_address, missing_name, missing_company, invalid_email"),
    sort_by: str = Query("created_at", pattern="^(name|created_at|last_contact_date|mrr|lead_score)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """
    List contacts with filtering and pagination.

    Filter Options:
    - contact_type: lead, prospect, customer, churned, person
    - category: residential, business, enterprise, government, non_profit
    - status: active, inactive, suspended, do_not_contact
    - qualification: unqualified, cold, warm, hot, qualified
    - owner_id: Filter by assigned owner
    - territory, city, state: Location filters
    - source: Lead source
    - is_organization: True for orgs, False for individuals
    - has_outstanding: True to filter contacts with outstanding balance
    - tag: Filter by tag
    - quality_issue: Filter by data quality issue
    """
    query = db.query(Contact)

    # Text search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(search_term),
                Contact.company_name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.phone.ilike(search_term),
                Contact.account_number.ilike(search_term),
            )
        )

    # Type filters
    if contact_type:
        query = query.filter(Contact.contact_type == ContactType(contact_type.value))
    if category:
        query = query.filter(Contact.category == ContactCategory(category.value))
    if status:
        query = query.filter(Contact.status == ContactStatus(status.value))
    if qualification:
        query = query.filter(Contact.lead_qualification == LeadQualification(qualification.value))

    # Assignment filters
    if owner_id is not None:
        query = query.filter(Contact.owner_id == owner_id)

    # Location filters
    if territory:
        query = query.filter(Contact.territory == territory)
    if city:
        query = query.filter(Contact.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(Contact.state.ilike(f"%{state}%"))

    # Source filter
    if source:
        query = query.filter(Contact.source == source)

    # Organization filter
    if is_organization is not None:
        query = query.filter(Contact.is_organization == is_organization)

    # Outstanding balance filter
    if has_outstanding is True:
        query = query.filter(Contact.outstanding_balance > 0)

    # Tag filter
    if tag:
        query = query.filter(Contact.tags.contains([tag]))

    # Quality issue filter
    if quality_issue:
        if quality_issue == "missing_email":
            query = query.filter(or_(
                Contact.email.is_(None),
                Contact.email == ""
            ))
        elif quality_issue == "missing_phone":
            query = query.filter(and_(
                or_(Contact.phone.is_(None), Contact.phone == ""),
                or_(Contact.mobile.is_(None), Contact.mobile == "")
            ))
        elif quality_issue == "missing_address":
            query = query.filter(and_(
                or_(Contact.address_line1.is_(None), Contact.address_line1 == ""),
                or_(Contact.city.is_(None), Contact.city == "")
            ))
        elif quality_issue == "missing_name":
            query = query.filter(or_(
                Contact.name.is_(None),
                Contact.name == ""
            ))
        elif quality_issue == "missing_company":
            query = query.filter(
                Contact.is_organization == True,
                or_(
                    Contact.company_name.is_(None),
                    Contact.company_name == ""
                )
            )
        elif quality_issue == "invalid_email":
            query = query.filter(
                Contact.email.isnot(None),
                Contact.email != "",
                or_(
                    ~Contact.email.contains("@"),
                    ~Contact.email.contains(".")
                )
            )

    # Count total
    total = query.count()

    # Sorting
    sort_column = getattr(Contact, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Pagination
    offset = (page - 1) * page_size
    contacts = query.offset(offset).limit(page_size).all()

    return ContactListResponse(
        data=[_contact_to_summary(c) for c in contacts],
        total=total,
        limit=page_size,
        offset=offset,
    )


@router.get(
    "/leads",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("crm:read"))],
)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    qualification: Optional[LeadQualificationEnum] = None,
    owner_id: Optional[int] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all leads (contact_type=lead or prospect)."""
    query = db.query(Contact).filter(
        Contact.contact_type.in_([ContactType.LEAD, ContactType.PROSPECT])
    )

    if qualification:
        query = query.filter(Contact.lead_qualification == LeadQualification(qualification.value))
    if owner_id:
        query = query.filter(Contact.owner_id == owner_id)
    if source:
        query = query.filter(Contact.source == source)

    total = query.count()
    offset = (page - 1) * page_size
    contacts = query.order_by(Contact.lead_score.desc().nullslast(), Contact.created_at.desc()).offset(offset).limit(page_size).all()

    return ContactListResponse(
        data=[_contact_to_summary(c) for c in contacts],
        total=total,
        limit=page_size,
        offset=offset,
    )


@router.get(
    "/customers",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("crm:read"))],
)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ContactStatusEnum] = None,
    category: Optional[ContactCategoryEnum] = None,
    territory: Optional[str] = None,
    has_outstanding: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all customers (contact_type=customer)."""
    query = db.query(Contact).filter(
        Contact.contact_type == ContactType.CUSTOMER
    )

    if status:
        query = query.filter(Contact.status == ContactStatus(status.value))
    if category:
        query = query.filter(Contact.category == ContactCategory(category.value))
    if territory:
        query = query.filter(Contact.territory == territory)
    if has_outstanding is True:
        query = query.filter(Contact.outstanding_balance > 0)

    total = query.count()
    offset = (page - 1) * page_size
    contacts = query.order_by(Contact.name).offset(offset).limit(page_size).all()

    return ContactListResponse(
        data=[_contact_to_summary(c) for c in contacts],
        total=total,
        limit=page_size,
        offset=offset,
    )


@router.get(
    "/organizations",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("crm:read"))],
)
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    contact_type: Optional[ContactTypeEnum] = None,
    db: Session = Depends(get_db),
):
    """List all organization contacts."""
    query = db.query(Contact).filter(Contact.is_organization == True)

    if contact_type:
        query = query.filter(Contact.contact_type == ContactType(contact_type.value))

    total = query.count()
    offset = (page - 1) * page_size
    contacts = query.order_by(Contact.name).offset(offset).limit(page_size).all()

    return ContactListResponse(
        data=[_contact_to_summary(c) for c in contacts],
        total=total,
        limit=page_size,
        offset=offset,
    )


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    dependencies=[Depends(Require("crm:read"))],
)
async def get_contact(contact_id: int, db: Session = Depends(get_db)):
    """Get a single contact by ID."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _contact_to_response(contact)


@router.get(
    "/{contact_id}/persons",
    response_model=List[PersonContactResponse],
    dependencies=[Depends(Require("crm:read"))],
)
async def get_contact_persons(contact_id: int, db: Session = Depends(get_db)):
    """Get all person contacts associated with an organization."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if not contact.is_organization:
        raise HTTPException(status_code=400, detail="Contact is not an organization")

    persons = db.query(Contact).filter(
        Contact.parent_id == contact_id,
        Contact.contact_type == ContactType.PERSON
    ).order_by(Contact.is_primary_contact.desc(), Contact.name).all()

    return [
        PersonContactResponse(
            id=p.id,
            name=p.name,
            first_name=p.first_name,
            last_name=p.last_name,
            email=p.email,
            phone=p.phone,
            mobile=p.mobile,
            designation=p.designation,
            department=p.department,
            is_primary_contact=p.is_primary_contact,
            is_billing_contact=p.is_billing_contact,
            is_decision_maker=p.is_decision_maker,
        )
        for p in persons
    ]


@router.post(
    "/",
    response_model=ContactResponse,
    status_code=201,
    dependencies=[Depends(Require("crm:write"))],
)
async def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    """Create a new contact."""
    # Validate person contacts have parent
    if payload.contact_type == ContactTypeEnum.PERSON and not payload.parent_id:
        raise HTTPException(status_code=400, detail="Person contacts must have a parent_id")

    # Validate parent exists and is organization
    if payload.parent_id:
        parent = db.query(Contact).filter(Contact.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent contact not found")
        if not parent.is_organization:
            raise HTTPException(status_code=400, detail="Parent contact must be an organization")

    contact = Contact(
        contact_type=ContactType(payload.contact_type.value),
        category=ContactCategory(payload.category.value),
        status=ContactStatus(payload.status.value),
        parent_id=payload.parent_id,
        is_organization=payload.is_organization,
        is_primary_contact=payload.is_primary_contact,
        is_billing_contact=payload.is_billing_contact,
        is_decision_maker=payload.is_decision_maker,
        designation=payload.designation,
        department=payload.department,
        name=payload.name,
        first_name=payload.first_name,
        last_name=payload.last_name,
        company_name=payload.company_name,
        email=payload.email,
        email_secondary=payload.email_secondary,
        billing_email=payload.billing_email,
        phone=payload.phone,
        phone_secondary=payload.phone_secondary,
        mobile=payload.mobile,
        website=payload.website,
        linkedin_url=payload.linkedin_url,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        gps_raw=payload.gps_raw,
        erpnext_id=payload.erpnext_id,
        zoho_id=payload.zoho_id,
        account_number=payload.account_number,
        contract_number=payload.contract_number,
        vat_id=payload.vat_id,
        billing_type=BillingType(payload.billing_type.value) if payload.billing_type else None,
        mrr=payload.mrr,
        credit_limit=payload.credit_limit,
        lead_qualification=LeadQualification(payload.lead_qualification.value) if payload.lead_qualification else None,
        lead_score=payload.lead_score,
        source=payload.source,
        source_campaign=payload.source_campaign,
        referrer=payload.referrer,
        industry=payload.industry,
        market_segment=payload.market_segment,
        territory=payload.territory,
        owner_id=payload.owner_id,
        sales_person=payload.sales_person,
        account_manager=payload.account_manager,
        email_opt_in=payload.email_opt_in,
        sms_opt_in=payload.sms_opt_in,
        whatsapp_opt_in=payload.whatsapp_opt_in,
        phone_opt_in=payload.phone_opt_in,
        preferred_language=payload.preferred_language,
        preferred_channel=payload.preferred_channel,
        tags=payload.tags,
        custom_fields=payload.custom_fields,
        notes=payload.notes,
        first_contact_date=datetime.utcnow(),
    )

    # If primary contact, unmark other primary contacts for same parent
    if payload.is_primary_contact and payload.parent_id:
        db.query(Contact).filter(
            Contact.parent_id == payload.parent_id,
            Contact.is_primary_contact == True
        ).update({"is_primary_contact": False})

    db.add(contact)
    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.patch(
    "/{contact_id}",
    response_model=ContactResponse,
    dependencies=[Depends(Require("crm:write"))],
)
async def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    """Update a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle enum conversions
    if "contact_type" in update_data and update_data["contact_type"]:
        update_data["contact_type"] = ContactType(update_data["contact_type"].value)
    if "category" in update_data and update_data["category"]:
        update_data["category"] = ContactCategory(update_data["category"].value)
    if "status" in update_data and update_data["status"]:
        update_data["status"] = ContactStatus(update_data["status"].value)
    if "billing_type" in update_data and update_data["billing_type"]:
        update_data["billing_type"] = BillingType(update_data["billing_type"].value)
    if "lead_qualification" in update_data and update_data["lead_qualification"]:
        update_data["lead_qualification"] = LeadQualification(update_data["lead_qualification"].value)

    # If marking as primary, unmark others
    if update_data.get("is_primary_contact") and contact.parent_id:
        db.query(Contact).filter(
            Contact.parent_id == contact.parent_id,
            Contact.id != contact_id,
            Contact.is_primary_contact == True
        ).update({"is_primary_contact": False})

    for key, value in update_data.items():
        setattr(contact, key, value)

    contact.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.delete(
    "/{contact_id}",
    dependencies=[Depends(Require("crm:write"))],
)
async def delete_contact(contact_id: int, hard: bool = False, db: Session = Depends(get_db)):
    """
    Delete a contact.

    By default, soft-deletes by setting status to inactive.
    Use hard=true for permanent deletion (cascades to child contacts).
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if hard:
        # Hard delete - also delete child contacts
        db.query(Contact).filter(Contact.parent_id == contact_id).delete()
        db.delete(contact)
        db.commit()
        return {"success": True, "message": "Contact permanently deleted"}

    # Soft delete
    contact.status = ContactStatus.INACTIVE
    db.commit()
    return {"success": True, "message": "Contact deactivated"}


# =============================================================================
# SEARCH ENDPOINT
# =============================================================================

@router.get(
    "/search/full-text",
    dependencies=[Depends(Require("crm:read"))],
)
async def full_text_search(
    q: str = Query(..., min_length=2),
    contact_type: Optional[ContactTypeEnum] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Full-text search across contacts using PostgreSQL tsvector.

    Searches: name, company_name, email, phone, account_number, notes
    """
    query = db.query(Contact)

    # Use full-text search
    search_query = text("""
        search_vector @@ plainto_tsquery('english', :search)
    """)
    query = query.filter(search_query).params(search=q)

    if contact_type:
        query = query.filter(Contact.contact_type == ContactType(contact_type.value))

    # Order by relevance
    rank_query = text("""
        ts_rank(search_vector, plainto_tsquery('english', :search)) DESC
    """)
    contacts = query.order_by(rank_query).params(search=q).limit(limit).all()

    return {
        "query": q,
        "count": len(contacts),
        "results": [_contact_to_summary(c) for c in contacts],
    }

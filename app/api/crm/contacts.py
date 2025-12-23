"""
Contacts API - Multiple contacts per customer/lead
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.crm import Contact

router = APIRouter(prefix="/contacts", tags=["crm-contacts"])


# ============= SCHEMAS =============
class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    is_primary: bool = False
    is_billing_contact: bool = False
    is_decision_maker: bool = False
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    is_primary: Optional[bool] = None
    is_billing_contact: Optional[bool] = None
    is_decision_maker: Optional[bool] = None
    is_active: Optional[bool] = None
    unsubscribed: Optional[bool] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: int
    customer_id: Optional[int]
    lead_id: Optional[int]
    first_name: str
    last_name: Optional[str]
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    designation: Optional[str]
    department: Optional[str]
    is_primary: bool
    is_billing_contact: bool
    is_decision_maker: bool
    is_active: bool
    unsubscribed: bool
    linkedin_url: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactListResponse(BaseModel):
    items: List[ContactResponse]
    total: int
    page: int
    page_size: int


# ============= ENDPOINTS =============
@router.get("", response_model=ContactListResponse, dependencies=[Depends(Require("crm:read"))])
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    is_primary: Optional[bool] = None,
    is_decision_maker: Optional[bool] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
):
    """List contacts with filtering and pagination."""
    query = db.query(Contact)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Contact.full_name.ilike(search_term),
                Contact.email.ilike(search_term),
            )
        )

    if customer_id:
        query = query.filter(Contact.customer_id == customer_id)

    if lead_id:
        query = query.filter(Contact.lead_id == lead_id)

    if is_primary is not None:
        query = query.filter(Contact.is_primary == is_primary)

    if is_decision_maker is not None:
        query = query.filter(Contact.is_decision_maker == is_decision_maker)

    if is_active is not None:
        query = query.filter(Contact.is_active == is_active)

    total = query.count()
    contacts = query.order_by(Contact.is_primary.desc(), Contact.full_name).offset((page - 1) * page_size).limit(page_size).all()

    return ContactListResponse(
        items=[_contact_to_response(c) for c in contacts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/by-customer/{customer_id}", dependencies=[Depends(Require("crm:read"))])
async def get_customer_contacts(customer_id: int, db: Session = Depends(get_db)):
    """Get all contacts for a customer."""
    contacts = db.query(Contact).filter(
        Contact.customer_id == customer_id,
        Contact.is_active == True
    ).order_by(Contact.is_primary.desc(), Contact.full_name).all()

    return {
        "items": [_contact_to_response(c) for c in contacts],
        "count": len(contacts),
    }


@router.get("/by-lead/{lead_id}", dependencies=[Depends(Require("crm:read"))])
async def get_lead_contacts(lead_id: int, db: Session = Depends(get_db)):
    """Get all contacts for a lead."""
    contacts = db.query(Contact).filter(
        Contact.lead_id == lead_id,
        Contact.is_active == True
    ).order_by(Contact.is_primary.desc(), Contact.full_name).all()

    return {
        "items": [_contact_to_response(c) for c in contacts],
        "count": len(contacts),
    }


@router.get("/{contact_id}", response_model=ContactResponse, dependencies=[Depends(Require("crm:read"))])
async def get_contact(contact_id: int, db: Session = Depends(get_db)):
    """Get a single contact by ID."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return _contact_to_response(contact)


@router.post("", response_model=ContactResponse, dependencies=[Depends(Require("crm:write"))])
async def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    """Create a new contact."""
    if not payload.customer_id and not payload.lead_id:
        raise HTTPException(status_code=400, detail="Either customer_id or lead_id is required")

    # Build full name
    full_name = payload.first_name
    if payload.last_name:
        full_name = f"{payload.first_name} {payload.last_name}"

    # If marked as primary, unmark other primary contacts
    if payload.is_primary:
        if payload.customer_id:
            db.query(Contact).filter(
                Contact.customer_id == payload.customer_id,
                Contact.is_primary == True
            ).update({"is_primary": False})
        elif payload.lead_id:
            db.query(Contact).filter(
                Contact.lead_id == payload.lead_id,
                Contact.is_primary == True
            ).update({"is_primary": False})

    contact = Contact(
        customer_id=payload.customer_id,
        lead_id=payload.lead_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        full_name=full_name,
        email=payload.email,
        phone=payload.phone,
        mobile=payload.mobile,
        designation=payload.designation,
        department=payload.department,
        is_primary=payload.is_primary,
        is_billing_contact=payload.is_billing_contact,
        is_decision_maker=payload.is_decision_maker,
        linkedin_url=payload.linkedin_url,
        notes=payload.notes,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.patch("/{contact_id}", response_model=ContactResponse, dependencies=[Depends(Require("crm:write"))])
async def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    """Update a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If marking as primary, unmark others
    if update_data.get("is_primary"):
        if contact.customer_id:
            db.query(Contact).filter(
                Contact.customer_id == contact.customer_id,
                Contact.id != contact_id,
                Contact.is_primary == True
            ).update({"is_primary": False})
        elif contact.lead_id:
            db.query(Contact).filter(
                Contact.lead_id == contact.lead_id,
                Contact.id != contact_id,
                Contact.is_primary == True
            ).update({"is_primary": False})

    for key, value in update_data.items():
        setattr(contact, key, value)

    # Update full name if first/last name changed
    if "first_name" in update_data or "last_name" in update_data:
        contact.full_name = contact.first_name
        if contact.last_name:
            contact.full_name = f"{contact.first_name} {contact.last_name}"

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post("/{contact_id}/set-primary", dependencies=[Depends(Require("crm:write"))])
async def set_primary_contact(contact_id: int, db: Session = Depends(get_db)):
    """Set a contact as the primary contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Unmark other primary contacts
    if contact.customer_id:
        db.query(Contact).filter(
            Contact.customer_id == contact.customer_id,
            Contact.is_primary == True
        ).update({"is_primary": False})
    elif contact.lead_id:
        db.query(Contact).filter(
            Contact.lead_id == contact.lead_id,
            Contact.is_primary == True
        ).update({"is_primary": False})

    contact.is_primary = True
    db.commit()

    return {"success": True, "message": "Contact set as primary"}


@router.delete("/{contact_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    """Soft-delete a contact (set inactive)."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.is_active = False
    db.commit()

    return {"success": True, "message": "Contact deactivated"}


def _contact_to_response(contact: Contact) -> ContactResponse:
    """Convert Contact model to response."""
    return ContactResponse(
        id=contact.id,
        customer_id=contact.customer_id,
        lead_id=contact.lead_id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        full_name=contact.full_name,
        email=contact.email,
        phone=contact.phone,
        mobile=contact.mobile,
        designation=contact.designation,
        department=contact.department,
        is_primary=contact.is_primary,
        is_billing_contact=contact.is_billing_contact,
        is_decision_maker=contact.is_decision_maker,
        is_active=contact.is_active,
        unsubscribed=contact.unsubscribed,
        linkedin_url=contact.linkedin_url,
        notes=contact.notes,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )

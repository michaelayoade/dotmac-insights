"""Inbox Contacts API - Unified contact directory management."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.auth import Require
from app.models.omni import InboxContact, OmniConversation, OmniParticipant
from app.models.customer import Customer
from app.models.sales import ERPNextLead

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class ContactCreateRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    tags: Optional[List[str]] = None
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    tags: Optional[List[str]] = None
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def serialize_contact(contact: InboxContact, db: Session = None) -> Dict[str, Any]:
    """Serialize a contact to JSON."""
    result = {
        "id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "company": contact.company,
        "job_title": contact.job_title,
        "customer_id": contact.customer_id,
        "lead_id": contact.lead_id,
        "tags": contact.tags or [],
        "meta": contact.meta,
        "total_conversations": contact.total_conversations,
        "last_contact_at": contact.last_contact_at.isoformat() if contact.last_contact_at else None,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }
    return result


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/contacts",
    dependencies=[Depends(Require("support:read"))],
)
async def list_contacts(
    search: Optional[str] = None,
    company: Optional[str] = None,
    tag: Optional[str] = None,
    has_customer: Optional[bool] = None,
    has_lead: Optional[bool] = None,
    sort_by: str = "last_contact_at",
    sort_order: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List contacts with filtering and pagination."""
    query = db.query(InboxContact)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                InboxContact.name.ilike(search_term),
                InboxContact.email.ilike(search_term),
                InboxContact.phone.ilike(search_term),
                InboxContact.company.ilike(search_term),
            )
        )

    if company:
        query = query.filter(InboxContact.company.ilike(f"%{company}%"))

    if tag:
        query = query.filter(InboxContact.tags.contains([tag]))

    if has_customer is not None:
        if has_customer:
            query = query.filter(InboxContact.customer_id.isnot(None))
        else:
            query = query.filter(InboxContact.customer_id.is_(None))

    if has_lead is not None:
        if has_lead:
            query = query.filter(InboxContact.lead_id.isnot(None))
        else:
            query = query.filter(InboxContact.lead_id.is_(None))

    total = query.count()

    # Apply sorting
    sort_column = getattr(InboxContact, sort_by, InboxContact.last_contact_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc().nullslast())
    else:
        query = query.order_by(sort_column.asc().nullsfirst())

    contacts = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_contact(c, db) for c in contacts],
    }


@router.get(
    "/contacts/{contact_id}",
    dependencies=[Depends(Require("support:read"))],
)
async def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single contact with conversation history."""
    contact = db.query(InboxContact).filter(InboxContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    result = serialize_contact(contact, db)

    # Get recent conversations for this contact
    convs = (
        db.query(OmniConversation)
        .filter(
            or_(
                OmniConversation.contact_email == contact.email,
                OmniConversation.customer_id == contact.customer_id,
            )
        )
        .order_by(OmniConversation.last_message_at.desc())
        .limit(10)
        .all()
    )

    result["recent_conversations"] = [
        {
            "id": c.id,
            "subject": c.subject,
            "status": c.status,
            "channel_type": c.channel.type if c.channel else None,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        }
        for c in convs
    ]

    return result


@router.post(
    "/contacts",
    dependencies=[Depends(Require("support:write"))],
    status_code=201,
)
async def create_contact(
    payload: ContactCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new contact."""
    # Check for existing contact with same email
    if payload.email:
        existing = db.query(InboxContact).filter(InboxContact.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Contact with this email already exists")

    contact = InboxContact(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        job_title=payload.job_title,
        tags=payload.tags,
        customer_id=payload.customer_id,
        lead_id=payload.lead_id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return serialize_contact(contact, db)


@router.patch(
    "/contacts/{contact_id}",
    dependencies=[Depends(Require("support:write"))],
)
async def update_contact(
    contact_id: int,
    payload: ContactUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a contact."""
    contact = db.query(InboxContact).filter(InboxContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.name is not None:
        contact.name = payload.name

    if payload.email is not None:
        # Check for duplicate email
        if payload.email != contact.email:
            existing = db.query(InboxContact).filter(
                InboxContact.email == payload.email,
                InboxContact.id != contact_id,
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Contact with this email already exists")
        contact.email = payload.email

    if payload.phone is not None:
        contact.phone = payload.phone

    if payload.company is not None:
        contact.company = payload.company

    if payload.job_title is not None:
        contact.job_title = payload.job_title

    if payload.tags is not None:
        contact.tags = payload.tags

    if payload.customer_id is not None:
        contact.customer_id = payload.customer_id if payload.customer_id > 0 else None

    if payload.lead_id is not None:
        contact.lead_id = payload.lead_id if payload.lead_id > 0 else None

    db.commit()
    db.refresh(contact)

    return serialize_contact(contact, db)


@router.delete(
    "/contacts/{contact_id}",
    dependencies=[Depends(Require("support:write"))],
    status_code=204,
)
async def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
):
    """Delete a contact."""
    contact = db.query(InboxContact).filter(InboxContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()

    return None


@router.get(
    "/contacts/companies",
    dependencies=[Depends(Require("support:read"))],
)
async def list_companies(
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List unique companies from contacts."""
    query = (
        db.query(
            InboxContact.company,
            func.count(InboxContact.id).label("contact_count"),
        )
        .filter(InboxContact.company.isnot(None))
        .group_by(InboxContact.company)
    )

    if search:
        query = query.filter(InboxContact.company.ilike(f"%{search}%"))

    total = query.count()

    companies = (
        query.order_by(func.count(InboxContact.id).desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {"company": c.company, "contact_count": c.contact_count}
            for c in companies
        ],
    }

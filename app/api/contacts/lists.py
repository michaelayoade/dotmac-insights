"""
Contact Lists API

CRUD operations for custom contact lists with saved filters.
Lists can be shared with team or kept private.
"""
from typing import Optional, List as ListType
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.models.contact_list import ContactList
from app.models.unified_contact import UnifiedContact
from app.utils.datetime_utils import utc_now


router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class ContactListFilters(BaseModel):
    """Filter criteria for a contact list."""
    contact_type: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    qualification: Optional[str] = None
    territory: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    is_organization: Optional[bool] = None
    has_outstanding: Optional[bool] = None
    tag: Optional[str] = None
    quality_issue: Optional[str] = None


class ContactListCreate(BaseModel):
    """Schema for creating a contact list."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_shared: bool = True
    is_favorite: bool = False
    filters: Optional[ContactListFilters] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None


class ContactListUpdate(BaseModel):
    """Schema for updating a contact list."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_shared: Optional[bool] = None
    is_favorite: Optional[bool] = None
    filters: Optional[ContactListFilters] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None
    sort_order: Optional[int] = None


class ContactListResponse(BaseModel):
    """Schema for contact list response."""
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    owner_name: Optional[str] = None
    is_shared: bool
    is_favorite: bool
    filters: Optional[dict]
    color: Optional[str]
    icon: Optional[str]
    sort_order: int
    contact_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ContactListListResponse(BaseModel):
    """Schema for list of contact lists."""
    items: ListType[ContactListResponse]
    total: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def count_contacts_for_filters(db: Session, filters: Optional[dict]) -> int:
    """Count contacts matching the given filters."""
    deleted_at = getattr(UnifiedContact, "deleted_at")
    if not filters:
        return db.query(UnifiedContact).filter(deleted_at.is_(None)).count()

    query = db.query(UnifiedContact).filter(deleted_at.is_(None))

    if filters.get("contact_type"):
        query = query.filter(UnifiedContact.contact_type == filters["contact_type"])
    if filters.get("category"):
        query = query.filter(UnifiedContact.category == filters["category"])
    if filters.get("status"):
        query = query.filter(UnifiedContact.status == filters["status"])
    if filters.get("qualification"):
        query = query.filter(UnifiedContact.lead_qualification == filters["qualification"])
    if filters.get("territory"):
        query = query.filter(UnifiedContact.territory == filters["territory"])
    if filters.get("city"):
        query = query.filter(UnifiedContact.city == filters["city"])
    if filters.get("state"):
        query = query.filter(UnifiedContact.state == filters["state"])
    if filters.get("source"):
        query = query.filter(UnifiedContact.source == filters["source"])
    if filters.get("is_organization") is not None:
        query = query.filter(UnifiedContact.is_organization == filters["is_organization"])
    if filters.get("has_outstanding"):
        query = query.filter(UnifiedContact.outstanding_balance > 0)
    if filters.get("tag"):
        query = query.filter(UnifiedContact.tags.contains([filters["tag"]]))

    # Quality issue filters
    quality_issue = filters.get("quality_issue")
    if quality_issue:
        if quality_issue == "missing_email":
            query = query.filter(or_(
                UnifiedContact.email.is_(None),
                UnifiedContact.email == ""
            ))
        elif quality_issue == "missing_phone":
            query = query.filter(and_(
                or_(UnifiedContact.phone.is_(None), UnifiedContact.phone == ""),
                or_(UnifiedContact.mobile.is_(None), UnifiedContact.mobile == "")
            ))
        elif quality_issue == "missing_address":
            query = query.filter(and_(
                or_(UnifiedContact.address_line1.is_(None), UnifiedContact.address_line1 == ""),
                or_(UnifiedContact.city.is_(None), UnifiedContact.city == "")
            ))
        elif quality_issue == "missing_name":
            query = query.filter(or_(
                UnifiedContact.name.is_(None),
                UnifiedContact.name == ""
            ))
        elif quality_issue == "missing_company":
            query = query.filter(
                UnifiedContact.is_organization == True,
                or_(
                    UnifiedContact.company_name.is_(None),
                    UnifiedContact.company_name == ""
                )
            )
        elif quality_issue == "invalid_email":
            query = query.filter(
                UnifiedContact.email.isnot(None),
                UnifiedContact.email != "",
                or_(
                    ~UnifiedContact.email.contains("@"),
                    ~UnifiedContact.email.contains(".")
                )
            )

    return query.count()


def list_to_response(db: Session, contact_list: ContactList) -> ContactListResponse:
    """Convert a ContactList model to response schema."""
    return ContactListResponse(
        id=contact_list.id,
        name=contact_list.name,
        description=contact_list.description,
        owner_id=contact_list.owner_id,
        owner_name=contact_list.owner.name if contact_list.owner else None,
        is_shared=contact_list.is_shared,
        is_favorite=contact_list.is_favorite,
        filters=contact_list.filters,
        color=contact_list.color,
        icon=contact_list.icon,
        sort_order=contact_list.sort_order,
        contact_count=count_contacts_for_filters(db, contact_list.filters),
        created_at=contact_list.created_at.isoformat(),
        updated_at=contact_list.updated_at.isoformat(),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/lists",
    response_model=ContactListListResponse,
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_contact_lists(
    include_shared: bool = Query(True, description="Include shared lists from other users"),
    favorites_only: bool = Query(False, description="Only return favorited lists"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Get all contact lists visible to the current user.

    Returns both user's own lists and shared lists from other users.
    """
    query = db.query(ContactList)

    if include_shared:
        # Show own lists + shared lists
        query = query.filter(
            or_(
                ContactList.owner_id == principal.id,
                ContactList.is_shared == True
            )
        )
    else:
        # Only own lists
        query = query.filter(ContactList.owner_id == principal.id)

    if favorites_only:
        query = query.filter(ContactList.is_favorite == True)

    # Order by favorite first, then sort_order, then name
    query = query.order_by(
        ContactList.is_favorite.desc(),
        ContactList.sort_order,
        ContactList.name
    )

    lists = query.all()
    items = [list_to_response(db, lst) for lst in lists]

    return ContactListListResponse(items=items, total=len(items))


@router.post(
    "/lists",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def create_contact_list(
    data: ContactListCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Create a new contact list.

    The list will be owned by the current user.
    """
    # Get max sort_order for the user
    max_sort = db.query(ContactList.sort_order).filter(
        ContactList.owner_id == principal.id
    ).order_by(ContactList.sort_order.desc()).first()
    next_sort = (max_sort[0] + 1) if max_sort else 0

    contact_list = ContactList(
        name=data.name,
        description=data.description,
        owner_id=principal.id,
        is_shared=data.is_shared,
        is_favorite=data.is_favorite,
        filters=data.filters.model_dump() if data.filters else None,
        color=data.color,
        icon=data.icon,
        sort_order=next_sort,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    db.add(contact_list)
    db.commit()
    db.refresh(contact_list)

    return list_to_response(db, contact_list)


@router.get(
    "/lists/{list_id}",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("contacts:read"))],
)
async def get_contact_list(
    list_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Get a specific contact list by ID.

    User must own the list or it must be shared.
    """
    contact_list = db.query(ContactList).filter(ContactList.id == list_id).first()

    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")

    # Check access
    if contact_list.owner_id != principal.id and not contact_list.is_shared:
        raise HTTPException(status_code=403, detail="You don't have access to this list")

    return list_to_response(db, contact_list)


@router.patch(
    "/lists/{list_id}",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def update_contact_list(
    list_id: int,
    data: ContactListUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Update a contact list.

    Only the owner can update a list.
    """
    contact_list = db.query(ContactList).filter(ContactList.id == list_id).first()

    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")

    if contact_list.owner_id != principal.id:
        raise HTTPException(status_code=403, detail="Only the owner can update this list")

    # Update fields
    if data.name is not None:
        contact_list.name = data.name
    if data.description is not None:
        contact_list.description = data.description
    if data.is_shared is not None:
        contact_list.is_shared = data.is_shared
    if data.is_favorite is not None:
        contact_list.is_favorite = data.is_favorite
    if data.filters is not None:
        contact_list.filters = data.filters.model_dump()
    if data.color is not None:
        contact_list.color = data.color
    if data.icon is not None:
        contact_list.icon = data.icon
    if data.sort_order is not None:
        contact_list.sort_order = data.sort_order

    contact_list.updated_at = utc_now()

    db.commit()
    db.refresh(contact_list)

    return list_to_response(db, contact_list)


@router.delete(
    "/lists/{list_id}",
    dependencies=[Depends(Require("contacts:write"))],
)
async def delete_contact_list(
    list_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Delete a contact list.

    Only the owner can delete a list.
    """
    contact_list = db.query(ContactList).filter(ContactList.id == list_id).first()

    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")

    if contact_list.owner_id != principal.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this list")

    db.delete(contact_list)
    db.commit()

    return {"message": "Contact list deleted successfully"}


@router.post(
    "/lists/{list_id}/favorite",
    response_model=ContactListResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def toggle_list_favorite(
    list_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Toggle the favorite status of a contact list.

    Any user with access can favorite a list (their own or shared).
    """
    contact_list = db.query(ContactList).filter(ContactList.id == list_id).first()

    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")

    # Check access
    if contact_list.owner_id != principal.id and not contact_list.is_shared:
        raise HTTPException(status_code=403, detail="You don't have access to this list")

    contact_list.is_favorite = not contact_list.is_favorite
    contact_list.updated_at = utc_now()

    db.commit()
    db.refresh(contact_list)

    return list_to_response(db, contact_list)

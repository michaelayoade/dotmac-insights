"""
Bulk Contact Operations

Import, bulk update, merge duplicates, bulk assign
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactCategory, ContactStatus,
    BillingType, LeadQualification
)
from .schemas import (
    BulkUpdateRequest, BulkAssignRequest, BulkTagRequest,
    MergeContactsRequest, ImportContactsRequest, ImportContactsResponse,
    UnifiedContactUpdate, ContactTypeEnum, ContactCategoryEnum
)

router = APIRouter()


# =============================================================================
# BULK UPDATE
# =============================================================================

@router.post("/bulk/update")
async def bulk_update_contacts(payload: BulkUpdateRequest, db: Session = Depends(get_db)):
    """
    Update multiple contacts at once.

    Only updates fields that are explicitly set in the payload.
    """
    if not payload.contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")

    if len(payload.contact_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 contacts per batch")

    update_data = payload.updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

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

    update_data["updated_at"] = datetime.utcnow()

    updated = db.query(UnifiedContact).filter(
        UnifiedContact.id.in_(payload.contact_ids)
    ).update(update_data, synchronize_session="fetch")

    db.commit()

    return {
        "success": True,
        "updated_count": updated,
        "contact_ids": payload.contact_ids,
    }


@router.post("/bulk/assign")
async def bulk_assign_contacts(payload: BulkAssignRequest, db: Session = Depends(get_db)):
    """
    Assign multiple contacts to a single owner.
    """
    if not payload.contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")

    if len(payload.contact_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 contacts per batch")

    updated = db.query(UnifiedContact).filter(
        UnifiedContact.id.in_(payload.contact_ids)
    ).update({
        "owner_id": payload.owner_id,
        "updated_at": datetime.utcnow(),
    }, synchronize_session="fetch")

    db.commit()

    return {
        "success": True,
        "updated_count": updated,
        "owner_id": payload.owner_id,
    }


@router.post("/bulk/tags")
async def bulk_tag_operation(payload: BulkTagRequest, db: Session = Depends(get_db)):
    """
    Bulk tag operation: add, remove, or set tags on multiple contacts.

    Operations:
    - add: Add tags to existing tags
    - remove: Remove specified tags
    - set: Replace all tags with specified tags
    """
    if not payload.contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")

    if len(payload.contact_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 contacts per batch")

    contacts = db.query(UnifiedContact).filter(
        UnifiedContact.id.in_(payload.contact_ids)
    ).all()

    for contact in contacts:
        current_tags = contact.tags or []

        if payload.operation == "add":
            contact.tags = list(set(current_tags + payload.tags))
        elif payload.operation == "remove":
            contact.tags = [t for t in current_tags if t not in payload.tags]
        elif payload.operation == "set":
            contact.tags = list(set(payload.tags))

    db.commit()

    return {
        "success": True,
        "updated_count": len(contacts),
        "operation": payload.operation,
    }


@router.post("/bulk/delete")
async def bulk_delete_contacts(
    contact_ids: List[int],
    hard: bool = False,
    db: Session = Depends(get_db)
):
    """
    Bulk delete (soft or hard) multiple contacts.
    """
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")

    if len(contact_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 contacts per batch")

    if hard:
        # Delete child contacts first
        db.query(UnifiedContact).filter(
            UnifiedContact.parent_id.in_(contact_ids)
        ).delete(synchronize_session="fetch")

        # Delete main contacts
        deleted = db.query(UnifiedContact).filter(
            UnifiedContact.id.in_(contact_ids)
        ).delete(synchronize_session="fetch")
    else:
        # Soft delete
        deleted = db.query(UnifiedContact).filter(
            UnifiedContact.id.in_(contact_ids)
        ).update({
            "status": ContactStatus.INACTIVE,
            "updated_at": datetime.utcnow(),
        }, synchronize_session="fetch")

    db.commit()

    return {
        "success": True,
        "deleted_count": deleted,
        "hard_delete": hard,
    }


# =============================================================================
# MERGE DUPLICATES
# =============================================================================

@router.post("/merge")
async def merge_contacts(payload: MergeContactsRequest, db: Session = Depends(get_db)):
    """
    Merge duplicate contacts into a primary contact.

    Strategies:
    - keep_primary: Keep all data from primary, just delete duplicates
    - merge_all: Merge non-null fields from duplicates into primary
    - manual: Only merge specified fields (not implemented yet)

    After merging:
    - Updates all references to point to primary contact
    - Deletes duplicate contacts
    """
    primary = db.query(UnifiedContact).filter(
        UnifiedContact.id == payload.primary_contact_id
    ).first()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary contact not found")

    duplicates = db.query(UnifiedContact).filter(
        UnifiedContact.id.in_(payload.duplicate_contact_ids)
    ).all()

    if not duplicates:
        raise HTTPException(status_code=404, detail="No duplicate contacts found")

    merged_fields = []

    if payload.merge_strategy == "merge_all":
        # Merge non-null fields from duplicates into primary
        mergeable_fields = [
            "email", "email_secondary", "billing_email", "phone", "phone_secondary",
            "mobile", "website", "linkedin_url", "address_line1", "address_line2",
            "city", "state", "postal_code", "country", "latitude", "longitude",
            "company_name", "industry", "market_segment", "territory", "source",
            "source_campaign", "referrer", "notes", "splynx_id", "erpnext_id",
            "chatwoot_contact_id", "zoho_id",
        ]

        for dup in duplicates:
            for field in mergeable_fields:
                primary_val = getattr(primary, field)
                dup_val = getattr(dup, field)
                if dup_val and not primary_val:
                    setattr(primary, field, dup_val)
                    merged_fields.append(f"{field} from #{dup.id}")

            # Merge tags
            if dup.tags:
                primary.tags = list(set((primary.tags or []) + dup.tags))

            # Merge custom fields
            if dup.custom_fields:
                primary.custom_fields = {**(primary.custom_fields or {}), **dup.custom_fields}

            # Append notes
            if dup.notes and dup.notes != primary.notes:
                if primary.notes:
                    primary.notes = f"{primary.notes}\n\n--- Merged from #{dup.id} ---\n{dup.notes}"
                else:
                    primary.notes = f"--- Merged from #{dup.id} ---\n{dup.notes}"

            # Sum up stats
            primary.total_conversations += dup.total_conversations
            primary.total_tickets += dup.total_tickets
            primary.total_orders += dup.total_orders
            primary.total_invoices += dup.total_invoices

    # Update child contacts to point to primary
    child_updates = db.query(UnifiedContact).filter(
        UnifiedContact.parent_id.in_(payload.duplicate_contact_ids)
    ).update({"parent_id": primary.id}, synchronize_session="fetch")

    # Record legacy IDs from duplicates
    legacy_ids = [d.id for d in duplicates]

    # Delete duplicates
    db.query(UnifiedContact).filter(
        UnifiedContact.id.in_(payload.duplicate_contact_ids)
    ).delete(synchronize_session="fetch")

    primary.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "primary_contact_id": primary.id,
        "merged_duplicate_ids": legacy_ids,
        "children_reassigned": child_updates,
        "merged_fields": merged_fields if payload.merge_strategy == "merge_all" else [],
    }


@router.get("/duplicates")
async def find_duplicate_contacts(
    field: str = Query("email", pattern="^(email|phone|name)$"),
    contact_type: Optional[ContactTypeEnum] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Find potential duplicate contacts based on email, phone, or name.
    """
    query = db.query(UnifiedContact)

    if contact_type:
        query = query.filter(UnifiedContact.contact_type == ContactType(contact_type.value))

    # Find duplicates based on field
    if field == "email":
        duplicates = db.query(
            UnifiedContact.email,
            func.count(UnifiedContact.id).label("count"),
            func.array_agg(UnifiedContact.id).label("ids"),
        ).filter(
            UnifiedContact.email.isnot(None),
            UnifiedContact.email != ""
        ).group_by(UnifiedContact.email).having(
            func.count(UnifiedContact.id) > 1
        ).limit(limit).all()

    elif field == "phone":
        duplicates = db.query(
            UnifiedContact.phone,
            func.count(UnifiedContact.id).label("count"),
            func.array_agg(UnifiedContact.id).label("ids"),
        ).filter(
            UnifiedContact.phone.isnot(None),
            UnifiedContact.phone != ""
        ).group_by(UnifiedContact.phone).having(
            func.count(UnifiedContact.id) > 1
        ).limit(limit).all()

    elif field == "name":
        duplicates = db.query(
            UnifiedContact.name,
            func.count(UnifiedContact.id).label("count"),
            func.array_agg(UnifiedContact.id).label("ids"),
        ).filter(
            UnifiedContact.name.isnot(None),
            UnifiedContact.name != ""
        ).group_by(UnifiedContact.name).having(
            func.count(UnifiedContact.id) > 1
        ).limit(limit).all()

    return {
        "field": field,
        "duplicate_groups": [
            {
                "value": d[0],
                "count": d.count,
                "contact_ids": d.ids,
            }
            for d in duplicates
        ],
        "total_groups": len(duplicates),
    }


# =============================================================================
# IMPORT
# =============================================================================

@router.post("/import", response_model=ImportContactsResponse)
async def import_contacts(payload: ImportContactsRequest, db: Session = Depends(get_db)):
    """
    Bulk import contacts from external source.

    Features:
    - Skip or update duplicates based on email/phone/name
    - Auto-assign owner
    - Set default source
    """
    created = 0
    skipped = 0
    errors = []

    for idx, row in enumerate(payload.contacts):
        try:
            # Check for duplicates
            if payload.skip_duplicates:
                if payload.duplicate_check_field == "email" and row.email:
                    existing = db.query(UnifiedContact).filter(
                        UnifiedContact.email == row.email
                    ).first()
                    if existing:
                        skipped += 1
                        continue
                elif payload.duplicate_check_field == "phone" and row.phone:
                    existing = db.query(UnifiedContact).filter(
                        UnifiedContact.phone == row.phone
                    ).first()
                    if existing:
                        skipped += 1
                        continue
                elif payload.duplicate_check_field == "name":
                    existing = db.query(UnifiedContact).filter(
                        UnifiedContact.name == row.name
                    ).first()
                    if existing:
                        skipped += 1
                        continue

            contact = UnifiedContact(
                name=row.name,
                email=row.email,
                phone=row.phone,
                company_name=row.company_name,
                contact_type=ContactType(row.contact_type.value) if row.contact_type else ContactType.LEAD,
                category=ContactCategory(row.category.value) if row.category else ContactCategory.RESIDENTIAL,
                status=ContactStatus.ACTIVE,
                source=row.source or payload.default_source,
                city=row.city,
                state=row.state,
                country=row.country or "Nigeria",
                notes=row.notes,
                tags=row.tags,
                owner_id=payload.owner_id,
                first_contact_date=datetime.utcnow(),
            )
            db.add(contact)
            created += 1

        except Exception as e:
            errors.append({
                "row": idx,
                "name": row.name,
                "error": str(e),
            })

    db.commit()

    return ImportContactsResponse(
        total_submitted=len(payload.contacts),
        created=created,
        skipped=skipped,
        errors=errors,
    )

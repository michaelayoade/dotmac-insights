"""
Contact Lifecycle Management Endpoints

Handles transitions: lead → prospect → customer → churned
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactStatus, LeadQualification, BillingType
)
from .schemas import (
    QualifyLeadRequest, ConvertToCustomerRequest, MarkChurnedRequest,
    AssignOwnerRequest, UnifiedContactResponse, ContactTypeEnum
)
from .contacts import _contact_to_response
from app.auth import Require
from app.feature_flags import feature_flags
from app.services.legacy_customer_sync import LegacyCustomerSync
from app.middleware.metrics import record_dual_write

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# LEAD LIFECYCLE
# =============================================================================

@router.post(
    "/{contact_id}/qualify",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def qualify_lead(contact_id: int, payload: QualifyLeadRequest, db: Session = Depends(get_db)):
    """
    Qualify a lead.

    Sets lead_qualification level. If qualified to 'qualified',
    automatically promotes lead to prospect.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.contact_type not in [ContactType.LEAD, ContactType.PROSPECT]:
        raise HTTPException(status_code=400, detail="Only leads and prospects can be qualified")

    contact.lead_qualification = LeadQualification(payload.qualification.value)
    if payload.lead_score is not None:
        contact.lead_score = payload.lead_score

    # Auto-promote to prospect if fully qualified
    if payload.qualification.value == "qualified" and contact.contact_type == ContactType.LEAD:
        contact.contact_type = ContactType.PROSPECT
        contact.qualified_date = datetime.utcnow()

    if payload.notes:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Qualified: {payload.notes}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Qualified: {payload.notes}"

    contact.last_contact_date = datetime.utcnow()
    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/convert-to-prospect",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def convert_to_prospect(contact_id: int, db: Session = Depends(get_db)):
    """
    Convert a lead to a prospect.

    Prospect is a qualified lead in the active sales pipeline.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.contact_type != ContactType.LEAD:
        raise HTTPException(status_code=400, detail="Only leads can be converted to prospects")

    contact.contact_type = ContactType.PROSPECT
    contact.qualified_date = datetime.utcnow()
    contact.last_contact_date = datetime.utcnow()

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/convert-to-customer",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def convert_to_customer(contact_id: int, payload: ConvertToCustomerRequest, db: Session = Depends(get_db)):
    """
    Convert a lead or prospect to a customer.

    This is a significant lifecycle event - the contact has completed
    the sales process and is now a paying customer.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.contact_type not in [ContactType.LEAD, ContactType.PROSPECT]:
        raise HTTPException(status_code=400, detail="Only leads and prospects can be converted to customers")

    # Update type
    contact.contact_type = ContactType.CUSTOMER
    contact.conversion_date = datetime.utcnow()
    contact.signup_date = datetime.utcnow()
    contact.last_contact_date = datetime.utcnow()

    # Update customer-specific fields
    if payload.account_number:
        # Check for duplicate account number
        existing = db.query(UnifiedContact).filter(
            UnifiedContact.account_number == payload.account_number,
            UnifiedContact.id != contact_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Account number already exists")
        contact.account_number = payload.account_number

    if payload.billing_type:
        contact.billing_type = BillingType(payload.billing_type.value)
    if payload.mrr is not None:
        contact.mrr = payload.mrr
    if payload.contract_start_date:
        contact.contract_start_date = payload.contract_start_date
    if payload.contract_end_date:
        contact.contract_end_date = payload.contract_end_date
    if payload.splynx_id:
        contact.splynx_id = payload.splynx_id

    if payload.notes:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Converted to customer: {payload.notes}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Converted to customer: {payload.notes}"

    # Dual-write: create/sync to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        try:
            sync = LegacyCustomerSync(db)
            sync.sync_to_customer(contact)
            record_dual_write("status_change", True)
            logger.info(f"Dual-write: converted contact {contact.id} synced to Customer table")
        except Exception as e:
            record_dual_write("status_change", False)
            logger.error(f"Dual-write failed for convert_to_customer {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/reactivate",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def reactivate_churned_customer(contact_id: int, db: Session = Depends(get_db)):
    """
    Reactivate a churned customer.

    Moves them back to active customer status.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.contact_type != ContactType.CHURNED:
        raise HTTPException(status_code=400, detail="Only churned contacts can be reactivated")

    contact.contact_type = ContactType.CUSTOMER
    contact.status = ContactStatus.ACTIVE
    contact.cancellation_date = None
    contact.churn_reason = None
    contact.last_contact_date = datetime.utcnow()

    if contact.notes:
        contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Reactivated"
    else:
        contact.notes = f"[{datetime.utcnow().isoformat()}] Reactivated"

    # Dual-write: sync status change to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        try:
            sync = LegacyCustomerSync(db)
            sync.sync_to_customer(contact)
            record_dual_write("status_change", True)
            logger.info(f"Dual-write: reactivated contact {contact.id} synced to Customer table")
        except Exception as e:
            record_dual_write("status_change", False)
            logger.error(f"Dual-write failed for reactivate {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/mark-churned",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def mark_churned(contact_id: int, payload: MarkChurnedRequest, db: Session = Depends(get_db)):
    """
    Mark a customer as churned.

    Records churn reason and date for analytics.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.contact_type != ContactType.CUSTOMER:
        raise HTTPException(status_code=400, detail="Only customers can be marked as churned")

    contact.contact_type = ContactType.CHURNED
    contact.status = ContactStatus.INACTIVE
    contact.cancellation_date = datetime.utcnow()
    contact.churn_reason = payload.reason

    if payload.notes:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Churned: {payload.reason}. {payload.notes}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Churned: {payload.reason}. {payload.notes}"

    # Dual-write: sync churned status to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        try:
            sync = LegacyCustomerSync(db)
            sync.sync_to_customer(contact)
            record_dual_write("status_change", True)
            logger.info(f"Dual-write: churned contact {contact.id} synced to Customer table")
        except Exception as e:
            record_dual_write("status_change", False)
            logger.error(f"Dual-write failed for mark_churned {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


# =============================================================================
# ASSIGNMENT
# =============================================================================

@router.post(
    "/{contact_id}/assign",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def assign_owner(contact_id: int, payload: AssignOwnerRequest, db: Session = Depends(get_db)):
    """
    Assign a contact to an owner (employee).
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.owner_id = payload.owner_id
    contact.last_contact_date = datetime.utcnow()

    if payload.notes:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Assigned to owner {payload.owner_id}: {payload.notes}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Assigned to owner {payload.owner_id}: {payload.notes}"

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/unassign",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def unassign_owner(contact_id: int, db: Session = Depends(get_db)):
    """
    Remove owner assignment from a contact.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.owner_id = None
    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


# =============================================================================
# STATUS MANAGEMENT
# =============================================================================

@router.post(
    "/{contact_id}/suspend",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def suspend_contact(contact_id: int, reason: str = None, db: Session = Depends(get_db)):
    """
    Suspend a contact (e.g., for non-payment).
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.status = ContactStatus.SUSPENDED

    if reason:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Suspended: {reason}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Suspended: {reason}"

    # Dual-write: sync suspended status to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        if contact.contact_type in (ContactType.CUSTOMER, ContactType.CHURNED):
            try:
                sync = LegacyCustomerSync(db)
                sync.sync_to_customer(contact)
                record_dual_write("status_change", True)
                logger.info(f"Dual-write: suspended contact {contact.id} synced to Customer table")
            except Exception as e:
                record_dual_write("status_change", False)
                logger.error(f"Dual-write failed for suspend {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/activate",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def activate_contact(contact_id: int, db: Session = Depends(get_db)):
    """
    Activate a contact (remove suspension, inactive status).
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.status = ContactStatus.ACTIVE
    contact.activation_date = datetime.utcnow()

    if contact.notes:
        contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Activated"
    else:
        contact.notes = f"[{datetime.utcnow().isoformat()}] Activated"

    # Dual-write: sync activated status to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        if contact.contact_type in (ContactType.CUSTOMER, ContactType.CHURNED):
            try:
                sync = LegacyCustomerSync(db)
                sync.sync_to_customer(contact)
                record_dual_write("status_change", True)
                logger.info(f"Dual-write: activated contact {contact.id} synced to Customer table")
            except Exception as e:
                record_dual_write("status_change", False)
                logger.error(f"Dual-write failed for activate {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


@router.post(
    "/{contact_id}/do-not-contact",
    response_model=UnifiedContactResponse,
    dependencies=[Depends(Require("contacts:write"))],
)
async def mark_do_not_contact(contact_id: int, reason: str = None, db: Session = Depends(get_db)):
    """
    Mark a contact as do-not-contact.

    This disables all communication preferences.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.status = ContactStatus.DO_NOT_CONTACT
    contact.email_opt_in = False
    contact.sms_opt_in = False
    contact.whatsapp_opt_in = False
    contact.phone_opt_in = False

    if reason:
        if contact.notes:
            contact.notes = f"{contact.notes}\n\n[{datetime.utcnow().isoformat()}] Marked do-not-contact: {reason}"
        else:
            contact.notes = f"[{datetime.utcnow().isoformat()}] Marked do-not-contact: {reason}"

    # Dual-write: sync status/opt-ins to Customer table
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED and contact.contact_type in (ContactType.CUSTOMER, ContactType.CHURNED):
        try:
            sync = LegacyCustomerSync(db)
            sync.sync_to_customer(contact)
            record_dual_write("status_change", True)
            logger.info(f"Dual-write: do-not-contact contact {contact.id} synced to Customer table")
        except Exception as e:
            record_dual_write("status_change", False)
            logger.error(f"Dual-write failed for do-not-contact {contact.id}: {e}")

    db.commit()
    db.refresh(contact)

    return _contact_to_response(contact)


# =============================================================================
# COMMUNICATION PREFERENCES
# =============================================================================

@router.patch(
    "/{contact_id}/communication-preferences",
    dependencies=[Depends(Require("contacts:write"))],
)
async def update_communication_preferences(
    contact_id: int,
    email_opt_in: bool = None,
    sms_opt_in: bool = None,
    whatsapp_opt_in: bool = None,
    phone_opt_in: bool = None,
    preferred_language: str = None,
    preferred_channel: str = None,
    db: Session = Depends(get_db),
):
    """
    Update communication preferences for a contact.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if email_opt_in is not None:
        contact.email_opt_in = email_opt_in
    if sms_opt_in is not None:
        contact.sms_opt_in = sms_opt_in
    if whatsapp_opt_in is not None:
        contact.whatsapp_opt_in = whatsapp_opt_in
    if phone_opt_in is not None:
        contact.phone_opt_in = phone_opt_in
    if preferred_language is not None:
        contact.preferred_language = preferred_language
    if preferred_channel is not None:
        contact.preferred_channel = preferred_channel

    db.commit()

    return {
        "success": True,
        "email_opt_in": contact.email_opt_in,
        "sms_opt_in": contact.sms_opt_in,
        "whatsapp_opt_in": contact.whatsapp_opt_in,
        "phone_opt_in": contact.phone_opt_in,
        "preferred_language": contact.preferred_language,
        "preferred_channel": contact.preferred_channel,
    }


# =============================================================================
# TAGGING
# =============================================================================

@router.post(
    "/{contact_id}/tags/add",
    dependencies=[Depends(Require("contacts:write"))],
)
async def add_tags(contact_id: int, tags: list[str], db: Session = Depends(get_db)):
    """
    Add tags to a contact.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    current_tags = contact.tags or []
    new_tags = list(set(current_tags + tags))
    contact.tags = new_tags

    db.commit()

    return {"success": True, "tags": contact.tags}


@router.post(
    "/{contact_id}/tags/remove",
    dependencies=[Depends(Require("contacts:write"))],
)
async def remove_tags(contact_id: int, tags: list[str], db: Session = Depends(get_db)):
    """
    Remove tags from a contact.
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    current_tags = contact.tags or []
    new_tags = [t for t in current_tags if t not in tags]
    contact.tags = new_tags

    db.commit()

    return {"success": True, "tags": contact.tags}


@router.put(
    "/{contact_id}/tags",
    dependencies=[Depends(Require("contacts:write"))],
)
async def set_tags(contact_id: int, tags: list[str], db: Session = Depends(get_db)):
    """
    Set tags for a contact (replaces existing).
    """
    contact = db.query(UnifiedContact).filter(UnifiedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.tags = list(set(tags))
    db.commit()

    return {"success": True, "tags": contact.tags}

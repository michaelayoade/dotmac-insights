"""Journal Entries: JE list, detail, CRUD, submit/approve/reject/post workflows."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    JournalEntry,
    JournalEntryType,
    GLEntry,
)

from .helpers import parse_date, paginate, invalidate_report_cache

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class JournalEntryAccountCreate(BaseModel):
    """Schema for creating a journal entry account line."""
    account: str
    debit: float = 0
    credit: float = 0
    party_type: Optional[str] = None
    party: Optional[str] = None
    cost_center: Optional[str] = None
    user_remark: Optional[str] = None


class JournalEntryCreate(BaseModel):
    """Schema for creating a journal entry."""
    voucher_type: str = "journal_entry"
    posting_date: str
    user_remark: Optional[str] = None
    company: Optional[str] = None
    accounts: List[JournalEntryAccountCreate] = []


# =============================================================================
# JOURNAL ENTRIES LIST & DETAIL
# =============================================================================

@router.get("/journal-entries", dependencies=[Depends(Require("accounting:read"))])
def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get journal entries list.

    Args:
        start_date: Filter from date
        end_date: Filter to date
        voucher_type: Filter by voucher type
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated list of journal entries
    """
    query = db.query(JournalEntry)

    if start_date:
        query = query.filter(JournalEntry.posting_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(JournalEntry.posting_date <= parse_date(end_date, "end_date"))

    if voucher_type:
        try:
            vtype = JournalEntryType(voucher_type.lower())
            query = query.filter(JournalEntry.voucher_type == vtype)
        except ValueError:
            pass

    query = query.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc())
    total, entries = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "voucher_type": e.voucher_type.value if e.voucher_type else None,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "company": e.company,
                "total_debit": float(e.total_debit),
                "total_credit": float(e.total_credit),
                "user_remark": e.user_remark,
                "is_opening": e.is_opening,
            }
            for e in entries
        ],
    }


@router.get("/journal-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))])
def get_journal_entry_detail(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get journal entry detail with all line items (GL entries).

    Args:
        entry_id: Journal entry ID

    Returns:
        Full journal entry details with line items
    """
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    # Get related GL entries (line items)
    gl_entries = db.query(GLEntry).filter(
        GLEntry.voucher_no == entry.erpnext_id,
        GLEntry.voucher_type == "Journal Entry",
    ).order_by(GLEntry.id).all()

    accounts = [
        {
            "id": acc.id,
            "account": acc.account,
            "account_type": acc.account_type,
            "party_type": acc.party_type,
            "party": acc.party,
            "debit": float(acc.debit or 0),
            "credit": float(acc.credit or 0),
            "debit_in_account_currency": float(acc.debit_in_account_currency or 0),
            "credit_in_account_currency": float(acc.credit_in_account_currency or 0),
            "exchange_rate": float(acc.exchange_rate or 1),
            "reference_type": acc.reference_type,
            "reference_name": acc.reference_name,
            "reference_due_date": acc.reference_due_date.isoformat() if acc.reference_due_date else None,
            "cost_center": acc.cost_center,
            "project": acc.project,
            "bank_account": acc.bank_account,
            "cheque_no": acc.cheque_no,
            "cheque_date": acc.cheque_date.isoformat() if acc.cheque_date else None,
            "user_remark": acc.user_remark,
            "idx": acc.idx,
        }
        for acc in getattr(entry, "accounts", [])
    ]

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "voucher_type": entry.voucher_type.value if entry.voucher_type else None,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "company": entry.company,
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "is_balanced": abs(entry.total_debit - entry.total_credit) < Decimal("0.01"),
        "user_remark": entry.user_remark,
        "is_opening": entry.is_opening,
        "line_items": [
            {
                "id": gl.id,
                "account": gl.account,
                "party_type": gl.party_type,
                "party": gl.party,
                "debit": float(gl.debit),
                "credit": float(gl.credit),
                "cost_center": gl.cost_center,
            }
            for gl in gl_entries
        ],
        "line_count": len(gl_entries),
        "accounts": accounts,
    }


# =============================================================================
# JOURNAL ENTRY CRUD
# =============================================================================

@router.post("/journal-entries", dependencies=[Depends(Require("books:write"))])
async def create_journal_entry(
    je_data: JournalEntryCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a new journal entry.

    Args:
        je_data: Journal entry data

    Returns:
        Created journal entry details
    """
    from app.models.accounting import JournalEntryItem
    from app.services.je_validator import JEValidator, ValidationError
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        voucher_type_enum = JournalEntryType(je_data.voucher_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid voucher type: {je_data.voucher_type}")

    posting_dt = parse_date(je_data.posting_date, "posting_date")

    # Create JE
    je = JournalEntry(
        voucher_type=voucher_type_enum,
        posting_date=datetime.combine(posting_dt, datetime.min.time()) if posting_dt else None,
        user_remark=je_data.user_remark,
        company=je_data.company,
        total_debit=Decimal("0"),
        total_credit=Decimal("0"),
        docstatus=0,  # Draft
    )

    # Parse account lines
    je_accounts: List[JournalEntryItem] = []
    for acc_data in je_data.accounts:
        je_acc = JournalEntryItem(
            account=acc_data.account,
            debit=Decimal(str(acc_data.debit)),
            credit=Decimal(str(acc_data.credit)),
            party_type=acc_data.party_type,
            party=acc_data.party,
            cost_center=acc_data.cost_center,
        )
        je_accounts.append(je_acc)

    # Validate
    validator = JEValidator(db)
    try:
        validator.validate_or_raise(je, je_accounts)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"errors": e.errors})

    # Calculate totals
    je.total_debit = sum(((a.debit or Decimal("0")) for a in je_accounts), Decimal("0"))
    je.total_credit = sum(((a.credit or Decimal("0")) for a in je_accounts), Decimal("0"))

    db.add(je)
    db.flush()

    # Add account lines
    for idx, acc in enumerate(je_accounts, 1):
        acc.journal_entry_id = je.id
        acc.idx = idx
        db.add(acc)

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        new_values=serialize_for_audit(je),
    )

    db.commit()

    return {
        "message": "Journal entry created",
        "id": je.id,
        "total_debit": str(je.total_debit),
        "total_credit": str(je.total_credit),
        "docstatus": je.docstatus,
    }


@router.patch("/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))])
def update_journal_entry(
    je_id: int,
    posting_date: Optional[str] = None,
    user_remark: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a draft journal entry.

    Args:
        je_id: Journal entry ID
        posting_date: New posting date
        user_remark: New remark

    Returns:
        Updated journal entry info
    """
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if je.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only update draft entries")

    old_values = serialize_for_audit(je)

    if posting_date:
        parsed_posting_date = parse_date(posting_date, "posting_date")
        je.posting_date = datetime.combine(parsed_posting_date, datetime.min.time()) if parsed_posting_date else None
    if user_remark is not None:
        je.user_remark = user_remark

    je.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        old_values=old_values,
        new_values=serialize_for_audit(je),
    )

    db.commit()

    return {
        "message": "Journal entry updated",
        "id": je.id,
    }


@router.delete("/journal-entries/{je_id}", dependencies=[Depends(Require("books:write"))])
def delete_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Delete a draft journal entry.

    Args:
        je_id: Journal entry ID

    Returns:
        Deletion confirmation
    """
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if je.docstatus != 0:
        raise HTTPException(status_code=400, detail="Can only delete draft entries")

    old_values = serialize_for_audit(je)

    # Audit log before delete
    audit = AuditLogger(db)
    audit.log_delete(
        doctype="journal_entry",
        document_id=je.id,
        user_id=user.id,
        old_values=old_values,
    )

    db.delete(je)
    db.commit()

    return {"message": "Journal entry deleted"}


# =============================================================================
# JOURNAL ENTRY WORKFLOW ACTIONS
# =============================================================================

@router.post("/journal-entries/{je_id}/submit", dependencies=[Depends(Require("books:write"))])
async def submit_journal_entry(
    je_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Submit a journal entry for approval.

    Args:
        je_id: Journal entry ID

    Returns:
        Submission status with approval info
    """
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    engine = ApprovalEngine(db)
    try:
        approval = engine.submit_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            amount=je.total_debit,
            document_name=je.erpnext_id,
        )
        db.commit()
        return {
            "message": "Journal entry submitted for approval",
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/approve", dependencies=[Depends(Require("books:approve"))])
async def approve_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Approve a journal entry at the current step.

    Args:
        je_id: Journal entry ID
        remarks: Approval remarks

    Returns:
        Approval status
    """
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.approve_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            remarks=remarks,
        )
        db.commit()
        return {
            "message": "Journal entry approved",
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/reject", dependencies=[Depends(Require("books:approve"))])
async def reject_journal_entry(
    je_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Reject a journal entry.

    Args:
        je_id: Journal entry ID
        reason: Rejection reason

    Returns:
        Rejection status
    """
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.reject_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            reason=reason,
        )
        db.commit()
        return {
            "message": "Journal entry rejected",
            "approval_id": approval.id,
            "status": approval.status.value,
            "rejection_reason": approval.rejection_reason,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/journal-entries/{je_id}/post", dependencies=[Depends(Require("books:approve"))])
async def post_journal_entry(
    je_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Post an approved journal entry to the GL.

    Args:
        je_id: Journal entry ID
        remarks: Posting remarks

    Returns:
        Posting status
    """
    from app.services.approval_engine import ApprovalEngine, ApprovalError

    engine = ApprovalEngine(db)
    try:
        approval = engine.post_document(
            doctype="journal_entry",
            document_id=je_id,
            user_id=user.id,
            remarks=remarks,
        )

        # Update JE docstatus to posted
        je = db.query(JournalEntry).filter(JournalEntry.id == je_id).first()
        if je:
            je.docstatus = 1  # Posted

        db.commit()

        # Invalidate report caches after posting
        await invalidate_report_cache()

        return {
            "message": "Journal entry posted",
            "approval_id": approval.id,
            "status": approval.status.value,
        }
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""Document Attachments: Upload and manage file attachments on accounting documents."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.document_attachment import DocumentAttachment

from .helpers import paginate

router = APIRouter()

# Configuration - should come from settings
UPLOAD_DIR = "/tmp/attachments"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"}


# =============================================================================
# DOCUMENT ATTACHMENTS
# =============================================================================

@router.get("/documents/{doctype}/{doc_id}/attachments", dependencies=[Depends(Require("accounting:read"))])
def list_document_attachments(
    doctype: str,
    doc_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attachments for a document."""
    attachments = db.query(DocumentAttachment).filter(
        DocumentAttachment.doctype == doctype,
        DocumentAttachment.document_id == doc_id,
    ).order_by(DocumentAttachment.uploaded_at.desc()).all()

    return {
        "total": len(attachments),
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "file_type": a.file_type,
                "file_size": a.file_size,
                "attachment_type": a.attachment_type,
                "is_primary": a.is_primary,
                "description": a.description,
                "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
                "uploaded_by_id": a.uploaded_by_id,
            }
            for a in attachments
        ],
    }


@router.post("/documents/{doctype}/{doc_id}/attachments", dependencies=[Depends(Require("books:write"))])
async def upload_attachment(
    doctype: str,
    doc_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Upload an attachment for a document."""
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = f"{unique_id}_{file.filename}"

    # Create upload directory if needed
    doc_dir = os.path.join(UPLOAD_DIR, doctype, str(doc_id))
    os.makedirs(doc_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(doc_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # If setting as primary, unset any existing primary
    if is_primary:
        db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == doc_id,
            DocumentAttachment.is_primary == True,
        ).update({"is_primary": False})

    # Create attachment record
    attachment = DocumentAttachment(
        doctype=doctype,
        document_id=doc_id,
        file_name=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        attachment_type=attachment_type,
        is_primary=is_primary,
        description=description,
        uploaded_by_id=user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return {
        "message": "Attachment uploaded",
        "id": attachment.id,
        "file_name": attachment.file_name,
        "file_size": attachment.file_size,
    }


@router.get("/attachments/{attachment_id}", dependencies=[Depends(Require("accounting:read"))])
def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attachment details."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return {
        "id": attachment.id,
        "doctype": attachment.doctype,
        "document_id": attachment.document_id,
        "file_name": attachment.file_name,
        "file_path": attachment.file_path,
        "file_type": attachment.file_type,
        "file_size": attachment.file_size,
        "attachment_type": attachment.attachment_type,
        "is_primary": attachment.is_primary,
        "description": attachment.description,
        "uploaded_at": attachment.uploaded_at.isoformat() if attachment.uploaded_at else None,
        "uploaded_by_id": attachment.uploaded_by_id,
    }


@router.delete("/attachments/{attachment_id}", dependencies=[Depends(Require("books:write"))])
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Delete an attachment."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Delete file from disk
    if os.path.exists(attachment.file_path):
        try:
            os.remove(attachment.file_path)
        except OSError:
            pass  # File might already be deleted

    db.delete(attachment)
    db.commit()

    return {"message": "Attachment deleted"}


@router.patch("/attachments/{attachment_id}", dependencies=[Depends(Require("books:write"))])
def update_attachment(
    attachment_id: int,
    description: Optional[str] = None,
    attachment_type: Optional[str] = None,
    is_primary: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update attachment metadata."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if description is not None:
        attachment.description = description

    if attachment_type is not None:
        attachment.attachment_type = attachment_type

    if is_primary is not None:
        if is_primary:
            # Unset any existing primary
            db.query(DocumentAttachment).filter(
                DocumentAttachment.doctype == attachment.doctype,
                DocumentAttachment.document_id == attachment.document_id,
                DocumentAttachment.is_primary == True,
                DocumentAttachment.id != attachment_id,
            ).update({"is_primary": False})
        attachment.is_primary = is_primary

    db.commit()

    return {
        "message": "Attachment updated",
        "id": attachment.id,
    }


# =============================================================================
# ATTACHMENT REQUIREMENTS
# =============================================================================

@router.get("/documents/{doctype}/{doc_id}/attachment-requirements", dependencies=[Depends(Require("accounting:read"))])
def check_attachment_requirements(
    doctype: str,
    doc_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Check if attachment requirements are met for a document."""
    from app.models.accounting_ext import AccountingControl

    # Get accounting control settings
    control = db.query(AccountingControl).first()

    required = False
    has_attachment = False

    # Check if attachment is required for this doctype
    if control:
        if doctype == "supplier_payment" and getattr(control, "require_attachment_supplier_payment", False):
            required = True
        elif doctype == "journal_entry" and getattr(control, "require_attachment_journal_entry", False):
            required = True
        elif doctype == "purchase_invoice" and getattr(control, "require_attachment_purchase_invoice", False):
            required = True

    # Check if document has attachments
    attachment_count = db.query(DocumentAttachment).filter(
        DocumentAttachment.doctype == doctype,
        DocumentAttachment.document_id == doc_id,
    ).count()

    has_attachment = attachment_count > 0

    return {
        "doctype": doctype,
        "document_id": doc_id,
        "attachment_required": required,
        "has_attachment": has_attachment,
        "attachment_count": attachment_count,
        "requirement_met": not required or has_attachment,
    }

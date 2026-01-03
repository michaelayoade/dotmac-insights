"""Document Attachments: Upload and manage file attachments on accounting documents."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.services.accounting import DocumentAttachmentService
from app.services.accounting.attachments_types import (
    AttachmentUploadData,
    AttachmentUpdateData,
)
from app.services.errors import NotFoundError

router = APIRouter()


# SERVICE DEPENDENCIES


def get_attachment_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DocumentAttachmentService:
    """Dependency to get a DocumentAttachmentService instance."""
    return DocumentAttachmentService(db, principal)


# DOCUMENT ATTACHMENTS


@router.get("/documents/{doctype}/{doc_id}/attachments", dependencies=[Depends(Require("accounting:read"))])
def list_document_attachments(
    doctype: str,
    doc_id: int,
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """List attachments for a document."""
    attachments = service.list_attachments(doctype, doc_id)

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
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """Upload an attachment for a document."""
    # Read file content first (async operation stays in route)
    content = await file.read()
    file_size = len(content)

    # Validate file using service
    validation = service.validate_file(file.filename or "", file_size)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.error)

    # Ensure upload directory exists
    service.ensure_upload_directory(doctype, doc_id)

    # Get file path for storage
    file_path = service.get_upload_path(doctype, doc_id, validation.sanitized_filename)

    # Write file to disk (I/O stays in route)
    with open(file_path, "wb") as f:
        f.write(content)

    # Create attachment record using service
    upload_data = AttachmentUploadData(
        doctype=doctype,
        document_id=doc_id,
        file_name=file.filename or "upload",
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        attachment_type=attachment_type,
        description=description,
        is_primary=is_primary,
    )

    attachment = service.create_attachment(upload_data)
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
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """Get attachment details."""
    try:
        attachment = service.get_attachment(attachment_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """Delete an attachment."""
    try:
        # Delete record and get file path
        file_path = service.delete_attachment(attachment_id)
        db.commit()

        # Delete file from disk (I/O stays in route)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass  # File might already be deleted

        return {"message": "Attachment deleted"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/attachments/{attachment_id}", dependencies=[Depends(Require("books:write"))])
def update_attachment(
    attachment_id: int,
    description: Optional[str] = None,
    attachment_type: Optional[str] = None,
    is_primary: Optional[bool] = None,
    db: Session = Depends(get_db),
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """Update attachment metadata."""
    try:
        update_data = AttachmentUpdateData(
            description=description,
            attachment_type=attachment_type,
            is_primary=is_primary,
        )
        attachment = service.update_attachment(attachment_id, update_data)
        db.commit()

        return {
            "message": "Attachment updated",
            "id": attachment.id,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ATTACHMENT REQUIREMENTS


@router.get("/documents/{doctype}/{doc_id}/attachment-requirements", dependencies=[Depends(Require("accounting:read"))])
def check_attachment_requirements(
    doctype: str,
    doc_id: int,
    service: DocumentAttachmentService = Depends(get_attachment_service),
) -> Dict[str, Any]:
    """Check if attachment requirements are met for a document."""
    result = service.check_requirements(doctype, doc_id)

    return {
        "doctype": result.doctype,
        "document_id": result.document_id,
        "attachment_required": result.attachment_required,
        "has_attachment": result.has_attachment,
        "attachment_count": result.attachment_count,
        "requirement_met": result.requirement_met,
    }

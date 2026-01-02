"""
Attachments Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models import (
    Project,
    ProjectStatus,
    ProjectPriority,
    ProjectType,
    ProjectUser,
    ProjectComment,
    ProjectActivity,
    ProjectActivityType,
    ProjectTemplate,
    TaskTemplate,
    MilestoneTemplate,
    Task,
    TaskStatus,
    TaskPriority,
    TaskDependency,
    Milestone,
    MilestoneStatus,
)
from app.models.customer import Customer
from app.models.employee import Employee
from app.api.projects.schemas import _log_activity

router = APIRouter()

# =============================================================================
# ATTACHMENTS
# =============================================================================

from fastapi import UploadFile, File, Form
import os
import uuid

from app.models.document_attachment import DocumentAttachment

# Configuration
UPLOAD_DIR = "/tmp/attachments/projects"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip"}

# Valid entity types for attachments
ATTACHMENT_ENTITY_TYPES = {"project", "task", "milestone"}


def _serialize_attachment(a: DocumentAttachment) -> Dict[str, Any]:
    """Serialize attachment to dict."""
    return {
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


@router.get("/projects/{entity_type}/{entity_id}/attachments", dependencies=[Depends(Require("explorer:read"))])
async def list_entity_attachments(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attachments for a project entity (project, task, or milestone)."""
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type. Must be one of: {ATTACHMENT_ENTITY_TYPES}")

    doctype = f"project_{entity_type}"  # e.g., "project_project", "project_task", "project_milestone"

    attachments = db.query(DocumentAttachment).filter(
        DocumentAttachment.doctype == doctype,
        DocumentAttachment.document_id == entity_id,
    ).order_by(DocumentAttachment.uploaded_at.desc()).all()

    return {
        "total": len(attachments),
        "data": [_serialize_attachment(a) for a in attachments],
    }


@router.post("/projects/{entity_type}/{entity_id}/attachments", dependencies=[Depends(Require("projects:write"))])
async def upload_entity_attachment(
    entity_type: str,
    entity_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Upload an attachment for a project entity."""
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type. Must be one of: {ATTACHMENT_ENTITY_TYPES}")

    # Verify entity exists
    entity: object | None = None
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id).first()
    elif entity_type == "milestone":
        entity = db.query(Milestone).filter(Milestone.id == entity_id, Milestone.is_deleted == False).first()
    else:
        entity = None

    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

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

    # Create upload directory
    doctype = f"project_{entity_type}"
    doc_dir = os.path.join(UPLOAD_DIR, entity_type, str(entity_id))
    os.makedirs(doc_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(doc_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # If setting as primary, unset any existing primary
    if is_primary:
        db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == entity_id,
            DocumentAttachment.is_primary == True,
        ).update({"is_primary": False})

    # Create attachment record
    attachment = DocumentAttachment(
        doctype=doctype,
        document_id=entity_id,
        file_name=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        attachment_type=attachment_type,
        is_primary=is_primary,
        description=description,
        uploaded_by_id=principal.id,
    )
    db.add(attachment)

    # Log activity
    _log_activity(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=ProjectActivityType.ATTACHMENT_ADDED,
        description=f"Attachment '{file.filename}' added",
        actor_id=principal.id,
        actor_name=user.name if hasattr(user, "name") else None,
        actor_email=user.email if hasattr(user, "email") else None,
    )

    db.commit()
    db.refresh(attachment)

    return {
        "message": "Attachment uploaded",
        "id": attachment.id,
        "file_name": attachment.file_name,
        "file_size": attachment.file_size,
    }


@router.get("/projects/attachments/{attachment_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attachment details."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
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


@router.delete("/projects/attachments/{attachment_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an attachment."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Delete file from disk
    if os.path.exists(attachment.file_path):
        try:
            os.remove(attachment.file_path)
        except OSError:
            pass  # File might already be deleted

    # Extract entity info for activity log
    entity_type = attachment.doctype.replace("project_", "")
    entity_id = attachment.document_id
    file_name = attachment.file_name

    db.delete(attachment)
    db.commit()

    return {"message": "Attachment deleted", "id": attachment_id}


@router.get("/projects/attachments/{attachment_id}/download", dependencies=[Depends(Require("explorer:read"))])
async def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
):
    """Download an attachment file."""
    from fastapi.responses import FileResponse

    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=attachment.file_path,
        filename=attachment.file_name,
        media_type=attachment.file_type or "application/octet-stream",
    )


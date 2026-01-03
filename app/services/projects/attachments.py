"""Attachment service for projects, tasks, and milestones.

This service handles:
- Uploading attachments with file validation
- Listing attachments for entities
- Deleting attachments
- Managing primary attachment flag
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.models.project import Project, Milestone, ProjectActivityType
from app.models.task import Task

from .activities import ActivityService
from .activity_types import ActivityCreateData
from .attachment_types import AttachmentConfig, AttachmentUploadData
from .errors import (
    AttachmentError,
    AttachmentNotFoundError,
    InvalidEntityTypeError,
    ProjectNotFoundError,
    TaskNotFoundError,
    MilestoneNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AttachmentService"]

VALID_ENTITY_TYPES = {"project", "task", "milestone"}

# Map entity types to document attachment types
ENTITY_TO_DOC_TYPE = {
    "project": "project",
    "task": "task",
    "milestone": "milestone",
}


class AttachmentService:
    """Service for managing project attachments.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
        config: Optional attachment configuration.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        config: Optional[AttachmentConfig] = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self.config = config or AttachmentConfig()
        self._activity_service: Optional[ActivityService] = None

    @property
    def activity_service(self) -> ActivityService:
        """Get activity service (lazy loaded)."""
        if self._activity_service is None:
            self._activity_service = ActivityService(self.db, self.principal)
        return self._activity_service

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def list_entity_attachments(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[DocumentAttachment]:
        """List attachments for an entity.

        Args:
            entity_type: Type of entity ('project', 'task', 'milestone')
            entity_id: ID of the entity

        Returns:
            List of attachments

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(entity_type, list(VALID_ENTITY_TYPES))

        doc_type = ENTITY_TO_DOC_TYPE[entity_type]

        attachments = (
            self.db.query(DocumentAttachment)
            .filter(
                DocumentAttachment.document_type == doc_type,
                DocumentAttachment.document_id == entity_id,
            )
            .order_by(DocumentAttachment.created_at.desc())
            .all()
        )

        return attachments

    def get_attachment(self, attachment_id: int) -> DocumentAttachment:
        """Get an attachment by ID.

        Args:
            attachment_id: ID of the attachment

        Returns:
            The attachment

        Raises:
            AttachmentNotFoundError: If attachment does not exist
        """
        attachment = (
            self.db.query(DocumentAttachment)
            .filter(DocumentAttachment.id == attachment_id)
            .first()
        )
        if not attachment:
            raise AttachmentNotFoundError(attachment_id)
        return attachment

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def upload_attachment(self, data: AttachmentUploadData) -> DocumentAttachment:
        """Upload a new attachment.

        Args:
            data: Attachment upload data including file content

        Returns:
            The created attachment record (not yet committed)

        Raises:
            InvalidEntityTypeError: If entity_type is not valid
            AttachmentError: If file validation fails
            ProjectNotFoundError: If project does not exist
            TaskNotFoundError: If task does not exist
            MilestoneNotFoundError: If milestone does not exist
        """
        if data.entity_type not in VALID_ENTITY_TYPES:
            raise InvalidEntityTypeError(data.entity_type, list(VALID_ENTITY_TYPES))

        # Validate entity exists
        self._validate_entity_exists(data.entity_type, data.entity_id)

        # Validate file
        self._validate_file(data.file_name, data.file_content)

        # Generate safe filename and save file
        safe_filename = self._generate_safe_filename(data.file_name)
        file_path = self._save_file(
            data.entity_type,
            data.entity_id,
            safe_filename,
            data.file_content,
        )

        # Create attachment record
        doc_type = ENTITY_TO_DOC_TYPE[data.entity_type]
        uploaded_by_id = self.principal.id if self.principal else None

        attachment = DocumentAttachment(
            document_type=doc_type,
            document_id=data.entity_id,
            file_name=data.file_name,
            file_path=file_path,
            file_size=len(data.file_content),
            content_type=data.content_type,
            attachment_type=data.attachment_type,
            description=data.description,
            is_primary=data.is_primary,
            uploaded_by_id=uploaded_by_id,
            company=data.company,
        )
        self.db.add(attachment)
        self.db.flush()

        # If this is marked as primary, unset other primary attachments
        if data.is_primary:
            self._unset_other_primary(
                doc_type,
                data.entity_id,
                attachment.id,
            )

        # Log activity
        self.activity_service.log_activity(
            ActivityCreateData(
                entity_type=data.entity_type,
                entity_id=data.entity_id,
                activity_type=ProjectActivityType.ATTACHMENT_ADDED,
                description=f"Attachment '{data.file_name}' added",
                company=data.company,
            )
        )

        return attachment

    def delete_attachment(self, attachment_id: int) -> None:
        """Delete an attachment.

        This deletes both the database record and the file on disk.

        Args:
            attachment_id: ID of the attachment to delete

        Raises:
            AttachmentNotFoundError: If attachment does not exist
        """
        attachment = self.get_attachment(attachment_id)

        # Delete file from disk if it exists
        if attachment.file_path and os.path.exists(attachment.file_path):
            try:
                os.remove(attachment.file_path)
            except OSError:
                pass  # Log but don't fail if file deletion fails

        # Delete database record
        self.db.delete(attachment)

    def set_primary(self, attachment_id: int) -> DocumentAttachment:
        """Set an attachment as primary for its entity.

        Args:
            attachment_id: ID of the attachment to set as primary

        Returns:
            The updated attachment

        Raises:
            AttachmentNotFoundError: If attachment does not exist
        """
        attachment = self.get_attachment(attachment_id)

        # Unset other primary attachments
        self._unset_other_primary(
            attachment.document_type,
            attachment.document_id,
            attachment.id,
        )

        attachment.is_primary = True

        return attachment

    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------

    def _validate_file(self, filename: str, content: bytes) -> None:
        """Validate file size and extension.

        Args:
            filename: Original filename
            content: File content bytes

        Raises:
            AttachmentError: If validation fails
        """
        # Check file size
        if len(content) > self.config.max_file_size:
            max_mb = self.config.max_file_size / (1024 * 1024)
            raise AttachmentError(f"File size exceeds maximum of {max_mb:.1f}MB")

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in self.config.allowed_extensions:
            allowed = ", ".join(sorted(self.config.allowed_extensions))
            raise AttachmentError(f"File type '{ext}' not allowed. Allowed types: {allowed}")

    def _generate_safe_filename(self, original: str) -> str:
        """Generate a safe, unique filename.

        Args:
            original: Original filename

        Returns:
            Safe filename with UUID prefix
        """
        # Get extension
        ext = Path(original).suffix.lower()

        # Generate unique name
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        # Clean original name (keep only alphanumeric and basic chars)
        base_name = Path(original).stem
        clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
        clean_name = clean_name[:50]  # Limit length

        return f"{timestamp}_{unique_id}_{clean_name}{ext}"

    def _save_file(
        self,
        entity_type: str,
        entity_id: int,
        filename: str,
        content: bytes,
    ) -> str:
        """Save file to disk.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            filename: Safe filename to use
            content: File content bytes

        Returns:
            Full path to saved file
        """
        # Create directory structure
        dir_path = Path(self.config.upload_dir) / entity_type / str(entity_id)
        dir_path.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = dir_path / filename
        file_path.write_bytes(content)

        return str(file_path)

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def _validate_entity_exists(self, entity_type: str, entity_id: int) -> None:
        """Validate that the referenced entity exists.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Raises:
            ProjectNotFoundError: If project does not exist
            TaskNotFoundError: If task does not exist
            MilestoneNotFoundError: If milestone does not exist
        """
        if entity_type == "project":
            exists = (
                self.db.query(Project)
                .filter(Project.id == entity_id, Project.is_deleted == False)
                .first()
            )
            if not exists:
                raise ProjectNotFoundError(entity_id)

        elif entity_type == "task":
            exists = self.db.query(Task).filter(Task.id == entity_id).first()
            if not exists:
                raise TaskNotFoundError(entity_id)

        elif entity_type == "milestone":
            exists = (
                self.db.query(Milestone)
                .filter(Milestone.id == entity_id, Milestone.is_deleted == False)
                .first()
            )
            if not exists:
                raise MilestoneNotFoundError(entity_id)

    def _unset_other_primary(
        self,
        document_type: str,
        document_id: int,
        exclude_id: int,
    ) -> None:
        """Unset primary flag on other attachments for the same entity.

        Args:
            document_type: Document type
            document_id: Document ID
            exclude_id: Attachment ID to exclude from update
        """
        self.db.query(DocumentAttachment).filter(
            DocumentAttachment.document_type == document_type,
            DocumentAttachment.document_id == document_id,
            DocumentAttachment.id != exclude_id,
            DocumentAttachment.is_primary == True,
        ).update({"is_primary": False})

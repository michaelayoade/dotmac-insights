"""Document Attachment service.

This module contains business logic for document attachments.
All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.

Note: File I/O operations (reading/writing files) should be handled by the route handler.
This service handles the database operations and validation logic.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.services.errors import NotFoundError, ValidationError

from .attachments_types import (
    AttachmentFilters,
    AttachmentUploadData,
    AttachmentUpdateData,
    AttachmentConfig,
    AttachmentRequirementResult,
    FileValidationResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["DocumentAttachmentService"]

# Default configuration
DEFAULT_CONFIG = AttachmentConfig()


class DocumentAttachmentService:
    """Service for document attachment business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        config: Optional[AttachmentConfig] = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self.config = config or DEFAULT_CONFIG

    def list_attachments(
        self,
        doctype: str,
        document_id: int,
        attachment_type: Optional[str] = None,
    ) -> List[DocumentAttachment]:
        """List attachments for a document.

        Args:
            doctype: The document type.
            document_id: The document ID.
            attachment_type: Optional filter by attachment type.

        Returns:
            List of DocumentAttachment objects.
        """
        query = self.db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == document_id,
        )

        if attachment_type:
            query = query.filter(DocumentAttachment.attachment_type == attachment_type)

        return query.order_by(DocumentAttachment.uploaded_at.desc()).all()

    def get_attachment(self, attachment_id: int) -> DocumentAttachment:
        """Get attachment by ID.

        Args:
            attachment_id: The attachment ID.

        Returns:
            The DocumentAttachment object.

        Raises:
            NotFoundError: If attachment not found.
        """
        attachment = (
            self.db.query(DocumentAttachment)
            .filter(DocumentAttachment.id == attachment_id)
            .first()
        )
        if not attachment:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return attachment

    def validate_file(self, filename: str, file_size: int) -> FileValidationResult:
        """Validate file for upload.

        Checks file extension against whitelist and file size against limit.
        Also sanitizes filename for security.

        Args:
            filename: The original filename.
            file_size: The file size in bytes.

        Returns:
            FileValidationResult with validation status and sanitized filename.
        """
        if not filename:
            return FileValidationResult(
                is_valid=False,
                error="File name is required",
            )

        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in self.config.allowed_extensions:
            return FileValidationResult(
                is_valid=False,
                error=f"File type {file_ext} not allowed. Allowed: {', '.join(sorted(self.config.allowed_extensions))}",
                file_extension=file_ext,
            )

        # Check file size
        if file_size > self.config.max_file_size:
            max_mb = self.config.max_file_size // (1024 * 1024)
            return FileValidationResult(
                is_valid=False,
                error=f"File too large. Maximum size is {max_mb}MB",
            )

        # Sanitize filename
        sanitized = self.sanitize_filename(filename)

        return FileValidationResult(
            is_valid=True,
            sanitized_filename=sanitized,
            file_extension=file_ext,
        )

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for secure storage.

        - Removes path components
        - Removes special characters except . - _
        - Prevents double extensions (e.g., .pdf.exe)
        - Adds unique prefix

        Args:
            filename: The original filename.

        Returns:
            Sanitized filename with unique prefix.
        """
        unique_id = uuid.uuid4().hex[:8]

        # Remove path components
        original_filename = os.path.basename(filename or "upload")

        # Remove special characters except . - _
        sanitized = re.sub(r'[^\w.\-]', '_', original_filename)

        # Prevent double extensions like .pdf.exe
        if sanitized.count('.') > 1:
            parts = sanitized.rsplit('.', 1)
            sanitized = parts[0].replace('.', '_') + '.' + parts[1]

        return f"{unique_id}_{sanitized}"

    def get_upload_path(self, doctype: str, document_id: int, filename: str) -> str:
        """Get the full path for uploading a file.

        Args:
            doctype: The document type.
            document_id: The document ID.
            filename: The sanitized filename.

        Returns:
            Full file path.
        """
        doc_dir = os.path.join(self.config.upload_dir, doctype, str(document_id))
        return os.path.join(doc_dir, filename)

    def ensure_upload_directory(self, doctype: str, document_id: int) -> str:
        """Ensure upload directory exists.

        Args:
            doctype: The document type.
            document_id: The document ID.

        Returns:
            Path to the upload directory.
        """
        doc_dir = os.path.join(self.config.upload_dir, doctype, str(document_id))
        os.makedirs(doc_dir, exist_ok=True)
        return doc_dir

    def create_attachment(self, data: AttachmentUploadData) -> DocumentAttachment:
        """Create an attachment record.

        Note: The actual file should already be saved by the route handler.

        Args:
            data: Attachment data.

        Returns:
            The created DocumentAttachment (not yet committed).
        """
        # If setting as primary, unset any existing primary
        if data.is_primary:
            self._unset_primary(data.doctype, data.document_id)

        attachment = DocumentAttachment(
            doctype=data.doctype,
            document_id=data.document_id,
            file_name=data.file_name,
            file_path=data.file_path,
            file_type=data.file_type,
            file_size=data.file_size,
            attachment_type=data.attachment_type,
            is_primary=data.is_primary,
            description=data.description,
            uploaded_by_id=self.principal.id if self.principal else None,
        )
        self.db.add(attachment)
        self.db.flush()

        return attachment

    def update_attachment(
        self, attachment_id: int, data: AttachmentUpdateData
    ) -> DocumentAttachment:
        """Update attachment metadata.

        Args:
            attachment_id: The attachment ID.
            data: Fields to update.

        Returns:
            The updated DocumentAttachment (not yet committed).

        Raises:
            NotFoundError: If attachment not found.
        """
        attachment = self.get_attachment(attachment_id)

        if data.description is not None:
            attachment.description = data.description

        if data.attachment_type is not None:
            attachment.attachment_type = data.attachment_type

        if data.is_primary is not None:
            if data.is_primary:
                # Unset any existing primary (excluding this one)
                self._unset_primary(
                    attachment.doctype,
                    attachment.document_id,
                    exclude_id=attachment_id,
                )
            attachment.is_primary = data.is_primary

        return attachment

    def delete_attachment(self, attachment_id: int) -> str:
        """Delete an attachment record.

        Note: The route handler should delete the actual file.

        Args:
            attachment_id: The attachment ID.

        Returns:
            The file path (so route can delete the file).

        Raises:
            NotFoundError: If attachment not found.
        """
        attachment = self.get_attachment(attachment_id)
        file_path = attachment.file_path

        self.db.delete(attachment)

        return file_path

    def set_primary(self, attachment_id: int) -> DocumentAttachment:
        """Set an attachment as the primary attachment.

        Args:
            attachment_id: The attachment ID.

        Returns:
            The updated DocumentAttachment.

        Raises:
            NotFoundError: If attachment not found.
        """
        attachment = self.get_attachment(attachment_id)

        # Unset any existing primary
        self._unset_primary(
            attachment.doctype,
            attachment.document_id,
            exclude_id=attachment_id,
        )

        attachment.is_primary = True
        return attachment

    def _unset_primary(
        self,
        doctype: str,
        document_id: int,
        exclude_id: Optional[int] = None,
    ) -> None:
        """Unset primary flag on all attachments for a document.

        Args:
            doctype: The document type.
            document_id: The document ID.
            exclude_id: Optional attachment ID to exclude from update.
        """
        query = self.db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == document_id,
            DocumentAttachment.is_primary == True,  # noqa: E712
        )

        if exclude_id:
            query = query.filter(DocumentAttachment.id != exclude_id)

        query.update({"is_primary": False})

    def check_requirements(
        self, doctype: str, document_id: int
    ) -> AttachmentRequirementResult:
        """Check if attachment requirements are met for a document.

        Args:
            doctype: The document type.
            document_id: The document ID.

        Returns:
            AttachmentRequirementResult with requirement status.
        """
        from app.models.accounting_ext import AccountingControl

        # Get accounting control settings
        control = self.db.query(AccountingControl).first()

        required = False

        # Check if attachment is required for this doctype
        if control:
            requirement_map = {
                "supplier_payment": "require_attachment_supplier_payment",
                "journal_entry": "require_attachment_journal_entry",
                "purchase_invoice": "require_attachment_purchase_invoice",
            }

            attr_name = requirement_map.get(doctype)
            if attr_name:
                required = getattr(control, attr_name, False)

        # Count attachments
        attachment_count = self.db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == document_id,
        ).count()

        has_attachment = attachment_count > 0

        return AttachmentRequirementResult(
            doctype=doctype,
            document_id=document_id,
            attachment_required=required,
            has_attachment=has_attachment,
            attachment_count=attachment_count,
            requirement_met=not required or has_attachment,
        )

    def get_attachment_count(self, doctype: str, document_id: int) -> int:
        """Get count of attachments for a document.

        Args:
            doctype: The document type.
            document_id: The document ID.

        Returns:
            Number of attachments.
        """
        return self.db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == document_id,
        ).count()

    def get_primary_attachment(
        self, doctype: str, document_id: int
    ) -> Optional[DocumentAttachment]:
        """Get the primary attachment for a document.

        Args:
            doctype: The document type.
            document_id: The document ID.

        Returns:
            The primary DocumentAttachment or None.
        """
        return (
            self.db.query(DocumentAttachment)
            .filter(
                DocumentAttachment.doctype == doctype,
                DocumentAttachment.document_id == document_id,
                DocumentAttachment.is_primary == True,  # noqa: E712
            )
            .first()
        )

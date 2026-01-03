"""Type definitions for document attachment service.

These dataclasses define the contract for attachment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

__all__ = [
    "AttachmentFilters",
    "AttachmentUploadData",
    "AttachmentUpdateData",
    "AttachmentConfig",
    "AttachmentRequirementResult",
    "FileValidationResult",
]


@dataclass
class AttachmentFilters:
    """Filters for listing attachments."""

    doctype: str
    document_id: int
    attachment_type: Optional[str] = None


@dataclass
class AttachmentUploadData:
    """Data for uploading an attachment."""

    doctype: str
    document_id: int
    file_name: str
    file_path: str
    file_type: Optional[str] = None
    file_size: int = 0
    attachment_type: Optional[str] = None
    description: Optional[str] = None
    is_primary: bool = False


@dataclass
class AttachmentUpdateData:
    """Data for updating attachment metadata (all fields optional)."""

    description: Optional[str] = None
    attachment_type: Optional[str] = None
    is_primary: Optional[bool] = None


@dataclass
class AttachmentConfig:
    """Attachment configuration settings."""

    upload_dir: str = "/tmp/attachments"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: Set[str] = None

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = {
                ".pdf", ".png", ".jpg", ".jpeg", ".gif",
                ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"
            }


@dataclass
class AttachmentRequirementResult:
    """Result of checking attachment requirements."""

    doctype: str
    document_id: int
    attachment_required: bool
    has_attachment: bool
    attachment_count: int
    requirement_met: bool


@dataclass
class FileValidationResult:
    """Result of file validation."""

    is_valid: bool
    error: Optional[str] = None
    sanitized_filename: Optional[str] = None
    file_extension: Optional[str] = None

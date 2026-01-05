"""Type definitions for attachment service.

These dataclasses define the contract for attachment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "AttachmentUploadData",
    "AttachmentConfig",
]


@dataclass
class AttachmentUploadData:
    """Data for uploading an attachment."""

    entity_type: str  # project, task, milestone
    entity_id: int
    file_name: str
    file_content: bytes
    content_type: str
    attachment_type: Optional[str] = None
    description: Optional[str] = None
    is_primary: bool = False
    company: Optional[str] = None


@dataclass(frozen=True)
class AttachmentConfig:
    """Configuration for attachment handling."""

    upload_dir: str = "/tmp/attachments/projects"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: frozenset = field(
        default_factory=lambda: frozenset({
            ".pdf", ".png", ".jpg", ".jpeg", ".gif",
            ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip"
        })
    )

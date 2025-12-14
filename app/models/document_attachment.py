"""Document Attachment model for tracking file attachments on documents."""
from __future__ import annotations

from sqlalchemy import String, ForeignKey, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.database import Base


class DocumentAttachment(Base):
    """
    Generic attachment model for any document type.

    Supports attachments on invoices, bills, payments, journal entries, etc.
    Uses doctype + document_id pattern for polymorphic linking.
    """

    __tablename__ = "document_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Polymorphic document link
    doctype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # File information
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # MIME type
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Size in bytes

    # Classification
    attachment_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # e.g., "receipt", "contract", "approval"
    is_primary: Mapped[bool] = mapped_column(default=False)  # Main attachment for document

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Audit
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        # Index for looking up attachments by document
        Index("ix_document_attachments_doc", "doctype", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentAttachment {self.file_name} on {self.doctype}:{self.document_id}>"

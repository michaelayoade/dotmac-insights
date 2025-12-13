"""
Audit Logger Service

Provides immutable audit logging for all accounting operations.
All changes to accounting documents are recorded with full before/after state.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.accounting_ext import AuditLog, AuditAction
from app.models.auth import User


class AuditLogger:
    """Service for creating immutable audit log entries."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        doctype: str,
        document_id: int,
        action: AuditAction,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        document_name: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        changed_fields: Optional[List[str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an immutable audit log entry.

        Args:
            doctype: Document type (e.g., "journal_entry", "expense")
            document_id: ID of the document
            action: Type of action performed
            user_id: ID of the user performing the action
            user_email: Email of the user (denormalized for immutability)
            user_name: Name of the user (denormalized for immutability)
            document_name: Human-readable document reference
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            changed_fields: List of field names that changed
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request tracking ID
            remarks: Additional context

        Returns:
            Created AuditLog entry
        """
        # If user details not provided but user_id is, try to look them up
        if user_id and (not user_email or not user_name):
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user_email = user_email or user.email
                user_name = user_name or user.full_name

        # Auto-detect changed fields if not provided
        if changed_fields is None and old_values and new_values:
            changed_fields = self._detect_changed_fields(old_values, new_values)

        entry = AuditLog(
            doctype=doctype,
            document_id=document_id,
            document_name=document_name,
            action=action,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            remarks=remarks,
            timestamp=datetime.utcnow(),
        )
        self.db.add(entry)
        # Flush immediately to ensure the log is persisted
        self.db.flush()
        return entry

    def log_create(
        self,
        doctype: str,
        document_id: int,
        new_values: Dict[str, Any],
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document creation."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.CREATE,
            user_id=user_id,
            new_values=new_values,
            **kwargs
        )

    def log_update(
        self,
        doctype: str,
        document_id: int,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document update."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.UPDATE,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            **kwargs
        )

    def log_delete(
        self,
        doctype: str,
        document_id: int,
        old_values: Dict[str, Any],
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document deletion."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.DELETE,
            user_id=user_id,
            old_values=old_values,
            **kwargs
        )

    def log_submit(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document submission for approval."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.SUBMIT,
            user_id=user_id,
            **kwargs
        )

    def log_approve(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        remarks: Optional[str] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document approval."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.APPROVE,
            user_id=user_id,
            remarks=remarks,
            **kwargs
        )

    def log_reject(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        remarks: Optional[str] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document rejection."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.REJECT,
            user_id=user_id,
            remarks=remarks,
            **kwargs
        )

    def log_post(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document posting to GL."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.POST,
            user_id=user_id,
            **kwargs
        )

    def log_cancel(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        remarks: Optional[str] = None,
        **kwargs
    ) -> AuditLog:
        """Log a document cancellation."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.CANCEL,
            user_id=user_id,
            remarks=remarks,
            **kwargs
        )

    def log_close(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a period close."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.CLOSE,
            user_id=user_id,
            **kwargs
        )

    def log_reopen(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log a period reopen."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.REOPEN,
            user_id=user_id,
            **kwargs
        )

    def log_export(
        self,
        doctype: str,
        document_id: int,
        user_id: Optional[int] = None,
        remarks: Optional[str] = None,
        **kwargs
    ) -> AuditLog:
        """Log a data export."""
        return self.log(
            doctype=doctype,
            document_id=document_id,
            action=AuditAction.EXPORT,
            user_id=user_id,
            remarks=remarks,
            **kwargs
        )

    def get_document_history(
        self,
        doctype: str,
        document_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        """
        Get audit history for a specific document.

        Args:
            doctype: Document type
            document_id: Document ID
            limit: Max records to return
            offset: Pagination offset

        Returns:
            List of audit log entries, most recent first
        """
        return (
            self.db.query(AuditLog)
            .filter(
                and_(
                    AuditLog.doctype == doctype,
                    AuditLog.document_id == document_id,
                )
            )
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_user_activity(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        """
        Get audit activity for a specific user.

        Args:
            user_id: User ID
            start_date: Optional start of date range
            end_date: Optional end of date range
            limit: Max records to return
            offset: Pagination offset

        Returns:
            List of audit log entries, most recent first
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return (
            query
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def _detect_changed_fields(
        self,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
    ) -> List[str]:
        """Detect which fields changed between old and new values."""
        changed = []
        all_keys = set(old_values.keys()) | set(new_values.keys())

        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            if old_val != new_val:
                changed.append(key)

        return sorted(changed)


def serialize_for_audit(obj: Any) -> Dict[str, Any]:
    """
    Serialize a SQLAlchemy model instance for audit logging.

    Converts model to dict, handling special types like datetime, Decimal, Enum.
    """
    from decimal import Decimal
    from enum import Enum

    if obj is None:
        return {}

    result = {}
    # Get all column names from the model
    for column in obj.__table__.columns:
        key = column.name
        value = getattr(obj, key, None)

        # Convert special types
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        elif isinstance(value, Enum):
            value = value.value
        elif hasattr(value, '__dict__'):
            # Skip relationships/complex objects
            continue

        result[key] = value

    return result

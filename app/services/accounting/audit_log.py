"""Audit log service for accounting module."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.accounting_ext import AuditLog
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams

from .audit_log_types import AuditLogFilters

__all__ = ["AuditLogService"]


class AuditLogService:
    """Service for listing audit log entries."""

    def __init__(self, db: Session, principal: Optional[object] = None) -> None:
        self.db = db
        self.principal = principal

    def list_audit_logs(
        self,
        filters: AuditLogFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[AuditLog]:
        """List audit log entries with filters and pagination."""
        query = self.db.query(AuditLog)

        if filters.query:
            query = query.filter(
                or_(
                    AuditLog.document_name.ilike(f"%{filters.query}%"),
                    AuditLog.user_name.ilike(f"%{filters.query}%"),
                    AuditLog.user_email.ilike(f"%{filters.query}%"),
                )
            )

        if filters.doc_type:
            query = query.filter(AuditLog.doctype == filters.doc_type)

        if filters.action:
            query = query.filter(AuditLog.action == filters.action)

        if filters.date_from:
            query = query.filter(AuditLog.timestamp >= filters.date_from)

        if filters.date_to:
            query = query.filter(AuditLog.timestamp <= filters.date_to)

        query = query.order_by(AuditLog.timestamp.desc())
        return paginate(query, pagination)

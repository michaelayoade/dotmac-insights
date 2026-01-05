"""
Activity Logger Service.

Records high-level user activity events for audit and admin visibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.middleware.rate_limit import get_client_ip
from app.models.activity_log import ActivityLog
from app.models.auth import User


class ActivityLogger:
    """Service for creating activity log entries."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        action: str,
        user: Optional[User] = None,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        summary: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        request: Optional[Request] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ActivityLog:
        if user:
            user_id = user_id or user.id
            user_email = user_email or user.email

        if user_id and not user_email:
            lookup = self.db.query(User).filter(User.id == user_id).first()
            if lookup:
                user_email = lookup.email

        if request:
            ip_address = ip_address or get_client_ip(request)
            user_agent = user_agent or request.headers.get("user-agent", "")[:500]
            request_id = request_id or getattr(request.state, "request_id", None)

        entry = ActivityLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            metadata=metadata,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(entry)
        return entry

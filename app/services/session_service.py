"""Session Service - User session tracking and management.

Provides functionality for:
- Creating session records from JWT tokens
- Listing active sessions for a user
- Revoking individual or all sessions
- Session activity tracking
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import Request
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.auth import TokenDenylist, UserSession
from app.utils.datetime_utils import utc_now

logger = structlog.get_logger()


class SessionService:
    """Service for managing user sessions."""

    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        user_id: int,
        session_id: str,
        expires_at: datetime,
        request: Optional[Request] = None,
    ) -> UserSession:
        """
        Create a new session record.

        Args:
            user_id: The user this session belongs to
            session_id: Unique session identifier (JWT jti)
            expires_at: When the session/token expires
            request: Optional FastAPI request for device info

        Returns:
            The created UserSession record
        """
        device_info = None
        ip_address = None

        if request:
            device_info = {
                "user_agent": request.headers.get("user-agent"),
                "accept_language": request.headers.get("accept-language"),
                "referer": request.headers.get("referer"),
            }
            ip_address = self._get_client_ip(request)

        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.flush()

        logger.info(
            "session_created",
            user_id=user_id,
            session_id=session_id[:12] + "...",
            ip_address=ip_address,
        )

        return session

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by its ID."""
        return self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()

    def get_active_sessions(self, user_id: int) -> list[UserSession]:
        """
        Get all active sessions for a user.

        Returns sessions that are:
        - Active (is_active = True)
        - Not expired
        - Not revoked
        """
        now = utc_now()
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > now,
                UserSession.revoked_at.is_(None),
            )
        ).order_by(UserSession.last_activity_at.desc()).all()

    def get_session_count(self, user_id: int) -> int:
        """Get the count of active sessions for a user."""
        now = utc_now()
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > now,
                UserSession.revoked_at.is_(None),
            )
        ).count()

    def update_activity(self, session_id: str) -> bool:
        """
        Update the last activity timestamp for a session.

        Returns True if session was found and updated.
        """
        session = self.get_session(session_id)
        if not session or not session.is_valid:
            return False

        session.last_activity_at = utc_now()
        return True

    def revoke_session(
        self,
        session_id: str,
        revoked_by_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke a specific session.

        Args:
            session_id: The session to revoke
            revoked_by_id: User who revoked the session
            reason: Reason for revocation

        Returns:
            True if session was found and revoked
        """
        session = self.get_session(session_id)
        if not session:
            return False

        now = utc_now()
        session.is_active = False
        session.revoked_at = now
        session.revoked_by_id = revoked_by_id
        session.revoke_reason = reason

        # Also add to token denylist
        self._add_to_denylist(session_id, session.expires_at, reason)

        logger.info(
            "session_revoked",
            session_id=session_id[:12] + "...",
            user_id=session.user_id,
            revoked_by_id=revoked_by_id,
            reason=reason,
        )

        return True

    def revoke_all_sessions(
        self,
        user_id: int,
        revoked_by_id: Optional[int] = None,
        reason: Optional[str] = None,
        exclude_session_id: Optional[str] = None,
    ) -> int:
        """
        Revoke all sessions for a user.

        Args:
            user_id: The user whose sessions to revoke
            revoked_by_id: User who revoked the sessions
            reason: Reason for revocation
            exclude_session_id: Optional session to exclude (current session)

        Returns:
            Number of sessions revoked
        """
        sessions = self.get_active_sessions(user_id)
        now = utc_now()
        count = 0

        for session in sessions:
            if exclude_session_id and session.session_id == exclude_session_id:
                continue

            session.is_active = False
            session.revoked_at = now
            session.revoked_by_id = revoked_by_id
            session.revoke_reason = reason

            # Add to token denylist
            self._add_to_denylist(session.session_id, session.expires_at, reason)
            count += 1

        logger.info(
            "all_sessions_revoked",
            user_id=user_id,
            revoked_by_id=revoked_by_id,
            count=count,
            reason=reason,
        )

        return count

    def revoke_sessions_except_current(
        self,
        user_id: int,
        current_session_id: str,
        revoked_by_id: Optional[int] = None,
    ) -> int:
        """Revoke all sessions except the current one."""
        return self.revoke_all_sessions(
            user_id=user_id,
            revoked_by_id=revoked_by_id,
            reason="Revoked other sessions",
            exclude_session_id=current_session_id,
        )

    def cleanup_expired_sessions(self, days_old: int = 30) -> int:
        """
        Clean up expired session records older than specified days.

        This is for database maintenance, as expired sessions are
        already inactive and can be removed.

        Args:
            days_old: Delete sessions expired more than this many days ago

        Returns:
            Number of sessions deleted
        """
        cutoff = utc_now() - timedelta(days=days_old)

        result = self.db.execute(
            select(UserSession).where(UserSession.expires_at < cutoff)
        )
        sessions = result.scalars().all()
        count = len(sessions)

        for session in sessions:
            self.db.delete(session)

        logger.info("expired_sessions_cleaned", count=count, days_old=days_old)

        return count

    def _add_to_denylist(
        self,
        jti: str,
        expires_at: datetime,
        reason: Optional[str] = None,
    ) -> None:
        """Add a token to the denylist."""
        # Check if already in denylist
        existing = self.db.query(TokenDenylist).filter(
            TokenDenylist.jti == jti
        ).first()

        if existing:
            return

        denylist_entry = TokenDenylist(
            jti=jti,
            expires_at=expires_at,
            reason=reason or "Session revoked",
        )
        self.db.add(denylist_entry)

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request, handling proxies."""
        # Check X-Forwarded-For header (for proxied requests)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

    def get_session_by_ip(self, user_id: int, ip_address: str) -> Optional[UserSession]:
        """Get active session for a user from a specific IP."""
        now = utc_now()
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.ip_address == ip_address,
                UserSession.is_active == True,
                UserSession.expires_at > now,
                UserSession.revoked_at.is_(None),
            )
        ).first()

    def get_sessions_summary(self, user_id: int) -> dict:
        """
        Get a summary of user's sessions.

        Returns:
            Dict with session statistics
        """
        now = utc_now()
        sessions = self.get_active_sessions(user_id)

        # Get unique IPs
        ips = set(s.ip_address for s in sessions if s.ip_address)

        # Get devices (simplified by user agent)
        devices = set()
        for s in sessions:
            if s.device_info and s.device_info.get("user_agent"):
                ua = s.device_info["user_agent"]
                # Simplified device detection
                if "Mobile" in ua:
                    devices.add("mobile")
                elif "Tablet" in ua:
                    devices.add("tablet")
                else:
                    devices.add("desktop")

        return {
            "active_count": len(sessions),
            "unique_ips": len(ips),
            "device_types": list(devices),
            "oldest_session": min((s.created_at for s in sessions), default=None),
            "newest_session": max((s.created_at for s in sessions), default=None),
            "last_activity": max((s.last_activity_at for s in sessions), default=None),
        }

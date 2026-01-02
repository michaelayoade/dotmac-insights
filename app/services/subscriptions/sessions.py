"""Session service - manages active RADIUS/NAS sessions.

This service handles:
- Active session monitoring (radacct table)
- Session history and analytics
- User disconnection (CoA/Disconnect-Request)
- Session statistics and reporting
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.router import Router
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .subscription_types import (
    ActiveSession,
    SessionFilters,
    SessionHistory,
    DisconnectRequest,
    DisconnectResult,
    SessionStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

logger = logging.getLogger(__name__)

__all__ = ["SessionService"]


class SessionService:
    """Service for RADIUS session management.

    This service queries the FreeRADIUS radacct table for session data
    and can send disconnect requests via MikroTik API or RADIUS CoA.
    """

    def __init__(
        self,
        db: Session,
        radius_db: Optional[Session] = None,
        principal: Optional["Principal"] = None,
    ):
        """Initialize session service.

        Args:
            db: Main application database session.
            radius_db: Optional separate RADIUS database session.
                       If not provided, uses main db (assumes shared schema).
            principal: Optional authenticated principal.
        """
        self.db = db
        self.radius_db = radius_db or db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Active Sessions
    # -------------------------------------------------------------------------

    def list_active_sessions(
        self,
        filters: Optional[SessionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> List[ActiveSession]:
        """List active RADIUS sessions.

        Active sessions are those with acctstoptime IS NULL in radacct.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            List of ActiveSession objects.
        """
        # Build WHERE clauses
        where_clauses = ["acctstoptime IS NULL"]
        params: Dict[str, any] = {}

        if filters:
            if filters.username:
                where_clauses.append("username ILIKE :username")
                params["username"] = f"%{filters.username}%"

            if filters.nas_ip:
                where_clauses.append("nasipaddress = :nas_ip")
                params["nas_ip"] = filters.nas_ip

            if filters.framed_ip:
                where_clauses.append("framedipaddress = :framed_ip")
                params["framed_ip"] = filters.framed_ip

            if filters.date_from:
                where_clauses.append("acctstarttime >= :date_from")
                params["date_from"] = filters.date_from

            if filters.date_to:
                where_clauses.append("acctstarttime <= :date_to")
                params["date_to"] = filters.date_to

        where_sql = " AND ".join(where_clauses)

        # Add pagination
        limit_sql = ""
        if pagination:
            limit_sql = f"LIMIT {pagination.limit} OFFSET {pagination.offset}"

        query = text(f"""
            SELECT
                acctsessionid,
                username,
                nasipaddress,
                nasportid,
                framedipaddress,
                callingstationid,
                calledstationid,
                acctstarttime,
                EXTRACT(EPOCH FROM (NOW() - acctstarttime))::integer as session_seconds,
                acctinputoctets,
                acctoutputoctets,
                acctinputpackets,
                acctoutputpackets
            FROM radacct
            WHERE {where_sql}
            ORDER BY acctstarttime DESC
            {limit_sql}
        """)

        result = self.radius_db.execute(query, params)
        sessions = []

        for row in result:
            session = ActiveSession(
                session_id=row[0],
                username=row[1],
                nas_ip=row[2],
                nas_port_id=row[3],
                framed_ip=row[4],
                calling_station_id=row[5],
                called_station_id=row[6],
                session_start=row[7],
                session_duration_seconds=row[8] or 0,
                input_octets=row[9] or 0,
                output_octets=row[10] or 0,
                input_packets=row[11] or 0,
                output_packets=row[12] or 0,
            )

            # Enrich with subscription info
            self._enrich_session_with_subscription(session)
            sessions.append(session)

        return sessions

    def get_active_session(self, session_id: str) -> Optional[ActiveSession]:
        """Get a specific active session by ID.

        Args:
            session_id: The RADIUS session ID (acctsessionid).

        Returns:
            ActiveSession if found, None otherwise.
        """
        query = text("""
            SELECT
                acctsessionid,
                username,
                nasipaddress,
                nasportid,
                framedipaddress,
                callingstationid,
                calledstationid,
                acctstarttime,
                EXTRACT(EPOCH FROM (NOW() - acctstarttime))::integer as session_seconds,
                acctinputoctets,
                acctoutputoctets,
                acctinputpackets,
                acctoutputpackets
            FROM radacct
            WHERE acctsessionid = :session_id AND acctstoptime IS NULL
        """)

        result = self.radius_db.execute(query, {"session_id": session_id})
        row = result.fetchone()

        if not row:
            return None

        session = ActiveSession(
            session_id=row[0],
            username=row[1],
            nas_ip=row[2],
            nas_port_id=row[3],
            framed_ip=row[4],
            calling_station_id=row[5],
            called_station_id=row[6],
            session_start=row[7],
            session_duration_seconds=row[8] or 0,
            input_octets=row[9] or 0,
            output_octets=row[10] or 0,
            input_packets=row[11] or 0,
            output_packets=row[12] or 0,
        )

        self._enrich_session_with_subscription(session)
        return session

    def get_user_active_sessions(self, username: str) -> List[ActiveSession]:
        """Get all active sessions for a username.

        Args:
            username: The PPP/Hotspot username.

        Returns:
            List of active sessions.
        """
        filters = SessionFilters(username=username, active_only=True)
        return self.list_active_sessions(filters)

    def get_subscription_sessions(
        self, subscription_id: int
    ) -> List[ActiveSession]:
        """Get active sessions for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            List of active sessions.
        """
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )

        if not sub or not sub.ppp_username:
            return []

        return self.get_user_active_sessions(sub.ppp_username)

    # -------------------------------------------------------------------------
    # Session History
    # -------------------------------------------------------------------------

    def get_session_history(
        self,
        filters: Optional[SessionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> List[SessionHistory]:
        """Get historical (completed) sessions.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            List of SessionHistory objects.
        """
        where_clauses = ["acctstoptime IS NOT NULL"]
        params: Dict[str, any] = {}

        if filters:
            if filters.username:
                where_clauses.append("username ILIKE :username")
                params["username"] = f"%{filters.username}%"

            if filters.nas_ip:
                where_clauses.append("nasipaddress = :nas_ip")
                params["nas_ip"] = filters.nas_ip

            if filters.date_from:
                where_clauses.append("acctstarttime >= :date_from")
                params["date_from"] = filters.date_from

            if filters.date_to:
                where_clauses.append("acctstoptime <= :date_to")
                params["date_to"] = filters.date_to

        where_sql = " AND ".join(where_clauses)

        limit_sql = ""
        if pagination:
            limit_sql = f"LIMIT {pagination.limit} OFFSET {pagination.offset}"

        query = text(f"""
            SELECT
                acctsessionid,
                username,
                nasipaddress,
                framedipaddress,
                callingstationid,
                acctstarttime,
                acctstoptime,
                acctsessiontime,
                acctinputoctets,
                acctoutputoctets,
                acctterminatecause
            FROM radacct
            WHERE {where_sql}
            ORDER BY acctstoptime DESC
            {limit_sql}
        """)

        result = self.radius_db.execute(query, params)
        history = []

        for row in result:
            history.append(SessionHistory(
                session_id=row[0],
                username=row[1],
                nas_ip=row[2],
                framed_ip=row[3],
                calling_station_id=row[4],
                session_start=row[5],
                session_stop=row[6],
                session_duration_seconds=row[7] or 0,
                input_octets=row[8] or 0,
                output_octets=row[9] or 0,
                terminate_cause=row[10],
            ))

        return history

    def get_user_session_history(
        self,
        username: str,
        limit: int = 50,
    ) -> List[SessionHistory]:
        """Get session history for a specific user.

        Args:
            username: The PPP/Hotspot username.
            limit: Maximum records to return.

        Returns:
            List of historical sessions.
        """
        filters = SessionFilters(username=username, active_only=False)
        pagination = PaginationParams(offset=0, limit=limit)
        return self.get_session_history(filters, pagination)

    # -------------------------------------------------------------------------
    # Session Disconnect
    # -------------------------------------------------------------------------

    def disconnect_session(self, request: DisconnectRequest) -> DisconnectResult:
        """Disconnect a RADIUS session.

        This sends a disconnect request to the NAS via:
        1. MikroTik API (if router is configured)
        2. RADIUS CoA (Disconnect-Request packet)

        Args:
            request: Disconnect request with session/user info.

        Returns:
            DisconnectResult with success status.
        """
        # Find the session
        session = None

        if request.session_id:
            session = self.get_active_session(request.session_id)
        elif request.username:
            sessions = self.get_user_active_sessions(request.username)
            if sessions:
                session = sessions[0]  # Disconnect first session found

        if not session:
            return DisconnectResult(
                success=False,
                session_id=request.session_id,
                username=request.username,
                message="Session not found",
                error_code="session_not_found",
            )

        # Try MikroTik API disconnect first
        try:
            result = self._disconnect_via_mikrotik(session, request.reason)
            if result.success:
                return result
        except Exception as e:
            logger.warning(f"MikroTik disconnect failed: {e}")

        # Fallback to RADIUS CoA
        try:
            result = self._disconnect_via_radius_coa(session, request.reason)
            return result
        except Exception as e:
            logger.error(f"RADIUS CoA disconnect failed: {e}")
            return DisconnectResult(
                success=False,
                session_id=session.session_id,
                username=session.username,
                message=f"Disconnect failed: {str(e)}",
                error_code="disconnect_failed",
            )

    def disconnect_user(self, username: str, reason: str = "admin_disconnect") -> List[DisconnectResult]:
        """Disconnect all sessions for a user.

        Args:
            username: The PPP/Hotspot username.
            reason: Disconnect reason.

        Returns:
            List of DisconnectResult for each session.
        """
        sessions = self.get_user_active_sessions(username)
        results = []

        for session in sessions:
            request = DisconnectRequest(
                session_id=session.session_id,
                username=username,
                nas_ip=session.nas_ip,
                reason=reason,
            )
            result = self.disconnect_session(request)
            results.append(result)

        return results

    def disconnect_subscription(
        self,
        subscription_id: int,
        reason: str = "admin_disconnect",
    ) -> List[DisconnectResult]:
        """Disconnect all sessions for a subscription.

        Args:
            subscription_id: The subscription ID.
            reason: Disconnect reason.

        Returns:
            List of DisconnectResult for each session.
        """
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )

        if not sub or not sub.ppp_username:
            return [DisconnectResult(
                success=False,
                message="Subscription not found or no username configured",
                error_code="subscription_not_found",
            )]

        return self.disconnect_user(sub.ppp_username, reason)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_session_stats(self) -> SessionStats:
        """Get session statistics summary.

        Returns:
            SessionStats with current statistics.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Count active sessions
        active_count = self.radius_db.execute(text("""
            SELECT COUNT(*) FROM radacct WHERE acctstoptime IS NULL
        """)).scalar() or 0

        # Count today's sessions
        today_count = self.radius_db.execute(text("""
            SELECT COUNT(*) FROM radacct WHERE acctstarttime >= :today
        """), {"today": today_start}).scalar() or 0

        # Total traffic for active sessions
        traffic = self.radius_db.execute(text("""
            SELECT
                COALESCE(SUM(acctinputoctets), 0) as total_input,
                COALESCE(SUM(acctoutputoctets), 0) as total_output
            FROM radacct
            WHERE acctstoptime IS NULL
        """)).fetchone()

        total_upload_gb = (traffic[0] or 0) / (1024**3)
        total_download_gb = (traffic[1] or 0) / (1024**3)

        # Average session duration (active sessions)
        avg_duration = self.radius_db.execute(text("""
            SELECT AVG(EXTRACT(EPOCH FROM (NOW() - acctstarttime)) / 60)
            FROM radacct
            WHERE acctstoptime IS NULL
        """)).scalar() or 0

        # Unique users
        unique_users = self.radius_db.execute(text("""
            SELECT COUNT(DISTINCT username) FROM radacct WHERE acctstoptime IS NULL
        """)).scalar() or 0

        # Sessions by NAS
        nas_result = self.radius_db.execute(text("""
            SELECT nasipaddress, COUNT(*) as count
            FROM radacct
            WHERE acctstoptime IS NULL
            GROUP BY nasipaddress
            ORDER BY count DESC
            LIMIT 10
        """))
        sessions_by_nas = {row[0]: row[1] for row in nas_result}

        # Top users by traffic
        top_users_result = self.radius_db.execute(text("""
            SELECT
                username,
                SUM(acctinputoctets + acctoutputoctets) as total_bytes
            FROM radacct
            WHERE acctstoptime IS NULL
            GROUP BY username
            ORDER BY total_bytes DESC
            LIMIT 10
        """))
        top_users = [
            {
                "username": row[0],
                "total_gb": round((row[1] or 0) / (1024**3), 2),
            }
            for row in top_users_result
        ]

        return SessionStats(
            total_active=active_count,
            total_today=today_count,
            total_upload_gb=round(total_upload_gb, 2),
            total_download_gb=round(total_download_gb, 2),
            avg_session_duration_minutes=round(avg_duration, 1),
            unique_users=unique_users,
            sessions_by_nas=sessions_by_nas,
            top_users_by_traffic=top_users,
        )

    def get_nas_session_count(self, nas_ip: str) -> int:
        """Get active session count for a specific NAS.

        Args:
            nas_ip: The NAS IP address.

        Returns:
            Number of active sessions.
        """
        count = self.radius_db.execute(text("""
            SELECT COUNT(*) FROM radacct
            WHERE nasipaddress = :nas_ip AND acctstoptime IS NULL
        """), {"nas_ip": nas_ip}).scalar()

        return count or 0

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _enrich_session_with_subscription(self, session: ActiveSession) -> None:
        """Enrich session with subscription information.

        Args:
            session: The session to enrich (modified in place).
        """
        if not session.username:
            return

        sub = (
            self.db.query(Subscription)
            .filter(Subscription.ppp_username == session.username)
            .first()
        )

        if sub:
            session.subscription_id = sub.id
            session.party_id = sub.party_id
            session.plan_name = sub.plan_name

    def _disconnect_via_mikrotik(
        self,
        session: ActiveSession,
        reason: str,
    ) -> DisconnectResult:
        """Disconnect session via MikroTik API.

        Args:
            session: The session to disconnect.
            reason: Disconnect reason.

        Returns:
            DisconnectResult.
        """
        # Find the router by NAS IP
        router = (
            self.db.query(Router)
            .filter(Router.ip_address == session.nas_ip)
            .first()
        )

        if not router:
            raise ValueError(f"Router not found for NAS IP: {session.nas_ip}")

        # Import MikroTik client
        from app.integrations.mikrotik.client import MikroTikClient

        client = MikroTikClient(
            host=router.ip_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port or 8728,
        )

        try:
            # Connect and disconnect the session
            client.connect()

            # Try to remove from active connections
            # The exact command depends on access method (PPP, Hotspot, etc.)
            if session.username:
                # Try PPPoE/PPP first
                client.execute(
                    "/ppp/active/remove",
                    {"numbers": session.username},
                )

            client.disconnect()

            return DisconnectResult(
                success=True,
                session_id=session.session_id,
                username=session.username,
                message=f"Disconnected via MikroTik API: {reason}",
            )

        except Exception as e:
            if client:
                try:
                    client.disconnect()
                except:
                    pass
            raise

    def _disconnect_via_radius_coa(
        self,
        session: ActiveSession,
        reason: str,
    ) -> DisconnectResult:
        """Disconnect session via RADIUS Change of Authorization.

        This sends a Disconnect-Request packet to the NAS.

        Args:
            session: The session to disconnect.
            reason: Disconnect reason.

        Returns:
            DisconnectResult.
        """
        # Find NAS secret
        router = (
            self.db.query(Router)
            .filter(Router.ip_address == session.nas_ip)
            .first()
        )

        nas_secret = router.radius_secret if router else "testing123"

        try:
            # Use radclient or pyrad to send Disconnect-Request
            # This is a simplified implementation
            import subprocess

            # Build radclient command
            # Format: echo "User-Name=username" | radclient nas_ip:coa_port disconnect secret
            coa_port = 3799  # Standard CoA port

            attrs = f'User-Name="{session.username}"\nAcct-Session-Id="{session.session_id}"'

            result = subprocess.run(
                [
                    "radclient",
                    "-x",
                    f"{session.nas_ip}:{coa_port}",
                    "disconnect",
                    nas_secret,
                ],
                input=attrs,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return DisconnectResult(
                    success=True,
                    session_id=session.session_id,
                    username=session.username,
                    message=f"Disconnected via RADIUS CoA: {reason}",
                )
            else:
                return DisconnectResult(
                    success=False,
                    session_id=session.session_id,
                    username=session.username,
                    message=f"CoA failed: {result.stderr}",
                    error_code="coa_failed",
                )

        except FileNotFoundError:
            # radclient not installed, try alternative
            logger.warning("radclient not found, CoA not available")
            return DisconnectResult(
                success=False,
                session_id=session.session_id,
                username=session.username,
                message="RADIUS CoA not available (radclient not installed)",
                error_code="coa_unavailable",
            )

        except subprocess.TimeoutExpired:
            return DisconnectResult(
                success=False,
                session_id=session.session_id,
                username=session.username,
                message="CoA request timed out",
                error_code="coa_timeout",
            )

        except Exception as e:
            return DisconnectResult(
                success=False,
                session_id=session.session_id,
                username=session.username,
                message=f"CoA error: {str(e)}",
                error_code="coa_error",
            )

    def check_radacct_table_exists(self) -> bool:
        """Check if radacct table exists in database.

        Returns:
            True if table exists.
        """
        try:
            self.radius_db.execute(text("SELECT 1 FROM radacct LIMIT 1"))
            return True
        except Exception:
            return False

"""
RADIUS Attribute Management

Manages RADIUS user records in FreeRADIUS SQL backend for:
- Authentication (radcheck table)
- Authorization/Rate Limiting (radreply table)

MikroTik-specific attributes are used for bandwidth control.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


def format_mikrotik_rate_limit(
    download_mbps: int,
    upload_mbps: int,
    *,
    burst_download: Optional[int] = None,
    burst_upload: Optional[int] = None,
    burst_time: Optional[int] = None,
) -> str:
    """
    Format MikroTik rate limit attribute string.

    The Mikrotik-Rate-Limit attribute format is:
    rx-rate[/tx-rate] [rx-burst-rate[/tx-burst-rate] [rx-burst-threshold[/tx-burst-threshold]
        [rx-burst-time[/tx-burst-time] [priority [rx-rate-min[/tx-rate-min]]]]]]

    Simple format: "download/upload" (e.g., "10M/5M")

    Args:
        download_mbps: Download speed in Mbps
        upload_mbps: Upload speed in Mbps
        burst_download: Optional burst download in Mbps
        burst_upload: Optional burst upload in Mbps
        burst_time: Optional burst time in seconds

    Returns:
        Formatted rate limit string
    """
    if burst_download and burst_upload and burst_time:
        # Full format with burst
        return (
            f"{download_mbps}M/{upload_mbps}M "
            f"{burst_download}M/{burst_upload}M "
            f"{download_mbps}M/{upload_mbps}M "
            f"{burst_time}/{burst_time}"
        )

    # Simple format
    return f"{download_mbps}M/{upload_mbps}M"


def format_wispr_bandwidth(mbps: int) -> str:
    """
    Format WISPr bandwidth attribute (in bps).

    Args:
        mbps: Speed in Mbps

    Returns:
        Speed in bps as string
    """
    return str(mbps * 1_000_000)


class RADIUSService:
    """
    Service for managing RADIUS user records.

    Uses direct SQL queries to FreeRADIUS tables:
    - radcheck: Authentication attributes (password)
    - radreply: Authorization attributes (rate limits, IP, etc.)
    - radgroupcheck: Group-based authentication
    - radgroupreply: Group-based authorization

    Note: This requires a separate RADIUS database connection.
    The RADIUS DB may be different from the main app DB.
    """

    def __init__(self, db: Session):
        """
        Initialize RADIUS service.

        Args:
            db: SQLAlchemy session connected to RADIUS database
        """
        self.db = db

    async def create_user(
        self,
        username: str,
        password: str,
        *,
        download_speed: Optional[int] = None,
        upload_speed: Optional[int] = None,
        ip_address: Optional[str] = None,
        subscription_id: Optional[int] = None,
    ) -> bool:
        """
        Create a new RADIUS user with authentication and rate limits.

        Args:
            username: PPP/Hotspot username
            password: Cleartext password
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps
            ip_address: IP address to assign
            subscription_id: Associated subscription ID

        Returns:
            True if created successfully
        """
        try:
            # Create authentication record (radcheck)
            await self._upsert_radcheck(username, "Cleartext-Password", password)

            # Create rate limit record (radreply)
            if download_speed and upload_speed:
                rate_limit = format_mikrotik_rate_limit(download_speed, upload_speed)
                await self._upsert_radreply(username, "Mikrotik-Rate-Limit", rate_limit)

            # Assign IP address
            if ip_address:
                await self._upsert_radreply(username, "Framed-IP-Address", ip_address)

            # Store subscription reference
            if subscription_id:
                await self._upsert_radreply(username, "Subscription-Id", str(subscription_id))

            logger.info(
                "RADIUS user created",
                extra={
                    "username": username,
                    "download_speed": download_speed,
                    "upload_speed": upload_speed,
                    "ip_address": ip_address,
                    "subscription_id": subscription_id,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to create RADIUS user: {e}", extra={"username": username})
            raise

    async def update_user(
        self,
        username: str,
        *,
        password: Optional[str] = None,
        download_speed: Optional[int] = None,
        upload_speed: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Update an existing RADIUS user.

        Args:
            username: PPP/Hotspot username
            password: New password (if changing)
            download_speed: New download speed in Mbps
            upload_speed: New upload speed in Mbps
            ip_address: New IP address

        Returns:
            True if updated successfully
        """
        try:
            if password:
                await self._upsert_radcheck(username, "Cleartext-Password", password)

            if download_speed and upload_speed:
                rate_limit = format_mikrotik_rate_limit(download_speed, upload_speed)
                await self._upsert_radreply(username, "Mikrotik-Rate-Limit", rate_limit)

            if ip_address:
                await self._upsert_radreply(username, "Framed-IP-Address", ip_address)

            logger.info(
                "RADIUS user updated",
                extra={
                    "username": username,
                    "download_speed": download_speed,
                    "upload_speed": upload_speed,
                    "ip_address": ip_address,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update RADIUS user: {e}", extra={"username": username})
            raise

    async def delete_user(self, username: str) -> bool:
        """
        Delete a RADIUS user and all associated attributes.

        Args:
            username: PPP/Hotspot username

        Returns:
            True if deleted
        """
        try:
            # Delete from radcheck
            self.db.execute(
                text("DELETE FROM radcheck WHERE username = :username"),
                {"username": username},
            )

            # Delete from radreply
            self.db.execute(
                text("DELETE FROM radreply WHERE username = :username"),
                {"username": username},
            )

            self.db.commit()

            logger.info("RADIUS user deleted", extra={"username": username})

            return True

        except Exception as e:
            logger.error(f"Failed to delete RADIUS user: {e}", extra={"username": username})
            self.db.rollback()
            raise

    async def suspend_user(self, username: str) -> bool:
        """
        Suspend a RADIUS user by adding Auth-Type := Reject.

        Args:
            username: PPP/Hotspot username

        Returns:
            True if suspended
        """
        try:
            # Add reject attribute
            await self._upsert_radcheck(username, "Auth-Type", "Reject", op=":=")

            logger.info("RADIUS user suspended", extra={"username": username})

            return True

        except Exception as e:
            logger.error(f"Failed to suspend RADIUS user: {e}", extra={"username": username})
            raise

    async def unsuspend_user(self, username: str) -> bool:
        """
        Unsuspend a RADIUS user by removing Auth-Type := Reject.

        Args:
            username: PPP/Hotspot username

        Returns:
            True if unsuspended
        """
        try:
            # Remove reject attribute
            self.db.execute(
                text(
                    "DELETE FROM radcheck WHERE username = :username "
                    "AND attribute = 'Auth-Type' AND value = 'Reject'"
                ),
                {"username": username},
            )
            self.db.commit()

            logger.info("RADIUS user unsuspended", extra={"username": username})

            return True

        except Exception as e:
            logger.error(f"Failed to unsuspend RADIUS user: {e}", extra={"username": username})
            self.db.rollback()
            raise

    async def update_rate_limit(
        self,
        username: str,
        download_speed: int,
        upload_speed: int,
    ) -> bool:
        """
        Update only the rate limit for a user.

        Args:
            username: PPP/Hotspot username
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Returns:
            True if updated
        """
        rate_limit = format_mikrotik_rate_limit(download_speed, upload_speed)
        await self._upsert_radreply(username, "Mikrotik-Rate-Limit", rate_limit)

        logger.info(
            "RADIUS rate limit updated",
            extra={
                "username": username,
                "rate_limit": rate_limit,
            },
        )

        return True

    async def sync_subscription(self, subscription: Subscription) -> bool:
        """
        Sync a subscription to RADIUS.

        Creates or updates the RADIUS user based on subscription state.

        Args:
            subscription: Subscription to sync

        Returns:
            True if synced
        """
        if not subscription.ppp_username:
            return True  # Nothing to sync

        from app.models.subscription import SubscriptionStatus

        if subscription.status == SubscriptionStatus.CANCELLED:
            # Delete from RADIUS
            return await self.delete_user(subscription.ppp_username)

        elif subscription.status == SubscriptionStatus.SUSPENDED:
            # Suspend in RADIUS
            return await self.suspend_user(subscription.ppp_username)

        elif subscription.status == SubscriptionStatus.ACTIVE:
            # Ensure user exists and is not suspended
            await self.unsuspend_user(subscription.ppp_username)
            return await self.update_user(
                subscription.ppp_username,
                password=subscription.ppp_password,
                download_speed=subscription.download_speed,
                upload_speed=subscription.upload_speed,
                ip_address=subscription.ipv4_address,
            )

        return True

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _upsert_radcheck(
        self,
        username: str,
        attribute: str,
        value: str,
        op: str = ":=",
    ) -> None:
        """Insert or update a radcheck record."""
        # Try update first
        result = self.db.execute(
            text(
                "UPDATE radcheck SET value = :value, op = :op "
                "WHERE username = :username AND attribute = :attribute"
            ),
            {"username": username, "attribute": attribute, "value": value, "op": op},
        )
        rowcount = getattr(result, "rowcount", 0)

        if rowcount == 0:
            # Insert if not exists
            self.db.execute(
                text(
                    "INSERT INTO radcheck (username, attribute, op, value) "
                    "VALUES (:username, :attribute, :op, :value)"
                ),
                {"username": username, "attribute": attribute, "value": value, "op": op},
            )

        self.db.commit()

    async def _upsert_radreply(
        self,
        username: str,
        attribute: str,
        value: str,
        op: str = ":=",
    ) -> None:
        """Insert or update a radreply record."""
        # Try update first
        result = self.db.execute(
            text(
                "UPDATE radreply SET value = :value, op = :op "
                "WHERE username = :username AND attribute = :attribute"
            ),
            {"username": username, "attribute": attribute, "value": value, "op": op},
        )
        rowcount = getattr(result, "rowcount", 0)

        if rowcount == 0:
            # Insert if not exists
            self.db.execute(
                text(
                    "INSERT INTO radreply (username, attribute, op, value) "
                    "VALUES (:username, :attribute, :op, :value)"
                ),
                {"username": username, "attribute": attribute, "value": value, "op": op},
            )

        self.db.commit()

    async def get_user_attributes(self, username: str) -> Dict[str, Any]:
        """
        Get all attributes for a RADIUS user.

        Returns:
            Dict with 'check' and 'reply' attribute lists
        """
        check_result = self.db.execute(
            text("SELECT attribute, op, value FROM radcheck WHERE username = :username"),
            {"username": username},
        )
        check_attrs = [
            {"attribute": row[0], "op": row[1], "value": row[2]}
            for row in check_result
        ]

        reply_result = self.db.execute(
            text("SELECT attribute, op, value FROM radreply WHERE username = :username"),
            {"username": username},
        )
        reply_attrs = [
            {"attribute": row[0], "op": row[1], "value": row[2]}
            for row in reply_result
        ]

        return {
            "username": username,
            "check": check_attrs,
            "reply": reply_attrs,
        }

"""
RADIUS Attribute Management

Manages RADIUS user records in FreeRADIUS SQL backend for:
- Authentication (radcheck table)
- Authorization/Rate Limiting (radreply table)
- Data Bundle Enforcement (data caps, CoA)

MikroTik-specific attributes are used for bandwidth control.
"""

from __future__ import annotations

import logging
import socket
import struct
import hashlib
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.data_bundle import CustomerBundle

logger = logging.getLogger(__name__)


class CoAAction(str, Enum):
    """RADIUS Change of Authorization actions."""
    DISCONNECT = "disconnect"  # PoD - Packet of Disconnect
    UPDATE_RATE = "update_rate"  # CoA - Update rate limit
    UPDATE_DATA_CAP = "update_data_cap"  # CoA - Update data cap
    THROTTLE = "throttle"  # CoA - Apply throttle speed


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


def format_mikrotik_data_limit(data_mb: int) -> tuple[str, str]:
    """
    Format MikroTik data limit attributes for bundle enforcement.

    Returns Mikrotik-Total-Limit and Mikrotik-Total-Limit-Gigawords
    for data caps larger than 4GB.

    Args:
        data_mb: Data limit in megabytes

    Returns:
        Tuple of (total_limit, gigawords) as strings
    """
    # Convert MB to bytes
    total_bytes = data_mb * 1024 * 1024

    # Split into low 32-bits and high 32-bits (gigawords)
    max_32bit = 2**32
    gigawords = total_bytes // max_32bit
    low_bytes = total_bytes % max_32bit

    return str(low_bytes), str(gigawords)


def format_session_timeout(minutes: int) -> str:
    """
    Format Session-Timeout attribute in seconds.

    Used to force periodic re-authentication for usage checks.

    Args:
        minutes: Timeout in minutes

    Returns:
        Timeout in seconds as string
    """
    return str(minutes * 60)


def build_coa_packet(
    secret: bytes,
    nas_ip: str,
    username: str,
    attributes: Dict[str, str],
    packet_id: int = 1,
) -> bytes:
    """
    Build a RADIUS CoA (Change of Authorization) packet.

    Implements RFC 5176 for Dynamic Authorization.

    Args:
        secret: RADIUS shared secret
        nas_ip: NAS IP address
        username: PPP/Hotspot username
        attributes: Dict of attribute name to value
        packet_id: Packet identifier

    Returns:
        Raw RADIUS CoA packet bytes
    """
    # RADIUS CoA code is 43
    COA_CODE = 43

    # Build attribute list
    attrs_data = b""

    # User-Name (attribute 1)
    user_name_bytes = username.encode("utf-8")
    attrs_data += struct.pack("!BB", 1, len(user_name_bytes) + 2) + user_name_bytes

    # Add vendor-specific attributes for MikroTik (vendor 14988)
    MIKROTIK_VENDOR_ID = 14988

    for attr_name, attr_value in attributes.items():
        if attr_name == "Mikrotik-Rate-Limit":
            # Mikrotik-Rate-Limit is vendor attribute 8
            value_bytes = attr_value.encode("utf-8")
            vsa_data = struct.pack("!BB", 8, len(value_bytes) + 2) + value_bytes
            # Vendor-Specific attribute (26) wrapper
            attrs_data += struct.pack("!BBL", 26, len(vsa_data) + 6, MIKROTIK_VENDOR_ID) + vsa_data

        elif attr_name == "Mikrotik-Total-Limit":
            # Mikrotik-Total-Limit is vendor attribute 17
            value_bytes = struct.pack("!I", int(attr_value))
            vsa_data = struct.pack("!BB", 17, len(value_bytes) + 2) + value_bytes
            attrs_data += struct.pack("!BBL", 26, len(vsa_data) + 6, MIKROTIK_VENDOR_ID) + vsa_data

        elif attr_name == "Session-Timeout":
            # Session-Timeout is attribute 27
            attrs_data += struct.pack("!BBI", 27, 6, int(attr_value))

    # Calculate packet length
    packet_length = 20 + len(attrs_data)  # 20 = header size

    # Build packet without authenticator
    packet = struct.pack("!BBH", COA_CODE, packet_id, packet_length)
    packet += b"\x00" * 16  # Placeholder for authenticator
    packet += attrs_data

    # Calculate authenticator (MD5 of packet + secret)
    authenticator = hashlib.md5(packet + secret).digest()

    # Replace placeholder with real authenticator
    packet = packet[:4] + authenticator + packet[20:]

    return packet


def build_pod_packet(
    secret: bytes,
    username: str,
    packet_id: int = 1,
) -> bytes:
    """
    Build a RADIUS PoD (Packet of Disconnect) packet.

    Args:
        secret: RADIUS shared secret
        username: PPP/Hotspot username to disconnect
        packet_id: Packet identifier

    Returns:
        Raw RADIUS Disconnect-Request packet bytes
    """
    # RADIUS Disconnect-Request code is 40
    DISCONNECT_CODE = 40

    # User-Name attribute
    user_name_bytes = username.encode("utf-8")
    attrs_data = struct.pack("!BB", 1, len(user_name_bytes) + 2) + user_name_bytes

    packet_length = 20 + len(attrs_data)

    packet = struct.pack("!BBH", DISCONNECT_CODE, packet_id, packet_length)
    packet += b"\x00" * 16
    packet += attrs_data

    authenticator = hashlib.md5(packet + secret).digest()
    packet = packet[:4] + authenticator + packet[20:]

    return packet


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

    # =========================================================================
    # Data Bundle / Data Cap Methods
    # =========================================================================

    async def set_data_cap(
        self,
        username: str,
        data_mb: int,
        session_timeout_minutes: int = 15,
    ) -> bool:
        """
        Set data cap attributes for a user (bundle enforcement).

        Args:
            username: PPP/Hotspot username
            data_mb: Data limit in megabytes
            session_timeout_minutes: Force re-auth interval for usage checks

        Returns:
            True if attributes set successfully
        """
        try:
            # Set total limit (handles >4GB via gigawords)
            low_bytes, gigawords = format_mikrotik_data_limit(data_mb)
            await self._upsert_radreply(username, "Mikrotik-Total-Limit", low_bytes)

            if int(gigawords) > 0:
                await self._upsert_radreply(username, "Mikrotik-Total-Limit-Gigawords", gigawords)

            # Set session timeout for periodic re-auth
            timeout = format_session_timeout(session_timeout_minutes)
            await self._upsert_radreply(username, "Session-Timeout", timeout)

            logger.info(
                "Data cap set for user",
                extra={
                    "username": username,
                    "data_mb": data_mb,
                    "session_timeout": session_timeout_minutes,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to set data cap: {e}", extra={"username": username})
            raise

    async def remove_data_cap(self, username: str) -> bool:
        """
        Remove data cap attributes for a user.

        Args:
            username: PPP/Hotspot username

        Returns:
            True if removed
        """
        try:
            self.db.execute(
                text(
                    "DELETE FROM radreply WHERE username = :username "
                    "AND attribute IN ('Mikrotik-Total-Limit', 'Mikrotik-Total-Limit-Gigawords')"
                ),
                {"username": username},
            )
            self.db.commit()

            logger.info("Data cap removed", extra={"username": username})
            return True

        except Exception as e:
            logger.error(f"Failed to remove data cap: {e}", extra={"username": username})
            self.db.rollback()
            raise

    # =========================================================================
    # Change of Authorization (CoA) Methods
    # =========================================================================

    async def send_coa(
        self,
        nas_ip: str,
        nas_secret: str,
        username: str,
        attributes: Dict[str, str],
        coa_port: int = 3799,
    ) -> bool:
        """
        Send a RADIUS Change of Authorization (CoA) packet to a NAS.

        Args:
            nas_ip: NAS/router IP address
            nas_secret: RADIUS shared secret
            username: PPP/Hotspot username
            attributes: Dict of attributes to update
            coa_port: CoA port (default 3799)

        Returns:
            True if CoA sent successfully
        """
        try:
            packet = build_coa_packet(
                secret=nas_secret.encode("utf-8"),
                nas_ip=nas_ip,
                username=username,
                attributes=attributes,
            )

            # Send via UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
            sock.sendto(packet, (nas_ip, coa_port))

            # Wait for ACK/NAK
            try:
                response, _ = sock.recvfrom(4096)
                response_code = response[0]

                # 44 = CoA-ACK, 45 = CoA-NAK
                if response_code == 44:
                    logger.info(
                        "CoA accepted",
                        extra={"username": username, "nas_ip": nas_ip},
                    )
                    return True
                else:
                    logger.warning(
                        "CoA rejected",
                        extra={"username": username, "nas_ip": nas_ip, "code": response_code},
                    )
                    return False

            except socket.timeout:
                logger.warning(
                    "CoA timeout",
                    extra={"username": username, "nas_ip": nas_ip},
                )
                return False
            finally:
                sock.close()

        except Exception as e:
            logger.error(f"Failed to send CoA: {e}", extra={"username": username})
            raise

    async def send_disconnect(
        self,
        nas_ip: str,
        nas_secret: str,
        username: str,
        coa_port: int = 3799,
    ) -> bool:
        """
        Send a RADIUS Disconnect-Request (PoD) to terminate a user session.

        Args:
            nas_ip: NAS/router IP address
            nas_secret: RADIUS shared secret
            username: PPP/Hotspot username to disconnect
            coa_port: CoA port (default 3799)

        Returns:
            True if disconnect sent successfully
        """
        try:
            packet = build_pod_packet(
                secret=nas_secret.encode("utf-8"),
                username=username,
            )

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
            sock.sendto(packet, (nas_ip, coa_port))

            try:
                response, _ = sock.recvfrom(4096)
                response_code = response[0]

                # 41 = Disconnect-ACK, 42 = Disconnect-NAK
                if response_code == 41:
                    logger.info(
                        "Disconnect accepted",
                        extra={"username": username, "nas_ip": nas_ip},
                    )
                    return True
                else:
                    logger.warning(
                        "Disconnect rejected",
                        extra={"username": username, "nas_ip": nas_ip, "code": response_code},
                    )
                    return False

            except socket.timeout:
                logger.warning(
                    "Disconnect timeout",
                    extra={"username": username, "nas_ip": nas_ip},
                )
                return False
            finally:
                sock.close()

        except Exception as e:
            logger.error(f"Failed to send disconnect: {e}", extra={"username": username})
            raise

    async def apply_throttle(
        self,
        nas_ip: str,
        nas_secret: str,
        username: str,
        throttle_speed_kbps: int,
    ) -> bool:
        """
        Apply throttle speed to a user via CoA (for bundle exhaustion).

        Args:
            nas_ip: NAS/router IP address
            nas_secret: RADIUS shared secret
            username: PPP/Hotspot username
            throttle_speed_kbps: Throttle speed in kbps

        Returns:
            True if throttle applied
        """
        # Format rate limit for throttle speed
        rate_limit = f"{throttle_speed_kbps}k/{throttle_speed_kbps}k"

        return await self.send_coa(
            nas_ip=nas_ip,
            nas_secret=nas_secret,
            username=username,
            attributes={"Mikrotik-Rate-Limit": rate_limit},
        )

    async def restore_speed(
        self,
        nas_ip: str,
        nas_secret: str,
        username: str,
        download_speed: int,
        upload_speed: int,
    ) -> bool:
        """
        Restore original speed for a user via CoA (after bundle renewal).

        Args:
            nas_ip: NAS/router IP address
            nas_secret: RADIUS shared secret
            username: PPP/Hotspot username
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Returns:
            True if speed restored
        """
        rate_limit = format_mikrotik_rate_limit(download_speed, upload_speed)

        return await self.send_coa(
            nas_ip=nas_ip,
            nas_secret=nas_secret,
            username=username,
            attributes={"Mikrotik-Rate-Limit": rate_limit},
        )

"""Async SNMP Client.

Async SNMP client for polling device metrics.
Supports SNMPv2c and SNMPv3 with retry logic and circuit breaker.

Usage:
    config = SNMPPollingConfig(...)
    async with SNMPClient(router_ip, config) as client:
        system_info = await client.get_system_info()
        interfaces = await client.get_interface_stats()
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.integrations.snmp.exceptions import (
    SNMPError,
    SNMPTimeoutError,
    SNMPAuthenticationError,
    SNMPConnectionError,
    SNMPNoSuchObjectError,
    SNMPEndOfMibError,
    DeviceUnreachableError,
)
from app.integrations.snmp.types import (
    SystemInfo,
    InterfaceData,
    DevicePollingResult,
    OIDResult,
    StandardOIDs,
    MikroTikOIDs,
)

if TYPE_CHECKING:
    from app.models.snmp_metrics import SNMPPollingConfig

logger = logging.getLogger(__name__)


# Optional pysnmp import - allows graceful degradation if not installed
try:
    from pysnmp.hlapi.asyncio import (
        getCmd,
        bulkCmd,
        nextCmd,
        SnmpEngine,
        CommunityData,
        UsmUserData,
        UdpTransportTarget,
        ContextData,
        ObjectType,
        ObjectIdentity,
    )
    from pysnmp.proto.rfc1902 import (
        Integer,
        Integer32,
        Unsigned32,
        Counter32,
        Counter64,
        Gauge32,
        TimeTicks,
        OctetString,
        IpAddress,
    )
    from pysnmp.proto.errind import (
        requestTimedOut,
        unknownUserName,
        wrongDigest,
        authenticationFailure,
    )
    # Authentication protocols
    from pysnmp.hlapi.asyncio import (
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
        usmNoAuthProtocol,
    )
    # Privacy protocols
    from pysnmp.hlapi.asyncio import (
        usmDESPrivProtocol,
        usmAesCfb128Protocol,
        usmNoPrivProtocol,
    )

    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False
    logger.warning("pysnmp-lextudio not installed. SNMP polling will be disabled.")


class SNMPClient:
    """Async SNMP client for device polling.

    Supports SNMPv2c (community string) and SNMPv3 (user-based security).
    Uses pysnmp-lextudio for async SNMP operations.

    Attributes:
        host: Target device IP address
        config: SNMP configuration (version, credentials, timeouts)
    """

    # Auth protocol mapping
    AUTH_PROTOCOLS = {
        "md5": "usmHMACMD5AuthProtocol",
        "sha": "usmHMACSHAAuthProtocol",
        "sha224": "usmHMAC128SHA224AuthProtocol",
        "sha256": "usmHMAC192SHA256AuthProtocol",
        "sha384": "usmHMAC256SHA384AuthProtocol",
        "sha512": "usmHMAC384SHA512AuthProtocol",
    }

    # Privacy protocol mapping
    PRIV_PROTOCOLS = {
        "des": "usmDESPrivProtocol",
        "aes": "usmAesCfb128Protocol",
        "aes192": "usmAesCfb192Protocol",
        "aes256": "usmAesCfb256Protocol",
    }

    def __init__(
        self,
        host: str,
        config: SNMPPollingConfig,
        router_id: Optional[int] = None,
    ):
        """Initialize SNMP client.

        Args:
            host: Target device IP address
            config: SNMP polling configuration
            router_id: Optional router ID for logging/error context
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp-lextudio is not installed")

        self.host = host
        self.config = config
        self.router_id = router_id or config.router_id
        self._engine: Optional[SnmpEngine] = None

    async def __aenter__(self) -> "SNMPClient":
        """Async context manager entry."""
        self._engine = SnmpEngine()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._engine:
            # Clean up SNMP engine resources
            self._engine = None

    def _get_auth_data(self):
        """Build authentication data based on SNMP version."""
        if self.config.snmp_version.value == "2c":
            return CommunityData(self.config.community or "public")

        # SNMPv3
        auth_protocol = usmNoAuthProtocol
        priv_protocol = usmNoPrivProtocol

        if self.config.auth_protocol:
            auth_proto_name = self.config.auth_protocol.value.lower()
            if auth_proto_name == "md5":
                auth_protocol = usmHMACMD5AuthProtocol
            elif auth_proto_name == "sha":
                auth_protocol = usmHMACSHAAuthProtocol

        if self.config.priv_protocol:
            priv_proto_name = self.config.priv_protocol.value.lower()
            if priv_proto_name == "des":
                priv_protocol = usmDESPrivProtocol
            elif priv_proto_name in ("aes", "aes128"):
                priv_protocol = usmAesCfb128Protocol

        return UsmUserData(
            self.config.username or "",
            self.config.auth_password or "",
            self.config.priv_password or "",
            authProtocol=auth_protocol,
            privProtocol=priv_protocol,
        )

    def _get_transport_target(self):
        """Build UDP transport target."""
        return UdpTransportTarget(
            (self.host, self.config.port),
            timeout=self.config.timeout_seconds,
            retries=self.config.retries,
        )

    def _handle_error(self, error_indication, error_status, error_index):
        """Handle SNMP error response."""
        if error_indication:
            error_str = str(error_indication)

            if "timeout" in error_str.lower() or error_indication == requestTimedOut:
                raise SNMPTimeoutError(
                    f"SNMP request timed out: {error_str}",
                    router_id=self.router_id,
                )

            if any(auth_err in error_str.lower() for auth_err in [
                "authentication", "wrong digest", "unknown user"
            ]):
                raise SNMPAuthenticationError(
                    f"SNMP authentication failed: {error_str}",
                    router_id=self.router_id,
                )

            if "no such" in error_str.lower() or "end of mib" in error_str.lower():
                raise SNMPNoSuchObjectError(
                    f"OID not found: {error_str}",
                    router_id=self.router_id,
                )

            raise SNMPConnectionError(
                f"SNMP error: {error_str}",
                router_id=self.router_id,
            )

        if error_status:
            raise SNMPError(
                f"SNMP error status: {error_status.prettyPrint()} at {error_index}",
                router_id=self.router_id,
            )

    def _parse_value(self, value) -> Any:
        """Parse SNMP value to Python type."""
        if value is None:
            return None

        # Handle different pysnmp types
        if isinstance(value, (Integer, Integer32, Unsigned32, Gauge32)):
            return int(value)
        if isinstance(value, (Counter32, Counter64)):
            return int(value)
        if isinstance(value, TimeTicks):
            return int(value)  # In hundredths of a second
        if isinstance(value, OctetString):
            # Try to decode as string, fall back to hex
            try:
                return value.prettyPrint()
            except Exception:
                return value.hexValue
        if isinstance(value, IpAddress):
            return str(value)

        # Default: return string representation
        return str(value)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(SNMPTimeoutError),
        reraise=True,
    )
    async def get(self, *oids: str) -> List[OIDResult]:
        """Execute SNMP GET for one or more OIDs.

        Args:
            *oids: One or more OID strings

        Returns:
            List of OIDResult with values
        """
        if not self._engine:
            raise SNMPError("Client not initialized. Use async with context manager.")

        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        error_indication, error_status, error_index, var_binds = await getCmd(
            self._engine,
            self._get_auth_data(),
            self._get_transport_target(),
            ContextData(),
            *object_types,
        )

        self._handle_error(error_indication, error_status, error_index)

        results = []
        for var_bind in var_binds:
            oid = str(var_bind[0])
            value = self._parse_value(var_bind[1])
            results.append(OIDResult(
                oid=oid,
                value=value,
                value_type=type(var_bind[1]).__name__,
            ))

        return results

    async def walk(self, base_oid: str, max_rows: int = 1000) -> List[Tuple[str, Any]]:
        """Walk an SNMP table (GETNEXT).

        Args:
            base_oid: Base OID to walk
            max_rows: Maximum rows to retrieve

        Returns:
            List of (oid, value) tuples
        """
        if not self._engine:
            raise SNMPError("Client not initialized. Use async with context manager.")

        results = []
        count = 0

        async for (
            error_indication,
            error_status,
            error_index,
            var_binds,
        ) in nextCmd(
            self._engine,
            self._get_auth_data(),
            self._get_transport_target(),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                # End of MIB or timeout - stop walking
                if "end of mib" in str(error_indication).lower():
                    break
                self._handle_error(error_indication, error_status, error_index)

            if error_status:
                break

            for var_bind in var_binds:
                oid = str(var_bind[0])
                # Stop if we've left the subtree
                if not oid.startswith(base_oid):
                    return results

                value = self._parse_value(var_bind[1])
                results.append((oid, value))

            count += 1
            if count >= max_rows:
                break

        return results

    async def bulk_walk(
        self,
        base_oid: str,
        max_repetitions: int = 25,
        max_rows: int = 1000,
    ) -> List[Tuple[str, Any]]:
        """Bulk walk an SNMP table (GETBULK).

        More efficient than walk() for large tables.

        Args:
            base_oid: Base OID to walk
            max_repetitions: Max rows per request
            max_rows: Maximum total rows

        Returns:
            List of (oid, value) tuples
        """
        if not self._engine:
            raise SNMPError("Client not initialized. Use async with context manager.")

        results = []
        count = 0

        async for (
            error_indication,
            error_status,
            error_index,
            var_binds,
        ) in bulkCmd(
            self._engine,
            self._get_auth_data(),
            self._get_transport_target(),
            ContextData(),
            0,  # nonRepeaters
            max_repetitions,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                if "end of mib" in str(error_indication).lower():
                    break
                self._handle_error(error_indication, error_status, error_index)

            if error_status:
                break

            for var_bind in var_binds:
                oid = str(var_bind[0])
                if not oid.startswith(base_oid):
                    return results

                value = self._parse_value(var_bind[1])
                results.append((oid, value))
                count += 1

                if count >= max_rows:
                    return results

        return results

    # =========================================================================
    # High-Level Methods
    # =========================================================================

    async def get_system_info(self) -> SystemInfo:
        """Get device system information.

        Returns:
            SystemInfo with device details
        """
        oids = [
            StandardOIDs.SYS_DESCR,
            StandardOIDs.SYS_OBJECT_ID,
            StandardOIDs.SYS_UPTIME,
            StandardOIDs.SYS_CONTACT,
            StandardOIDs.SYS_NAME,
            StandardOIDs.SYS_LOCATION,
        ]

        results = await self.get(*oids)

        info = SystemInfo(
            sys_descr=results[0].as_str if len(results) > 0 else "",
            sys_object_id=results[1].as_str if len(results) > 1 else "",
            sys_uptime_seconds=results[2].as_int // 100 if len(results) > 2 else 0,
            sys_contact=results[3].as_str if len(results) > 3 else "",
            sys_name=results[4].as_str if len(results) > 4 else "",
            sys_location=results[5].as_str if len(results) > 5 else "",
        )

        # Try to get MikroTik-specific info
        try:
            mt_results = await self.get(
                MikroTikOIDs.HW_CPU_LOAD,
                MikroTikOIDs.HW_TEMPERATURE,
            )
            if mt_results:
                info.cpu_load = float(mt_results[0].as_int) if mt_results[0].value else None
                # Temperature is in 0.1C units
                if mt_results[1].value is not None:
                    info.temperature = float(mt_results[1].as_int) / 10.0
        except SNMPNoSuchObjectError:
            # Not a MikroTik device or OIDs not supported
            pass
        except Exception as e:
            logger.debug(f"Failed to get MikroTik OIDs: {e}")

        return info

    async def get_interface_stats(self) -> List[InterfaceData]:
        """Get interface statistics for all interfaces.

        Returns:
            List of InterfaceData with counters and status
        """
        interfaces: Dict[int, InterfaceData] = {}

        # Walk interface description table to get names
        try:
            if_descr_results = await self.walk(StandardOIDs.IF_DESCR)
            for oid, value in if_descr_results:
                # Extract index from OID: 1.3.6.1.2.1.2.2.1.2.{index}
                parts = oid.split(".")
                if len(parts) > 0:
                    index = int(parts[-1])
                    interfaces[index] = InterfaceData(
                        index=index,
                        name=str(value) if value else f"if{index}",
                    )
        except Exception as e:
            logger.warning(f"Failed to walk IF-MIB::ifDescr: {e}")
            return []

        if not interfaces:
            return []

        # Walk other interface properties
        property_oids = [
            (StandardOIDs.IF_TYPE, "interface_type"),
            (StandardOIDs.IF_MTU, "mtu"),
            (StandardOIDs.IF_SPEED, "speed_bps"),
            (StandardOIDs.IF_ADMIN_STATUS, "admin_status"),
            (StandardOIDs.IF_OPER_STATUS, "oper_status"),
        ]

        for base_oid, attr_name in property_oids:
            try:
                results = await self.walk(base_oid)
                for oid, value in results:
                    parts = oid.split(".")
                    if len(parts) > 0:
                        index = int(parts[-1])
                        if index in interfaces:
                            setattr(interfaces[index], attr_name, int(value) if value else 0)
            except Exception as e:
                logger.debug(f"Failed to walk {base_oid}: {e}")

        # Get 64-bit counters (preferred) or fall back to 32-bit
        counter_oids = [
            (StandardOIDs.IF_HC_IN_OCTETS, "rx_bytes"),
            (StandardOIDs.IF_HC_OUT_OCTETS, "tx_bytes"),
            (StandardOIDs.IF_HC_IN_UCAST_PKTS, "rx_packets"),
            (StandardOIDs.IF_HC_OUT_UCAST_PKTS, "tx_packets"),
        ]

        for base_oid, attr_name in counter_oids:
            try:
                results = await self.walk(base_oid)
                for oid, value in results:
                    parts = oid.split(".")
                    if len(parts) > 0:
                        index = int(parts[-1])
                        if index in interfaces:
                            setattr(interfaces[index], attr_name, int(value) if value else 0)
            except SNMPNoSuchObjectError:
                # Device doesn't support 64-bit counters, try 32-bit
                pass
            except Exception as e:
                logger.debug(f"Failed to walk {base_oid}: {e}")

        # Fall back to 32-bit counters if needed
        if not any(iface.rx_bytes > 0 for iface in interfaces.values()):
            fallback_oids = [
                (StandardOIDs.IF_IN_OCTETS, "rx_bytes"),
                (StandardOIDs.IF_OUT_OCTETS, "tx_bytes"),
                (StandardOIDs.IF_IN_UCAST_PKTS, "rx_packets"),
                (StandardOIDs.IF_OUT_UCAST_PKTS, "tx_packets"),
            ]
            for base_oid, attr_name in fallback_oids:
                try:
                    results = await self.walk(base_oid)
                    for oid, value in results:
                        parts = oid.split(".")
                        if len(parts) > 0:
                            index = int(parts[-1])
                            if index in interfaces:
                                setattr(interfaces[index], attr_name, int(value) if value else 0)
                except Exception as e:
                    logger.debug(f"Failed to walk {base_oid}: {e}")

        # Get error counters
        error_oids = [
            (StandardOIDs.IF_IN_ERRORS, "rx_errors"),
            (StandardOIDs.IF_OUT_ERRORS, "tx_errors"),
            (StandardOIDs.IF_IN_DISCARDS, "rx_discards"),
            (StandardOIDs.IF_OUT_DISCARDS, "tx_discards"),
        ]

        for base_oid, attr_name in error_oids:
            try:
                results = await self.walk(base_oid)
                for oid, value in results:
                    parts = oid.split(".")
                    if len(parts) > 0:
                        index = int(parts[-1])
                        if index in interfaces:
                            setattr(interfaces[index], attr_name, int(value) if value else 0)
            except Exception as e:
                logger.debug(f"Failed to walk {base_oid}: {e}")

        # Try to get interface aliases (ifAlias)
        try:
            alias_results = await self.walk(StandardOIDs.IF_ALIAS)
            for oid, value in alias_results:
                parts = oid.split(".")
                if len(parts) > 0:
                    index = int(parts[-1])
                    if index in interfaces:
                        interfaces[index].alias = str(value) if value else ""
        except Exception:
            pass

        # Get high-speed interface speed (for gigabit+)
        try:
            speed_results = await self.walk(StandardOIDs.IF_HIGH_SPEED)
            for oid, value in speed_results:
                parts = oid.split(".")
                if len(parts) > 0:
                    index = int(parts[-1])
                    if index in interfaces and value:
                        # ifHighSpeed is in Mbps, convert to bps
                        interfaces[index].speed_bps = int(value) * 1_000_000
        except Exception:
            pass

        return list(interfaces.values())

    async def get_active_session_counts(self) -> Dict[str, int]:
        """Get active session counts (MikroTik-specific).

        Returns:
            Dict with ppp, hotspot, dhcp counts
        """
        counts = {
            "ppp": 0,
            "hotspot": 0,
            "dhcp": 0,
        }

        try:
            # Count PPP active sessions
            ppp_results = await self.walk(MikroTikOIDs.PPP_ACTIVE_USER)
            counts["ppp"] = len(ppp_results)
        except Exception:
            pass

        try:
            # Count hotspot active sessions
            hotspot_results = await self.walk(MikroTikOIDs.HOTSPOT_ACTIVE_USER)
            counts["hotspot"] = len(hotspot_results)
        except Exception:
            pass

        return counts

    async def poll_device(self) -> DevicePollingResult:
        """Execute complete device poll.

        Collects system info, interface stats, and session counts.

        Returns:
            DevicePollingResult with all collected data
        """
        from datetime import datetime

        start_time = time.monotonic()
        result = DevicePollingResult(
            router_id=self.router_id,
            timestamp=datetime.utcnow(),
            success=False,
        )

        try:
            # Get system info
            result.system_info = await self.get_system_info()

            # Get interface stats
            result.interfaces = await self.get_interface_stats()

            # Get session counts (MikroTik)
            try:
                counts = await self.get_active_session_counts()
                result.active_ppp_sessions = counts["ppp"]
                result.active_hotspot_sessions = counts["hotspot"]
                result.active_dhcp_leases = counts["dhcp"]
            except Exception:
                pass  # Non-MikroTik devices won't have these

            result.success = True

        except SNMPError as e:
            result.error = str(e)
            logger.warning(
                f"SNMP poll failed for router {self.router_id}: {e}",
                extra={"router_id": self.router_id},
            )

        except Exception as e:
            result.error = f"Unexpected error: {e}"
            logger.exception(
                f"Unexpected error polling router {self.router_id}",
                extra={"router_id": self.router_id},
            )

        finally:
            elapsed = time.monotonic() - start_time
            result.poll_duration_ms = int(elapsed * 1000)

        return result

    async def test_connection(self) -> bool:
        """Test if device is reachable via SNMP.

        Returns:
            True if connection successful
        """
        try:
            results = await self.get(StandardOIDs.SYS_UPTIME)
            return len(results) > 0 and results[0].value is not None
        except SNMPError:
            return False

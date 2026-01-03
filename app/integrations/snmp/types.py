"""SNMP Type Definitions.

Data classes and type definitions for SNMP polling results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class SystemInfo:
    """Device system information from SNMP."""

    sys_descr: str = ""
    sys_object_id: str = ""
    sys_uptime_seconds: int = 0
    sys_contact: str = ""
    sys_name: str = ""
    sys_location: str = ""

    # MikroTik-specific
    cpu_load: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used: Optional[int] = None
    memory_total: Optional[int] = None
    temperature: Optional[float] = None
    board_name: Optional[str] = None
    ros_version: Optional[str] = None


@dataclass
class InterfaceData:
    """Interface statistics from SNMP."""

    index: int
    name: str
    alias: str = ""
    interface_type: int = 0
    mtu: int = 0
    speed_bps: Optional[int] = None
    mac_address: str = ""

    # Admin and operational status (1=up, 2=down, 3=testing)
    admin_status: int = 2
    oper_status: int = 2

    # 64-bit counters (ifHC*)
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0

    # 32-bit error counters
    rx_errors: int = 0
    tx_errors: int = 0
    rx_discards: int = 0
    tx_discards: int = 0

    # Last change timestamp
    last_change: Optional[int] = None

    @property
    def is_up(self) -> bool:
        """Check if interface is operationally up."""
        return self.oper_status == 1

    @property
    def oper_status_str(self) -> str:
        """Human-readable operational status."""
        status_map = {
            1: "up",
            2: "down",
            3: "testing",
            4: "unknown",
            5: "dormant",
            6: "not_present",
            7: "lower_layer_down",
        }
        return status_map.get(self.oper_status, "unknown")


@dataclass
class DevicePollingResult:
    """Complete polling result for a device."""

    router_id: int
    timestamp: datetime
    success: bool
    error: Optional[str] = None

    # System info
    system_info: Optional[SystemInfo] = None

    # Interface data
    interfaces: List[InterfaceData] = field(default_factory=list)

    # Session counts (MikroTik-specific)
    active_ppp_sessions: Optional[int] = None
    active_hotspot_sessions: Optional[int] = None
    active_dhcp_leases: Optional[int] = None

    # Polling duration
    poll_duration_ms: Optional[int] = None


@dataclass
class OIDResult:
    """Result of an SNMP GET operation."""

    oid: str
    value: Any
    value_type: str = "unknown"

    @property
    def as_int(self) -> int:
        """Get value as integer."""
        try:
            return int(self.value)
        except (ValueError, TypeError):
            return 0

    @property
    def as_str(self) -> str:
        """Get value as string."""
        if self.value is None:
            return ""
        return str(self.value)


@dataclass
class RateCalculation:
    """Calculated rate between two polling intervals."""

    interface_index: int
    rx_rate_bps: int = 0
    tx_rate_bps: int = 0
    rx_pps: int = 0
    tx_pps: int = 0
    interval_seconds: float = 0.0


# Common SNMP OIDs
class StandardOIDs:
    """Standard SNMP OIDs (RFC 1213, RFC 2863)."""

    # System MIB (SNMPv2-MIB)
    SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
    SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
    SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
    SYS_NAME = "1.3.6.1.2.1.1.5.0"
    SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

    # Interface MIB (IF-MIB)
    IF_TABLE = "1.3.6.1.2.1.2.2"
    IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
    IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
    IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
    IF_MTU = "1.3.6.1.2.1.2.2.1.4"
    IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
    IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"
    IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
    IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
    IF_LAST_CHANGE = "1.3.6.1.2.1.2.2.1.9"

    # 32-bit counters (legacy, use HC when available)
    IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
    IF_IN_UCAST_PKTS = "1.3.6.1.2.1.2.2.1.11"
    IF_IN_DISCARDS = "1.3.6.1.2.1.2.2.1.13"
    IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
    IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
    IF_OUT_UCAST_PKTS = "1.3.6.1.2.1.2.2.1.17"
    IF_OUT_DISCARDS = "1.3.6.1.2.1.2.2.1.19"
    IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"

    # 64-bit counters (ifXTable, RFC 2863)
    IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
    IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
    IF_HC_IN_UCAST_PKTS = "1.3.6.1.2.1.31.1.1.1.7"
    IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"
    IF_HC_OUT_UCAST_PKTS = "1.3.6.1.2.1.31.1.1.1.11"
    IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"
    IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"


class MikroTikOIDs:
    """MikroTik-specific OIDs (Enterprise MIB 14988)."""

    # Base OID
    MIKROTIK_BASE = "1.3.6.1.4.1.14988"

    # Health MIB
    HW_VOLTAGE = "1.3.6.1.4.1.14988.1.1.3.8.0"
    HW_TEMPERATURE = "1.3.6.1.4.1.14988.1.1.3.10.0"
    HW_PROCESSOR_TEMPERATURE = "1.3.6.1.4.1.14988.1.1.3.11.0"
    HW_CURRENT = "1.3.6.1.4.1.14988.1.1.3.13.0"
    HW_CPU_LOAD = "1.3.6.1.4.1.14988.1.1.3.14.0"
    HW_POWER = "1.3.6.1.4.1.14988.1.1.3.12.0"

    # System info
    LICENSE_ID = "1.3.6.1.4.1.14988.1.1.4.1.0"
    SOFTWARE_ID = "1.3.6.1.4.1.14988.1.1.4.3.0"

    # Memory
    TOTAL_MEMORY = "1.3.6.1.4.1.14988.1.1.16.1.1.2"
    USED_MEMORY = "1.3.6.1.4.1.14988.1.1.16.1.1.3"

    # Active sessions (these are typically tables, need walk)
    PPP_ACTIVE_TABLE = "1.3.6.1.4.1.14988.1.1.5.1"
    HOTSPOT_ACTIVE_TABLE = "1.3.6.1.4.1.14988.1.1.5.3"
    DHCP_LEASE_TABLE = "1.3.6.1.4.1.14988.1.1.5.4"

    # For counting active sessions
    PPP_ACTIVE_USER = "1.3.6.1.4.1.14988.1.1.5.1.1.2"
    HOTSPOT_ACTIVE_USER = "1.3.6.1.4.1.14988.1.1.5.3.1.2"


# Interface type constants (IANAifType-MIB)
class InterfaceType:
    """Common interface type values from IANAifType-MIB."""

    OTHER = 1
    REGULAR_1822 = 2
    HDH_1822 = 3
    DDN_X25 = 4
    RFC877_X25 = 5
    ETHERNET_CSMACD = 6
    ISO88023_CSMACD = 7
    ISO88024_TOKEN_BUS = 8
    ISO88025_TOKEN_RING = 9
    ISO88026_MAN = 10
    STAR_LAN = 11
    PROTEON_10MBIT = 12
    PROTEON_80MBIT = 13
    HYPERCHANNEL = 14
    FDDI = 15
    LAPB = 16
    SDLC = 17
    DS1 = 18
    E1 = 19
    BASIC_ISDN = 20
    PRIMARY_ISDN = 21
    PROP_POINT_TO_POINT = 22
    PPP = 23
    SOFTWARE_LOOPBACK = 24
    EON = 25
    ETHERNET_3MBIT = 26
    NSIP = 27
    SLIP = 28
    ULTRA = 29
    DS3 = 30
    SIP = 31
    FRAME_RELAY = 32
    VLAN = 53
    L2VLAN = 135
    TUNNEL = 131
    GRE = 131
    BRIDGE = 209
    GIGE = 117
    TEN_GIGE = 6
    WIFI = 71

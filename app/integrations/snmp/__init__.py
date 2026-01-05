"""SNMP Integration Package.

Provides async SNMP polling capabilities for network device monitoring.
Supports SNMPv2c and SNMPv3 protocols.

Usage:
    from app.integrations.snmp import SNMPClient
    from app.models.snmp_metrics import SNMPPollingConfig

    config = SNMPPollingConfig(...)
    async with SNMPClient(router.ip, config) as client:
        result = await client.poll_device()
        if result.success:
            print(f"CPU: {result.system_info.cpu_load}%")

Requirements:
    pysnmp-lextudio>=5.0.0
"""
from app.integrations.snmp.client import SNMPClient, PYSNMP_AVAILABLE
from app.integrations.snmp.exceptions import (
    SNMPError,
    SNMPTimeoutError,
    SNMPAuthenticationError,
    SNMPConnectionError,
    SNMPNoSuchObjectError,
    SNMPEndOfMibError,
    SNMPConfigurationError,
    DeviceUnreachableError,
    CircuitBreakerOpenError,
)
from app.integrations.snmp.types import (
    SystemInfo,
    InterfaceData,
    DevicePollingResult,
    OIDResult,
    RateCalculation,
    StandardOIDs,
    MikroTikOIDs,
    InterfaceType,
)

__all__ = [
    # Client
    "SNMPClient",
    "PYSNMP_AVAILABLE",
    # Exceptions
    "SNMPError",
    "SNMPTimeoutError",
    "SNMPAuthenticationError",
    "SNMPConnectionError",
    "SNMPNoSuchObjectError",
    "SNMPEndOfMibError",
    "SNMPConfigurationError",
    "DeviceUnreachableError",
    "CircuitBreakerOpenError",
    # Types
    "SystemInfo",
    "InterfaceData",
    "DevicePollingResult",
    "OIDResult",
    "RateCalculation",
    "StandardOIDs",
    "MikroTikOIDs",
    "InterfaceType",
]

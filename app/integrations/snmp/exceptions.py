"""SNMP Integration Exceptions.

Custom exceptions for SNMP polling operations.
"""
from __future__ import annotations

from typing import Optional, Dict, Any


class SNMPError(Exception):
    """Base exception for all SNMP-related errors."""

    def __init__(
        self,
        message: str,
        *,
        router_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.router_id = router_id
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.router_id:
            parts.append(f"(router_id={self.router_id})")
        return " ".join(parts)


class SNMPTimeoutError(SNMPError):
    """SNMP request timed out."""

    pass


class SNMPAuthenticationError(SNMPError):
    """SNMP authentication failed (wrong community or v3 credentials)."""

    pass


class SNMPConnectionError(SNMPError):
    """Failed to connect to the device via SNMP."""

    pass


class SNMPNoSuchObjectError(SNMPError):
    """Requested OID does not exist on the device."""

    def __init__(
        self,
        message: str,
        *,
        oid: Optional[str] = None,
        **kwargs,
    ):
        self.oid = oid
        super().__init__(message, **kwargs)


class SNMPEndOfMibError(SNMPError):
    """Reached end of MIB during walk operation."""

    pass


class SNMPConfigurationError(SNMPError):
    """Invalid SNMP configuration."""

    pass


class DeviceUnreachableError(SNMPError):
    """Device is not reachable via SNMP."""

    pass


class CircuitBreakerOpenError(SNMPError):
    """Circuit breaker is open, blocking SNMP requests to this device."""

    pass

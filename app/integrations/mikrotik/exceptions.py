"""
MikroTik Integration Exceptions

Custom exceptions for MikroTik RouterOS API operations.
"""

from __future__ import annotations

from typing import Optional, Dict, Any


class MikroTikError(Exception):
    """Base exception for all MikroTik-related errors."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        router_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.router_id = router_id
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"[{self.code}]")
        if self.router_id:
            parts.append(f"(router_id={self.router_id})")
        return " ".join(parts)


class ConnectionError(MikroTikError):
    """Failed to connect to the router."""

    pass


class AuthenticationError(MikroTikError):
    """Invalid credentials or access denied."""

    pass


class TimeoutError(MikroTikError):
    """Request timed out."""

    pass


class APIError(MikroTikError):
    """Router returned an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        **kwargs,
    ):
        self.status_code = status_code
        super().__init__(message, **kwargs)


class ResourceNotFoundError(APIError):
    """Requested resource does not exist on the router."""

    pass


class ResourceExistsError(APIError):
    """Resource already exists (duplicate)."""

    pass


class ValidationError(MikroTikError):
    """Invalid parameters for router operation."""

    pass


class ProvisioningError(MikroTikError):
    """Error during subscription provisioning."""

    def __init__(
        self,
        message: str,
        *,
        subscription_id: Optional[int] = None,
        access_method: Optional[str] = None,
        **kwargs,
    ):
        self.subscription_id = subscription_id
        self.access_method = access_method
        super().__init__(message, **kwargs)


class DeprovisioningError(ProvisioningError):
    """Error during subscription deprovisioning."""

    pass


class DisconnectError(MikroTikError):
    """Failed to disconnect an active session."""

    def __init__(
        self,
        message: str,
        *,
        subscription_id: Optional[int] = None,
        access_method: Optional[str] = None,
        **kwargs,
    ):
        self.subscription_id = subscription_id
        self.access_method = access_method
        super().__init__(message, **kwargs)


class RouterUnavailableError(MikroTikError):
    """Router is not reachable or not responding."""

    pass


class CircuitBreakerOpenError(MikroTikError):
    """Circuit breaker is open, blocking requests to this router."""

    pass

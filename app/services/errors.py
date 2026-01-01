"""Shared service-layer exceptions."""


class ServiceError(Exception):
    """Base error for service-layer failures."""


class ValidationError(ServiceError):
    """Raised when service input/state is invalid."""

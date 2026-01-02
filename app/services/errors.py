"""Shared service-layer exceptions with HTTP mapping."""


class ServiceError(Exception):
    """Base error for service-layer failures."""

    http_code: int = 500

    def __init__(self, message: str = "Service error", http_code: int | None = None) -> None:
        self.message = message
        if http_code is not None:
            self.http_code = http_code
        super().__init__(message)


class NotFoundError(ServiceError):
    """Raised when a requested resource is not found."""

    http_code = 404


class ValidationError(ServiceError):
    """Raised when service input/state is invalid."""

    http_code = 422


class ConflictError(ServiceError):
    """Raised when operation conflicts with current resource state."""

    http_code = 409


class ForbiddenError(ServiceError):
    """Raised when principal lacks permission for the operation."""

    http_code = 403

"""Fleet-specific error types.

These errors extend the base service errors to provide
domain-specific exceptions for the fleet module.
"""
from app.services.errors import NotFoundError, ValidationError

__all__ = [
    "FleetError",
    "VehicleNotFoundError",
    "DriverNotFoundError",
    "DuplicateLicensePlateError",
    "InvalidOdometerError",
]


class FleetError(ValidationError):
    """Base error for fleet-related issues."""

    pass


class VehicleNotFoundError(NotFoundError):
    """Raised when a vehicle is not found."""

    def __init__(self, vehicle_id: int, message: str = None):
        self.vehicle_id = vehicle_id
        super().__init__(message or f"Vehicle with ID {vehicle_id} not found")


class DriverNotFoundError(NotFoundError):
    """Raised when a driver (employee) is not found."""

    def __init__(self, employee_id: int, message: str = None):
        self.employee_id = employee_id
        super().__init__(message or f"Driver with ID {employee_id} not found")


class DuplicateLicensePlateError(FleetError):
    """Raised when trying to create a vehicle with a duplicate license plate."""

    def __init__(self, license_plate: str):
        self.license_plate = license_plate
        super().__init__(f"Vehicle with license plate '{license_plate}' already exists")


class InvalidOdometerError(FleetError):
    """Raised when odometer reading is invalid (e.g., less than previous)."""

    def __init__(self, new_value, current_value):
        self.new_value = new_value
        self.current_value = current_value
        super().__init__(
            f"New odometer value ({new_value}) cannot be less than current value ({current_value})"
        )

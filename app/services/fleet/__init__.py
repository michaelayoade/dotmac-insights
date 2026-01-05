"""Fleet management domain services.

This module contains business logic for:
- Vehicles (CRUD, driver assignments, odometer tracking)
- Insurance (expiry tracking, policy management)
- Dashboard (fleet analytics and metrics)
"""
from .vehicles import VehicleService
from .dashboard import FleetDashboardService

from .vehicle_types import (
    VehicleFilters,
    VehicleCreateData,
    VehicleUpdateData,
    VehicleSummary,
    InsuranceExpiryFilters,
    OdometerUpdateData,
    DriverAssignmentData,
)
from .errors import (
    FleetError,
    VehicleNotFoundError,
    DriverNotFoundError,
    DuplicateLicensePlateError,
    InvalidOdometerError,
)

__all__ = [
    # Services
    "VehicleService",
    "FleetDashboardService",
    # Vehicle types
    "VehicleFilters",
    "VehicleCreateData",
    "VehicleUpdateData",
    "VehicleSummary",
    "InsuranceExpiryFilters",
    "OdometerUpdateData",
    "DriverAssignmentData",
    # Errors
    "FleetError",
    "VehicleNotFoundError",
    "DriverNotFoundError",
    "DuplicateLicensePlateError",
    "InvalidOdometerError",
]

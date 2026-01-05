"""Type definitions for fleet vehicle service.

These dataclasses define the contract for vehicle operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

__all__ = [
    "VehicleFilters",
    "VehicleCreateData",
    "VehicleUpdateData",
    "VehicleSummary",
    "InsuranceExpiryFilters",
    "OdometerUpdateData",
    "DriverAssignmentData",
]


@dataclass
class VehicleFilters:
    """Filters for querying vehicles."""

    search: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    fuel_type: Optional[str] = None
    employee_id: Optional[int] = None
    is_active: Optional[bool] = None
    company: Optional[str] = None
    sort_by: str = "license_plate"
    sort_order: str = "asc"


@dataclass
class VehicleCreateData:
    """Data for creating a vehicle."""

    license_plate: str
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    chassis_no: Optional[str] = None
    color: Optional[str] = None
    doors: Optional[int] = None
    wheels: Optional[int] = None
    vehicle_value: Decimal = field(default_factory=lambda: Decimal("0"))
    acquisition_date: Optional[date] = None
    fuel_type: Optional[str] = None
    fuel_uom: Optional[str] = None
    odometer_value: Decimal = field(default_factory=lambda: Decimal("0"))
    uom: Optional[str] = None
    insurance_company: Optional[str] = None
    policy_no: Optional[str] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    employee_id: Optional[int] = None
    location: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True


@dataclass
class VehicleUpdateData:
    """Data for updating a vehicle (all fields optional)."""

    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    chassis_no: Optional[str] = None
    color: Optional[str] = None
    doors: Optional[int] = None
    wheels: Optional[int] = None
    vehicle_value: Optional[Decimal] = None
    acquisition_date: Optional[date] = None
    fuel_type: Optional[str] = None
    fuel_uom: Optional[str] = None
    odometer_value: Optional[Decimal] = None
    uom: Optional[str] = None
    insurance_company: Optional[str] = None
    policy_no: Optional[str] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    employee_id: Optional[int] = None
    location: Optional[str] = None
    company: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class VehicleSummary:
    """Fleet summary statistics."""

    total_vehicles: int = 0
    active_vehicles: int = 0
    inactive_vehicles: int = 0
    by_fuel_type: Dict[str, int] = field(default_factory=dict)
    by_make: Dict[str, int] = field(default_factory=dict)
    insurance_expiring_soon: int = 0
    total_value: Decimal = field(default_factory=lambda: Decimal("0"))
    avg_odometer: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class InsuranceExpiryFilters:
    """Filters for insurance expiry queries."""

    days_ahead: int = 30
    include_expired: bool = False
    company: Optional[str] = None


@dataclass
class OdometerUpdateData:
    """Data for updating vehicle odometer."""

    odometer_value: Decimal
    reading_date: Optional[date] = None


@dataclass
class DriverAssignmentData:
    """Data for assigning a driver to a vehicle."""

    employee_id: Optional[int]  # None to unassign

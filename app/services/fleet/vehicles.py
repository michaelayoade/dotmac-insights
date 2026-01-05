"""Vehicle service for fleet management.

This service handles:
- CRUD operations for vehicles
- Insurance tracking
- Odometer management
- Driver assignments
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.vehicle import Vehicle
from app.models.employee import Employee
from app.services.types import PaginatedResult, PaginationParams

from .errors import (
    VehicleNotFoundError,
    DriverNotFoundError,
    DuplicateLicensePlateError,
    InvalidOdometerError,
)
from .vehicle_types import (
    VehicleFilters,
    VehicleCreateData,
    VehicleUpdateData,
    OdometerUpdateData,
    DriverAssignmentData,
    InsuranceExpiryFilters,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["VehicleService"]


class VehicleService:
    """Service for managing fleet vehicles.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def list_vehicles(
        self,
        filters: Optional[VehicleFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Vehicle]:
        """List vehicles with filtering and pagination.

        Args:
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Paginated list of vehicles with driver info eagerly loaded
        """
        if filters is None:
            filters = VehicleFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = select(Vehicle).options(joinedload(Vehicle.assigned_driver))

        # Build conditions
        conditions = []
        if filters.search:
            search_pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    Vehicle.license_plate.ilike(search_pattern),
                    Vehicle.make.ilike(search_pattern),
                    Vehicle.model.ilike(search_pattern),
                    Vehicle.chassis_no.ilike(search_pattern),
                )
            )
        if filters.make:
            conditions.append(Vehicle.make == filters.make)
        if filters.model:
            conditions.append(Vehicle.model == filters.model)
        if filters.fuel_type:
            conditions.append(Vehicle.fuel_type == filters.fuel_type)
        if filters.employee_id is not None:
            conditions.append(Vehicle.employee_id == filters.employee_id)
        if filters.is_active is not None:
            conditions.append(Vehicle.is_active == filters.is_active)
        if filters.company:
            conditions.append(Vehicle.company == filters.company)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total
        count_query = select(func.count()).select_from(Vehicle)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total = self.db.execute(count_query).scalar() or 0

        # Apply sorting
        sort_column = getattr(Vehicle, filters.sort_by, Vehicle.license_plate)
        if filters.sort_order == "desc":
            sort_column = desc(sort_column)
        query = query.order_by(sort_column)

        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        vehicles = self.db.execute(query).unique().scalars().all()

        return PaginatedResult(
            items=list(vehicles),
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_vehicle(self, vehicle_id: int) -> Vehicle:
        """Get a vehicle by ID.

        Args:
            vehicle_id: ID of the vehicle

        Returns:
            The vehicle with driver info eagerly loaded

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        query = (
            select(Vehicle)
            .options(joinedload(Vehicle.assigned_driver))
            .where(Vehicle.id == vehicle_id)
        )
        vehicle = self.db.execute(query).unique().scalar_one_or_none()

        if not vehicle:
            raise VehicleNotFoundError(vehicle_id)

        return vehicle

    def get_vehicles_by_driver(self, employee_id: int) -> List[Vehicle]:
        """Get all vehicles assigned to a specific driver.

        Args:
            employee_id: ID of the driver (employee)

        Returns:
            List of vehicles assigned to the driver
        """
        query = (
            select(Vehicle)
            .options(joinedload(Vehicle.assigned_driver))
            .where(Vehicle.employee_id == employee_id)
            .order_by(Vehicle.license_plate)
        )
        vehicles = self.db.execute(query).unique().scalars().all()
        return list(vehicles)

    def get_distinct_makes(self) -> List[str]:
        """Get list of distinct vehicle makes.

        Returns:
            Sorted list of unique makes
        """
        rows = self.db.execute(
            select(Vehicle.make)
            .where(Vehicle.make.isnot(None))
            .distinct()
            .order_by(Vehicle.make)
        ).scalars().all()
        return list(rows)

    def get_distinct_fuel_types(self) -> List[str]:
        """Get list of distinct fuel types.

        Returns:
            Sorted list of unique fuel types
        """
        rows = self.db.execute(
            select(Vehicle.fuel_type)
            .where(Vehicle.fuel_type.isnot(None))
            .distinct()
            .order_by(Vehicle.fuel_type)
        ).scalars().all()
        return list(rows)

    # -------------------------------------------------------------------------
    # Mutation Methods
    # -------------------------------------------------------------------------

    def create_vehicle(self, data: VehicleCreateData) -> Vehicle:
        """Create a new vehicle.

        Args:
            data: Vehicle creation data

        Returns:
            The created vehicle (not yet committed)

        Raises:
            DuplicateLicensePlateError: If license plate already exists
            DriverNotFoundError: If specified driver does not exist
        """
        # Check for duplicate license plate
        existing = self.db.execute(
            select(Vehicle).where(Vehicle.license_plate == data.license_plate)
        ).scalar_one_or_none()
        if existing:
            raise DuplicateLicensePlateError(data.license_plate)

        # Validate driver if specified
        if data.employee_id:
            driver = self.db.query(Employee).filter(
                Employee.id == data.employee_id
            ).first()
            if not driver:
                raise DriverNotFoundError(data.employee_id)

        vehicle = Vehicle(
            license_plate=data.license_plate,
            make=data.make,
            model=data.model,
            model_year=data.model_year,
            chassis_no=data.chassis_no,
            color=data.color,
            doors=data.doors,
            wheels=data.wheels,
            vehicle_value=data.vehicle_value,
            acquisition_date=data.acquisition_date,
            fuel_type=data.fuel_type,
            fuel_uom=data.fuel_uom,
            odometer_value=data.odometer_value,
            uom=data.uom,
            insurance_company=data.insurance_company,
            policy_no=data.policy_no,
            insurance_start_date=data.insurance_start_date,
            insurance_end_date=data.insurance_end_date,
            employee_id=data.employee_id,
            location=data.location,
            company=data.company,
            is_active=data.is_active,
        )
        self.db.add(vehicle)
        self.db.flush()
        return vehicle

    def update_vehicle(
        self,
        vehicle_id: int,
        data: VehicleUpdateData,
    ) -> Vehicle:
        """Update a vehicle.

        Args:
            vehicle_id: ID of the vehicle to update
            data: Vehicle update data

        Returns:
            The updated vehicle (not yet committed)

        Raises:
            VehicleNotFoundError: If vehicle does not exist
            DuplicateLicensePlateError: If new license plate already exists
            DriverNotFoundError: If specified driver does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)

        # Check for duplicate license plate if changing
        if data.license_plate and data.license_plate != vehicle.license_plate:
            existing = self.db.execute(
                select(Vehicle).where(
                    Vehicle.license_plate == data.license_plate,
                    Vehicle.id != vehicle_id,
                )
            ).scalar_one_or_none()
            if existing:
                raise DuplicateLicensePlateError(data.license_plate)
            vehicle.license_plate = data.license_plate

        # Validate driver if changing
        if data.employee_id is not None and data.employee_id != vehicle.employee_id:
            if data.employee_id:  # Not None/unassigning
                driver = self.db.query(Employee).filter(
                    Employee.id == data.employee_id
                ).first()
                if not driver:
                    raise DriverNotFoundError(data.employee_id)
            vehicle.employee_id = data.employee_id

        # Update other fields
        if data.make is not None:
            vehicle.make = data.make
        if data.model is not None:
            vehicle.model = data.model
        if data.model_year is not None:
            vehicle.model_year = data.model_year
        if data.chassis_no is not None:
            vehicle.chassis_no = data.chassis_no
        if data.color is not None:
            vehicle.color = data.color
        if data.doors is not None:
            vehicle.doors = data.doors
        if data.wheels is not None:
            vehicle.wheels = data.wheels
        if data.vehicle_value is not None:
            vehicle.vehicle_value = data.vehicle_value
        if data.acquisition_date is not None:
            vehicle.acquisition_date = data.acquisition_date
        if data.fuel_type is not None:
            vehicle.fuel_type = data.fuel_type
        if data.fuel_uom is not None:
            vehicle.fuel_uom = data.fuel_uom
        if data.uom is not None:
            vehicle.uom = data.uom
        if data.location is not None:
            vehicle.location = data.location
        if data.company is not None:
            vehicle.company = data.company
        if data.is_active is not None:
            vehicle.is_active = data.is_active

        # Handle odometer separately (needs date tracking)
        if data.odometer_value is not None and data.odometer_value != vehicle.odometer_value:
            vehicle.odometer_value = data.odometer_value
            vehicle.last_odometer_date = date.today()

        # Insurance fields
        if data.insurance_company is not None:
            vehicle.insurance_company = data.insurance_company
        if data.policy_no is not None:
            vehicle.policy_no = data.policy_no
        if data.insurance_start_date is not None:
            vehicle.insurance_start_date = data.insurance_start_date
        if data.insurance_end_date is not None:
            vehicle.insurance_end_date = data.insurance_end_date

        vehicle.updated_at = datetime.now(timezone.utc)
        return vehicle

    def delete_vehicle(self, vehicle_id: int) -> None:
        """Delete a vehicle (hard delete).

        Args:
            vehicle_id: ID of the vehicle to delete

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)
        self.db.delete(vehicle)

    def deactivate_vehicle(self, vehicle_id: int) -> Vehicle:
        """Deactivate a vehicle (soft delete).

        Args:
            vehicle_id: ID of the vehicle to deactivate

        Returns:
            The deactivated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)
        vehicle.is_active = False
        vehicle.updated_at = datetime.now(timezone.utc)
        return vehicle

    def activate_vehicle(self, vehicle_id: int) -> Vehicle:
        """Activate a previously deactivated vehicle.

        Args:
            vehicle_id: ID of the vehicle to activate

        Returns:
            The activated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)
        vehicle.is_active = True
        vehicle.updated_at = datetime.now(timezone.utc)
        return vehicle

    # -------------------------------------------------------------------------
    # Odometer Methods
    # -------------------------------------------------------------------------

    def update_odometer(
        self,
        vehicle_id: int,
        data: OdometerUpdateData,
        validate_increase: bool = True,
    ) -> Vehicle:
        """Update vehicle odometer reading.

        Args:
            vehicle_id: ID of the vehicle
            data: Odometer update data
            validate_increase: If True, validates new reading is >= current

        Returns:
            The updated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
            InvalidOdometerError: If new value is less than current (when validated)
        """
        vehicle = self.get_vehicle(vehicle_id)

        if validate_increase and data.odometer_value < vehicle.odometer_value:
            raise InvalidOdometerError(data.odometer_value, vehicle.odometer_value)

        vehicle.odometer_value = data.odometer_value
        vehicle.last_odometer_date = data.reading_date or date.today()
        vehicle.updated_at = datetime.now(timezone.utc)

        return vehicle

    # -------------------------------------------------------------------------
    # Driver Assignment Methods
    # -------------------------------------------------------------------------

    def assign_driver(
        self,
        vehicle_id: int,
        data: DriverAssignmentData,
    ) -> Vehicle:
        """Assign or unassign a driver to a vehicle.

        Args:
            vehicle_id: ID of the vehicle
            data: Driver assignment data

        Returns:
            The updated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
            DriverNotFoundError: If driver does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)

        if data.employee_id:
            # Validate driver exists
            driver = self.db.query(Employee).filter(
                Employee.id == data.employee_id
            ).first()
            if not driver:
                raise DriverNotFoundError(data.employee_id)

        vehicle.employee_id = data.employee_id
        vehicle.updated_at = datetime.now(timezone.utc)

        return vehicle

    def unassign_driver(self, vehicle_id: int) -> Vehicle:
        """Remove driver assignment from a vehicle.

        Args:
            vehicle_id: ID of the vehicle

        Returns:
            The updated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        return self.assign_driver(
            vehicle_id,
            DriverAssignmentData(employee_id=None),
        )

    # -------------------------------------------------------------------------
    # Insurance Methods
    # -------------------------------------------------------------------------

    def get_vehicles_insurance_expiring(
        self,
        filters: Optional[InsuranceExpiryFilters] = None,
    ) -> List[Vehicle]:
        """Get vehicles with insurance expiring within specified days.

        Args:
            filters: Expiry filter parameters

        Returns:
            List of vehicles with expiring insurance, ordered by expiry date
        """
        if filters is None:
            filters = InsuranceExpiryFilters()

        expiry_threshold = date.today() + timedelta(days=filters.days_ahead)
        today = date.today()

        conditions = [
            Vehicle.is_active == True,
            Vehicle.insurance_end_date.isnot(None),
            Vehicle.insurance_end_date <= expiry_threshold,
        ]

        if not filters.include_expired:
            conditions.append(Vehicle.insurance_end_date >= today)

        if filters.company:
            conditions.append(Vehicle.company == filters.company)

        query = (
            select(Vehicle)
            .options(joinedload(Vehicle.assigned_driver))
            .where(and_(*conditions))
            .order_by(Vehicle.insurance_end_date)
        )

        vehicles = self.db.execute(query).unique().scalars().all()
        return list(vehicles)

    def update_insurance(
        self,
        vehicle_id: int,
        insurance_company: Optional[str] = None,
        policy_no: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Vehicle:
        """Update vehicle insurance information.

        Args:
            vehicle_id: ID of the vehicle
            insurance_company: Insurance company name
            policy_no: Policy number
            start_date: Insurance start date
            end_date: Insurance end date

        Returns:
            The updated vehicle

        Raises:
            VehicleNotFoundError: If vehicle does not exist
        """
        vehicle = self.get_vehicle(vehicle_id)

        if insurance_company is not None:
            vehicle.insurance_company = insurance_company
        if policy_no is not None:
            vehicle.policy_no = policy_no
        if start_date is not None:
            vehicle.insurance_start_date = start_date
        if end_date is not None:
            vehicle.insurance_end_date = end_date

        vehicle.updated_at = datetime.now(timezone.utc)
        return vehicle

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def enrich_with_driver_name(self, vehicle: Vehicle) -> Tuple[Vehicle, Optional[str]]:
        """Get vehicle with driver name if assigned.

        Args:
            vehicle: The vehicle to enrich

        Returns:
            Tuple of (vehicle, driver_name or None)
        """
        driver_name = None
        if vehicle.assigned_driver:
            driver_name = vehicle.assigned_driver.name
        return vehicle, driver_name

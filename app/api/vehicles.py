"""
Vehicle Management API

Provides endpoints for managing fleet vehicles, driver assignments,
insurance tracking, and vehicle lifecycle management.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.models.vehicle import Vehicle
from app.auth import Require
from app.services.fleet import (
    VehicleService,
    FleetDashboardService,
    VehicleFilters,
    VehicleUpdateData,
    InsuranceExpiryFilters,
    VehicleNotFoundError,
    DuplicateLicensePlateError,
    DriverNotFoundError,
)
from app.services.types import PaginationParams

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


# ============= PYDANTIC SCHEMAS =============

class VehicleResponse(BaseModel):
    id: int
    erpnext_id: Optional[str] = None
    license_plate: str
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    chassis_no: Optional[str] = None
    color: Optional[str] = None
    doors: Optional[int] = None
    wheels: Optional[int] = None
    vehicle_value: Decimal = Decimal("0")
    acquisition_date: Optional[date] = None
    fuel_type: Optional[str] = None
    fuel_uom: Optional[str] = None
    odometer_value: Decimal = Decimal("0")
    last_odometer_date: Optional[date] = None
    uom: Optional[str] = None
    insurance_company: Optional[str] = None
    policy_no: Optional[str] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    driver_name: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleUpdatePayload(BaseModel):
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    color: Optional[str] = None
    odometer_value: Optional[Decimal] = None
    acquisition_date: Optional[date] = None
    fuel_uom: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    employee_id: Optional[int] = None
    is_active: Optional[bool] = None
    insurance_company: Optional[str] = None
    policy_no: Optional[str] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None


class VehicleSummary(BaseModel):
    total_vehicles: int
    active_vehicles: int
    inactive_vehicles: int
    by_fuel_type: Dict[str, int]
    by_make: Dict[str, int]
    insurance_expiring_soon: int
    total_value: Decimal
    avg_odometer: Decimal


class VehicleListResponse(BaseModel):
    items: List[VehicleResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============= ENDPOINTS =============

@router.get("", response_model=VehicleListResponse, dependencies=[Depends(Require("fleet:read"))])
async def list_vehicles(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    make: Optional[str] = None,
    model: Optional[str] = None,
    fuel_type: Optional[str] = None,
    employee_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    sort_by: str = Query("license_plate", regex="^(license_plate|make|model|acquisition_date|vehicle_value|odometer_value)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
):
    """List all vehicles with filtering and pagination."""
    service = VehicleService(db)

    filters = VehicleFilters(
        search=search,
        make=make,
        model=model,
        fuel_type=fuel_type,
        employee_id=employee_id,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pagination = PaginationParams(page=page, limit=page_size)

    result = service.list_vehicles(filters, pagination)

    # Build response with driver names
    items = []
    for v in result.items:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return VehicleListResponse(
        items=items,
        total=result.total,
        page=page,
        page_size=page_size,
        pages=(result.total + page_size - 1) // page_size,
    )


@router.get("/summary", response_model=VehicleSummary, dependencies=[Depends(Require("fleet:read"))])
async def get_vehicle_summary(db: Session = Depends(get_db)):
    """Get fleet summary statistics."""
    service = FleetDashboardService(db)
    summary = service.get_fleet_summary()

    return VehicleSummary(
        total_vehicles=summary.total_vehicles,
        active_vehicles=summary.active_vehicles,
        inactive_vehicles=summary.inactive_vehicles,
        by_fuel_type=summary.by_fuel_type,
        by_make=summary.by_make,
        insurance_expiring_soon=summary.insurance_expiring_soon,
        total_value=summary.total_value,
        avg_odometer=summary.avg_odometer,
    )


@router.get("/insurance/expiring", response_model=List[VehicleResponse], dependencies=[Depends(Require("fleet:read"))])
async def get_vehicles_insurance_expiring(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Days until expiry"),
):
    """Get vehicles with insurance expiring within specified days."""
    service = VehicleService(db)

    filters = InsuranceExpiryFilters(
        days_ahead=days,
        include_expired=False,
    )
    vehicles = service.get_vehicles_insurance_expiring(filters)

    items = []
    for v in vehicles:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return items


@router.get("/makes", response_model=List[str], dependencies=[Depends(Require("fleet:read"))])
async def get_vehicle_makes(db: Session = Depends(get_db)):
    """Get list of distinct vehicle makes."""
    service = VehicleService(db)
    return service.get_distinct_makes()


@router.get("/fuel-types", response_model=List[str], dependencies=[Depends(Require("fleet:read"))])
async def get_fuel_types(db: Session = Depends(get_db)):
    """Get list of distinct fuel types."""
    service = VehicleService(db)
    return service.get_distinct_fuel_types()


@router.get("/{vehicle_id}", response_model=VehicleResponse, dependencies=[Depends(Require("fleet:read"))])
async def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Get a single vehicle by ID."""
    service = VehicleService(db)

    try:
        vehicle = service.get_vehicle(vehicle_id)
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    item = VehicleResponse.model_validate(vehicle)
    if vehicle.assigned_driver:
        item.driver_name = vehicle.assigned_driver.name

    return item


@router.patch("/{vehicle_id}", response_model=VehicleResponse, dependencies=[Depends(Require("fleet:write"))])
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdatePayload,
    db: Session = Depends(get_db),
):
    """Update a vehicle."""
    service = VehicleService(db)

    # Convert payload to service DTO
    data = VehicleUpdateData(
        license_plate=payload.license_plate,
        make=payload.make,
        model=payload.model,
        model_year=payload.model_year,
        color=payload.color,
        odometer_value=payload.odometer_value,
        acquisition_date=payload.acquisition_date,
        fuel_uom=payload.fuel_uom,
        location=payload.location,
        company=payload.company,
        employee_id=payload.employee_id,
        is_active=payload.is_active,
        insurance_company=payload.insurance_company,
        policy_no=payload.policy_no,
        insurance_start_date=payload.insurance_start_date,
        insurance_end_date=payload.insurance_end_date,
    )

    try:
        vehicle = service.update_vehicle(vehicle_id, data)
        db.commit()
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    except DuplicateLicensePlateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DriverNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    item = VehicleResponse.model_validate(vehicle)
    if vehicle.assigned_driver:
        item.driver_name = vehicle.assigned_driver.name

    return item


@router.get("/by-driver/{employee_id}", response_model=List[VehicleResponse], dependencies=[Depends(Require("fleet:read"))])
async def get_vehicles_by_driver(employee_id: int, db: Session = Depends(get_db)):
    """Get all vehicles assigned to a specific driver."""
    service = VehicleService(db)
    vehicles = service.get_vehicles_by_driver(employee_id)

    items = []
    for v in vehicles:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return items

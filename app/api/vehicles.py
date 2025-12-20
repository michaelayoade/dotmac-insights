"""
Vehicle Management API

Provides endpoints for managing fleet vehicles, driver assignments,
insurance tracking, and vehicle lifecycle management.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.vehicle import Vehicle
from app.models.employee import Employee
from app.auth import Require

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

    class Config:
        from_attributes = True


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

@router.get("", response_model=VehicleListResponse, dependencies=[Depends(Require("hr:read"))])
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
    query = select(Vehicle).options(joinedload(Vehicle.assigned_driver))

    # Apply filters
    conditions = []
    if search:
        search_pattern = f"%{search}%"
        conditions.append(
            or_(
                Vehicle.license_plate.ilike(search_pattern),
                Vehicle.make.ilike(search_pattern),
                Vehicle.model.ilike(search_pattern),
                Vehicle.chassis_no.ilike(search_pattern),
            )
        )
    if make:
        conditions.append(Vehicle.make == make)
    if model:
        conditions.append(Vehicle.model == model)
    if fuel_type:
        conditions.append(Vehicle.fuel_type == fuel_type)
    if employee_id is not None:
        conditions.append(Vehicle.employee_id == employee_id)
    if is_active is not None:
        conditions.append(Vehicle.is_active == is_active)

    if conditions:
        query = query.where(and_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(Vehicle)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = db.execute(count_query).scalar() or 0

    # Apply sorting
    sort_col = getattr(Vehicle, sort_by)
    if sort_order == "desc":
        sort_col = desc(sort_col)
    query = query.order_by(sort_col)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    vehicles = db.execute(query).unique().scalars().all()

    # Build response with driver names
    items = []
    for v in vehicles:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return VehicleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/summary", response_model=VehicleSummary, dependencies=[Depends(Require("hr:read"))])
async def get_vehicle_summary(db: Session = Depends(get_db)):
    """Get fleet summary statistics."""
    # Count totals
    total = db.execute(select(func.count()).select_from(Vehicle)).scalar() or 0
    active = db.execute(
        select(func.count()).select_from(Vehicle).where(Vehicle.is_active == True)
    ).scalar() or 0

    # By fuel type
    fuel_type_rows = db.execute(
        select(Vehicle.fuel_type, func.count())
        .where(Vehicle.fuel_type.isnot(None))
        .group_by(Vehicle.fuel_type)
    ).all()
    by_fuel_type = {row[0]: row[1] for row in fuel_type_rows}

    # By make
    make_rows = db.execute(
        select(Vehicle.make, func.count())
        .where(Vehicle.make.isnot(None))
        .group_by(Vehicle.make)
        .order_by(desc(func.count()))
        .limit(10)
    ).all()
    by_make = {row[0]: row[1] for row in make_rows}

    # Insurance expiring in 30 days
    expiry_threshold = date.today() + timedelta(days=30)
    insurance_expiring = db.execute(
        select(func.count())
        .select_from(Vehicle)
        .where(
            and_(
                Vehicle.is_active == True,
                Vehicle.insurance_end_date.isnot(None),
                Vehicle.insurance_end_date <= expiry_threshold,
            )
        )
    ).scalar() or 0

    # Total value and avg odometer
    totals = db.execute(
        select(
            func.coalesce(func.sum(Vehicle.vehicle_value), 0),
            func.coalesce(func.avg(Vehicle.odometer_value), 0),
        )
    ).first()

    return VehicleSummary(
        total_vehicles=total,
        active_vehicles=active,
        inactive_vehicles=total - active,
        by_fuel_type=by_fuel_type,
        by_make=by_make,
        insurance_expiring_soon=insurance_expiring,
        total_value=Decimal(str(totals[0])),
        avg_odometer=Decimal(str(round(totals[1], 2))),
    )


@router.get("/insurance/expiring", response_model=List[VehicleResponse], dependencies=[Depends(Require("hr:read"))])
async def get_vehicles_insurance_expiring(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Days until expiry"),
):
    """Get vehicles with insurance expiring within specified days."""
    expiry_threshold = date.today() + timedelta(days=days)

    query = (
        select(Vehicle)
        .options(joinedload(Vehicle.assigned_driver))
        .where(
            and_(
                Vehicle.is_active == True,
                Vehicle.insurance_end_date.isnot(None),
                Vehicle.insurance_end_date <= expiry_threshold,
                Vehicle.insurance_end_date >= date.today(),
            )
        )
        .order_by(Vehicle.insurance_end_date)
    )

    vehicles = db.execute(query).unique().scalars().all()

    items = []
    for v in vehicles:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return items


@router.get("/makes", response_model=List[str], dependencies=[Depends(Require("hr:read"))])
async def get_vehicle_makes(db: Session = Depends(get_db)):
    """Get list of distinct vehicle makes."""
    rows = db.execute(
        select(Vehicle.make)
        .where(Vehicle.make.isnot(None))
        .distinct()
        .order_by(Vehicle.make)
    ).scalars().all()
    return rows


@router.get("/fuel-types", response_model=List[str], dependencies=[Depends(Require("hr:read"))])
async def get_fuel_types(db: Session = Depends(get_db)):
    """Get list of distinct fuel types."""
    rows = db.execute(
        select(Vehicle.fuel_type)
        .where(Vehicle.fuel_type.isnot(None))
        .distinct()
        .order_by(Vehicle.fuel_type)
    ).scalars().all()
    return rows


@router.get("/{vehicle_id}", response_model=VehicleResponse, dependencies=[Depends(Require("hr:read"))])
async def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Get a single vehicle by ID."""
    query = (
        select(Vehicle)
        .options(joinedload(Vehicle.assigned_driver))
        .where(Vehicle.id == vehicle_id)
    )
    vehicle = db.execute(query).unique().scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    item = VehicleResponse.model_validate(vehicle)
    if vehicle.assigned_driver:
        item.driver_name = vehicle.assigned_driver.name

    return item


@router.patch("/{vehicle_id}", response_model=VehicleResponse, dependencies=[Depends(Require("hr:write"))])
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdatePayload,
    db: Session = Depends(get_db),
):
    """Update a vehicle."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Update odometer date only if odometer value actually changed
    if "odometer_value" in update_data and update_data["odometer_value"] != vehicle.odometer_value:
        update_data["last_odometer_date"] = date.today()
    elif "odometer_value" in update_data and update_data["odometer_value"] == vehicle.odometer_value:
        # Remove odometer_value from update if unchanged to avoid unnecessary write
        del update_data["odometer_value"]

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    vehicle.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(vehicle)

    item = VehicleResponse.model_validate(vehicle)
    if vehicle.assigned_driver:
        item.driver_name = vehicle.assigned_driver.name

    return item


@router.get("/by-driver/{employee_id}", response_model=List[VehicleResponse], dependencies=[Depends(Require("hr:read"))])
async def get_vehicles_by_driver(employee_id: int, db: Session = Depends(get_db)):
    """Get all vehicles assigned to a specific driver."""
    query = (
        select(Vehicle)
        .options(joinedload(Vehicle.assigned_driver))
        .where(Vehicle.employee_id == employee_id)
        .order_by(Vehicle.license_plate)
    )
    vehicles = db.execute(query).unique().scalars().all()

    items = []
    for v in vehicles:
        item = VehicleResponse.model_validate(v)
        if v.assigned_driver:
            item.driver_name = v.assigned_driver.name
        items.append(item)

    return items

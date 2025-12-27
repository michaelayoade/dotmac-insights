"""Vehicle model for fleet management from ERPNext."""
from __future__ import annotations

from sqlalchemy import String, Text, Date, ForeignKey, Numeric, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class Vehicle(Base):
    """Vehicles from ERPNext Fleet Management.

    Tracks company vehicles including cars, motorcycles, trucks, etc.
    Used for fleet management, driver assignments, and expense tracking.
    """

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic Info
    license_plate: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chassis_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wheels: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Value and Acquisition
    vehicle_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    acquisition_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    # Fuel
    fuel_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    fuel_uom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Litre, Gallon, etc.

    # Odometer
    odometer_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    last_odometer_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    uom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # km, miles

    # Insurance
    insurance_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    policy_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    insurance_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    # Driver Assignment (FK to Employee)
    employee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ERPNext employee ID
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Location and Company
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_driver: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Vehicle {self.license_plate} ({self.make} {self.model})>"
